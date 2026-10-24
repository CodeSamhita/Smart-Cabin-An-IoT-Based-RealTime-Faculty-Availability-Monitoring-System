# Face recognition on a web page - bare-bone version of the one in smartcabin_pi.py: register and check.
# Every CHECK_INTERVAL s it takes a picture and shows who is in it. "Register" takes 10 photos of one face.
#
# How it works (same 3 steps as smartcabin_pi.py and face_app.py):
#   1. DETECT : find where the faces are in the picture   (YuNet model)
#   2. EMBED  : turn each face into 128 numbers            (SFace model)
#   3. MATCH  : compare with the saved people (cosine similarity). Too far from everyone -> "Unknown"
# The two models (about 37 MB) are downloaded into models/ on the first run. Faces are saved in known_faces.json.
#
# Run:  python3 8_face_recognition.py      then open the address it prints (port 8084)
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
import numpy as np
from picamera2 import Picamera2

PORT = 8084
# Faces need more pixels than whole bodies: in a test photo no face was found at 640x480, one at 1296x972.
RESOLUTIONS = ["320x240", "640x480", "1296x972"]
MIN_FACE_CONFIDENCE = 0.9     # ignore weak face detections
SAMPLES = 10                  # photos taken when registering
REGISTER_SECONDS = 30         # give up registering after this long
CHECK_INTERVAL = 1.5          # seconds between pictures when checking
SAMPLE_INTERVAL = 0.3         # seconds between photos when registering

FOLDER = os.path.dirname(os.path.abspath(__file__))
MODEL_FOLDER = os.path.join(FOLDER, "models")
FACES_FILE = os.path.join(FOLDER, "known_faces.json")

# OpenCV's official model files. Older OpenCV (below 4.8) needs the older detector.
YUNET_NEW = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
YUNET_OLD = "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx"
SFACE = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

settings = {"threshold": 0.36,   # higher = stricter matching (try 0.30 - 0.50), same as smartcabin_pi.py
            "resolution": "1296x972"}
state = {"in_view": [], "taken_at": "-", "pictures": 0, "detect_ms": 0, "message": "starting...",
         "ready": False, "register_name": None, "register_count": 0}
lock = threading.Lock()
latest_jpeg = None


# ---------- Models ----------
def download(url):
    os.makedirs(MODEL_FOLDER, exist_ok=True)
    path = os.path.join(MODEL_FOLDER, url.split("/")[-1])
    if not os.path.exists(path):
        print("Downloading", os.path.basename(path), "...")
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)      # only keep the file once it is complete
    return path


def load_models():
    major, minor = [int(n) for n in cv2.__version__.split(".")[:2]]
    yunet = download(YUNET_NEW if (major, minor) >= (4, 8) else YUNET_OLD)
    sface = download(SFACE)
    detector = cv2.FaceDetectorYN.create(yunet, "", (640, 480), MIN_FACE_CONFIDENCE)   # size is set per picture
    recognizer = cv2.FaceRecognizerSF.create(sface, "")
    return detector, recognizer


# ---------- The 3 steps ----------
def find_faces(detector, frame):
    # Each face row: x, y, w, h, 10 numbers for eyes/nose/mouth, confidence
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    ok, faces = detector.detect(frame)
    return [] if faces is None else faces


def embed(recognizer, frame, face):
    aligned = recognizer.alignCrop(frame, face)       # straighten and crop the face
    vector = recognizer.feature(aligned).flatten()
    return vector / np.linalg.norm(vector)            # length 1, so dot product = cosine similarity


def identify(vector, known):
    # Returns (name, score). "Unknown" if nobody is similar enough.
    best_name, best_score = "Unknown", -1.0
    for name, vectors in known.items():
        score = float(np.max(vectors @ vector))       # best match among that person's photos
        if score > best_score:
            best_name, best_score = name, score
    if best_score < settings["threshold"]:
        return "Unknown", best_score
    return best_name, best_score


# ---------- Saved faces ----------
def load_faces():
    # {name: array of embeddings}
    if not os.path.exists(FACES_FILE):
        return {}
    with open(FACES_FILE) as f:
        saved = json.load(f)
    return {name: np.array(vectors, dtype=np.float32) for name, vectors in saved.items()}


def save_faces():
    with open(FACES_FILE, "w") as f:
        json.dump({name: vectors.tolist() for name, vectors in known.items()}, f)


known = load_faces()


# ---------- Camera ----------
def start_camera(camera, resolution):
    width, height = [int(n) for n in resolution.split("x")]
    # "RGB888" in picamera2 gives the colour order OpenCV uses (BGR)
    camera.configure(camera.create_still_configuration(main={"size": (width, height), "format": "RGB888"}))
    camera.start()
    time.sleep(1)                             # let exposure and white balance settle


