import time
import yaml
import cv2
import requests
from ultralytics import YOLO
import os
from datetime import datetime


def load_cfg(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def post_event(base_url, camera_id, track_id, direction="unknown", count_delta=1, meta=None, timeout=1.5):
    payload = {
        "camera_id": camera_id,
        "direction": direction,
        "count_delta": int(count_delta),
        "meta": {"track_id": int(track_id), **(meta or {})},
    }
    try:
        r = requests.post(f"{base_url}/events", json=payload, timeout=timeout)
        r.raise_for_status()
        return True
    except Exception:
        return False


def head_point(x1, y1, x2, y2):
    cx = (x1 + x2) / 2.0
    hy = y1 + 0.15 * (y2 - y1)
    return cx, hy


def clamp(v, a, b):
    return max(a, min(b, v))


def save_person_snapshot(frame_bgr, bbox_xyxy, out_dir, prefix="count"):
    try:
        os.makedirs(out_dir, exist_ok=True)

        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = bbox_xyxy

        bw, bh = (x2 - x1), (y2 - y1)
        mx, my = int(0.15 * bw), int(0.15 * bh)

        cx1 = clamp(int(x1 - mx), 0, w - 1)
        cy1 = clamp(int(y1 - my), 0, h - 1)
        cx2 = clamp(int(x2 + mx), 0, w - 1)
        cy2 = clamp(int(y2 + my), 0, h - 1)

        crop = frame_bgr[cy1:cy2, cx1:cx2]

        if crop is None or crop.size == 0:
            print("⚠ Crop vacío, no se guarda snapshot")
            return None

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{ts}.jpg"
        path = os.path.abspath(os.path.join(out_dir, filename))

        print("📸 Intentando guardar en:", path)

        ok = cv2.imwrite(path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

        if ok:
            print("✅ Snapshot guardado correctamente")
            return filename
        else:
            print("❌ cv2.imwrite devolvió False")
            return None

    except Exception as e:
        print("💥 Error guardando snapshot:", e)
        return None


def rotate_frame(frame, rot):
    if rot == 0:
        return frame
    if rot == 90:
        return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
    if rot == 180:
        return cv2.rotate(frame, cv2.ROTATE_180)
    if rot == 270:
        return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError("rotate_deg must be one of: 0, 90, 180, 270")


def transform_point(x, y, w, h, rot):
    if rot == 0:
        return x, y
    if rot == 90:
        return (h - 1 - y), x
    if rot == 180:
        return (w - 1 - x), (h - 1 - y)
    if rot == 270:
        return y, (w - 1 - x)
    raise ValueError("rotate_deg must be one of: 0, 90, 180, 270")


def transform_bbox_xyxy(x1, y1, x2, y2, w, h, rot):
    corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    tc = [transform_point(x, y, w, h, rot) for x, y in corners]
    xs = [p[0] for p in tc]
    ys = [p[1] for p in tc]
    return min(xs), min(ys), max(xs), max(ys)


def main():
    cfg = load_cfg()

    source = cfg.get("source", 0)  # 0 o RTSP string
    model_path = cfg.get("model", "yolov8n.pt")
    conf = float(cfg.get("conf", 0.4))
    iou = float(cfg.get("iou", 0.5))
    rotate_deg = int(cfg.get("rotate_deg", 0))

    backend_cfg = cfg.get("backend", {})
    backend_url = backend_cfg.get("url", "http://127.0.0.1:8000")
    camera_id = backend_cfg.get("camera_id", "CAM-PC-01")

    dcfg = cfg.get("display", {})
    show = bool(dcfg.get("show", True))
    show_ids = bool(dcfg.get("show_ids", True))
    draw_head = bool(dcfg.get("draw_head", True))
    draw_line = bool(dcfg.get("draw_line", True))

    snap_cfg = cfg.get("snapshots", {})
    snapshot_dir = snap_cfg.get("dir", "snapshots")
    snapshot_on = bool(snap_cfg.get("enabled", True))

    line = cfg.get("line", {})
    line_pos = float(line.get("pos", 0.5))
    arm_px = int(line.get("arm_px", 80))
    cross_tol = int(line.get("cross_tol_px", 18))
    min_box_h = int(line.get("min_box_h_px", 110))

    # Direcciones
    dir_lr = line.get("dir_lr", "in")    # izquierda -> derecha
    dir_rl = line.get("dir_rl", "out")   # derecha -> izquierda

    unique = cfg.get("unique", {})
    TRACK_TTL_SECONDS = float(unique.get("track_ttl_seconds", 25.0))

    # ====== Modelo + captura OpenCV (esto garantiza ventana) ======
    model = YOLO(model_path)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir la cámara (SOURCE/RTSP/credenciales/red).")

    window_name = "people_counter (unique once)"
    if show:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1100, 750)

    total_in = 0
    total_out = 0

    # tracking state
    armed = {}         # tid -> "L" o "R"
    last_seen_ts = {}  # tid -> last seen

    # Manejo de reutilización de IDs (epoch por tid)
    tid_epoch = {}      # tid -> epoch int
    tid_last_gone = {}  # tid -> ts cuando “murió”
    counted = set()     # set of (tid, epoch) ya contados

    # Person IDs propios (solo para mostrar)
    next_person_id = 1
    key_to_person = {}  # (tid, epoch) -> person_id

    last_cleanup = time.time()

    while True:
        now = time.time()

        ret, frame0 = cap.read()
        if not ret or frame0 is None:
            print("No se pudo leer frame. Reintentando...")
            time.sleep(0.5)
            continue

        h0, w0 = frame0.shape[:2]

        # Rotación para visualizar y para conteo (coherente)
        frame = rotate_frame(frame0, rotate_deg)
        hr, wr = frame.shape[:2]
        LINE_X = int(wr * line_pos)

        # Detect + Track por frame
        res = model.track(
            frame0,  # IMPORTANT: tracking sobre frame original; bbox se transforma si hay rotación
            conf=conf,
            iou=iou,
            classes=[0],
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]

        boxes = res.boxes
        if boxes is None or boxes.xyxy is None or boxes.id is None or len(boxes.xyxy) == 0:
            # Limpieza de “muertos”
            if (now - last_cleanup) > 1.0:
                dead = [tid for tid, ts in last_seen_ts.items() if (now - ts) > TRACK_TTL_SECONDS]
                for tid in dead:
                    last_seen_ts.pop(tid, None)
                    armed.pop(tid, None)
                    tid_last_gone[tid] = now
                last_cleanup = now

            # Igual mostramos pantalla aunque no haya detecciones
            if show:
                if draw_line:
                    cv2.line(frame, (LINE_X, 0), (LINE_X, hr), (0, 255, 0), 2)
                cv2.putText(frame, f"IN: {total_in}  OUT: {total_out}",
                            (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            continue

        xyxy = boxes.xyxy.cpu().numpy()
        ids = boxes.id.cpu().numpy().astype(int)

        for (x1, y1, x2, y2), tid in zip(xyxy, ids):
            # bbox rotado para dibujar/contar en el frame mostrado
            if rotate_deg != 0:
                rx1, ry1, rx2, ry2 = transform_bbox_xyxy(x1, y1, x2, y2, w0, h0, rotate_deg)
            else:
                rx1, ry1, rx2, ry2 = x1, y1, x2, y2

            box_h = (ry2 - ry1)
            if box_h < min_box_h:
                continue

            last_seen_ts[tid] = now

            # epoch: si el tid “murió” y reapareció, sube epoch
            if tid not in tid_epoch:
                tid_epoch[tid] = 0
            if tid in tid_last_gone and (now - tid_last_gone[tid]) > TRACK_TTL_SECONDS:
                tid_epoch[tid] += 1
                tid_last_gone.pop(tid, None)
                armed.pop(tid, None)

            epoch = tid_epoch[tid]
            key = (tid, epoch)

            hx, hy = head_point(rx1, ry1, rx2, ry2)
            dx = hx - LINE_X

            # auto-arming
            if tid not in armed and abs(dx) > cross_tol:
                armed[tid] = "L" if dx < 0 else "R"

            # armado normal (histéresis)
            if dx <= -arm_px:
                armed[tid] = "L"
            elif dx >= arm_px:
                armed[tid] = "R"

            # Cruce
            if abs(dx) <= cross_tol:
                a = armed.get(tid)
                if a is not None:
                    if key not in counted:
                        counted.add(key)

                        # person_id
                        if key not in key_to_person:
                            key_to_person[key] = next_person_id
                            next_person_id += 1
                        person_id = key_to_person[key]

                        if a == "L":
                            direction = dir_lr
                            total_in += 1
                        else:
                            direction = dir_rl
                            total_out += 1

                        # 📸 Snapshot SOLO al contar
                        snapshot_filename = None
                        if snapshot_on:
                            snapshot_filename = save_person_snapshot(
                                frame,  # frame rotado para que snapshot coincida con lo que ves
                                (rx1, ry1, rx2, ry2),
                                snapshot_dir,
                                prefix=f"{camera_id}_{direction}",
                            )

                        post_event(
                            backend_url,
                            camera_id,
                            tid,
                            direction=direction,
                            count_delta=1,
                            meta={
                                "event": "unique_once_per_person",
                                "person_id": person_id,
                                "track_epoch": epoch,
                                "snapshot": snapshot_filename,
                            },
                        )

                    # desarma para evitar jitter
                    armed.pop(tid, None)

            # Draw
            if show:
                cv2.rectangle(frame, (int(rx1), int(ry1)), (int(rx2), int(ry2)), (0, 255, 255), 2)
                if show_ids:
                    pid = key_to_person.get(key)
                    label = f"id:{tid} e:{epoch}" if pid is None else f"id:{tid} e:{epoch} p:{pid}"
                    cv2.putText(
                        frame,
                        label,
                        (int(rx1), max(20, int(ry1) - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2,
                    )
                if draw_head:
                    cv2.circle(frame, (int(hx), int(hy)), 4, (255, 255, 255), -1)

        if show:
            if draw_line:
                cv2.line(frame, (LINE_X, 0), (LINE_X, hr), (0, 255, 0), 2)
                cv2.line(frame, (LINE_X - cross_tol, 0), (LINE_X - cross_tol, hr), (0, 255, 0), 1)
                cv2.line(frame, (LINE_X + cross_tol, 0), (LINE_X + cross_tol, hr), (0, 255, 0), 1)
                cv2.putText(
                    frame,
                    "COUNT LINE",
                    (min(LINE_X + 6, wr - 220), 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2,
                )

            cv2.putText(
                frame,
                f"IN: {total_in}  OUT: {total_out}",
                (20, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.1,
                (255, 255, 255),
                3,
            )

            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

        # Limpieza de “muertos”
        if (now - last_cleanup) > 1.0:
            dead = [tid for tid, ts in last_seen_ts.items() if (now - ts) > TRACK_TTL_SECONDS]
            for tid in dead:
                last_seen_ts.pop(tid, None)
                armed.pop(tid, None)
                tid_last_gone[tid] = now
            last_cleanup = now

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()