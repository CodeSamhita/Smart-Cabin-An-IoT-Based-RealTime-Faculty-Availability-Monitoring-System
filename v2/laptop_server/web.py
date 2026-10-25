# Smart Cabin laptop server - the web server: pages for browsers and JSON calls for pages and Pis.
# Every call answers {"ok": true/false, "message": "...", ...}. Every call is wrapped in try / except:
# a user mistake gives its message, anything else is logged with the full error and answered with
# "Server error: ..." so the page can show it.
#
#   public (no login) : /  /search  /api/people-status  /api/public  /api/person  /api/filters  /api/health
#   admin (login)     : /devices  /api/admin/...
#   devices (key)     : /api/device/...   (headers X-Device-Serial and X-Device-Key)

import http.server
import json
import mimetypes
import os
import ssl
import time
import traceback
import urllib.parse

import devices
import logbook
import people
import registrations
import security
import settings
import status
from security import UserError

# The pages are the user's design, in pages/ (Main.dc.html is the home page, served at / ). A page file is served
# at /<file> (or /<folder>/<file>), the same layout as on disk, so the pages' relative links work both through the
# server and when an HTML file is opened by itself.
HOME_PAGE = "Main.dc.html"
SHORT_ADDRESSES = {"/search": "/Search.dc.html", "/devices": "/Devices.dc.html", "/login": "/Login.dc.html"}
PAGE_FILE_TYPES = (".html", ".js", ".css")
# Scripts only from this server; inline styles and Google Fonts are allowed because the design uses them
SECURITY_POLICY = ("default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                   "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:")
ROUTES = {}          # (method, path) -> (function, who may call it: "public" / "admin" / "device")


def route(method, path, who="public"):
    def add(function):
        ROUTES[(method, path)] = (function, who)
        return function
    return add


def field(body, name, required=True):
    value = body.get(name, "")
    value = value.strip() if isinstance(value, str) else value
    if required and value in ("", None):
        raise UserError("Missing: " + name)
    return value


# ---------- public ----------
@route("GET", "/api/health")
def api_health(req, query, body):
    return {"message": "Server is running", "time": logbook.now_text()}


@route("GET", "/api/filters")
def api_filters(req, query, body):
    return people.filters()


@route("GET", "/api/public")
def api_public(req, query, body):
    return status.public_people(query.get("q", ""), query.get("school", ""), query.get("department", ""),
                                query.get("degree", ""))


@route("GET", "/api/people-status")
def api_people_status(req, query, body):
    return status.everyone()


@route("GET", "/api/person")
def api_person(req, query, body):
    return {"person": status.person_detail(field(query, "id"))}


# ---------- admin ----------
@route("GET", "/api/admin/me")
def api_me(req, query, body):
    return {"logged_in": bool(req.admin), "username": req.admin, "admin_exists": security.admin_exists(),
            "from_this_laptop": req.is_local()}


@route("POST", "/api/admin/create")
def api_create_admin(req, query, body):
    if not req.is_local():
        raise UserError("The admin account can only be made on the laptop itself (open https://localhost:"
                        + str(settings.PORT) + "/login there).")
    security.create_admin(field(body, "username"), field(body, "password"))
    logbook.event("admin", "admin account created")
    return {"message": "Admin account made. Now log in."}


@route("POST", "/api/admin/login")
def api_login(req, query, body):
    token = security.login(field(body, "username"), field(body, "password"))
    req.new_cookie = token
    logbook.event("admin", "logged in from " + req.client_address[0])
    return {"message": "Logged in"}


@route("POST", "/api/admin/logout", "admin")
def api_logout(req, query, body):
    security.logout(req.cookie())
    req.new_cookie = ""
    return {"message": "Logged out"}


@route("GET", "/api/admin/devices", "admin")
def api_devices(req, query, body):
    result = []
    for d in devices.all_devices():
        health = devices.health_of(d["device"])
        registration = registrations.current_for_device(d["device"])
        last = float(d["last_seen"] or 0)
        result.append({"device": d["device"], "serial": d["serial"], "model": d["model"], "location": d["location"],
                       "ip": d["ip"], "first_seen": d["first_seen"], "key_set": bool(d["key_hash"]),
                       "seconds_since_seen": int(time.time() - last) if last else None,
                       "online": bool(last) and time.time() - last <= settings.SILENT_SECONDS,
                       "person": registration["name"] if registration else "",
                       "person_id": registration["person_id"] if registration else "",
                       "temperature": health.get("temperature", ""), "cpu_percent": health.get("cpu_percent", ""),
                       "memory_free_mb": health.get("memory_free_mb", ""), "throttled": health.get("throttled", ""),
                       "parts": json.loads(health.get("parts") or "{}"), "last_error": health.get("last_error", ""),
                       "page_url": health.get("page_url", "")})
    return {"devices": result}


@route("POST", "/api/admin/location", "admin")
def api_location(req, query, body):
    device, location = field(body, "device"), field(body, "location")
    devices.set_location(device, location)
    registrations.update_location(device, " ".join(location.split()))
    return {"message": device + " is now at: " + location + ". The device gets it within a minute."}


@route("POST", "/api/admin/pin", "admin")
def api_pin(req, query, body):
    device = field(body, "device")
    if not devices.find(devices.all_devices(), "device", device):
        raise UserError("No device " + device)
    pin = security.make_pin(device)
    logbook.event("setup pin", "made for " + device, device)
    return {"message": "Setup PIN for " + device + ": " + pin + " (valid " + str(settings.PIN_MINUTES)
                       + " min, one use)", "pin": pin}


@route("POST", "/api/admin/reset-key", "admin")
def api_reset_key(req, query, body):
    devices.reset_key(field(body, "device"))
    return {"message": "Key reset. The device gets a new key at its next hello (within a minute)."}


@route("POST", "/api/admin/unregister", "admin")
def api_admin_unregister(req, query, body):
    removed = registrations.unregister(field(body, "device"))
    return {"message": (removed + " removed. The device forgets them at its next report.") if removed
            else "Nobody was registered there."}


@route("GET", "/api/admin/log", "admin")
def api_log(req, query, body):
    import csv_store
    return {"lines": logbook.recent(150), "events": csv_store.read("events_log.csv")[-60:]}


# ---------- devices ----------
def device_answer(row):
    registration = registrations.current_for_device(row["device"])
    person = None
    if registration:
        p = people.get(registration["person_id"]) or {}
        person = {"id": registration["person_id"], "name": registration["name"],
                  "designation": p.get("designation", "")}
    problem = setup_problem(row)
    return {"device": row["device"], "location": row["location"], "person": person,
            "setup_allowed": not problem, "setup_message": problem or "Setup allowed",
            "registered_at": registration["from_time"] if registration else ""}


@route("POST", "/api/device/hello")
def api_hello(req, query, body):
    row, new_key = devices.hello(req.headers.get("X-Device-Serial", ""), field(body, "model", False),
                                 req.client_address[0], req.headers.get("X-Device-Key", ""))
    devices.save_health(row["device"], body.get("health"), field(body, "page_url", False))
    answer = device_answer(row)
    answer["key"] = new_key
    answer["message"] = "Hello " + row["device"]
    return answer


@route("POST", "/api/device/report", "device")
def api_report(req, query, body):
    row = req.device
    devices.touch(row["device"], req.client_address[0])
    devices.save_health(row["device"], body.get("health"), field(body, "page_url", False))
    status.receive_report(row, body)
    answer = device_answer(row)
    answer["message"] = "Report saved"
    return answer


def setup_problem(device):
    # Why this device may not register a person right now, or "" if it may
    if not device["location"]:
        return "The admin has not set this device's location yet (Devices page on the server)."
    current = registrations.current_for_device(device["device"])
    if current:
        return current["name"] + " is already registered here. The admin must remove them first."
    return ""


@route("POST", "/api/device/setup-allowed", "device")
def api_setup_allowed(req, query, body):
    # Registration at the device is allowed while nobody is registered there and it has a location
    problem = setup_problem(req.device)
    return {"allowed": not problem, "message": problem or "Setup allowed", "location": req.device["location"]}


@route("GET", "/api/device/people", "device")
def api_device_people(req, query, body):
    # A copy of the people list for registration at the device (only the public columns)
    rows = people.all_people()
    return {"people": [{"id": p["id"], "name": p["name"], "designation": p["designation"], "role": p.get("role", ""),
                        "school": p["school"], "department": p["department"]} for p in rows],
            "message": str(len(rows)) + " people"}


@route("POST", "/api/device/register", "device")
def api_device_register(req, query, body):
    device = req.device
    problem = setup_problem(device)
    if problem:
        raise UserError(problem)
    person = registrations.register(device["device"], device["location"], field(body, "person_id"),
                                    field(body, "card_id", False), field(body, "face_photos", False) or 0)
    return {"message": person["name"] + " is registered at " + device["device"] + ".", "location": device["location"]}


@route("POST", "/api/device/credentials", "device")
def api_device_credentials(req, query, body):
    # The registered person added / deleted a face set or a card at the device
    card_ids = body.get("card_ids") if isinstance(body.get("card_ids"), list) else []
    registrations.update_credentials(req.device["device"], field(body, "person_id"), card_ids[:20],
                                     field(body, "face_photos", False) or 0)
    return {"message": "Saved on the server"}


@route("POST", "/api/device/unregister", "device")
def api_device_unregister(req, query, body):
    security.check_pin(req.device["device"], field(body, "pin"), use_it=True)
    removed = registrations.unregister(req.device["device"])
    return {"message": (removed + " removed from this device.") if removed else "Nobody was registered here."}


# ---------- the request handler ----------
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SmartCabin"
    sys_version = ""

    def log_message(self, form, *args):
        pass                                                   # our own logging below instead

    def is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def cookie(self):
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "session":
                return value
        return ""

    def send(self, code, data, content_type="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", SECURITY_POLICY)
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "new_cookie", None) is not None:
            age = settings.SESSION_HOURS * 3600 if self.new_cookie else 0
            self.send_header("Set-Cookie", "session=" + self.new_cookie + "; Path=/; HttpOnly; SameSite=Strict; Max-Age="
                             + str(age) + ("; Secure" if settings.USE_HTTPS else ""))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        with open(path, "rb") as f:
            data = f.read()
        kind = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if kind.startswith("text/") or kind.endswith("javascript"):
            kind += "; charset=utf-8"
        self.send(200, data, kind)

    def send_page_file(self, path):
        # /<file> or /<folder>/<file> from pages/: no hidden names, only page file types (no ../ tricks)
        parts = path.split("/")[1:]
        if (len(parts) in (1, 2) and all(p and not p.startswith(".") and p == os.path.basename(p) for p in parts)
                and parts[-1].endswith(PAGE_FILE_TYPES)):
            file = os.path.join(settings.PAGES_FOLDER, *parts)
            if os.path.isfile(file):
                return self.send_file(file)
        return self.send(404, {"ok": False, "message": "No page file " + path})

    def send_redirect(self, target):
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def handle_any(self, method):
        started = time.time()
        url = urllib.parse.urlparse(self.path)
        path = url.path.rstrip("/") or "/"
        try:
            if method == "GET" and path in ("/", "/" + HOME_PAGE):
                return self.send_file(os.path.join(settings.PAGES_FOLDER, HOME_PAGE))
            if method == "GET" and path in SHORT_ADDRESSES:
                return self.send_redirect(SHORT_ADDRESSES[path])
            if method == "GET" and (method, path) not in ROUTES and not path.startswith("/api/"):
                return self.send_page_file(path)
            if (method, path) not in ROUTES:
                return self.send(404, {"ok": False, "message": "No such page or call: " + method + " " + path})
            function, who = ROUTES[(method, path)]
            query = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            body = self.read_body() if method == "POST" else {}
            self.admin = security.session_user(self.cookie())
            self.device = None
            if who == "admin" and not self.admin:
                return self.send(401, {"ok": False, "message": "Please log in as admin first.", "login": True})
            if who == "device":
                self.device = devices.check_key(self.headers.get("X-Device-Serial"), self.headers.get("X-Device-Key"),
                                                self.client_address[0])
            answer = function(self, query, body) or {}
            answer.setdefault("ok", True)
            answer.setdefault("message", "Done")
            self.send(200, answer)
            if method == "POST" and not path.startswith("/api/device/report"):
                logbook.log.info("%s %s from %s -> ok (%d ms)", method, path, self.client_address[0],
                                 (time.time() - started) * 1000)
        except UserError as error:
            logbook.log.warning("%s %s from %s -> refused: %s", method, path, self.client_address[0], error)
            self.send(400, {"ok": False, "message": str(error)})
        except Exception as error:
            logbook.log.error("%s %s from %s -> SERVER ERROR\n%s", method, path, self.client_address[0],
                              traceback.format_exc())
            try:
                self.send(500, {"ok": False, "message": "Server error: " + type(error).__name__ + ": " + str(error)
                                + " (details in logs/server.log)"})
            except Exception:
                pass

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > settings.MAX_BODY_BYTES:
            raise UserError("Request too big.")
        if length == 0:
            return {}
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise UserError("The request was not valid JSON.")
        if not isinstance(data, dict):
            raise UserError("The request must be a JSON object.")
        return data


def start():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", settings.PORT), Handler)
    server.daemon_threads = True
    if settings.USE_HTTPS:
        security.make_certificate()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(settings.CERT_FILE, settings.KEY_FILE)
        server.socket = context.wrap_socket(server.socket, server_side=True)
    return server
