# Smart Cabin - hardware test web page: Pi Camera, NeoPixel LEDs and RC522 RFID reader.
# Uses the same pins and libraries as smartcabin_pi.py, so if this passes, the main program will work too.
#
# Run:  sudo python3 test_hardware.py      then open http://<pi address>:8080 (the address is printed)
# sudo is needed for the LEDs. Stop smartcabin_pi.py first (it holds the camera and the LEDs).
# The first run installs any missing libraries by itself.
#
# The page shows:
#   Camera : live picture (one per second) and its brightness
#   LEDs   : buttons for each colour, a "test all" sequence and Off. The LEDs can't report back, so look at them.
#   RFID   : whether the reader answers (chip version), and every card tapped
#
# Wiring (GPIO numbers, physical pin in brackets):
#   RC522 : SDA -> GPIO8 (24)  SCK -> GPIO11 (23)  MOSI -> GPIO10 (19)  MISO -> GPIO9 (21)
#           RST -> GPIO25 (22) 3.3V -> 3.3V (1)    GND -> GND (6)       IRQ -> not used
#   LEDs  : DIN -> GPIO18 (12) 5V -> 5V (2)        GND -> GND (14)
#   Camera: ribbon cable, blue side facing the Ethernet / USB ports (Pi 4) or away from the board (Zero)

import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Same settings as smartcabin_pi.py
RFID_RST_PIN = 25
LED_PIN = 18                  # must be GPIO18 (the PWM pin)
LED_COUNT = 8
LED_BRIGHTNESS = 60           # 0 - 255
PORT = 8080                   # not 8000, so it never clashes with smartcabin_pi.py

COLORS = {"red": (255, 0, 0), "green": (0, 255, 0), "blue": (0, 0, 255), "white": (255, 255, 255), "off": (0, 0, 0)}


# ---------- Install anything that is missing ----------
def is_missing(module):
    try:
        __import__(module)
        return False
    except ImportError:
        return True


def install_missing_libraries():
    apt_names = []
    pip_names = []
    if is_missing("picamera2"):
        apt_names.append("python3-picamera2")
    if is_missing("RPi.GPIO"):
        apt_names.append("python3-rpi-lgpio")
    if is_missing("spidev"):
        apt_names.append("python3-spidev")
    if is_missing("mfrc522"):
        pip_names.append("mfrc522")
    if is_missing("rpi_ws281x"):
        pip_names.append("rpi_ws281x")
    if pip_names:
        apt_names += ["python3-pip", "python3-dev", "gcc"]    # needed to build the LED library

    if apt_names:
        print("Installing", " ".join(apt_names), "- this can take a few minutes...")
        subprocess.run(["sudo", "apt-get", "update"])
        subprocess.run(["sudo", "apt-get", "install", "-y"] + apt_names)
    if pip_names:
        # --no-deps: the GPIO and SPI libraries already came from apt above
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "--no-deps"] + pip_names)


# ---------- Shared state (read by the web page) ----------
lock = threading.Lock()
state = {
    "camera": {"status": "waiting", "text": "starting...", "brightness": None},
    "leds": {"status": "waiting", "text": "starting..."},
    "rfid": {"status": "waiting", "text": "starting...", "cards": []},
}


def set_part(part, status, text):
    # status is "ok", "error" or "waiting"
    with lock:
        state[part]["status"] = status
        state[part]["text"] = text


# ---------- 1. Camera ----------
camera = None
camera_lock = threading.Lock()     # only one web request uses the camera at a time


def open_camera():
    global camera
    from picamera2 import Picamera2
    if not Picamera2.global_camera_info():
        raise RuntimeError("no camera found - check the ribbon cable (blue side) and both clips")
    camera = Picamera2()
    camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
    camera.start()
    time.sleep(1)                                     # let the exposure settle


def close_camera():
    global camera
    try:
        camera.close()
    except Exception:
        pass
    camera = None


def take_photo():
    # Returns the picture as JPEG bytes, or None if the camera doesn't work
    with camera_lock:
        try:
            if camera is None:
                open_camera()
            image = camera.capture_image("main").convert("RGB")
        except Exception as error:
            message = str(error)
            if "busy" in message.lower() or "acquire" in message.lower():
                message += " - is smartcabin_pi.py still running? Stop it first."
            set_part("camera", "error", message)
            close_camera()
            return None

    gray = image.convert("L")
    brightness = round(sum(gray.getdata()) / (gray.width * gray.height))    # 0 = black, 255 = white
    with lock:
        state["camera"]["brightness"] = brightness
    if brightness < 10:
        set_part("camera", "error", "picture is almost black - lens cap on, or the room is dark")
    else:
        set_part("camera", "ok", "working, " + str(image.width) + " x " + str(image.height))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()


# ---------- 2. NeoPixel LEDs ----------
leds = None
led_lock = threading.Lock()