# ---------- Picture loop: register or check ----------
def register_step(recognizer, frame, faces, samples):
    # One registering picture. Returns the samples so far ([] once registering is over).
    name = state["register_name"]
    if len(faces) == 1:
        samples.append(embed(recognizer, frame, faces[0]))
    size = frame.shape[1] / 640                       # bigger text and lines on bigger pictures
    for face in faces:
        x, y, w, h = [int(v) for v in face[:4]]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 255), max(2, int(2 * size)))
    text = "Registering " + name + ": " + str(len(samples)) + "/" + str(SAMPLES)
    if len(faces) > 1:
        text += " - only one face, please"
    cv2.putText(frame, text, (10, int(30 * size)), cv2.FONT_HERSHEY_SIMPLEX, 0.7 * size, (0, 220, 255),
                max(2, int(2 * size)))

    with lock:
        state["register_count"] = len(samples)
        if len(samples) >= SAMPLES:
            new = np.array(samples, dtype=np.float32)
            known[name] = np.vstack([known[name], new]) if name in known else new   # registering again adds photos
            save_faces()
            state["message"] = "Saved " + name + " (" + str(len(known[name])) + " photos)."
            state["register_name"] = None
            return []
        if time.time() - state["register_started"] > REGISTER_SECONDS:
            state["message"] = "Registering timed out with " + str(len(samples)) + " photos - not saved. " \
                               "Only one face, well lit, close to the camera."
            state["register_name"] = None
            return []
    return samples


