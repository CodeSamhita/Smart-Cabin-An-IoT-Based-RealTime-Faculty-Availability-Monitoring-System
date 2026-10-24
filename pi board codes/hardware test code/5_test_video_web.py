# Pi Camera live video on a web page, with controls - bare code.
# Run:  python3 5_test_video_web.py      then open the address it prints (port 8081)
# Stop smartcabin_pi.py first: only one program can use the camera at a time.
#
# The video is MJPEG (a stream of JPEG pictures), made by the Pi's hardware encoder, so any browser shows it.
# Controls:
#   resolution, fps, bitrate, flip  -> the stream restarts with the new setting (about 1 s)
#   brightness, contrast, ...       -> change straight away
# The page also shows the real fps and Mbps of the stream.
#
# Library (once):  sudo apt install -y python3-picamera2

import io
import json
import logging
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from libcamera import Transform
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

PORT = 8081
RESOLUTIONS = ["320x240", "640x480", "1296x972"]   # the sizes used in this project (encoder can do up to 1920x1080)

# Defaults: the project's usual range is 30 - 40 fps at 10 - 15 Mbps
settings = {"resolution": "640x480", "fps": 30, "bitrate": 12, "hflip": 0, "vflip": 0,
            "Brightness": 0.0, "Contrast": 1.0, "Saturation": 1.0, "Sharpness": 1.0, "ExposureValue": 0.0}
RESTART_SETTINGS = ["resolution", "fps", "bitrate", "hflip", "vflip"]
LIVE_SETTINGS = ["Brightness", "Contrast", "Saturation", "Sharpness", "ExposureValue"]

stats = {"fps": 0, "mbps": 0}


# ---------- Camera -> stream ----------
class StreamOutput(io.BufferedIOBase):
    # The encoder writes each JPEG here; the web page readers wait for the next one
    def __init__(self):
        self.frame = None
        self.frames = 0
        self.bytes = 0
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.frames += 1
            self.bytes += len(buf)
            self.condition.notify_all()


output = StreamOutput()
camera = None
camera_lock = threading.Lock()


def start_stream():
    width, height = [int(n) for n in settings["resolution"].split("x")]
    frame_time = int(1e6 / settings["fps"])
    config = camera.create_video_configuration(
        main={"size": (width, height)},
        transform=Transform(hflip=settings["hflip"], vflip=settings["vflip"]),
        controls={"FrameDurationLimits": (frame_time, frame_time)})
    camera.configure(config)
    camera.start_recording(MJPEGEncoder(bitrate=settings["bitrate"] * 1000000), FileOutput(output))
    set_live_controls()


def restart_stream():
    with camera_lock:
        camera.stop_recording()
        start_stream()


def set_live_controls():
    controls = {name: settings[name] for name in LIVE_SETTINGS if name in camera.camera_controls}
    camera.set_controls(controls)


def measure_loop():
    # Every second: how many pictures and bytes came out of the encoder
    last_frames, last_bytes, last_time = 0, 0, time.time()
    while True:
        time.sleep(1)
        now = time.time()
        seconds = now - last_time
        stats["fps"] = round((output.frames - last_frames) / seconds, 1)
        stats["mbps"] = round((output.bytes - last_bytes) * 8 / seconds / 1e6, 2)
        last_frames, last_bytes, last_time = output.frames, output.bytes, now


