import time
import json
import yaml
import cv2
import requests
from ultralytics import YOLO

def load_cfg(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def in_roi(px, py, roi):
    return roi["x1"] <= px <= roi["x2"] and roi["y1"] <= py <= roi["y2"]

def head_point(x1, y1, x2, y2):
    # punto cercano a la cabeza (útil en cámara alta)
    cx = (x1 + x2) / 2.0
    hy = y1 + 0.15 * (y2 - y1)
    return cx, hy

def post_event(base_url, camera_id, track_id, count_delta=1, meta=None, timeout=1.5):
    payload = {
        "camera_id": camera_id,
        "direction": "unknown",
        "count_delta": int(count_delta),
        "meta": {
            "track_id": int(track_id),
            **(meta or {})
        }
    }
    try:
        r = requests.post(f"{base_url}/events", json=payload, timeout=timeout)
        r.raise_for_status()
        return True
    except Exception:
        return False

def main():
    cfg = load_cfg()
    source = cfg.get("source", 0)
    model_path = cfg.get("model", "yolov8n.pt")

    conf = float(cfg.get("conf", 0.4))
    iou  = float(cfg.get("iou", 0.5))

    show = bool(cfg.get("display", {}).get("show", True))
    draw_roi = bool(cfg.get("display", {}).get("draw_roi", True))
    show_ids = bool(cfg.get("display", {}).get("show_ids", True))

    roi = cfg["roi_service"]
    dwell_frames = int(cfg.get("logic", {}).get("dwell_frames", 8))
    cooldown_s = float(cfg.get("logic", {}).get("cooldown_seconds", 10))

    backend_url = cfg.get("backend", {}).get("url", "http://127.0.0.1:8000")
    camera_id = cfg.get("backend", {}).get("camera_id", "CAM-PC-01")

    model = YOLO(model_path)

    # Estado por track
    dwell = {}          # track_id -> frames dentro ROI
    in_service = set()  # track_id que ya calificó como "en servicio"
    last_count_ts = {}  # track_id -> timestamp último conteo
    total = 0

    # Trackeo con ByteTrack (incluido en Ultralytics)
    # classes=[0] => solo personas
    stream = model.track(
        source=source,
        conf=conf,
        iou=iou,
        classes=[0],
        persist=True,
        tracker="bytetrack.yaml",
        stream=True,
        verbose=False
    )

    last_cleanup = time.time()

    for res in stream:
        frame = res.orig_img
        now = time.time()

        # Detecciones trackeadas
        boxes = res.boxes
        if boxes is not None and boxes.xyxy is not None:
            xyxy = boxes.xyxy.cpu().numpy()
            ids = None
            if boxes.id is not None:
                ids = boxes.id.cpu().numpy().astype(int)

            if ids is not None:
                for (x1, y1, x2, y2), tid in zip(xyxy, ids):
                    hx, hy = head_point(x1, y1, x2, y2)
                    inside = in_roi(hx, hy, roi)

                    # dwell counting
                    if inside:
                        dwell[tid] = dwell.get(tid, 0) + 1
                        if dwell[tid] >= dwell_frames:
                            in_service.add(tid)
                    else:
                        # Si estaba en servicio y salió => cuenta (con cooldown)
                        if tid in in_service:
                            last_ts = last_count_ts.get(tid, 0)
                            if (now - last_ts) >= cooldown_s:
                                total += 1
                                last_count_ts[tid] = now
                                ok = post_event(
                                    backend_url, camera_id, tid, 1,
                                    meta={"event": "ticket_pass", "roi": roi}
                                )
                                # si quieres debug rápido:
                                # print("COUNT", tid, "posted:", ok)
                            # evita conteo repetido inmediato
                            in_service.discard(tid)

                        # reset dwell cuando sale
                        dwell[tid] = 0

                    # Dibujo
                    if show:
                        p1 = (int(x1), int(y1))
                        p2 = (int(x2), int(y2))
                        cv2.rectangle(frame, p1, p2, (0, 255, 255), 2)
                        if show_ids:
                            cv2.putText(
                                frame, f"id:{tid}",
                                (int(x1), max(20, int(y1) - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                            )
                        cv2.circle(frame, (int(hx), int(hy)), 4, (255, 255, 255), -1)

        if show:
            if draw_roi:
                cv2.rectangle(
                    frame,
                    (roi["x1"], roi["y1"]),
                    (roi["x2"], roi["y2"]),
                    (0, 200, 0), 3
                )
                cv2.putText(
                    frame, "ROI TICKET",
                    (roi["x1"], max(30, roi["y1"] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 200, 0), 2
                )

            cv2.putText(
                frame, f"TOTAL: {total}",
                (20, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3
            )
            cv2.imshow("people_counter (webcam)", frame)
            if cv2.waitKey(1) & 0xFF == 27:  # ESC
                break

        # Limpieza simple para no acumular ids viejos
        if (now - last_cleanup) > 30:
            # elimina entradas antiguas si no se han contado hace rato
            to_del = [tid for tid, ts in last_count_ts.items() if (now - ts) > 300]
            for tid in to_del:
                last_count_ts.pop(tid, None)
                dwell.pop(tid, None)
                in_service.discard(tid)
            last_cleanup = now

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

