import sqlite3
from backend.config import settings

def get_conn():
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Tabla principal
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        ts TEXT NOT NULL,
        camera_id TEXT,
        direction TEXT,
        count_delta INTEGER NOT NULL,
        meta_json TEXT,
        sent_ok INTEGER NOT NULL DEFAULT 0,
        sent_at TEXT
    )
    """)

    # 🔹 En caso de que la tabla ya exista (producción),
    # aseguramos que las columnas nuevas existan
    cols = {row[1] for row in cur.execute("PRAGMA table_info(events)")}

    if "sent_ok" not in cols:
        cur.execute("ALTER TABLE events ADD COLUMN sent_ok INTEGER NOT NULL DEFAULT 0")

    if "sent_at" not in cols:
        cur.execute("ALTER TABLE events ADD COLUMN sent_at TEXT")

    conn.commit()
    conn.close()