import io
import unittest

from leadbot.bot import process_update
from leadbot.core import Conversation, Store, is_valid_contact, parse_budget
from leadbot.export import export_csv


class FakeClient:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class ValidationTests(unittest.TestCase):
    def test_contacts(self):
        for ok in ("a@b.co", "+7 (999) 123-45-67", "@neon_dev"):
            self.assertTrue(is_valid_contact(ok), ok)
        for bad in ("", "hello", "a@b", "@ab", "12"):
            self.assertFalse(is_valid_contact(bad), bad)

    def test_budget(self):
        self.assertEqual(parse_budget("500"), 500.0)
        self.assertEqual(parse_budget("1 200,5"), 1200.5)
        self.assertIsNone(parse_budget("skip"))
        self.assertIsNone(parse_budget("Пропустить"))
        self.assertEqual(parse_budget("abc"), "invalid")
        self.assertEqual(parse_budget("-3"), "invalid")


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.conv = Conversation(self.store)

    def test_happy_path_saves_lead(self):
        self.conv.handle(1, "/start", "en")
        self.conv.handle(1, "Alex")
        self.conv.handle(1, "alex@example.com")
        self.conv.handle(1, "Need a landing page for my shop")
        reply = self.conv.handle(1, "500")
        self.assertIn("#1", reply[0])
        leads = self.store.list_leads()
        self.assertEqual(len(leads), 1)
        self.assertEqual((leads[0].name, leads[0].contact, leads[0].budget), ("Alex", "alex@example.com", 500.0))
        self.assertIsNone(self.store.get_session(1))

    def test_invalid_input_keeps_step(self):
        self.conv.handle(1, "/start")
        self.conv.handle(1, "Alex")
        self.conv.handle(1, "not a contact")
        self.assertEqual(self.store.get_session(1)["step"], "contact")
        self.conv.handle(1, "@alex_dev")
        self.conv.handle(1, "short")
        self.assertEqual(self.store.get_session(1)["step"], "task")

    def test_russian_locale_and_skip_budget(self):
        self.assertIn("Привет", self.conv.handle(2, "/start", "ru-RU")[0])
        self.conv.handle(2, "Игорь")
        self.conv.handle(2, "+79991234567")
        self.conv.handle(2, "Нужен Telegram-бот для заявок")
        reply = self.conv.handle(2, "пропустить")
        self.assertIn("Заявка", reply[0])
        self.assertIsNone(self.store.list_leads()[0].budget)

    def test_cancel_and_idle(self):
        self.assertIn("/start", self.conv.handle(3, "hello")[0])
        self.conv.handle(3, "/start")
        self.conv.handle(3, "/cancel")
        self.assertIsNone(self.store.get_session(3))

    def test_sessions_are_isolated_per_chat(self):
        self.conv.handle(1, "/start")
        self.conv.handle(2, "/start")
        self.conv.handle(1, "Alice")
        self.assertEqual(self.store.get_session(1)["step"], "contact")
        self.assertEqual(self.store.get_session(2)["step"], "name")

    def test_sql_injection_text_is_stored_literally(self):
        self.conv.handle(1, "/start")
        self.conv.handle(1, "Robert'); DROP TABLE leads;--")
        self.conv.handle(1, "bob@example.com")
        self.conv.handle(1, "Some long enough task text")
        self.conv.handle(1, "skip")
        self.assertEqual(self.store.list_leads()[0].name, "Robert'); DROP TABLE leads;--")


class BotAndExportTests(unittest.TestCase):
    def test_process_update_replies_and_ignores_non_text(self):
        conv, client = Conversation(Store()), FakeClient()
        process_update({"message": {"chat": {"id": 7}, "text": "/start", "from": {"language_code": "en"}}}, conv, client)
        process_update({"message": {"chat": {"id": 7}, "sticker": {}}}, conv, client)
        process_update({"edited_message": {}}, conv, client)
        self.assertEqual(len(client.sent), 1)
        self.assertEqual(client.sent[0][0], 7)

    def test_export_csv(self):
        store = Store()
        store.save_lead(1, "A", "a@b.co", "Task text here", 100)
        out = io.StringIO()
        self.assertEqual(export_csv(store, out), 1)
        self.assertTrue(out.getvalue().startswith("id,chat_id,name,contact,task,budget,created_at"))


if __name__ == "__main__":
    unittest.main()