def start_leds():
    global leds
    if os.geteuid() != 0:
        set_part("leds", "error", "need sudo - run: sudo python3 test_hardware.py")
        return
    try:
        from rpi_ws281x import PixelStrip
        leds = PixelStrip(LED_COUNT, LED_PIN, 800000, 10, False, LED_BRIGHTNESS)
        leds.begin()
        show_all(COLORS["off"])
        set_part("leds", "ok", "ready - press a colour and look at the LEDs")
    except Exception as error:
        set_part("leds", "error", "LED library can't start: " + str(error))


def show_all(color):
    for i in range(LED_COUNT):
        leds.setPixelColorRGB(i, color[0], color[1], color[2])
    leds.show()


def led_colour(name):
    with led_lock:
        show_all(COLORS[name])
    set_part("leds", "ok", "showing " + name)


def led_test_sequence():
    # Each colour on all LEDs, then one LED at a time, so you can see that every LED works
    with led_lock:
        for name in ["red", "green", "blue", "white"]:
            set_part("leds", "ok", "test: all LEDs " + name)
            show_all(COLORS[name])
            time.sleep(1.5)
        for i in range(LED_COUNT):
            set_part("leds", "ok", "test: LED " + str(i + 1) + " of " + str(LED_COUNT))
            show_all(COLORS["off"])
            leds.setPixelColorRGB(i, 0, 150, 255)
            leds.show()
            time.sleep(0.4)
        show_all(COLORS["off"])
    set_part("leds", "ok", "test done - did every colour and every LED light up?")


# ---------- 3. RC522 RFID reader ----------
def read_card(reader):
    # Returns the card id like "A1B2C3D4", or None if no card is on the reader
    status, tag_type = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return None
    status, uid = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return None
    return "".join(format(b, "02X") for b in uid[:4])


def rfid_loop():
    if not os.path.exists("/dev/spidev0.0"):
        subprocess.run(["sudo", "raspi-config", "nonint", "do_spi", "0"])    # turn SPI on
        set_part("rfid", "error", "SPI was off, now turned on - reboot the Pi (sudo reboot) and run this again")
        return
    try:
        import RPi.GPIO as GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)                        # so RFID_RST_PIN means GPIO25, as in smartcabin_pi.py
        from mfrc522 import MFRC522
        reader = MFRC522(pin_rst=RFID_RST_PIN)
    except Exception as error:
        set_part("rfid", "error", "library problem: " + str(error))
        return

    connected = False
    last_check = 0.0
    last_card, last_time = None, 0.0
    while True:
        # Every 2 s: the RC522 has a version number inside. If we can't read it, the reader is not connected.
        if time.time() - last_check > 2:
            last_check = time.time()
            version = reader.Read_MFRC522(0x37)
            if version in (0x00, 0xFF):
                connected = False
                set_part("rfid", "error", "not responding - check SDA, SCK, MOSI, MISO, 3.3V, GND "
                                          "and that no solder joins two pins")
            else:
                if not connected:
                    reader.MFRC522_Init()             # it came (back), so set it up again
                    connected = True
                with lock:
                    no_cards = not state["rfid"]["cards"]
                set_part("rfid", "ok", "connected, chip version " + hex(version) +
                         (" - tap a card" if no_cards else ""))

        if connected:
            card = read_card(reader)
            if card and (card != last_card or time.time() - last_time > 3):    # one tap counts once
                with lock:
                    state["rfid"]["cards"].insert(0, {"id": card, "time": time.strftime("%H:%M:%S")})
                    del state["rfid"]["cards"][20:]   # keep the last 20
            if card:
                last_card, last_time = card, time.time()
        time.sleep(0.1)


