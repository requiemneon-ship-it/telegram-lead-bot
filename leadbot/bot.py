"""Entry point: python -m leadbot.bot"""
from __future__ import annotations

import logging
import os
import sys
import time

from .core import Conversation, Store
from .telegram_api import TelegramClient, TelegramError

log = logging.getLogger("leadbot")


def process_update(update: dict, conversation: Conversation, client: TelegramClient) -> None:
    message = update.get("message") or {}
    text = message.get("text")
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None or text is None:
        return  # ignore stickers, edits, channel posts, etc.
    lang = (message.get("from") or {}).get("language_code")
    for reply in conversation.handle(chat_id, text, lang):
        client.send_message(chat_id, reply)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN (get one from @BotFather).", file=sys.stderr)
        return 2

    conversation = Conversation(Store(os.environ.get("LEADBOT_DB", "leads.db")))
    client = TelegramClient(token)
    log.info("Bot started")
    while True:
        try:
            for update in client.updates():
                try:
                    process_update(update, conversation, client)
                except Exception:  # one bad update must not stop the bot
                    log.exception("Failed to process update %s", update.get("update_id"))
        except (TelegramError, OSError) as exc:
            log.warning("Polling error: %s; retrying in 5s", exc)
            time.sleep(5)
        except KeyboardInterrupt:
            log.info("Stopped")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
