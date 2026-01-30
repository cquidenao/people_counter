import sqlite3
from backend.config import settings

def get_conn():
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        camera_id TEXT,
        direction TEXT,
        count_delta INTEGER NOT NULL,
        meta_json TEXT
    )
    """)
    conn.commit()
    conn.close()
