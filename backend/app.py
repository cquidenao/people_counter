from fastapi import FastAPI, Query, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import json
import os

from backend.db import init_db, get_conn
from backend.models import EventIn, EventOut, make_event_out
from backend.config import settings

from fastapi.staticfiles import StaticFiles
import pathlib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://people-counter-dashboard.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# Config Seguridad (ENV
# =========================
API_KEY = os.getenv("API_KEY", "")  # define esto en producción
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://TU-VERCEL.vercel.app").split(",")

def require_api_key(x_api_key: str | None):
    # Si no defines API_KEY, no valida (útil en dev). En prod, define API_KEY sí o sí.
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# =========================
# App
# =========================

SNAP_DIR = os.getenv("SNAPSHOT_DIR", "snapshots")
pathlib.Path(SNAP_DIR).mkdir(parents=True, exist_ok=True)

app.mount("/snapshots", StaticFiles(directory=SNAP_DIR), name="snapshots")



@app.on_event("startup")
def _startup():
    init_db()

@app.get("/health")
def health():
    return {"ok": True, "app": settings.APP_NAME}

@app.get("/status")
def status(x_api_key: str | None = Header(default=None, alias="x-api-key")):
    require_api_key(x_api_key)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(count_delta), 0) AS total FROM events")
    total = cur.fetchone()["total"]
    conn.close()
    return {"total_count": int(total)}

@app.post("/events", response_model=EventOut)
def create_event(
    event: EventIn,
    x_api_key: str | None = Header(default=None, alias="x-api-key")
):
    # Si quieres proteger también el POST, deja esto.
    # Si el NUC enviará eventos localmente y no por internet, igual conviene.
    require_api_key(x_api_key)

    out = make_event_out(event)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (id, ts, camera_id, direction, count_delta, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
        (out.id, out.ts, out.camera_id, out.direction, out.count_delta, json.dumps(out.meta)),
    )
    conn.commit()
    conn.close()
    return out

@app.get("/events", response_model=List[EventOut])
def list_events(
    limit: int = Query(100, ge=1, le=2000),
    camera_id: Optional[str] = None,
    x_api_key: str | None = Header(default=None, alias="x-api-key")
):
    require_api_key(x_api_key)

    conn = get_conn()
    cur = conn.cursor()

    if camera_id:
        cur.execute(
            "SELECT * FROM events WHERE camera_id=? ORDER BY ts DESC LIMIT ?",
            (camera_id, limit),
        )
    else:
        cur.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,))

    rows = cur.fetchall()
    conn.close()

    out: List[EventOut] = []
    for r in rows:
        out.append(EventOut(
            id=r["id"],
            ts=r["ts"],
            camera_id=r["camera_id"],
            direction=r["direction"],
            count_delta=int(r["count_delta"]),
            meta=json.loads(r["meta_json"] or "{}"),
        ))
    return out

@app.get("/metrics")
def metrics(x_api_key: str | None = Header(default=None, alias="x-api-key")):
    require_api_key(x_api_key)

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COALESCE(SUM(count_delta), 0) AS total FROM events")
    total = int(cur.fetchone()["total"])

    cur.execute("""
        SELECT COALESCE(SUM(count_delta), 0) AS last_24h
        FROM events
        WHERE ts >= datetime('now', '-24 hours')
    """)
    last_24h = int(cur.fetchone()["last_24h"])

    cur.execute("""
        SELECT COALESCE(SUM(count_delta), 0) AS last_1h
        FROM events
        WHERE ts >= datetime('now', '-1 hours')
    """)
    last_1h = int(cur.fetchone()["last_1h"])

    conn.close()
    return {"total": total, "last_1h": last_1h, "last_24h": last_24h}
