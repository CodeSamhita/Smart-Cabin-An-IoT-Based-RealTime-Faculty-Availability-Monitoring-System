# Smart Cabin cabin device - its own small setup page (Python's built-in web server, port 8000).
# Open it from a phone or laptop on the same Wi-Fi: http://<pi address>:8000
# The camera picture is shown only to the logged-in owner during setup, and never leaves this device otherwise.

import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import actions
import config
import faces
import leds
import pairing
import presence
import server_link
import shared

PAGE_FILE = os.path.join(config.FOLDER, "page.html")


def status(token):
    with shared.lock:
        s = shared.state
        data = {"connected": s["connected"], "server_ok": s["server_ok"], "server": server_link.server_url(),
                "cabin": s["cabin"], "owner": s["owner"], "status": s["status"], "reason": s["reason"],
                "until": s["until"], "led": leds.current, "faculty_in": s["faculty_in"], "headcount": presence.headcount(),
                "phone_near": s["phone_near"], "message": s["message"], "sensors": s["sensors"],
                "simulate": config.SIMULATE, "logged_in": actions.logged_in(token), "enrol_name": s["enrol_name"],
                "enrol_left": max(0, round(s["enrol_until"] - time.time())), "register_face": s["register_face"],
                "face_progress": s["face_progress"], "face_samples": config.FACE_SAMPLES, "link_card": s["link_card"],
                "pairing": s["pairing"], "nearby": s["nearby"], "last_card": s["last_card"]}
    data["face_photos"] = faces.photo_count()
    data["pin"] = pairing.PIN                          # shown while waiting for the admin to add this device
    data["device_name"] = socket.gethostname()
    data["device_id"] = pairing.device_id()            # the ID the admin can link to a cabin
    with shared.lock:
        data["pairing_server"] = shared.state["pairing_server"]
    return data


class Handler(BaseHTTPRequestHandler):
    def send(self, body, content_type="application/json", code=200, cookie=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        if cookie is not None:
            self.send_header("Set-Cookie", "pi_page=" + cookie + "; HttpOnly; SameSite=Strict; Path=/")
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

    def token(self):
        for part in self.headers.get("Cookie", "").split(";"):
            if part.strip().startswith("pi_page="):
                return part.strip()[len("pi_page="):]
        return ""

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            with open(PAGE_FILE, "rb") as f:
                self.send(f.read(), "text/html; charset=utf-8")
        elif path == "/status.json":
            self.send(status(self.token()))
        elif path == "/picture.jpg":
            with shared.lock:
                jpeg = shared.state["last_jpeg"]
            if not actions.logged_in(self.token()) or jpeg is None:
                self.send({"detail": "log in to see the camera"}, code=403)
            else:
                self.send(jpeg, "image/jpeg")
        else:
            self.send({"detail": "not found"}, code=404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            data = {}
        path = self.path.split("?")[0]
        token = self.token()

        # Allowed without the setup login
        if path == "/api/connect":
            return self.answer(*actions.connect(str(data.get("code", "")), str(data.get("server", ""))))
        if path == "/api/login":
            ok, message, new_token = actions.login(str(data.get("username", "")), str(data.get("password", "")))
            return self.send({"ok": ok, "message": message}, code=200 if ok else 400, cookie=new_token if ok else None)
        if config.SIMULATE and path == "/api/sim/card":
            actions.card_tapped(str(data.get("uid", "")).upper())
            return self.answer(True, "Simulated tap.")
        if config.SIMULATE and path == "/api/sim/phone":
            return self.answer(*actions.sim_phone(bool(data.get("near"))))

        # Everything else needs the setup login
        if not actions.logged_in(token):
            return self.send({"ok": False, "message": "Log in first."}, code=403)
        routes = {
            "/api/logout": lambda: actions.logout(),
            "/api/face/start": lambda: actions.start_face(),
            "/api/face/delete": lambda: actions.delete_face(),
            "/api/card/link": lambda: actions.start_card_link(),
            "/api/phone/pair": lambda: actions.start_pairing(),
            "/api/phone/pair-device": lambda: actions.pair_device(str(data.get("address", "")), str(data.get("name", ""))),
            "/api/zones/from-picture": lambda: actions.zones_from_picture(),
            "/api/zones/clear": lambda: actions.clear_zones(),
            "/api/button": lambda: actions.press_button(str(data.get("name", ""))),
        }
        if path not in routes:
            return self.send({"ok": False, "message": "not found"}, code=404)
        self.answer(*routes[path]())

    def answer(self, ok, message):
        self.send({"ok": ok, "message": message}, code=200 if ok else 400)

    def log_message(self, *args):
        pass                                             # keep the terminal quiet


def my_address():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))                       # nothing is sent, this only picks the network
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


def serve():
    server = ThreadingHTTPServer(("", config.PAGE_PORT), Handler)
    print("Cabin device page:  http://" + my_address() + ":" + str(config.PAGE_PORT) +
          "   or  http://" + socket.gethostname() + ".local:" + str(config.PAGE_PORT))
    server.serve_forever()