def change_setting(name, value):
    if name not in settings:
        return "unknown setting"
    if name == "resolution":
        if value not in RESOLUTIONS:
            return "unknown resolution"
        settings[name] = value
    elif name in ("fps", "bitrate", "hflip", "vflip"):
        settings[name] = int(float(value))
    else:
        settings[name] = float(value)

    if name in RESTART_SETTINGS:
        restart_stream()
    else:
        set_live_controls()
    return "ok"


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pi Camera</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  .wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
  img { max-width: 100%; width: 800px; background: #000; border-radius: 6px; }
  .panel { background: #fff; border-radius: 8px; padding: 12px 16px; min-width: 260px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  label { display: block; margin: 10px 0 2px; font-size: 14px; }
  select, input[type=range] { width: 100%; }
  .stats { font-family: monospace; margin-bottom: 4px; }
  button { margin-top: 12px; }
</style></head>
<body>
<h1>Pi Camera</h1>
<div class="wrap">
  <img src="/stream.mjpg" alt="live video">
  <div class="panel">
    <div class="stats" id="stats">...</div>
    <div class="stats" id="model"></div>

    <label>Resolution</label>
    <select id="resolution" onchange="send(this.id, this.value)"></select>
    <label>FPS: <b id="fps-val"></b></label>
    <input type="range" id="fps" min="1" max="60" step="1" onchange="send(this.id, this.value)" oninput="show(this)">
    <label>Bitrate (Mbps): <b id="bitrate-val"></b></label>
    <input type="range" id="bitrate" min="1" max="25" step="1" onchange="send(this.id, this.value)" oninput="show(this)">
    <label><input type="checkbox" id="hflip" onchange="send(this.id, this.checked ? 1 : 0)"> Flip left-right</label>
    <label><input type="checkbox" id="vflip" onchange="send(this.id, this.checked ? 1 : 0)"> Flip upside down</label>

    <label>Brightness: <b id="Brightness-val"></b></label>
    <input type="range" id="Brightness" min="-1" max="1" step="0.1" oninput="show(this); send(this.id, this.value)">
    <label>Contrast: <b id="Contrast-val"></b></label>
    <input type="range" id="Contrast" min="0" max="4" step="0.1" oninput="show(this); send(this.id, this.value)">
    <label>Saturation: <b id="Saturation-val"></b></label>
    <input type="range" id="Saturation" min="0" max="4" step="0.1" oninput="show(this); send(this.id, this.value)">
    <label>Sharpness: <b id="Sharpness-val"></b></label>
    <input type="range" id="Sharpness" min="0" max="16" step="0.5" oninput="show(this); send(this.id, this.value)">
    <label>Exposure (EV): <b id="ExposureValue-val"></b></label>
    <input type="range" id="ExposureValue" min="-4" max="4" step="0.5" oninput="show(this); send(this.id, this.value)">
    <button onclick="reset()">Reset picture settings</button>
  </div>
</div>
<script>
const DEFAULTS = {Brightness: 0, Contrast: 1, Saturation: 1, Sharpness: 1, ExposureValue: 0};

function show(el) { document.getElementById(el.id + "-val").textContent = el.value; }

async function send(name, value) {
  await fetch("/set?name=" + name + "&value=" + value, {method: "POST"});
}

function reset() {
  for (const name in DEFAULTS) {
    const el = document.getElementById(name);
    el.value = DEFAULTS[name];
    show(el);
    send(name, DEFAULTS[name]);
  }
}

async function load() {
  // Put the Pi's current settings into the controls
  const s = await (await fetch("/status.json")).json();
  document.getElementById("resolution").innerHTML =
    s.resolutions.map(r => "<option" + (r === s.settings.resolution ? " selected" : "") + ">" + r + "</option>").join("");
  for (const name in s.settings) {
    const el = document.getElementById(name);
    if (!el || name === "resolution") continue;
    if (el.type === "checkbox") el.checked = s.settings[name] === 1;
    else { el.value = s.settings[name]; show(el); }
  }
  document.getElementById("model").textContent = "Camera: " + s.model;
}

async function refreshStats() {
  try {
    const s = await (await fetch("/status.json")).json();
    document.getElementById("stats").textContent = "Real: " + s.stats.fps + " fps, " + s.stats.mbps + " Mbps";
  } catch (e) {
    document.getElementById("stats").textContent = "Can't reach the Pi";
  }
}

load();
setInterval(refreshStats, 1000);
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
            body = {"settings": settings, "stats": stats, "resolutions": RESOLUTIONS,
                    "model": camera.camera_properties.get("Model", "?")}
            self.send(json.dumps(body).encode(), "application/json")
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
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                self.wfile.write(b"--FRAME\r\nContent-Type: image/jpeg\r\nContent-Length: " +
                                 str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass                                    # the browser tab was closed

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/set":
            return self.send(b"not found", "text/plain", 404)
        query = parse_qs(url.query)
        try:
            result = change_setting(query["name"][0], query["value"][0])
        except (KeyError, ValueError) as error:
            result = "bad request: " + str(error)
        self.send(result.encode(), "text/plain", 200 if result == "ok" else 400)

    def log_message(self, *args):
        pass                                        # keep the terminal quiet


def my_address():
    # The IP address other devices on the network use to reach this Pi
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                  # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def main():
    global camera
    if not Picamera2.global_camera_info():
        sys.exit("No camera found - check the ribbon cable")
    Picamera2.set_logging(logging.ERROR)
    try:
        camera = Picamera2()
    except Exception as error:
        sys.exit("Can't open the camera: " + str(error) + " - is smartcabin_pi.py still running?")

    start_stream()
    threading.Thread(target=measure_loop, daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("Camera page:")
    print("  http://" + my_address() + ":" + str(PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(PORT))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        camera.stop_recording()
        camera.close()


if __name__ == "__main__":
    main()
