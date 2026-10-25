# The setup page: page.html + /status.json (what to show) + /api/... (the buttons).
import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import config
import register
import shared
import storage


def status():
    users = storage.load_users()
    with shared.lock:
        d = shared.draft
        s = shared.state
        return {
            "sim": config.SIM, "pi_name": socket.gethostname(), "message": s["message"],
            "draft": {"active": d["active"], "name": d["name"], "step": d["step"],
                      "face_photos": len(d["face"]), "card": d["card"], "devices": d["devices"]},
            "face": {"ok": s["face_ok"], "text": s["face_text"], "capturing": s["face_capturing"]},
            "card": {"ok": s["card_ok"], "text": s["card_text"], "waiting": s["card_waiting"]},
            "phone": {"ok": s["phone_ok"], "text": s["phone_text"], "pairing": s["pairing"],
                      "seconds_left": max(0, round(s["pairing_until"] - time.time())),
                      "nearby": s["nearby"], "dropped": s["dropped"]},
            "samples": config.FACE_SAMPLES, "max_devices": config.MAX_DEVICES,
            "users": [{"user_id": u["user_id"], "name": u["name"], "card": u["card_uid"],
                       "face_photos": int(u["face_photos"] or 0), "registered": u["registered"],
                       "devices": [x["device_name"] for x in u["devices"]]} for u in users],
        }


def action(path, query):
    # /api/<name>?... -> the matching function in register.py
    value = lambda key: query.get(key, [""])[0]
    actions = {
        "/api/start": lambda: register.start(value("name")),
        "/api/next": lambda: register.next_step(skip=False),
        "/api/skip": lambda: register.next_step(skip=True),
        "/api/back": register.back,
        "/api/face": register.face_start,
        "/api/card": register.card_start,
        "/api/tap": register.sim_tap,
        "/api/phone": register.phone_start,
        "/api/pair": lambda: register.phone_pair(value("address").upper(), value("name")),
        "/api/unpair": lambda: register.phone_remove(value("address").upper()),
        "/api/save": register.save,
        "/api/cancel": register.cancel,
        "/api/delete": lambda: register.delete(value("user_id")),
    }
    if path not in actions:
        return False, "unknown action"
    return actions[path]()


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
            with open(os.path.join(config.FOLDER, "page.html"), "rb") as f:    # read each time: edits show at once
                self.send(f.read(), "text/html; charset=utf-8")
        elif path == "/status.json":
            self.send(json.dumps(status()).encode(), "application/json")
        elif path == "/latest.jpg":
            jpeg = shared.latest_jpeg
            if jpeg is None:
                self.send(b"no picture yet", "text/plain", 503)
            else:
                self.send(jpeg, "image/jpeg")
        else:
            self.send(b"not found", "text/plain", 404)

    def do_POST(self):
        url = urlparse(self.path)
        ok, text = action(url.path, parse_qs(url.query))
        self.send(text.encode(), "text/plain", 200 if ok else 400)

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


def serve():
    server = ThreadingHTTPServer(("", config.PORT), Handler)
    print("Setup page" + (" (simulation)" if config.SIM else "") + ":")
    print("  http://" + my_address() + ":" + str(config.PORT))
    print("  http://" + socket.gethostname() + ".local:" + str(config.PORT))
    server.serve_forever()
