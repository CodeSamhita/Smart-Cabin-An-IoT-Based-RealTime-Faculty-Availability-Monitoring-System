# People counter on the Pi, shown on a web page: live video with a box around each person and the count.
# Two detectors, switchable on the page, so you can compare speed and accuracy:
#   MobileNet-SSD : small and fast. Downloaded by itself on the first run (23 MB).
#   YOLOv8n       : the same model as the laptop's headcount.py, more accurate but slower.
#                   Needs models/yolov8n.onnx, made once on the laptop (see the README in this folder).
# The count only changes after CONFIRM_READINGS readings in a row agree (same rule as headcount.py),
# so it doesn't jump when someone is half hidden for one frame.
#
# Run:  python3 6_people_count_web.py      then open the address it prints (port 8082)
# Stop smartcabin_pi.py first: only one program can use the camera at a time.
#
# Libraries (once):  sudo apt install -y python3-picamera2 python3-opencv

import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
from picamera2 import Picamera2

PORT = 8082
WIDTH, HEIGHT = 640, 480
CONFIRM_READINGS = 3

FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_FOLDER = os.path.join(FOLDER, "models")
MOBILENET_PROTO = os.path.join(MODEL_FOLDER, "mobilenet_ssd.prototxt")
MOBILENET_WEIGHTS = os.path.join(MODEL_FOLDER, "mobilenet_ssd.caffemodel")
MOBILENET_URLS = {MOBILENET_PROTO: "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
                  MOBILENET_WEIGHTS: "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"}
YOLO_FILE = os.path.join(MODEL_FOLDER, "yolov8n.onnx")
YOLO_SIZE = 320               # the size yolov8n.onnx was exported with (imgsz=320)

MOBILENET_PERSON = 15         # class number of "person" in MobileNet-SSD (VOC classes)
YOLO_PERSON = 0               # class number of "person" in YOLO (COCO classes)

settings = {"model": "mobilenet", "confidence": 0.5}
state = {"seen": 0, "count": 0, "detect_ms": 0, "fps": 0, "message": "starting...", "note": ""}
lock = threading.Lock()


# ---------- Detectors ----------
def download_mobilenet():
    os.makedirs(MODEL_FOLDER, exist_ok=True)
    for path, url in MOBILENET_URLS.items():
        if not os.path.exists(path):
            print("Downloading", os.path.basename(path), "...")
            urllib.request.urlretrieve(url, path + ".part")
            os.replace(path + ".part", path)      # only keep the file once it is complete


def load_model(name):
    if name == "mobilenet":
        download_mobilenet()
        return cv2.dnn.readNetFromCaffe(MOBILENET_PROTO, MOBILENET_WEIGHTS)
    if not os.path.exists(YOLO_FILE):
        return None
    return cv2.dnn.readNetFromONNX(YOLO_FILE)


def detect_mobilenet(net, frame, confidence):
    # Returns a list of boxes (x1, y1, x2, y2, score) around people
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()[0, 0]          # each row: _, class, score, x1, y1, x2, y2 (0 - 1)
    boxes = []
    for row in detections:
        if int(row[1]) == MOBILENET_PERSON and row[2] >= confidence:
            boxes.append((int(row[3] * w), int(row[4] * h), int(row[5] * w), int(row[6] * h), float(row[2])))
    return boxes


def detect_yolo(net, frame, confidence):
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1 / 255, (YOLO_SIZE, YOLO_SIZE), swapRB=True)
    net.setInput(blob)
    rows = net.forward()[0].T                 # each row: centre x, centre y, width, height, 80 class scores
    scale_x, scale_y = w / YOLO_SIZE, h / YOLO_SIZE
    found, scores = [], []
    for row in rows:
        score = float(row[4 + YOLO_PERSON])
        if score >= confidence:
            cx, cy, bw, bh = row[0] * scale_x, row[1] * scale_y, row[2] * scale_x, row[3] * scale_y
            found.append([int(cx - bw / 2), int(cy - bh / 2), int(bw), int(bh)])
            scores.append(score)
    # YOLO gives several boxes per person; keep the best one of each overlapping group
    keep = cv2.dnn.NMSBoxes(found, scores, confidence, 0.45)
    boxes = []
    for i in (keep.flatten() if len(keep) else []):
        x, y, bw, bh = found[i]
        boxes.append((x, y, x + bw, y + bh, scores[i]))
    return boxes


def steady_count(recent, last_steady):
    # Only accept a new count when the last few readings all agree
    if len(recent) < CONFIRM_READINGS:
        return last_steady
    last_few = recent[-CONFIRM_READINGS:]
    return last_few[0] if len(set(last_few)) == 1 else last_steady


def draw(frame, boxes, count):
    for x1, y1, x2, y2, score in boxes:
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(frame, str(round(score * 100)) + "%", (x1, max(y1 - 6, 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 0), 2)
    cv2.putText(frame, "People: " + str(count), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 220, 0), 2)


# ---------- Camera -> detect -> picture for the page ----------
latest_jpeg = None
new_picture = threading.Condition()


