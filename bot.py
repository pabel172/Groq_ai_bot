#!/usr/bin/env python3
import asyncio
import html
import logging
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from groq import AsyncGroq
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, friendly and intelligent AI assistant. Answer clearly and accurately. "
    "Keep responses reasonably concise unless the user asks for detail. "
    "Do not claim to have performed actions you cannot actually perform.",
)
DATABASE = os.getenv("DATABASE", "bot.db").strip()
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "12"))
MAX_USER_MESSAGE_LENGTH = int(os.getenv("MAX_USER_MESSAGE_LENGTH", "12000"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
RATE_LIMIT_MESSAGES = int(os.getenv("RATE_LIMIT_MESSAGES", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("groq-telegram-bot")

ADMIN_ID: Optional[int] = None
if ADMIN_ID_RAW:
    try:
        ADMIN_ID = int(ADMIN_ID_RAW)
    except ValueError:
        logger.warning("ADMIN_ID is not a valid numeric Telegram user ID.")

groq_client: Optional[AsyncGroq] = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
user_requests = defaultdict(deque)


def get_db():
    db_dir = os.path.dirname(DATABASE)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                message_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                user_id INTEGER PRIMARY KEY,
                messages TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def register_user(user):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO users
                (user_id, username, first_name, last_name, created_at, last_seen, message_count)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                last_seen=excluded.last_seen
        """, (user.id, user.username, user.first_name, user.last_name, now, now))
        conn.commit()
    finally:
        conn.close()


def increment_message_count(user_id):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET message_count = message_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_count():
    conn = get_db()
    try:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
    finally:
        conn.close()


def get_total_messages():
    conn = get_db()
    try:
        return int(conn.execute("SELECT COALESCE(SUM(message_count), 0) FROM users").fetchone()[0])
    finally:
        conn.close()


def load_conversation(user_id):
    import json
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT messages FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row:
            return []
        try:
            return json.loads(row["messages"])
        except Exception:
            return []
    finally:
        conn.close()


def save_conversation(user_id, messages):
    import json
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        conn.execute("""
            INSERT INTO conversations (user_id, messages, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                messages=excluded.messages,
                updated_at=excluded.updated_at
        """, (user_id, json.dumps(messages, ensure_ascii=False), now))
        conn.commit()
    finally:
        conn.close()


def clear_conversation(user_id):
    conn = get_db()
    try:
        conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()


def is_rate_limited(user_id):
    now = time.monotonic()
    requests = user_requests[user_id]
    while requests and now - requests[0] > RATE_LIMIT_WINDOW:
        requests.popleft()
    if len(requests) >= RATE_LIMIT_MESSAGES:
        return True
    requests.append(now)
    return False


def split_text(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    chunks = []
    while len(text) > max_length:
        split_at = text.rfind("\n", 0, max_length)
        if split_at < 1000:
            split_at = text.rfind(" ", 0, max_length)
        if split_at < 1000:
            split_at = max_length
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def is_admin(user_id):
    return ADMIN_ID is not None and user_id == ADMIN_ID


async def ask_groq(user_id, user_message):
    if groq_client is None:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    history = load_conversation(user_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    messages = [messages[0]] + messages[-MAX_HISTORY:]

    completion = await groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )

    response = completion.choices[0].message.content or "I couldn't generate a response this time."
    new_history = (history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": response},
    ])[-MAX_HISTORY:]
    save_conversation(user_id, new_history)
    return response


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)
    first_name = html.escape(user.first_name or "there")
    await update.message.reply_text(
        f"👋 <b>Hello {first_name}!</b>\n\n"
        "🤖 I am an AI assistant powered by Groq.\n\n"
        "Just send me a message and I'll answer.\n\n"
        "<b>Commands:</b>\n"
        "/start — Start the bot\n"
        "/help — Show help\n"
        "/newchat — Start a fresh conversation\n"
        "/clear — Clear conversation memory\n"
        "/about — About this bot",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>AI Bot Help</b>\n\n"
        "Send any text message to chat with the AI.\n\n"
        "<b>Commands</b>\n"
        "/start — Start the bot\n"
        "/help — Show this help\n"
        "/newchat — Reset your AI conversation\n"
        "/clear — Delete your conversation memory\n"
        "/about — About the bot\n\n"
        "💡 The bot remembers recent messages during your conversation.",
        parse_mode="HTML",
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 <b>Groq Telegram AI Bot</b>\n\n"
        f"🧠 Model: <code>{html.escape(MODEL)}</code>\n"
        "⚡ AI Provider: Groq\n"
        "🐍 Language: Python\n"
        "💾 Database: SQLite\n\n"
        "Open-source Telegram AI assistant.",
        parse_mode="HTML",
    )


async def newchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_conversation(update.effective_user.id)
    await update.message.reply_text(
        "🧹 <b>New conversation started.</b>\n\n"
        "Your previous conversation memory has been cleared.",
        parse_mode="HTML",
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_conversation(update.effective_user.id)
    await update.message.reply_text("✅ Your conversation memory has been deleted.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    await update.message.reply_text(
        "📊 <b>Bot Statistics</b>\n\n"
        f"👥 Users: <b>{get_user_count()}</b>\n"
        f"💬 Messages: <b>{get_total_messages()}</b>\n"
        f"🧠 Model: <code>{html.escape(MODEL)}</code>",
        parse_mode="HTML",
    )


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT user_id, username, first_name, message_count
            FROM users ORDER BY message_count DESC LIMIT 20
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        await update.message.reply_text("No users found.")
        return

    lines = ["👥 <b>Top Users</b>", ""]
    for row in rows:
        name = html.escape(row["username"] or row["first_name"] or "Unknown")
        lines.append(f"• {name} — {row['message_count']} messages")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Admin only.")
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/broadcast Your message here")
        return

    message = " ".join(context.args)
    conn = get_db()
    try:
        user_ids = [row["user_id"] for row in conn.execute("SELECT user_id FROM users").fetchall()]
    finally:
        conn.close()

    success = failed = 0
    status = await update.message.reply_text("📢 Broadcasting...")
    for user_id in user_ids:
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            success += 1
        except Exception as exc:
            failed += 1
            logger.warning("Broadcast failed for %s: %s", user_id, exc)
        await asyncio.sleep(0.05)

    await status.edit_text(
        f"📢 <b>Broadcast finished</b>\n\n✅ Sent: {success}\n❌ Failed: {failed}",
        parse_mode="HTML",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    register_user(user)
    user_id = user.id
    user_message = update.message.text.strip()

    if not user_message:
        return

    if len(user_message) > MAX_USER_MESSAGE_LENGTH:
        await update.message.reply_text(
            f"⚠️ Your message is too long.\n\nMaximum allowed length: {MAX_USER_MESSAGE_LENGTH} characters."
        )
        return

    if is_rate_limited(user_id):
        await update.message.reply_text(
            "⏳ You're sending messages too quickly.\n\nPlease wait a little and try again."
        )
        return

    increment_message_count(user_id)
    thinking_message = None

    try:
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING,
        )
        thinking_message = await update.message.reply_text("🤔 Thinking...")
        response = await ask_groq(user_id, user_message)

        try:
            await thinking_message.delete()
        except Exception:
            pass

        for chunk in split_text(response):
            await update.message.reply_text(chunk)

    except Exception as exc:
        logger.exception("AI request failed: %s", exc)
        if thinking_message:
            try:
                await thinking_message.edit_text(
                    "❌ Sorry, I couldn't process your request.\n\nPlease try again in a moment."
                )
                return
            except Exception:
                pass
        await update.message.reply_text(
            "❌ Something went wrong while contacting the AI.\n\nPlease try again later."
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception: %s", context.error, exc_info=context.error)


async def post_init(application: Application):
    commands = [
        ("start", "Start the AI bot"),
        ("help", "Show help"),
        ("newchat", "Start a new conversation"),
        ("clear", "Clear conversation memory"),
        ("about", "About the bot"),
    ]
    if ADMIN_ID is not None:
        commands += [
            ("stats", "Bot statistics"),
            ("users", "Show top users"),
            ("broadcast", "Broadcast a message"),
        ]
    await application.bot.set_my_commands(commands)


def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\nCopy .env.example to .env and configure it."
        )


def main():
    validate_config()
    init_database()
    logger.info("Starting Telegram Groq AI Bot...")
    logger.info("Model: %s", MODEL)

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("newchat", newchat_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    application.add_error_handler(error_handler)

    webhook_url = os.getenv("WEBHOOK_URL", "").strip()
    port = int(os.getenv("PORT", "8080"))
    listen_address = os.getenv("LISTEN_ADDRESS", "0.0.0.0").strip()

    if webhook_url:
        logger.info("Bot is running in webhook mode on port %d...", port)
        application.run_webhook(
            listen=listen_address,
            port=port,
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
    else:
        logger.info("Bot is running in polling mode.")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
