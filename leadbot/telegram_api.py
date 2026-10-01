"""Minimal Telegram Bot API client built on the standard library (long polling)."""
from __future__ import annotations

import json
import urllib.request
from typing import Any, Iterator


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, timeout: int = 30) -> None:
        if not token:
            raise ValueError("Telegram token is empty")
        self._base = f"https://api.telegram.org/bot{token}"
        self._timeout = timeout

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        req = urllib.request.Request(
            f"{self._base}/{method}",
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )
        # Long polling holds the connection for `timeout` seconds, so allow some slack.
        with urllib.request.urlopen(req, timeout=self._timeout + 10) as resp:
            body = json.load(resp)
        if not body.get("ok"):
            raise TelegramError(body.get("description", "unknown Telegram error"))
        return body["result"]

    def send_message(self, chat_id: int, text: str) -> None:
        self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def updates(self, offset: int = 0) -> Iterator[dict[str, Any]]:
        """Yield updates forever, advancing the offset so each is delivered once."""
        while True:
            batch = self._call("getUpdates", {"offset": offset, "timeout": self._timeout})
            for update in batch:
                offset = update["update_id"] + 1
                yield update