def check_step(recognizer, frame, faces):
    # One checking picture: name every face. Returns the list of (name, score).
    with lock:
        people = dict(known)
    size = frame.shape[1] / 640                       # bigger text and lines on bigger pictures
    results = []
    for face in faces:
        name, score = identify(embed(recognizer, frame, face), people)
        x, y, w, h = [int(v) for v in face[:4]]
        colour = (0, 200, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(frame, (x, y), (x + w, y + h), colour, max(2, int(2 * size)))
        cv2.putText(frame, name + " (" + format(score, ".2f") + ")", (x, max(y - int(10 * size), 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6 * size, colour, max(2, int(2 * size)))
        results.append((name, round(score, 2)))
    return results


def picture_loop(camera):
    global latest_jpeg
    with lock:
        state["message"] = "loading the face models..."
    detector, recognizer = load_models()
    with lock:
        state["message"] = "ready"
        state["ready"] = True
    samples = []
    resolution = settings["resolution"]
    while True:
        if settings["resolution"] != resolution:      # changed on the page
            resolution = settings["resolution"]
            camera.stop()
            start_camera(camera, resolution)
        frame = camera.capture_array()
        start = time.time()
        faces = find_faces(detector, frame)
        registering = state["register_name"] is not None

        if registering:
            samples = register_step(recognizer, frame, faces, samples)
            results = []
        else:
            results = check_step(recognizer, frame, faces)
        detect_ms = round((time.time() - start) * 1000)

        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with lock:
            latest_jpeg = jpeg.tobytes()
            if not registering:
                state["in_view"] = results
            state.update(taken_at=time.strftime("%H:%M:%S"), pictures=state["pictures"] + 1, detect_ms=detect_ms)
        time.sleep(SAMPLE_INTERVAL if registering else CHECK_INTERVAL)


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Face Recognition</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  h2 { font-size: 15px; margin: 18px 0 6px; border-top: 1px solid #eee; padding-top: 12px; }
  .wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  img { width: 720px; max-width: 100%; background: #000; border-radius: 6px; display: block; }
  .panel { background: #fff; border-radius: 8px; padding: 12px 16px; width: 300px; max-width: 100%; box-sizing: border-box;
           box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .small { color: #555; margin: 4px 0; font-size: 14px; }
  .stats { font-family: monospace; margin: 4px 0; font-size: 13px; }
  .who div { font-size: 18px; padding: 3px 0; }
  .unknown { color: #c62828; }
  input[type=text] { width: 100%; box-sizing: border-box; font-size: 15px; padding: 6px; }
  input[type=range] { width: 100%; }
  button { font-size: 14px; padding: 5px 10px; margin: 6px 4px 0 0; border: 1px solid #ccc; border-radius: 5px; background: #fff; cursor: pointer; }
  button:hover { background: #eee; }
  .person { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; border-bottom: 1px solid #f0f0f0; }
  .person button { margin: 0; }
</style></head>
<body>
<h1>Face Recognition</h1>
<div class="wrap">
  <img id="picture" alt="last picture">
  <div class="panel">
    <div class="small">In the last picture</div>
    <div class="who" id="who">-</div>
    <div class="stats" id="stats"></div>
    <div class="small" id="message"></div>

    <h2>Register</h2>
    <input type="text" id="name" placeholder="Name, e.g. Dr. Rao">
    <button onclick="register()">Register</button>
    <div class="small">Only that person in view, facing the camera. It takes 10 photos (a few seconds).</div>

    <h2>Registered people</h2>
    <div id="people"></div>

    <h2>Settings</h2>
    <label class="small">Resolution (faces need more pixels than bodies)</label>
    <select id="resolution" onchange="post('/set?resolution=' + this.value)" style="width:100%"></select>
    <label class="small">Threshold: <b id="threshold-val"></b> (higher = stricter)</label>
    <input type="range" id="threshold" min="0.2" max="0.6" step="0.01"
           oninput="document.getElementById('threshold-val').textContent = this.value"
           onchange="post('/set?threshold=' + this.value)">
  </div>
</div>
<script>
let lastPicture = 0;

async function post(url) {
  const r = await fetch(url, {method: "POST"});
  if (r.status === 409) alert(await r.text());
  refresh();
}

function register() {
  const name = document.getElementById("name").value.trim();
  if (!name) return alert("Type a name first");
  post("/register?name=" + encodeURIComponent(name));
  document.getElementById("name").value = "";
}

function remove(name) {
  if (confirm("Delete " + name + "?")) post("/delete?name=" + encodeURIComponent(name));
}

function escape(text) {
  return text.replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
}

async function refresh(first) {
  try {
    const s = await (await fetch("/status.json")).json();
    document.getElementById("who").innerHTML = s.state.in_view.length
      ? s.state.in_view.map(([n, score]) => "<div class='" + (n === "Unknown" ? "unknown" : "") + "'>" +
                                            escape(n) + " (" + score.toFixed(2) + ")</div>").join("")
      : "<div class='small'>no face</div>";
    document.getElementById("stats").textContent =
      "Picture " + s.state.pictures + " at " + s.state.taken_at + ", " + s.state.detect_ms + " ms";
    document.getElementById("message").textContent = s.state.register_name
      ? "Registering " + s.state.register_name + ": " + s.state.register_count + " / 10"
      : s.state.message;
    document.getElementById("people").innerHTML = s.people.length
      ? s.people.map(([n, photos]) => "<div class='person'><span>" + escape(n) + " <span class='small'>(" + photos +
          " photos)</span></span><button data-name='" + escape(n) + "' onclick='remove(this.dataset.name)'>Delete</button></div>").join("")
      : "<div class='small'>Nobody yet.</div>";
    if (s.state.pictures !== lastPicture) {          // only load the picture when there is a new one
      lastPicture = s.state.pictures;
      document.getElementById("picture").src = "/latest.jpg?n=" + lastPicture;
    }
    if (first) {
      document.getElementById("resolution").innerHTML = s.resolutions.map(r =>
        "<option" + (r === s.settings.resolution ? " selected" : "") + ">" + r + "</option>").join("");
      document.getElementById("threshold").value = s.settings.threshold;
      document.getElementById("threshold-val").textContent = s.settings.threshold;
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
                people = [[name, len(vectors)] for name, vectors in sorted(known.items())]
                body = json.dumps({"settings": settings, "state": state, "people": people, "resolutions": RESOLUTIONS})
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
        name = query.get("name", [""])[0].strip()[:60]
        with lock:
            if url.path == "/register" and not state["ready"]:
                return self.send(b"still loading the face models", "text/plain", 409)
            if url.path == "/register" and name:
                state.update(register_name=name, register_count=0, register_started=time.time())
                state["message"] = "Registering " + name + "..."
            elif url.path == "/delete" and name in known:
                del known[name]
                save_faces()
                state["message"] = "Deleted " + name + "."
            elif url.path == "/set" and query.get("threshold", [""])[0].replace(".", "", 1).isdigit():
                settings["threshold"] = min(max(float(query["threshold"][0]), 0.1), 0.9)
            elif url.path == "/set" and query.get("resolution", [""])[0] in RESOLUTIONS:
                settings["resolution"] = query["resolution"][0]
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
    if not hasattr(cv2, "FaceDetectorYN"):
        sys.exit("This OpenCV (" + cv2.__version__ + ") is too old. Need 4.5.4 or newer.")
    if not Picamera2.global_camera_info():
        sys.exit("No camera found - check the ribbon cable")
    Picamera2.set_logging(logging.ERROR)
    try:
        camera = Picamera2()
    except Exception as error:
        sys.exit("Can't open the camera: " + str(error) + " - is smartcabin_pi.py still running?")
    start_camera(camera, settings["resolution"])

    threading.Thread(target=picture_loop, args=(camera,), daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("Face recognition page:")
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
