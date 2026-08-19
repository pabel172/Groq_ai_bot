# 🤖 Telegram Groq AI Bot

A lightweight Telegram AI chatbot powered by Groq, designed for GitHub and Termux.

## Features

- Groq AI chat
- Per-user conversation memory
- SQLite database
- `/start`, `/help`, `/about`
- `/newchat` and `/clear`
- Admin `/stats`, `/users`, `/broadcast`
- Basic per-user rate limiting
- Environment-variable secrets
- Long-polling Telegram bot
- Termux-friendly
- Automatic restart script
- Optional Termux:Boot startup

## Files

```text
telegram-groq-ai-bot/
├── bot.py
├── .env.example
├── requirements.txt
├── .gitignore
└── README.md
```

## 1. Create your Telegram bot

Open `@BotFather` in Telegram and use `/newbot`. Copy the bot token.

## 2. Create a Groq API key

Open the Groq Console and create an API key.

Never publish your real Groq API key or Telegram bot token.

## 3. Termux installation

```bash
pkg update && pkg upgrade -y
pkg install python git nano tmux -y
```

Clone your repository:

```bash
git clone https://github.com/pabel172/telegram-groq-ai-bot.git
cd telegram-groq-ai-bot
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure secrets

```bash
cp .env.example .env
nano .env
```

Set:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
GROQ_API_KEY=YOUR_GROQ_API_KEY
ADMIN_ID=YOUR_TELEGRAM_USER_ID
GROQ_MODEL=openai/gpt-oss-20b
```

Save with `Ctrl+O`, Enter, then exit with `Ctrl+X`.

## 5. Run

```bash
python bot.py
```

Open the bot in Telegram and send `/start`.

## 6. Stop

Press:

```text
Ctrl+C
```

## 7. Keep it running with tmux

```bash
tmux new -s groqbot
cd ~/telegram-groq-ai-bot
source .venv/bin/activate
python bot.py
```

Detach with `Ctrl+B`, then `D`.

Return later:

```bash
tmux attach -t groqbot
```

## 8. Automatic restart after a crash

Create:

```bash
nano run.sh
```

Paste:

```bash
#!/data/data/com.termux/files/usr/bin/bash

cd ~/telegram-groq-ai-bot
source .venv/bin/activate

while true
do
    echo "Starting Telegram AI bot..."
    python bot.py
    echo "Bot stopped. Restarting in 5 seconds..."
    sleep 5
done
```

Make executable:

```bash
chmod +x run.sh
```

Run it:

```bash
./run.sh
```

For a background tmux session:

```bash
tmux new -s groqbot
./run.sh
```

Detach with `Ctrl+B`, then `D`.

## 9. Start after Android reboot

Install Termux:Boot from the same trusted source/distribution you use for Termux.

Then:

```bash
mkdir -p ~/.termux/boot
nano ~/.termux/boot/start-groq-bot
```

Paste:

```bash
#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock
sleep 10

cd ~/telegram-groq-ai-bot
source .venv/bin/activate

tmux new-session -d -s groqbot "./run.sh"
```

Then:

```bash
chmod +x ~/.termux/boot/start-groq-bot
```

Allow Termux to run in the background in Android battery settings.

## 10. Change the AI model

Edit `.env`:

```env
GROQ_MODEL=openai/gpt-oss-20b
```

Use a currently supported Groq model. Model availability and limits can change.

## 11. Security

Never commit:

```text
.env
bot.db
```

The `.gitignore` already excludes them.

If a secret is accidentally published, rotate/revoke it immediately.

## 12. Update from GitHub

```bash
cd ~/telegram-groq-ai-bot
git pull
source .venv/bin/activate
pip install -r requirements.txt --upgrade
./run.sh
```

## 13. Database

The bot automatically creates `bot.db`.

It contains Telegram user information and conversation memory. Do not publish it.

## 14. Troubleshooting

Check Python:

```bash
python --version
```

Check packages:

```bash
pip show groq
pip show python-telegram-bot
```

Check the bot directly:

```bash
python bot.py
```

Check tmux:

```bash
tmux ls
```

If `.env` is missing:

```bash
cp .env.example .env
nano .env
```

## License

MIT