def detect_loop(camera):
    global latest_jpeg
    nets = {}
    recent = []
    steady = 0
    last_time = time.time()
    while True:
        name = settings["model"]
        if name not in nets:
            with lock:
                state["message"] = "loading " + name + "..."
            try:
                nets[name] = load_model(name)
            except Exception as error:
                with lock:
                    state["message"] = "can't load " + name + ": " + str(error)
                time.sleep(5)
                continue
        net = nets[name]
        if net is None:                       # yolov8n.onnx not there yet
            with lock:
                state["note"] = "YOLOv8n: models/yolov8n.onnx is missing - see the README. Using MobileNet-SSD."
            settings["model"] = "mobilenet"
            del nets[name]
            continue

        frame = camera.capture_array()
        start = time.time()
        if name == "mobilenet":
            boxes = detect_mobilenet(net, frame, settings["confidence"])
        else:
            boxes = detect_yolo(net, frame, settings["confidence"])
        detect_ms = (time.time() - start) * 1000

        recent = (recent + [len(boxes)])[-10:]
        steady = steady_count(recent, steady)
        draw(frame, boxes, steady)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])

        now = time.time()
        with lock:
            state.update(seen=len(boxes), count=steady, detect_ms=round(detect_ms),
                         fps=round(1 / (now - last_time), 1), message="running " + name)
        last_time = now
        with new_picture:
            latest_jpeg = jpeg.tobytes()
            new_picture.notify_all()


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>People Counter</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  .wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  img { max-width: 100%; width: 720px; background: #000; border-radius: 6px; }
  .panel { background: #fff; border-radius: 8px; padding: 12px 16px; min-width: 260px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .count { font-size: 64px; font-weight: 700; line-height: 1; }
  .small { color: #555; margin: 4px 0; }
  .stats { font-family: monospace; margin: 4px 0; }
  label { display: block; margin: 12px 0 2px; font-size: 14px; }
  select, input[type=range] { width: 100%; }
</style></head>
<body>
<h1>People Counter</h1>
<div class="wrap">
  <img src="/stream.mjpg" alt="live video">
  <div class="panel">
    <div class="small">People in view</div>
    <div class="count" id="count">-</div>
    <div class="small">Seen in this frame: <b id="seen">-</b></div>
    <div class="stats" id="stats"></div>
    <div class="small" id="message"></div>
    <div class="small" id="note" style="color:#c62828"></div>

    <label>Detector</label>
    <select id="model" onchange="send('model', this.value)">
      <option value="mobilenet">MobileNet-SSD (fast)</option>
      <option value="yolo">YOLOv8n (accurate)</option>
    </select>
    <label>Confidence: <b id="confidence-val"></b></label>
    <input type="range" id="confidence" min="0.2" max="0.9" step="0.05"
           oninput="document.getElementById('confidence-val').textContent = this.value"
           onchange="send('confidence', this.value)">
  </div>
</div>
<script>
async function send(name, value) {
  await fetch("/set?name=" + name + "&value=" + value, {method: "POST"});
}

async function refresh(first) {
  try {
    const s = await (await fetch("/status.json")).json();
    document.getElementById("count").textContent = s.state.count;
    document.getElementById("seen").textContent = s.state.seen;
    document.getElementById("stats").textContent = s.state.detect_ms + " ms per detect, " + s.state.fps + " fps";
    document.getElementById("message").textContent = s.state.message;
    document.getElementById("note").textContent = s.state.note;
    const model = document.getElementById("model");
    if (document.activeElement !== model) model.value = s.settings.model;   // it falls back if YOLO is missing
    if (first) {
      document.getElementById("confidence").value = s.settings.confidence;
      document.getElementById("confidence-val").textContent = s.settings.confidence;
    }
  } catch (e) {
    document.getElementById("message").textContent = "Can't reach the Pi";
  }
}

refresh(true);
setInterval(refresh, 1000);
</script>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def send(self, body, content_type, code=200):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status.json":
            with lock:
                body = json.dumps({"settings": settings, "state": state})
            self.send(body.encode(), "application/json")
        elif path == "/stream.mjpg":
            self.stream()
        else:
            self.send(b"not found", "text/plain", 404)

    def stream(self):
        # One JPEG after another; the browser shows them as video
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=FRAME")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                with new_picture:
                    new_picture.wait()
                    jpeg = latest_jpeg
                self.wfile.write(b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                 str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass                                  # the browser tab was closed

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        name = query.get("name", [""])[0]
        value = query.get("value", [""])[0]
        if url.path == "/set" and name == "model" and value in ("mobilenet", "yolo"):
            settings["model"] = value
        elif url.path == "/set" and name == "confidence" and value.replace(".", "", 1).isdigit():
            settings["confidence"] = min(max(float(value), 0.05), 0.95)
        else:
            return self.send(b"bad request", "text/plain", 400)
        self.send(b"ok", "text/plain")

    def log_message(self, *args):
        pass                                      # keep the terminal quiet


def my_address():
    # The IP address other devices on the network use to reach this Pi
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def main():
    if not Picamera2.global_camera_info():
        sys.exit("No camera found - check the ribbon cable")
    Picamera2.set_logging(logging.ERROR)
    try:
        camera = Picamera2()
    except Exception as error:
        sys.exit("Can't open the camera: " + str(error) + " - is smartcabin_pi.py still running?")
    # "RGB888" in picamera2 gives the colour order OpenCV uses (BGR)
    camera.configure(camera.create_video_configuration(main={"size": (WIDTH, HEIGHT), "format": "RGB888"}))
    camera.start()

    threading.Thread(target=detect_loop, args=(camera,), daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("People counter page:")
    print("  http://" + my_address() + ":" + str(PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(PORT))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        camera.stop()
        camera.close()


if __name__ == "__main__":
    main()
