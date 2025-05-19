# ─────────────────────────────────────────────────────────────
# stream_manager.py
# ─────────────────────────────────────────────────────────────
import cv2
import torch
import numpy as np
import threading
import time
import json
from collections import deque

# ——— Model Setup ———
DEVICE = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
MODEL  = torch.hub.load('ultralytics/yolov5', 'yolov5m', trust_repo=True).to(DEVICE)
MODEL.conf, MODEL.iou = 0.25, 0.45
MODEL.eval()

model_lock = threading.Lock()
IP_URL     = "http://192.168.116.233:4747/video"

# ——— Shared State ———
latest        = {'webcam': None, 'ipcam': None}
caps          = {}
flags_stream  = {'webcam': False, 'ipcam': False}
flags_detect  = {'webcam': False, 'ipcam': False}
flags_heatmap = {'webcam': False, 'ipcam': False}
params        = {
    'webcam': {'resolution': '640x360', 'fps': 30, 'bitrate': 60},
    'ipcam':  {'resolution': '640x360', 'fps': 30, 'bitrate': 60},
}
threads = {}
lock    = threading.Lock()

# ——— Analytics State ———
analytics = {
    s: {
        'times':  deque(maxlen=100),
        'counts': deque(maxlen=100),
        'confs':  deque(maxlen=100)
    } for s in ('webcam','ipcam')
}

mqtt_client = None
last_pub    = {'webcam': 0.0, 'ipcam': 0.0}
MQTT_EVENT_BASE = 'yolo/events'
PUBLISH_INTERVAL = 1.0

def initialize_shared_state():
    global mqtt_client
    import mqtt_handler
    mqtt_client = mqtt_handler.mqtt_client

def make_pipeline(src):
    if src == 'webcam':
        return "avfvideosrc device-index=0 ! videoconvert ! videoflip method=horizontal-flip ! video/x-raw,format=BGR ! appsink sync=false"
    else:
        return (
            f"souphttpsrc location={IP_URL} do-timestamp=true blocksize=4096 ! "
            "multipartdemux ! jpegdec ! videoconvert ! video/x-raw,format=BGR ! appsink sync=false"
        )

def grabber(src):
    cap = caps[src]
    while flags_stream[src]:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        with lock:
            latest[src] = frame.copy()
    cap.release()
    with lock:
        latest[src] = None

def stop_stream(src):
    if not flags_stream[src]:
        return False
    flags_stream[src] = False
    th = threads.get(src)
    if th and th.is_alive():
        th.join(timeout=1.0)
    with lock:
        caps.pop(src, None)
        threads.pop(src, None)
        flags_detect[src]   = False
        flags_heatmap[src]  = False
        latest[src]         = None
        analytics[src]['times'].clear()
        analytics[src]['counts'].clear()
        analytics[src]['confs'].clear()
    return True

def start_stream(src, resolution, fps, bitrate):
    fps = max(1, min(int(fps), 30))
    if flags_stream[src]:
        stop_stream(src)
        time.sleep(0.2)
    cap = cv2.VideoCapture(make_pipeline(src), cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        return False
    with lock:
        caps[src]          = cap
        flags_stream[src]  = True
        flags_detect[src]  = False
        flags_heatmap[src] = False
        params[src]        = {'resolution': resolution, 'fps': fps, 'bitrate': bitrate}
        analytics[src]['times'].clear()
        analytics[src]['counts'].clear()
        analytics[src]['confs'].clear()
    t = threading.Thread(target=grabber, args=(src,), daemon=True)
    threads[src] = t
    t.start()
    return True

def make_mjpeg_stream(src):
    bg_sub   = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=False)
    heat_acc = None

    while True:
        with lock:
            frame   = latest[src]
            det_on  = flags_detect[src]
            heat_on = flags_heatmap[src]
            cfg     = params[src].copy()

        if frame is None:
            time.sleep(0.1)
            continue

        out = frame.copy()
        cnt, avg_conf = 0, 0.0

        if det_on:
            with model_lock, torch.inference_mode():
                res  = MODEL([out], size=640)
                dets = res.xyxy[0].cpu().numpy()
                out  = np.squeeze(res.render())

            cnt = len(dets)
            if cnt:
                avg_conf = float(dets[:,4].mean())

            now = time.time()
            if now - last_pub[src] >= PUBLISH_INTERVAL:
                ts = analytics[src]['times']
                fps_act = round(len(ts)/(ts[-1]-ts[0]),1) if len(ts)>=2 else 0.0

                mqtt_client.publish(
                    f"{MQTT_EVENT_BASE}/{src}/metrics",
                    json.dumps({
                        'count': cnt,
                        'avg_conf': avg_conf,
                        'actual_fps': fps_act,
                        'ts': now
                    })
                )
                last_pub[src] = now

            with lock:
                analytics[src]['counts'].append(cnt)
                analytics[src]['confs'].append(avg_conf)

        if heat_on:
            gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
            fg   = bg_sub.apply(gray)
            if heat_acc is None:
                heat_acc = fg.astype('float')
            heat_acc = heat_acc * 0.95 + fg * 0.05
            norm     = cv2.normalize(heat_acc, None, 0, 255, cv2.NORM_MINMAX).astype('uint8')
            cmap     = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
            out      = cv2.addWeighted(out, 0.7, cmap, 0.3, 0)

        tw, th = map(int, cfg['resolution'].split('x'))
        h0, w0 = out.shape[:2]
        curr, tgt = w0/h0, tw/th
        if curr>tgt:
            nw = int(tgt*h0); x1=(w0-nw)//2; out=out[:,x1:x1+nw]
        else:
            nh = int(w0/tgt); y1=(h0-nh)//2; out=out[y1:y1+nh,:]
        out = cv2.resize(out,(tw,th))

        with lock:
            analytics[src]['times'].append(time.time())

        ret, jpg = cv2.imencode('.jpg', out, [int(cv2.IMWRITE_JPEG_QUALITY), cfg['bitrate']])
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               jpg.tobytes() + b'\r\n')
        time.sleep(1.0/cfg['fps'])
