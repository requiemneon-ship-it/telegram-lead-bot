"""Tests the HTTP layer against a fake Telegram server running on localhost (no real token needed)."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from leadbot.bot import process_update
from leadbot.core import Conversation, Store
from leadbot.telegram_api import TelegramClient, TelegramError

TOKEN = "123:TEST"


class FakeTelegram(BaseHTTPRequestHandler):
    # Class-level state, reset for every test server.
    batches: list = []
    sent: list = []
    offsets: list = []

    def log_message(self, *args):  # keep test output quiet
        pass

    def _reply(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["content-length"])))
        if self.path != f"/bot{TOKEN}/{self.path.rsplit('/', 1)[-1]}":
            return self._reply({"ok": False, "description": "Unauthorized"}, 401)
        method = self.path.rsplit("/", 1)[-1]
        if method == "getUpdates":
            self.offsets.append(payload["offset"])
            batch = self.batches.pop(0) if self.batches else []
            return self._reply({"ok": True, "result": batch})
        if method == "sendMessage":
            if payload["chat_id"] == -1:
                return self._reply({"ok": False, "description": "chat not found"}, 400)
            self.sent.append(payload)
            return self._reply({"ok": True, "result": {}})
        return self._reply({"ok": False, "description": "unknown method"}, 404)


def update(update_id, chat_id, text, lang="en"):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id}, "text": text, "from": {"language_code": lang}}}


class TelegramClientTests(unittest.TestCase):
    def setUp(self):
        FakeTelegram.batches, FakeTelegram.sent, FakeTelegram.offsets = [], [], []
        self.server = HTTPServer(("127.0.0.1", 0), FakeTelegram)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = TelegramClient(TOKEN, timeout=1, api_url=f"http://127.0.0.1:{self.server.server_port}")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            TelegramClient("")

    def test_send_message(self):
        self.client.send_message(5, "hello")
        self.assertEqual(FakeTelegram.sent, [{"chat_id": 5, "text": "hello"}])

    def test_api_error_becomes_telegram_error(self):
        with self.assertRaises(TelegramError) as ctx:
            self.client.send_message(-1, "x")
        self.assertIn("chat not found", str(ctx.exception))

    def test_wrong_token_is_reported(self):
        bad = TelegramClient("999:BAD", timeout=1, api_url=f"http://127.0.0.1:{self.server.server_port}")
        with self.assertRaises(Exception):
            bad.send_message(1, "x")

    def test_updates_advance_offset_and_yield_in_order(self):
        FakeTelegram.batches = [[update(10, 1, "a"), update(11, 1, "b")], [update(12, 1, "c")]]
        got = []
        for u in self.client.updates():
            got.append(u["update_id"])
            if len(got) == 3:
                break
        self.assertEqual(got, [10, 11, 12])
        self.assertEqual(FakeTelegram.offsets[:2], [0, 12])  # second poll confirms updates up to 11

    def test_full_dialog_through_http_layer(self):
        FakeTelegram.batches = [
            [update(1, 42, "/start")],
            [update(2, 42, "Alex")],
            [update(3, 42, "alex@example.com")],
            [update(4, 42, "Need a landing page for a shop")],
            [update(5, 42, "300")],
        ]
        store = Store()
        conversation = Conversation(store)
        handled = 0
        for u in self.client.updates():
            process_update(u, conversation, self.client)
            handled += 1
            if handled == 5:
                break
        self.assertEqual(len(FakeTelegram.sent), 5)
        self.assertIn("#1", FakeTelegram.sent[-1]["text"])
        lead = store.list_leads()[0]
        self.assertEqual((lead.name, lead.contact, lead.budget), ("Alex", "alex@example.com", 300.0))


if __name__ == "__main__":
    unittest.main()
