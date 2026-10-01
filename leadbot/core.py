"""Conversation logic for the lead-intake bot. No network code lives here."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

STEPS = ("name", "contact", "task", "budget")

MESSAGES = {
    "en": {
        "welcome": "Hi! I'll collect a few details so we can discuss your project.\nWhat's your name?",
        "ask_contact": "Nice to meet you, {name}! How can we reach you? (email, phone or @username)",
        "bad_contact": "That doesn't look like an email, phone or @username. Please try again.",
        "ask_task": "Briefly describe the task (at least 10 characters).",
        "bad_task": "Please add a few more details about the task.",
        "ask_budget": "What's your approximate budget in USD? (a number, or 'skip')",
        "bad_budget": "Please send a number like 500, or 'skip'.",
        "done": "Thanks! Your request #{id} is saved. We'll get back to you soon.",
        "cancelled": "Cancelled. Send /start to begin again.",
        "idle": "Send /start to leave a request.",
    },
    "ru": {
        "welcome": "Привет! Я соберу несколько деталей, чтобы обсудить ваш проект.\nКак вас зовут?",
        "ask_contact": "Приятно познакомиться, {name}! Как с вами связаться? (email, телефон или @username)",
        "bad_contact": "Не похоже на email, телефон или @username. Попробуйте ещё раз.",
        "ask_task": "Коротко опишите задачу (не менее 10 символов).",
        "bad_task": "Добавьте, пожалуйста, чуть больше деталей о задаче.",
        "ask_budget": "Примерный бюджет в USD? (число или «пропустить»)",
        "bad_budget": "Отправьте число, например 500, или «пропустить».",
        "done": "Спасибо! Заявка №{id} сохранена. Скоро свяжемся.",
        "cancelled": "Отменено. Отправьте /start, чтобы начать заново.",
        "idle": "Отправьте /start, чтобы оставить заявку.",
    },
}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[\d\s\-()]{7,20}$")
_HANDLE = re.compile(r"^@[A-Za-z0-9_]{5,32}$")
_SKIP = {"skip", "пропустить", "-"}


def is_valid_contact(text: str) -> bool:
    text = text.strip()
    return bool(_EMAIL.match(text) or _PHONE.match(text) or _HANDLE.match(text))


def parse_budget(text: str) -> float | None | str:
    """Return a number, None for 'skip', or the string 'invalid'."""
    text = text.strip().lower()
    if text in _SKIP:
        return None
    try:
        value = float(text.replace(",", ".").replace(" ", ""))
    except ValueError:
        return "invalid"
    return value if value >= 0 else "invalid"


@dataclass
class Lead:
    id: int
    chat_id: int
    name: str
    contact: str
    task: str
    budget: float | None
    created_at: str


class Store:
    """SQLite persistence for in-progress conversations and finished leads."""

    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                chat_id INTEGER PRIMARY KEY,
                step TEXT NOT NULL,
                lang TEXT NOT NULL,
                name TEXT, contact TEXT, task TEXT
            );
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                name TEXT NOT NULL, contact TEXT NOT NULL, task TEXT NOT NULL,
                budget REAL,
                created_at TEXT NOT NULL
            );
            """
        )

    def get_session(self, chat_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM sessions WHERE chat_id = ?", (chat_id,)).fetchone()

    def start_session(self, chat_id: int, lang: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO sessions (chat_id, step, lang) VALUES (?, 'name', ?)", (chat_id, lang)
        )
        self.db.commit()

    def update_session(self, chat_id: int, **fields: str) -> None:
        allowed = {"step", "name", "contact", "task"}
        assert set(fields) <= allowed, "unexpected session field"
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.db.execute(f"UPDATE sessions SET {cols} WHERE chat_id = ?", (*fields.values(), chat_id))
        self.db.commit()

    def end_session(self, chat_id: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        self.db.commit()

    def save_lead(self, chat_id: int, name: str, contact: str, task: str, budget: float | None) -> int:
        cur = self.db.execute(
            "INSERT INTO leads (chat_id, name, contact, task, budget, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (chat_id, name, contact, task, budget, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        self.db.commit()
        return int(cur.lastrowid)

    def list_leads(self) -> list[Lead]:
        rows = self.db.execute("SELECT * FROM leads ORDER BY id").fetchall()
        return [Lead(**dict(r)) for r in rows]


def detect_lang(language_code: str | None) -> str:
    return "ru" if (language_code or "").lower().startswith("ru") else "en"


class Conversation:
    """Finite-state machine: name -> contact -> task -> budget -> saved."""

    def __init__(self, store: Store) -> None:
        self.store = store

    def handle(self, chat_id: int, text: str, language_code: str | None = None) -> list[str]:
        text = (text or "").strip()
        session = self.store.get_session(chat_id)

        if text.lower().startswith("/start"):
            lang = detect_lang(language_code)
            self.store.start_session(chat_id, lang)
            return [MESSAGES[lang]["welcome"]]

        if session is None:
            return [MESSAGES[detect_lang(language_code)]["idle"]]

        lang = session["lang"]
        msg = MESSAGES[lang]

        if text.lower().startswith("/cancel"):
            self.store.end_session(chat_id)
            return [msg["cancelled"]]

        step = session["step"]
        if step == "name":
            if not 1 <= len(text) <= 80:
                return [msg["welcome"]]
            self.store.update_session(chat_id, name=text, step="contact")
            return [msg["ask_contact"].format(name=text)]

        if step == "contact":
            if not is_valid_contact(text):
                return [msg["bad_contact"]]
            self.store.update_session(chat_id, contact=text, step="task")
            return [msg["ask_task"]]

        if step == "task":
            if len(text) < 10:
                return [msg["bad_task"]]
            self.store.update_session(chat_id, task=text[:2000], step="budget")
            return [msg["ask_budget"]]

        # step == "budget"
        budget = parse_budget(text)
        if budget == "invalid":
            return [msg["bad_budget"]]
        lead_id = self.store.save_lead(chat_id, session["name"], session["contact"], session["task"], budget)
        self.store.end_session(chat_id)
        return [msg["done"].format(id=lead_id)]
