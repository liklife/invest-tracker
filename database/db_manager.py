import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'instance', 'tracker.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создает таблицы, если их нет"""
    with get_db() as conn:
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
            conn.executescript(f.read())
        print("✅ База данных создана/проверена")

if __name__ == '__main__':
    # Создаем папку instance если нет
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()