# Память бота на ПК (SQLite): клиент ↔ тема в группе владельца, режим (бот или мастер), последние сообщения.
# Номера телефонов из именных заказов храним не дольше, чем до выдачи + 30 дней (правило в чат-бот.md).
import sqlite3
import time

HISTORY = 12  # сколько последних реплик видит модель


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        create table if not exists clients(user_id integer primary key, name text, topic_id integer,
            mode text default 'bot', lang text default 'ru', updated real);
        create table if not exists messages(id integer primary key autoincrement, user_id integer,
            role text, text text, at real);
        create table if not exists meta(k text primary key, v text);
        """)

    def client(self, user_id: int) -> dict | None:
        row = self.db.execute("select user_id,name,topic_id,mode,lang from clients where user_id=?", (user_id,)).fetchone()
        return dict(zip(("user_id", "name", "topic_id", "mode", "lang"), row)) if row else None

    def by_topic(self, topic_id: int) -> dict | None:
        row = self.db.execute("select user_id from clients where topic_id=?", (topic_id,)).fetchone()
        return self.client(row[0]) if row else None

    def save_client(self, user_id: int, **fields):
        cur = self.client(user_id) or {"user_id": user_id, "name": "", "topic_id": None, "mode": "bot", "lang": "ru"}
        cur.update(fields)
        self.db.execute("insert or replace into clients values(?,?,?,?,?,?)",
                        (user_id, cur["name"], cur["topic_id"], cur["mode"], cur["lang"], time.time()))
        self.db.commit()
        return cur

    def add(self, user_id: int, role: str, text: str):
        self.db.execute("insert into messages(user_id,role,text,at) values(?,?,?,?)", (user_id, role, text, time.time()))
        self.db.commit()

    def history(self, user_id: int) -> list[dict]:
        rows = self.db.execute("select role,text from messages where user_id=? order by id desc limit ?",
                               (user_id, HISTORY)).fetchall()
        return [{"role": r, "content": t} for r, t in reversed(rows)]

    def get(self, k: str, default=None):
        row = self.db.execute("select v from meta where k=?", (k,)).fetchone()
        return row[0] if row else default

    def set(self, k: str, v):
        self.db.execute("insert or replace into meta values(?,?)", (k, str(v)))
        self.db.commit()
