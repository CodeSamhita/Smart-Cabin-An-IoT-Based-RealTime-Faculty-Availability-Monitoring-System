# People counter on the Pi, snapshot style: take one picture, count the people in it, wait, repeat.
# Same detectors as 6_people_count_web.py, but no live video:
#   1. take a picture   2. find the people   3. drop the fake ones   4. show the picture and count   5. wait
# Much lighter on the CPU than live video, which matters on the Zero 2W.
#
# Detectors (switchable on the page):
#   MobileNet-SSD : small and fast. Downloaded by itself on the first run (23 MB).
#   YOLOv8n       : more accurate, slower. Needs models/yolov8n.onnx (see the README in this folder).
#
# A camera can't tell a photo or poster of a person from a real one, so two checks (each on/off on the page):
#   Stillness check : a real person is never perfectly still. A box whose picture hasn't changed for
#                     STILL_SECONDS is marked "still" and not counted (catches posters and framed photos).
#   Ignore zones    : areas of the picture that are never counted, e.g. where a poster hangs.
#                     Drawn on the page, or made from the boxes seen in an empty room. Saved in ignore_zones.json.
# The count only changes after CONFIRM_READINGS pictures in a row agree (same rule as headcount.py).
#
# Run:  python3 7_people_count_snapshot.py      then open the address it prints (port 8083)
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

PORT = 8083
WIDTH, HEIGHT = 640, 480
CONFIRM_READINGS = 3
FORGET_SECONDS = 10           # a box not seen for this long is forgotten by the stillness check

FOLDER = os.path.dirname(os.path.abspath(__file__))
ZONES_FILE = os.path.join(FOLDER, "ignore_zones.json")
MODEL_FOLDER = os.path.join(FOLDER, "models")
MOBILENET_PROTO = os.path.join(MODEL_FOLDER, "mobilenet_ssd.prototxt")
MOBILENET_WEIGHTS = os.path.join(MODEL_FOLDER, "mobilenet_ssd.caffemodel")
MOBILENET_URLS = {MOBILENET_PROTO: "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
                  MOBILENET_WEIGHTS: "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel"}
YOLO_FILE = os.path.join(MODEL_FOLDER, "yolov8n.onnx")
YOLO_SIZE = 320               # the size yolov8n.onnx was exported with (imgsz=320)

MOBILENET_PERSON = 15         # class number of "person" in MobileNet-SSD (VOC classes)
YOLO_PERSON = 0               # class number of "person" in YOLO (COCO classes)

COLOURS = {"counted": (0, 220, 0), "still": (0, 140, 255), "ignored": (150, 150, 150)}   # BGR

settings = {"model": "mobilenet", "confidence": 0.5, "interval": 1.5,     # interval = seconds between pictures
            "still_check": 1, "still_seconds": 60, "move_threshold": 4.0, "zones_on": 1}
state = {"seen": 0, "counted": 0, "still": 0, "ignored": 0, "count": 0, "detect_ms": 0, "taken_at": "-",
         "pictures": 0, "message": "starting...", "note": ""}
last_boxes = []               # boxes of the last picture, 0 - 1 coordinates, for "make zones from boxes"
lock = threading.Lock()


# ---------- Detectors (same as 6_people_count_web.py) ----------
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


