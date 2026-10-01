# Telegram Lead Bot

[![CI](https://github.com/requiemneon-ship-it/telegram-lead-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/requiemneon-ship-it/telegram-lead-bot/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

**EN** — A Telegram bot that collects client requests step by step (name → contact → task → budget), validates every answer, stores leads in SQLite and exports them to CSV. Russian and English are picked automatically from the user's Telegram language.
**RU** — Telegram-бот, который по шагам собирает заявки клиентов (имя → контакт → задача → бюджет), проверяет ответы, сохраняет лиды в SQLite и выгружает их в CSV. Язык (русский или английский) выбирается автоматически по языку Telegram.

Zero third-party dependencies: only the Python standard library.

## Features

- Guided dialog implemented as a finite-state machine, with `/start` and `/cancel`
- Input validation: email / phone / `@username`, minimum task length, numeric budget (or "skip")
- Per-chat sessions in SQLite, so a restart does not lose in-progress dialogs
- Parameterized SQL queries throughout
- Long-polling client with retry on network errors; a bad update never crashes the bot
- CSV export of collected leads

## Run

```bash
export TELEGRAM_BOT_TOKEN=123456:ABC...   # from @BotFather
python -m leadbot.bot                      # stores data in ./leads.db (override with LEADBOT_DB)

python -m leadbot.export leads.db > leads.csv
```

On Windows PowerShell: `$env:TELEGRAM_BOT_TOKEN = "123456:ABC..."`.

## Tests

```bash
python -m unittest discover -s tests -t . -v
```

The conversation logic (`leadbot/core.py`) has no network code, so the full dialog is tested without a Telegram token: happy path, validation errors, RU locale, cancel, per-chat isolation and SQL-injection-looking input.

> The HTTP layer (`leadbot/telegram_api.py`) is a thin wrapper over the Bot API and is not covered by automated tests; it has to be verified manually with a real bot token.

## Structure

```
leadbot/core.py          conversation state machine, validation, SQLite store
leadbot/telegram_api.py  Bot API client (urllib, long polling)
leadbot/bot.py           entry point and update loop
leadbot/export.py        CSV export
tests/test_core.py       unit tests
```

## Possible next steps

- Notify an admin chat when a new lead arrives
- Webhook mode instead of long polling
- Push leads to a CRM (for example the [PipelineMint](https://github.com/requiemneon-ship-it/pipeline-mint) API)

## License

MIT
