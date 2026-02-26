from datetime import datetime
from replay_sqlite_to_unus import post_unus_http

# usa tu función post_unus_http tal cual ya la tienes
# post_unus_http(cfg_unus, fecha_hora)

cfg_unus = {
  "base_url": "https://unus.cl/WS_RECIBE_MOVIMIENTOS/wsRecibeMovimientos.asmx",
  "base_datos_cliente": "CASI_COEXPAN",   # EXACTO como INI
  "casi_cod": "001",                      # con ceros
  "lect_cod": "A",
  "pass": "M1",
  "timeout": 15
}

ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
ok, resp = post_unus_http(cfg_unus, ts)
print(ok, resp)