# ---------- Ignore zones ----------
def load_zones():
    # Each zone is [x1, y1, x2, y2] in 0 - 1 (so it fits any picture size)
    try:
        with open(ZONES_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_zones():
    with open(ZONES_FILE, "w") as f:
        json.dump(zones, f)


zones = load_zones()


def in_ignore_zone(box, w, h):
    # True if at least half of the box is inside an ignore zone
    x1, y1, x2, y2 = box[:4]
    area = max(1, (x2 - x1) * (y2 - y1))
    for zx1, zy1, zx2, zy2 in zones:
        overlap_w = min(x2, zx2 * w) - max(x1, zx1 * w)
        overlap_h = min(y2, zy2 * h) - max(y1, zy1 * h)
        if overlap_w > 0 and overlap_h > 0 and overlap_w * overlap_h / area >= 0.5:
            return True
    return False


# ---------- Stillness check ----------
tracks = []                   # one per box seen recently: box, reference picture, when it last moved, last seen


def overlap(a, b):
    # Intersection over union of two boxes: 1 = same box, 0 = not touching
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def box_picture(frame, box):
    # The part of the picture inside the box, grey and always the same small size, so two can be compared
    h, w = frame.shape[:2]
    x1, y1 = max(0, box[0]), max(0, box[1])
    x2, y2 = min(w, box[2]), min(h, box[3])
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    grey = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    return cv2.resize(grey, (32, 64))


def check_stillness(frame, boxes, now):
    # Returns, for each box, (seconds it has been still, how much it changed 0 - 255)
    global tracks
    results = []
    used = set()
    for box in boxes:
        best, best_overlap = None, 0.0
        for i, track in enumerate(tracks):
            o = overlap(box, track["box"])
            if i not in used and o > best_overlap:
                best, best_overlap = i, o
        picture = box_picture(frame, box)
        if best is None or best_overlap < 0.4 or picture is None:
            tracks.append({"box": box, "ref": picture, "moved_at": now, "seen_at": now})   # a new box
            used.add(len(tracks) - 1)
            results.append((0.0, 0.0))
            continue

        track = tracks[best]
        used.add(best)
        change = float(cv2.absdiff(picture, track["ref"]).mean()) if track["ref"] is not None else 255.0
        if change > settings["move_threshold"] or best_overlap < 0.8:     # it changed, or the box moved
            track["moved_at"] = now
            track["ref"] = picture
        track["box"] = box
        track["seen_at"] = now
        results.append((now - track["moved_at"], change))

    tracks = [t for t in tracks if now - t["seen_at"] < FORGET_SECONDS]
    return results


# ---------- Drawing ----------
def draw(frame, labelled, count):
    h, w = frame.shape[:2]
    if settings["zones_on"]:
        for zx1, zy1, zx2, zy2 in zones:
            cv2.rectangle(frame, (int(zx1 * w), int(zy1 * h)), (int(zx2 * w), int(zy2 * h)), (0, 165, 255), 1)
            cv2.putText(frame, "ignore", (int(zx1 * w) + 4, int(zy1 * h) + 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
    for box, status, still_for, change in labelled:
        x1, y1, x2, y2, score = box
        colour = COLOURS[status]
        text = str(round(score * 100)) + "%"
        if status == "still":
            text += " still " + str(round(still_for)) + "s"
        elif status == "ignored":
            text += " ignored"
        elif settings["still_check"]:
            text += " change " + str(round(change, 1))
        cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(frame, text, (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 2)
    cv2.putText(frame, "People: " + str(count) + "   " + time.strftime("%H:%M:%S"), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 220, 0), 2)


# ---------- Snapshot loop: picture -> detect -> drop fakes -> show -> wait ----------
latest_jpeg = None


def snapshot_loop(camera):
    global latest_jpeg, last_boxes
    nets = {}
    recent = []
    steady = 0
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

        # 1. take a picture
        frame = camera.capture_array()
        now = time.time()
        h, w = frame.shape[:2]

        # 2. find the people
        start = time.time()
        if name == "mobilenet":
            boxes = detect_mobilenet(net, frame, settings["confidence"])
        else:
            boxes = detect_yolo(net, frame, settings["confidence"])
        detect_ms = (time.time() - start) * 1000

        # 3. drop the fake ones: in an ignore zone, or not moving for too long
        stillness = check_stillness(frame, boxes, now)
        labelled = []
        with lock:
            for box, (still_for, change) in zip(boxes, stillness):
                if settings["zones_on"] and in_ignore_zone(box, w, h):
                    status = "ignored"
                elif settings["still_check"] and still_for >= settings["still_seconds"]:
                    status = "still"
                else:
                    status = "counted"
                labelled.append((box, status, still_for, change))
        counted = sum(1 for item in labelled if item[1] == "counted")

        # 4. show the picture with boxes and the count
        recent = (recent + [counted])[-10:]
        steady = steady_count(recent, steady)
        draw(frame, labelled, steady)
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with lock:
            latest_jpeg = jpeg.tobytes()
            last_boxes = [[b[0] / w, b[1] / h, b[2] / w, b[3] / h, s] for b, s, _, _ in labelled]
            state.update(seen=len(boxes), counted=counted,
                         still=sum(1 for item in labelled if item[1] == "still"),
                         ignored=sum(1 for item in labelled if item[1] == "ignored"),
                         count=steady, detect_ms=round(detect_ms), taken_at=time.strftime("%H:%M:%S"),
                         pictures=state["pictures"] + 1, message="running " + name)

        # 5. wait before the next picture
        time.sleep(settings["interval"])


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>People Counter</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  h2 { font-size: 15px; margin: 18px 0 4px; border-top: 1px solid #eee; padding-top: 12px; }
  .wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  .picture { position: relative; width: 720px; max-width: 100%; user-select: none; }
  .picture img { display: block; width: 100%; background: #000; border-radius: 6px; }
  .picture.drawing { cursor: crosshair; touch-action: none; }
  #drag { position: absolute; border: 2px dashed #ff8c00; background: rgba(255,140,0,.15); display: none; pointer-events: none; }
  .panel { background: #fff; border-radius: 8px; padding: 12px 16px; width: 300px; max-width: 100%; box-sizing: border-box;
           box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .count { font-size: 64px; font-weight: 700; line-height: 1; }
  .small { color: #555; margin: 4px 0; font-size: 14px; }
  .stats { font-family: monospace; margin: 4px 0; font-size: 13px; }
  label { display: block; margin: 10px 0 2px; font-size: 14px; }
  select, input[type=range] { width: 100%; }
  button { font-size: 14px; padding: 5px 10px; margin: 4px 4px 0 0; border: 1px solid #ccc; border-radius: 5px; background: #fff; cursor: pointer; }
  button:hover { background: #eee; }
  button.on { background: #ff8c00; color: #fff; border-color: #ff8c00; }
  .key span { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin: 0 4px 0 8px; }
</style></head>
<body>
<h1>People Counter (snapshots)</h1>
<div class="wrap">
  <div class="picture" id="picture-box">
    <img id="picture" alt="last picture" draggable="false">
    <div id="drag"></div>
  </div>
  <div class="panel">
    <div class="small">People in view</div>
    <div class="count" id="count">-</div>
    <div class="small">Last picture: <b id="seen">-</b> found, <b id="counted">-</b> counted,
      <b id="still">-</b> still, <b id="ignored">-</b> ignored</div>
    <div class="small key"><span style="background:#00dc00"></span>counted<span style="background:#ff8c00"></span>still
      <span style="background:#969696"></span>ignored</div>
    <div class="stats" id="stats"></div>
    <div class="small" id="message"></div>
    <div class="small" id="note" style="color:#c62828"></div>

    <label>Detector</label>
    <select id="model" onchange="send('model', this.value)">
      <option value="mobilenet">MobileNet-SSD (fast)</option>
      <option value="yolo">YOLOv8n (accurate)</option>
    </select>
    <label>Confidence: <b id="confidence-val"></b></label>
    <input type="range" id="confidence" min="0.2" max="0.9" step="0.05" oninput="show(this)" onchange="send(this.id, this.value)">
    <label>Wait between pictures: <b id="interval-val"></b> s</label>
    <input type="range" id="interval" min="0.5" max="5" step="0.5" oninput="show(this)" onchange="send(this.id, this.value)">

    <h2>Stillness check</h2>
    <label><input type="checkbox" id="still_check" onchange="send(this.id, this.checked ? 1 : 0)"> Don't count people who don't move</label>
    <label>Not counted after still for: <b id="still_seconds-val"></b> s</label>
    <input type="range" id="still_seconds" min="10" max="300" step="10" oninput="show(this)" onchange="send(this.id, this.value)">
    <label>Movement threshold: <b id="move_threshold-val"></b></label>
    <input type="range" id="move_threshold" min="1" max="20" step="0.5" oninput="show(this)" onchange="send(this.id, this.value)">
    <div class="small">Each green box shows its "change". A real person goes above the threshold now and then;
      a poster stays below it. Raise it if posters count, lower it if still people drop out.</div>

    <h2>Ignore zones</h2>
    <label><input type="checkbox" id="zones_on" onchange="send(this.id, this.checked ? 1 : 0)"> Use ignore zones</label>
    <button id="draw-btn" onclick="toggleDraw()">Draw a zone</button>
    <button onclick="post('/zones/from_boxes')">Ignore boxes seen now</button>
    <button onclick="if (confirm('Delete all ignore zones?')) post('/zones/clear')">Clear all</button>
    <div class="small">"Ignore boxes seen now": use it when the room is empty but a poster or photo is still found.</div>
    <div id="zones"></div>
  </div>
</div>
<script>
let lastPicture = 0;
let drawing = false;
let start = null;
const box = document.getElementById("picture-box");
const drag = document.getElementById("drag");

function show(el) { document.getElementById(el.id + "-val").textContent = el.value; }
async function send(name, value) { await fetch("/set?name=" + name + "&value=" + value, {method: "POST"}); }
async function post(url) { await fetch(url, {method: "POST"}); refresh(); }

// ---- drawing an ignore zone on the picture ----
function toggleDraw() {
  drawing = !drawing;
  box.classList.toggle("drawing", drawing);
  document.getElementById("draw-btn").classList.toggle("on", drawing);
  document.getElementById("draw-btn").textContent = drawing ? "Drag on the picture..." : "Draw a zone";
}

function where(e) {
  // Mouse / finger position on the picture, 0 - 1
  const r = box.getBoundingClientRect();
  return [Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1)];
}

function showDrag(a, b) {
  drag.style.display = "block";
  drag.style.left = Math.min(a[0], b[0]) * 100 + "%";
  drag.style.top = Math.min(a[1], b[1]) * 100 + "%";
  drag.style.width = Math.abs(a[0] - b[0]) * 100 + "%";
  drag.style.height = Math.abs(a[1] - b[1]) * 100 + "%";
}

box.addEventListener("pointerdown", e => {
  if (!drawing) return;
  start = where(e);
  box.setPointerCapture(e.pointerId);
});
box.addEventListener("pointermove", e => { if (start) showDrag(start, where(e)); });
box.addEventListener("pointerup", async e => {
  if (!start) return;
  const end = where(e);
  const x1 = Math.min(start[0], end[0]), y1 = Math.min(start[1], end[1]);
  const x2 = Math.max(start[0], end[0]), y2 = Math.max(start[1], end[1]);
  start = null;
  drag.style.display = "none";
  toggleDraw();
  if (x2 - x1 > 0.02 && y2 - y1 > 0.02)
    await post("/zones/add?x1=" + x1.toFixed(3) + "&y1=" + y1.toFixed(3) + "&x2=" + x2.toFixed(3) + "&y2=" + y2.toFixed(3));
});

// ---- status ----
function showZones(zones) {
  document.getElementById("zones").innerHTML = zones.length
    ? zones.map((z, i) => "<button onclick=\\"post('/zones/delete?i=" + i + "')\\">Delete zone " + (i + 1) + "</button>").join("")
    : "<div class='small'>No ignore zones yet.</div>";
}

async function refresh(first) {
  try {
    const s = await (await fetch("/status.json")).json();
    for (const name of ["count", "seen", "counted", "still", "ignored"])
      document.getElementById(name).textContent = s.state[name];
    document.getElementById("stats").textContent =
      "Picture " + s.state.pictures + " at " + s.state.taken_at + ", detect " + s.state.detect_ms + " ms";
    document.getElementById("message").textContent = s.state.message;
    document.getElementById("note").textContent = s.state.note;
    if (s.state.pictures !== lastPicture) {          // only load the picture when there is a new one
      lastPicture = s.state.pictures;
      document.getElementById("picture").src = "/latest.jpg?n=" + lastPicture;
    }
    const model = document.getElementById("model");
    if (document.activeElement !== model) model.value = s.settings.model;   // it falls back if YOLO is missing
    showZones(s.zones);
    if (first) {
      for (const name of ["confidence", "interval", "still_seconds", "move_threshold"]) {
        document.getElementById(name).value = s.settings[name];
        show(document.getElementById(name));
      }
      for (const name of ["still_check", "zones_on"])
        document.getElementById(name).checked = s.settings[name] === 1;
    }
  } catch (e) {
    document.getElementById("message").textContent = "Can't reach the Pi";
  }
}

refresh(true);
setInterval(refresh, 500);
</script>
</body></html>
"""

NUMBER_SETTINGS = {"confidence": (0.05, 0.95), "interval": (0.0, 60.0), "still_seconds": (5, 3600),
                   "move_threshold": (0.5, 50.0), "still_check": (0, 1), "zones_on": (0, 1)}


def is_number(text):
    return text.replace(".", "", 1).isdigit()


def change_setting(name, value):
    if name == "model" and value in ("mobilenet", "yolo"):
        settings["model"] = value
        return True
    if name in NUMBER_SETTINGS and is_number(value):
        low, high = NUMBER_SETTINGS[name]
        number = min(max(float(value), low), high)
        settings[name] = int(number) if name in ("still_check", "zones_on", "still_seconds") else number
        return True
    return False


def change_zones(path, query):
    # Add, delete or clear ignore zones. Returns True if the request was understood.
    global zones
    with lock:
        if path == "/zones/add":
            try:
                zone = [min(max(float(query[k][0]), 0.0), 1.0) for k in ("x1", "y1", "x2", "y2")]
            except (KeyError, ValueError):
                return False
            zones.append(zone)
        elif path == "/zones/delete":
            index = query.get("i", [""])[0]
            if not index.isdigit() or int(index) >= len(zones):
                return False
            del zones[int(index)]
        elif path == "/zones/clear":
            zones = []
        elif path == "/zones/from_boxes":
            # Every box in the last picture that isn't ignored yet becomes a zone (a little bigger than the box)
            for x1, y1, x2, y2, status in last_boxes:
                if status != "ignored":
                    pad_x, pad_y = (x2 - x1) * 0.05, (y2 - y1) * 0.05
                    zones.append([round(max(0.0, x1 - pad_x), 3), round(max(0.0, y1 - pad_y), 3),
                                  round(min(1.0, x2 + pad_x), 3), round(min(1.0, y2 + pad_y), 3)])
        else:
            return False
        save_zones()
    return True


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
                body = json.dumps({"settings": settings, "state": state, "zones": zones})
            self.send(body.encode(), "application/json")
        elif path == "/latest.jpg":
            with lock:
                jpeg = latest_jpeg
            if jpeg is None:
                self.send(b"no picture yet", "text/plain", 503)
            else:
                self.send(jpeg, "image/jpeg")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/set":
            ok = change_setting(query.get("name", [""])[0], query.get("value", [""])[0])
        elif url.path.startswith("/zones/"):
            ok = change_zones(url.path, query)
        else:
            ok = False
        self.send(b"ok" if ok else b"bad request", "text/plain", 200 if ok else 400)

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
    camera.configure(camera.create_still_configuration(main={"size": (WIDTH, HEIGHT), "format": "RGB888"}))
    camera.start()
    time.sleep(1)                             # let exposure and white balance settle

    threading.Thread(target=snapshot_loop, args=(camera,), daemon=True).start()

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
