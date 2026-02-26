import configparser
import requests
from datetime import datetime
from pathlib import Path
import json
import logging

STATE_PATH = Path("counter_state.json")

logging.basicConfig(
    filename="sync_unus.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def load_cfg(path="cliente.ini"):
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    return cfg["unus"]

def today_key(dt=None):
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d")

def fmt_ts(dt=None):
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {}

def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def increment_daily_total(casi_cod: str) -> int:
    state = load_state()
    day = today_key()
    state.setdefault(day, {})
    state[day].setdefault(casi_cod, 0)
    state[day][casi_cod] += 1
    save_state(state)
    return state[day][casi_cod]

def enviar_acumulado_por_cruce(ini_path="cliente.ini"):
    cfg = load_cfg(ini_path)

    total_hoy = increment_daily_total(cfg["casi_cod"])

    url = cfg["base_url"].rstrip("/") + "/recibeMovimientosDeaUno_V6"

    payload = {
        "BASE_DATOS_CLIENTE": cfg["base_datos_cliente"],
        "CASI_COD": cfg["casi_cod"],
        "LECT_COD": cfg["lect_cod"],
        "FECHA_HORA": fmt_ts(),
        "pass": str(total_hoy),
    }

    try:
        r = requests.post(url, data=payload, timeout=15)
        r.raise_for_status()
        logging.info(f"Enviado OK → total hoy: {total_hoy}")
        return True
    except Exception as e:
        logging.error(f"Error enviando evento: {e}")
        return False