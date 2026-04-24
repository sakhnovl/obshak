# Obshak

Telegram bot on `aiogram` with MySQL-backed chat history and Gemini model fallback support.

## Stack

- Python 3.12+
- aiogram 3
- MySQL
- Google Gemini via `google-genai`

## What the project does

- handles Telegram messages
- stores per-user message history in MySQL
- supports admin commands for Gemini keys and model management
- falls back across multiple Gemini models and keys

## Quick start

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy env template and fill in your values:

```bash
cp .env.example .env
```

4. Make sure MySQL is running and accessible with the credentials from `.env`.
5. Start the bot:

```bash
python start.py
```

## Required environment variables

- `BOT_TOKEN` or `TELEGRAM_BOT_TOKEN`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `MYSQL_PASSWORD`

Optional:

- `TELEGRAM_ADMIN_IDS`
- `CODEX_TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY`
- `GEMINI_MODELS`

## Tests

```bash
pytest
```

Some tests require a reachable MySQL instance configured through `.env`.

## GitHub readiness notes

- real secrets must stay only in local `.env`
- `.env.example` contains placeholders only
- caches and logs are ignored via `.gitignore`

## Before publishing

- rotate any Telegram or Gemini tokens that were ever stored locally or shared
- review `requirements.txt` and update pinned versions when needed
- create a fresh GitHub repository, then run `git init` if this folder is not yet a git repo