# ---------- Web page ----------
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Cabin - Hardware Test</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #f4f5f7; color: #222; }
  h1 { font-size: 22px; margin: 0 0 16px; }
  .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
  .card { background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
  .card h2 { font-size: 18px; margin: 0 0 8px; display: flex; justify-content: space-between; align-items: center; }
  .badge { font-size: 13px; padding: 3px 10px; border-radius: 20px; color: #fff; background: #888; }
  .ok { background: #1a8f3c; } .error { background: #c62828; } .waiting { background: #888; }
  .text { margin: 0 0 12px; color: #555; min-height: 20px; }
  img { display: block; width: 100%; border-radius: 6px; background: #ddd; aspect-ratio: 4 / 3; object-fit: cover; }
  button { font-size: 15px; padding: 8px 14px; margin: 0 6px 8px 0; border: 1px solid #ccc; border-radius: 6px;
           background: #fff; cursor: pointer; }
  button:hover { background: #eee; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  table { width: 100%; border-collapse: collapse; }
  td { padding: 6px 4px; border-bottom: 1px solid #eee; font-family: monospace; font-size: 15px; }
  .empty { color: #999; }
</style></head>
<body>
<h1>Smart Cabin - Hardware Test</h1>
<div class="grid">
  <div class="card">
    <h2>Pi Camera <span id="camera-badge" class="badge">...</span></h2>
    <p class="text" id="camera-text"></p>
    <img id="photo" alt="camera picture">
    <p class="text">Brightness: <b id="brightness">-</b> (0 - 255) &nbsp;
      <button id="pause" onclick="togglePause()">Pause</button></p>
  </div>
  <div class="card">
    <h2>NeoPixel LEDs <span id="leds-badge" class="badge">...</span></h2>
    <p class="text" id="leds-text"></p>
    <button onclick="led('red')"><span class="dot" style="background:#e00"></span>Red</button>
    <button onclick="led('green')"><span class="dot" style="background:#0b0"></span>Green</button>
    <button onclick="led('blue')"><span class="dot" style="background:#00e"></span>Blue</button>
    <button onclick="led('white')"><span class="dot" style="background:#fff;border:1px solid #aaa"></span>White</button>
    <br><button onclick="led('test')">Test all</button><button onclick="led('off')">Off</button>
    <p class="text">The LEDs can't report back - look at them. If nothing lights: DIN on GPIO18 (pin 12),
      5V, GND, and the arrow on the strip must point away from the Pi.</p>
  </div>
  <div class="card">
    <h2>RFID reader <span id="rfid-badge" class="badge">...</span></h2>
    <p class="text" id="rfid-text"></p>
    <table id="cards"></table>
    <p class="text">The RC522 only reads 13.56 MHz cards. Hold the card flat on the reader for a second.</p>
  </div>
</div>
<script>
let paused = false;

function showPart(part, info) {
  const badge = document.getElementById(part + "-badge");
  badge.className = "badge " + info.status;
  badge.textContent = info.status === "ok" ? "OK" : info.status === "error" ? "PROBLEM" : "WAIT";
  document.getElementById(part + "-text").textContent = info.text;
}

async function refreshStatus() {
  try {
    const s = await (await fetch("/status.json")).json();
    showPart("camera", s.camera);
    showPart("leds", s.leds);
    showPart("rfid", s.rfid);
    document.getElementById("brightness").textContent = s.camera.brightness ?? "-";
    const table = document.getElementById("cards");
    table.innerHTML = s.rfid.cards.length
      ? s.rfid.cards.map(c => "<tr><td>" + c.id + "</td><td>" + c.time + "</td></tr>").join("")
      : "<tr><td class='empty'>No card tapped yet</td></tr>";
  } catch (e) {
    for (const part of ["camera", "leds", "rfid"])
      showPart(part, {status: "error", text: "can't reach the Pi - is test_hardware.py still running?"});
  }
}

function nextPhoto() {
  if (paused) return setTimeout(nextPhoto, 500);
  const img = document.getElementById("photo");
  img.onload = img.onerror = () => setTimeout(nextPhoto, 1000);   // ask for the next picture once this one arrived
  img.src = "/photo.jpg?t=" + Date.now();
}

function togglePause() {
  paused = !paused;
  document.getElementById("pause").textContent = paused ? "Resume" : "Pause";
}

async function led(name) {
  await fetch("/led?do=" + name, {method: "POST"});
  refreshStatus();
}

refreshStatus();
setInterval(refreshStatus, 1000);
nextPhoto();
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
        path = self.path.split("?")[0]
        if path == "/":
            self.send(PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/status.json":
            with lock:
                body = json.dumps(state)
            self.send(body.encode(), "application/json")
        elif path == "/photo.jpg":
            photo = take_photo()
            if photo is None:
                self.send(b"camera not working", "text/plain", 503)
            else:
                self.send(photo, "image/jpeg")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        if not self.path.startswith("/led?do="):
            return self.send(b"not found", "text/plain", 404)
        action = self.path.split("=", 1)[1]
        if leds is None:
            return self.send(b"LEDs not working", "text/plain", 503)
        if action == "test":
            threading.Thread(target=led_test_sequence, daemon=True).start()
        elif action in COLORS:
            threading.Thread(target=led_colour, args=(action,), daemon=True).start()
        else:
            return self.send(b"unknown colour", "text/plain", 400)
        self.send(b"ok", "text/plain")

    def log_message(self, *args):
        pass                                          # keep the terminal quiet


def my_address():
    # The IP address other devices on the network use to reach this Pi
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                    # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


# ---------- Main ----------
def main():
    install_missing_libraries()
    start_leds()
    threading.Thread(target=rfid_loop, daemon=True).start()

    server = ThreadingHTTPServer(("", PORT), Handler)
    print("Hardware test page:")
    print("  http://" + my_address() + ":" + str(PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(PORT))
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if leds is not None:
            show_all(COLORS["off"])
        if camera is not None:
            close_camera()


if __name__ == "__main__":
    main()
