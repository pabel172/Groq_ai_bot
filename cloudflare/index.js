/**
 * Telegram Groq AI Bot - Cloudflare Worker Edition
 * Free serverless deployment on Cloudflare Workers
 */

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Groq Telegram Bot Worker active", { status: 200 });
    }

    try {
      const update = await request.json();
      if (update && update.message) {
        ctx.waitUntil(handleMessage(update.message, env));
      }
      return new Response("OK", { status: 200 });
    } catch (err) {
      console.error("Error processing update:", err);
      return new Response("Internal Error", { status: 500 });
    }
  },
};

async function handleMessage(message, env) {
  if (!message || !message.text || !message.chat) return;

  const chatId = message.chat.id;
  const userId = message.from ? message.from.id : chatId;
  const text = message.text.trim();
  const botToken = env.BOT_TOKEN;
  const groqApiKey = env.GROQ_API_KEY;
  const model = env.GROQ_MODEL || "llama-3.3-70b-versatile";
  const systemPrompt = env.SYSTEM_PROMPT || "You are a helpful, friendly and intelligent AI assistant.";

  if (!botToken || !groqApiKey) {
    await sendTelegramMessage(botToken, chatId, "⚠️ Bot configuration error: Missing secrets.");
    return;
  }

  // Handle Commands
  if (text.startsWith("/")) {
    const command = text.split(" ")[0].toLowerCase();
    if (command === "/start") {
      const firstName = message.from && message.from.first_name ? message.from.first_name : "there";
      const startMsg = `👋 <b>Hello ${escapeHtml(firstName)}!</b>\n\n` +
        `🤖 I am an AI assistant powered by Groq (running on Cloudflare Workers).\n\n` +
        `Send me any message to start chatting!\n\n` +
        `<b>Commands:</b>\n` +
        `/start — Start the bot\n` +
        `/help — Show help\n` +
        `/clear or /newchat — Clear chat memory\n` +
        `/about — About the bot`;
      await sendTelegramMessage(botToken, chatId, startMsg, "HTML");
      return;
    } else if (command === "/help") {
      const helpMsg = `🤖 <b>AI Bot Help</b>\n\n` +
        `Send any text message to chat with the AI.\n\n` +
        `<b>Commands:</b>\n` +
        `/start — Start the bot\n` +
        `/help — Show this message\n` +
        `/clear or /newchat — Reset conversation\n` +
        `/about — About this bot`;
      await sendTelegramMessage(botToken, chatId, helpMsg, "HTML");
      return;
    } else if (command === "/about") {
      const aboutMsg = `🤖 <b>Groq Telegram AI Bot</b>\n\n` +
        `🧠 Model: <code>${escapeHtml(model)}</code>\n` +
        `⚡ Platform: Cloudflare Workers (Free Serverless)\n` +
        `⚡ AI Provider: Groq`;
      await sendTelegramMessage(botToken, chatId, aboutMsg, "HTML");
      return;
    } else if (command === "/clear" || command === "/newchat") {
      if (env.CONVERSATIONS) {
        await env.CONVERSATIONS.delete(`user_${userId}`);
      }
      await sendTelegramMessage(botToken, chatId, "🧹 Conversation memory cleared!");
      return;
    }
  }

  // Send Typing Chat Action
  await sendChatAction(botToken, chatId, "typing");

  // Retrieve History (KV Storage if available)
  let history = [];
  if (env.CONVERSATIONS) {
    try {
      const saved = await env.CONVERSATIONS.get(`user_${userId}`);
      if (saved) history = JSON.parse(saved);
    } catch (e) {
      console.error("KV read error:", e);
    }
  }

  // Build Messages Array
  const messages = [{ role: "system", content: systemPrompt }];
  messages.push(...history);
  messages.push({ role: "user", content: text });

  // Limit conversation history
  const maxHistory = parseInt(env.MAX_HISTORY || "10", 10);
  const slicedMessages = [messages[0], ...messages.slice(-maxHistory)];

  try {
    const groqResponse = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${groqApiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: model,
        messages: slicedMessages,
        temperature: parseFloat(env.TEMPERATURE || "0.7"),
        max_tokens: parseInt(env.MAX_OUTPUT_TOKENS || "2048", 10)
      })
    });

    if (!groqResponse.ok) {
      const errorText = await groqResponse.text();
      console.error("Groq API error:", groqResponse.status, errorText);
      await sendTelegramMessage(botToken, chatId, "❌ Error contacting AI service. Please try again later.");
      return;
    }

    const groqData = await groqResponse.json();
    const replyText = groqData.choices?.[0]?.message?.content || "I couldn't generate a response.";

    // Save updated history
    if (env.CONVERSATIONS) {
      const updatedHistory = [
        ...history,
        { role: "user", content: text },
        { role: "assistant", content: replyText }
      ].slice(-maxHistory);
      try {
        await env.CONVERSATIONS.put(`user_${userId}`, JSON.stringify(updatedHistory), {
          expirationTtl: 86400 * 7 // 7 days expiration
        });
      } catch (e) {
        console.error("KV write error:", e);
      }
    }

    // Split & send reply
    const chunks = splitText(replyText);
    for (const chunk of chunks) {
      await sendTelegramMessage(botToken, chatId, chunk);
    }
  } catch (err) {
    console.error("Failed to generate AI response:", err);
    await sendTelegramMessage(botToken, chatId, "❌ Something went wrong while generating response.");
  }
}

async function sendTelegramMessage(token, chatId, text, parseMode = null) {
  const url = `https://api.telegram.org/bot${token}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: text,
  };
  if (parseMode) body.parse_mode = parseMode;

  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function sendChatAction(token, chatId, action) {
  const url = `https://api.telegram.org/bot${token}/sendChatAction`;
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, action: action }),
  });
}

function splitText(text, maxLength = 4000) {
  if (text.length <= maxLength) return [text];
  const chunks = [];
  let current = text;
  while (current.length > maxLength) {
    let splitAt = current.lastIndexOf("\n", maxLength);
    if (splitAt < 1000) splitAt = current.lastIndexOf(" ", maxLength);
    if (splitAt < 1000) splitAt = maxLength;
    chunks.push(current.substring(0, splitAt));
    current = current.substring(splitAt).trim();
  }
  if (current) chunks.push(current);
  return chunks;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
