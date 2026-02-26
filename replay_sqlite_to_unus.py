import sqlite3
import yaml
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

DUP_TOKENS = [
    "PRIMARY KEY constraint",
    "duplicate key",
    "Cannot insert duplicate key",
]


def load_cfg(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_ts(ts: str) -> str:
    """
    Deja ts en 'YYYY-MM-DD HH:MM:SS'
    Soporta:
      - 'YYYY-MM-DD HH:MM:SS'
      - 'YYYY-MM-DD HH:MM:SS.fff'
      - 'YYYY-MM-DDTHH:MM:SS(.ms)Z'
      - 'DD/MM/YYYY HH:MM:SS'
    """
    if ts is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    s = str(ts).strip()

    # ISO -> espacio
    s = s.replace("T", " ").replace("Z", "")

    # Quitar milisegundos si vienen ('.000')
    if "." in s:
        s = s.split(".", 1)[0]

    # Cortar a 19 chars por seguridad
    s = s[:19]

    # DD/MM/YYYY -> YYYY-MM-DD
    if len(s) >= 19 and s[2] == "/" and s[5] == "/":
        dt = datetime.strptime(s, "%d/%m/%Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # Validar formato final
    try:
        datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        return s
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_sent_columns(conn: sqlite3.Connection):
    """
    Asegura que existan columnas de control de envío en events.
    - sent_ok: 0 no enviado, 1 enviado
    - sent_at: timestamp de cuando se marcó como enviado (opcional)
    """
    cur = conn.cursor()

    cols = {r[1] for r in cur.execute("PRAGMA table_info(events)").fetchall()}

    if "sent_ok" not in cols:
        cur.execute("ALTER TABLE events ADD COLUMN sent_ok INTEGER NOT NULL DEFAULT 0")

    if "sent_at" not in cols:
        cur.execute("ALTER TABLE events ADD COLUMN sent_at TEXT")

    conn.commit()


def post_unus_v6(cfg_unus, fecha_hora: str):
    """
    HTTP POST simple a /recibeMovimientosDeaUno_V6
    - OK => éxito
    - duplicate key / PRIMARY KEY => lo tratamos como éxito (ya estaba)
    - xsi:nil=true => fallo
    """
    base = cfg_unus["base_url"].rstrip("/")
    url = base + "/recibeMovimientosDeaUno_V6"

    payload = {
        "BASE_DATOS_CLIENTE": cfg_unus["base_datos_cliente"],
        "CASI_COD": str(cfg_unus["casi_cod"]),
        "LECT_COD": str(cfg_unus["lect_cod"]),
        "FECHA_HORA": fecha_hora,  # OBLIGATORIO: YYYY-MM-DD HH:MM:SS
        "pass": str(cfg_unus["pass"]),  # password (NO conteo)
    }

    masked = payload.copy()
    masked["pass"] = "***"
    print("POST URL:", url)
    print("DEBUG payload:", masked)

    r = requests.post(url, data=payload, timeout=float(cfg_unus.get("timeout", 15)))
    print("Status:", r.status_code)
    r.raise_for_status()

    xml_text = (r.text or "").strip()

    # 1) NULL explícito
    if 'xsi:nil="true"' in xml_text.lower():
        return False, "NULL"

    # 2) Duplicado => lo consideramos OK
    low = xml_text.lower()
    if any(tok.lower() in low for tok in DUP_TOKENS):
        return True, "DUPLICATE_OK"

    # 3) Parse <string>OK</string>
    resp = ""
    try:
        root = ET.fromstring(xml_text)
        resp = (root.text or "").strip()
    except Exception:
        resp = xml_text.strip()

    if resp.upper() == "OK":
        return True, "OK"

    return False, resp


def main():
    cfg = load_cfg()
    unus = cfg["unus"]

    db_path = cfg.get("sqlite_path", "people_counter.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Asegurar columnas de envío en BD
    ensure_sent_columns(conn)

    # Queremos enviar “desde ayer 00:00” sí o sí (como lo tenías)
    start_dt = (datetime.now() - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_ts = start_dt.strftime("%Y-%m-%d %H:%M:%S")
    print("Enviando desde:", start_ts)

    # Traemos SOLO pendientes (sent_ok = 0) desde ayer
    rows = cur.execute(
        """
        SELECT id, ts, count_delta
        FROM events
        WHERE ts >= ?
          AND COALESCE(sent_ok, 0) = 0
        ORDER BY ts ASC
        """,
        (start_ts,),
    ).fetchall()

    if not rows:
        print("No hay eventos pendientes desde ayer.")
        conn.close()
        return

    enviados = 0
    fallos = 0

    for row in rows:
        # Mantener tu lógica: solo enviamos si delta > 0
        if int(row["count_delta"]) <= 0:
            # Opcional: si quieres marcar estos como "no enviables" para que no queden pendientes eternos
            # cur.execute("UPDATE events SET sent_ok = 1, sent_at = ? WHERE id = ?", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]))
            # conn.commit()
            continue

        ts = normalize_ts(row["ts"])

        ok, resp = post_unus_v6(unus, ts)
        print("Respuesta WS:", resp)

        if ok:
            enviados += 1
            # ✅ Marcamos en BD como enviado
            cur.execute(
                "UPDATE events SET sent_ok = 1, sent_at = ? WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
            )
            conn.commit()
        else:
            fallos += 1
            print("❌ Fallo enviando. Se detiene para no perder orden.")
            print("Última respuesta:", resp)
            break

    print(f"Eventos marcados como enviados (BD): {enviados} | fallos: {fallos}")
    conn.close()


if __name__ == "__main__":
    main()