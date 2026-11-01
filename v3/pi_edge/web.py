# Smart Cabin edge device - this device's own page: https://<pi>:8000 (the user's designs in pages/).
#   PiDevice.dc.html   : the device's status (Simple / Advanced view), device details, parts (anyone on the network;
#                        no pictures, no card ids)
#   PiRegister.dc.html : registration (name, face, card, save), allowed by the server while nobody is registered here.
#                        The camera preview and the log are shown only to the browser that started it (session key).
# Every call answers {"ok": true/false, "message": "..."} and is wrapped in try / except.

import csv
import http.server
import json
import os
import ssl
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse

import details
import health
import person_data
import registration
import rfid
import server_link
import settings
import shared
from logbook import log, recent
from registration import PageError

PAGES = os.path.join(settings.FOLDER, "pages")      # the user's designs (PiDevice.dc.html, PiRegister.dc.html) + scripts
HOME_PAGE = "PiDevice.dc.html"
CERT = os.path.join(settings.DATA_FOLDER, "page_cert.pem")
KEY = os.path.join(settings.DATA_FOLDER, "page_key.pem")
LABELS = {"available": "Available", "meeting": "In a meeting", "not_available": "Not available"}
SECURITY_POLICY = ("default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                   "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:")


def person_extra(person_id):
    # School and department of the registered person, from the people list copied at registration
    try:
        with open(registration.PEOPLE_COPY, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["id"] == person_id:
                    return row
    except OSError:
        pass
    return {}


def state_for_page(token, with_details=False):
    s = shared.snapshot()
    person = s["person"]
    local = registration.local_person() or {}
    extra = person_extra(person["id"]) if person else {}
    view = registration.view(token)
    answer = {
        "device": s["device"] or "not numbered yet", "location": s["location"] or "",
        "server_ok": s["server_ok"], "server_message": s["server_message"], "server_url": server_link.current_url(),
        # Setup is open while nobody is registered here; the server is not needed for it (requests are sent later)
        "setup_allowed": not (local and registration.approval(local) == "approved") and not s["deactivated"],
        "deactivated": s["deactivated"],
        "setup_message": s["setup_message"], "registered_at": s["registered_at"],
        "approval": registration.approval(local) if local else "", "approval_name": local.get("name", ""),
        "person_id": person["id"] if person else "", "designation": person.get("designation", "") if person else "",
        "school": extra.get("school", ""), "department": extra.get("department", ""),
        "face_photos": registration.face_photo_count(local) if person else 0,
        "person_data": person_data.view() if person else None,
        "page_url": server_link.page_url(),
        "simulation": settings.SIMULATE, "computer": settings.COMPUTER,
        "camera_source": ("the test picture (--picture)" if settings.TEST_PICTURE_GIVEN else
                          "this computer's webcam, if it has one" if settings.USE_WEBCAM else "off (--no-webcam)"),
        "person": person["name"] if person else "", "status": s["status"], "status_label": LABELS.get(s["status"], s["status"]),
        "in_cabin": s["in_cabin"], "confidence": s["confidence"], "headcount": s["headcount"], "dark": s["dark"],
        "card_in": s["card_in"], "led": s["led"], "card_warning": s["card_warning"],
        "checking_seconds": max(0, int(s["checking_until"] - time.time())) if s["checking_until"] else 0,
        "face_recent": time.time() - s["face_seen_at"] < settings.FACE_RECENT_SECONDS,
        "vision_paused": s["vision_paused"], "picture_ms": s["picture_ms"],
        "last_picture": time.strftime("%H:%M:%S", time.localtime(s["last_picture_at"])) if s["last_picture_at"] else "none yet",
        "temperature": health.temperature(), "cpu_percent": health.cpu_percent(),
        "parts": s["parts"], "last_error": s["last_error"],
        "registration": view,
    }
    if view:
        answer["log"] = recent(40)
    if with_details:
        import wifi
        answer["wifi"] = wifi.view()
        answer["details"] = details.collect()
        for group in answer["details"]["groups"]:
            for row in group["rows"]:
                if row[0] == "IP address":
                    row[1] = server_link.my_address()
    return answer


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SmartCabinEdge"
    sys_version = ""

    def log_message(self, form, *args):
        pass

    def send(self, code, data, content_type="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", SECURITY_POLICY)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def handle_any(self, method):
        url = urllib.parse.urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        token = self.headers.get("X-Session", "") or query.get("t", "")
        try:
            if method == "GET" and path == "/":
                return self.send_page_file(HOME_PAGE)
            if method == "GET" and path.endswith((".html", ".js", ".css")) and path.count("/") == 1:
                return self.send_page_file(path[1:])                  # /<file> from pages/
            if method == "GET" and path == "/live.mjpg":          # the Advanced view's Live view: a picture stream
                import live
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return live.stream(self.wfile)                    # until the page closes (BrokenPipe, caught below)
            if method == "GET" and path == "/live.jpg":           # one live picture
                import live
                jpeg = live.frame_jpeg()
                if not jpeg:
                    return self.send(404, {"ok": False, "message": "no picture: the camera does not work (see Parts)"})
                return self.send(200, jpeg, "image/jpeg")
            if method == "GET" and path == "/preview.jpg":
                registration.check(token)
                if not registration.preview_jpeg:
                    return self.send(404, {"ok": False, "message": "no preview right now"})
                return self.send(200, registration.preview_jpeg, "image/jpeg")
            body = self.read_body() if method == "POST" else {}
            answer = self.route(method, path, body, token, query)
            if answer is None:
                return self.send(404, {"ok": False, "message": "No such call: " + method + " " + path})
            answer.setdefault("ok", True)
            answer.setdefault("message", "Done")
            self.send(200, answer)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass                                          # the browser left (or stopped reading) before the answer was sent
        except PageError as problem:
            self.send(400, {"ok": False, "message": str(problem)})
        except Exception as problem:
            log.error("page %s %s failed\n%s", method, path, traceback.format_exc())
            shared.error("page " + path, problem)
            try:
                self.send(500, {"ok": False, "message": "Device error: " + type(problem).__name__ + ": " + str(problem)
                                + " (details in logs/edge.log)"})
            except Exception:
                pass

    def route(self, method, path, body, token, query):
        call = server_link.call
        if (method, path) == ("GET", "/api/state"):
            return state_for_page(token, with_details=bool(query.get("details")))
        if (method, path) == ("POST", "/api/register/start"):
            new_token = registration.start(call)
            import identity
            return {"token": new_token, "message": "Registration started. Find your name.",
                    "expected": identity.boot_info()["person"]}           # from smartcabin.txt: shown first
        if (method, path) == ("GET", "/api/register/people"):
            people = registration.people_list(token)
            return {"people": people, "message": str(len(people)) + " people"}
        if (method, path) == ("POST", "/api/register/pick"):
            p = registration.pick(token, body.get("person_id", ""), call)
            return {"message": "Selected: " + p["name"] + ". Now register your face."}
        if (method, path) == ("POST", "/api/register/face"):
            registration.start_face(token)
            return {"message": "Taking photos: look at the camera."}
        if (method, path) == ("POST", "/api/register/card"):
            registration.start_card(token)
            return {"message": "Tap your card on the reader within %d s." % settings.CARD_WAIT_SECONDS}
        if (method, path) == ("POST", "/api/register/save"):
            state, message = registration.save(token, call, bool(body.get("replace")), body.get("update_note", ""))
            return {"state": state, "message": message}
        if (method, path) == ("POST", "/api/register/cancel"):
            registration.check(token)
            registration.end("cancelled on the page")
            return {"message": "Registration cancelled. Nothing was saved."}
        if (method, path) == ("POST", "/api/person/add-face"):
            person_data.add_face(call)
            return {"message": "Look at the camera: taking %d more photos." % settings.FACE_PHOTOS}
        if (method, path) == ("POST", "/api/person/add-card"):
            person_data.add_card()
            return {"message": "Hold the new card on the reader within %d s." % settings.CARD_WAIT_SECONDS}
        if (method, path) == ("POST", "/api/person/delete-face"):
            return {"message": person_data.delete_face(str(body.get("set_id", "")), call)}
        if (method, path) == ("POST", "/api/person/delete-card"):
            try:
                index = int(body.get("index", -1))
            except (TypeError, ValueError):
                raise PageError("No such card.")
            return {"message": person_data.delete_card(index, call)}
        if (method, path) == ("POST", "/api/wifi/add"):
            import wifi
            return {"message": wifi.add(body.get("ssid", ""), body.get("password", ""), body.get("username", ""))}
        if (method, path) == ("POST", "/api/wifi/remove"):
            import wifi
            return {"message": wifi.remove(str(body.get("name", "")))}
        if (method, path) == ("POST", "/api/person/stop"):
            person_data.stop()
            return {"message": "Cancelled."}
        if (method, path) == ("POST", "/api/sim/tap"):
            if not settings.SIMULATE:
                raise PageError("This device has a real card reader: tap the card on it.")
            card = str(body.get("card_id", "")).strip().upper()
            if not card:
                raise PageError("Type a card id, e.g. A1B2C3D4")
            rfid.sim_tap(card)
            return {"message": "Card " + card + " tapped (simulated)."}
        return None

    def send_page_file(self, name):
        # pages/<name>: no hidden names, no ../ tricks, only page file types
        name = urllib.parse.unquote(name)
        kind = {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}.get(os.path.splitext(name)[1])
        file = os.path.join(PAGES, name)
        safe = name and not name.startswith(".") and name == os.path.basename(name)
        if not kind or not safe or not os.path.isfile(file):
            return self.send(404, {"ok": False, "message": "No page file " + name})
        with open(file, "rb") as f:
            self.send(200, f.read(), kind + "; charset=utf-8")

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 16 * 1024:
            raise PageError("Request too big.")
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise PageError("The request was not valid JSON.")
        return data if isinstance(data, dict) else {}


def make_certificate():
    # A self-signed certificate for the page. True if one is there (HTTPS), False = plain HTTP.
    if os.path.exists(CERT) and os.path.exists(KEY):
        return True
    os.makedirs(settings.DATA_FOLDER, exist_ok=True)
    try:
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1825", "-subj",
                        "/CN=Smart Cabin device", "-keyout", KEY, "-out", CERT], check=True, capture_output=True, timeout=120)
        return True
    except (OSError, subprocess.SubprocessError):
        pass
    try:                                                          # a laptop without openssl: the cryptography library
        import datetime
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Smart Cabin device")])
        start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(start)
                .not_valid_after(start + datetime.timedelta(days=1825)).sign(key, hashes.SHA256()))
        with open(KEY, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                      serialization.NoEncryption()))
        with open(CERT, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        return True
    except Exception as problem:
        log.warning("no HTTPS for the page (no openssl, no cryptography): %s", problem)
        return False


class PageServer(http.server.ThreadingHTTPServer):
    # The secure handshake happens in each connection's own thread, with a time limit - not while accepting
    # connections - so one browser that connects and then says nothing can't freeze the page for everyone.
    daemon_threads = True
    context = None                  # the https settings, or None for a plain page

    def finish_request(self, request, client_address):
        if self.context is None:
            return super().finish_request(request, client_address)
        request.settimeout(HANDSHAKE_SECONDS)
        try:
            request = self.context.wrap_socket(request, server_side=True)
        except (ssl.SSLError, OSError):
            return                  # the browser gave up (e.g. at the certificate warning) or never answered
        try:
            super().finish_request(request, client_address)
        finally:
            request.close()


HANDSHAKE_SECONDS = 10


class ToHttps(http.server.BaseHTTPRequestHandler):
    # Port 80: anyone typing smartcabin.local (plain http) is sent on to the https page
    def do_GET(self):
        host = (self.headers.get("Host") or settings.HOSTNAME + ".local").split(":")[0]
        self.send_response(301)
        self.send_header("Location", "https://" + host + "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, form, *args):
        pass


def serve_also(port, handler, context):
    # The same page on a second port (in its own thread); a port that is taken is only logged
    try:
        extra = PageServer(("0.0.0.0", port), handler)
        extra.context = context
        threading.Thread(target=extra.serve_forever, name="page-" + str(port), daemon=True).start()
        return True
    except OSError as problem:
        log.warning("page not on port %d: %s", port, problem)
        return False


def serve():
    server = PageServer(("0.0.0.0", settings.PAGE_PORT), Handler)
    https = "--http" not in sys.argv and make_certificate()        # --http: plain page, only for troubleshooting
    context = None
    if https:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(CERT, KEY)
        server.context = context
    ports = str(settings.PAGE_PORT)
    if https and settings.ON_PI and not settings.SIMULATE:          # https://smartcabin.local without a port number
        if serve_also(443, Handler, context):
            ports += ", 443"
        if serve_also(80, ToHttps, None):
            ports += ", 80 (sends on to https)"
    shared.update(page_https=https)
    shared.set_part("page", True, ("https" if https else "http (no certificate)") + " on port " + ports)
    log.info("device page: %s", server_link.page_url())
    server.serve_forever()
