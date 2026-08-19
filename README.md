# 🤖 Telegram Groq AI Bot

A lightweight, powerful Telegram AI chatbot powered by Groq.
Supports local running (Termux/PC), VPS container running, and **100% Free Serverless deployment on Cloudflare Workers**.

## Features

- ⚡ Powered by Groq's super-fast inference models (e.g. `llama-3.3-70b-versatile`)
- ☁️ **100% Free Cloudflare Workers deployment** (No server/VPS required!)
- 🚀 **GitHub Actions CI/CD** integration for automated deployment
- 🐍 Python version for local / Termux / VPS running with SQLite database
- 💬 Per-user conversation memory
- 🛠️ Commands: `/start`, `/help`, `/about`, `/newchat`, `/clear`, `/stats`, `/users`, `/broadcast`
- 🛡️ Built-in rate limiting and environment-variable secret safety

---

## ⚡ Option A: Free Deployment on Cloudflare Workers (Recommended)

Deploy the bot for free on Cloudflare Workers without needing a 24/7 VPS or server.

### 1. Requirements
- A [Telegram Bot Token](https://t.me/BotFather)
- A [Groq API Key](https://console.groq.com/keys)
- A free [Cloudflare Account](https://dash.cloudflare.com)

### 2. Quick Deploy with Wrangler CLI

1. Clone repository:
```bash
git clone https://github.com/pabel172/Groq_ai_bot.git
cd Groq_ai_bot/cloudflare
```

2. Install dependencies:
```bash
npm install
```

3. Login to Cloudflare:
```bash
npx wrangler login
```

4. Set secret variables:
```bash
npx wrangler secret put BOT_TOKEN
npx wrangler secret put GROQ_API_KEY
```

5. Deploy worker:
```bash
npx wrangler deploy
```

6. Link your Telegram Bot Webhook to your worker URL:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://telegram-groq-ai-bot.<YOUR_SUBDOMAIN>.workers.dev"
```

---

## 🐙 Deployment via GitHub Actions

Automatically deploy updates to Cloudflare Workers whenever you push to GitHub:

1. Push this repository to your GitHub account.
2. In your GitHub repository, go to **Settings > Secrets and variables > Actions**.
3. Add the following repository secrets:
   - `CLOUDFLARE_API_TOKEN`: Cloudflare API token with Workers permissions.
   - `CLOUDFLARE_SUBDOMAIN`: Your Cloudflare workers.dev subdomain.
   - `BOT_TOKEN`: Telegram bot token.
   - `GROQ_API_KEY`: Groq API key.
4. Push code to `main` branch. GitHub Actions will deploy and set your webhook automatically!

---

## 🐍 Option B: Python Installation (Termux / Linux / VPS / Docker)

### 1. Install & Configure

```bash
git clone https://github.com/pabel172/Groq_ai_bot.git
cd Groq_ai_bot

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Secrets

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
GROQ_API_KEY=YOUR_GROQ_API_KEY
ADMIN_ID=YOUR_TELEGRAM_USER_ID
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Run

**Polling mode:**
```bash
python bot.py
```

**Webhook mode (Optional for web hosts):**
Set `WEBHOOK_URL` and `PORT` in your `.env`:
```env
WEBHOOK_URL=https://your-domain.com
PORT=8080
```
Then run:
```bash
python bot.py
```

---

## 🧪 Testing

Run unit tests locally:
```bash
python3 -m unittest test_bot.py
```

---

## 📄 License

MIT
