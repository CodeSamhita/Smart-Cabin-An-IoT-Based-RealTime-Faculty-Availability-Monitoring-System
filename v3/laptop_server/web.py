# Smart Cabin laptop server - the web server: pages for browsers and JSON calls for pages and Pis.
# Every call answers {"ok": true/false, "message": "...", ...}. Every call is wrapped in try / except:
# a user mistake gives its message, anything else is logged with the full error and answered with
# "Server error: ..." so the page can show it.
#
#   public (no login) : /  /search  /api/people-status  /api/public  /api/person  /api/filters  /api/health
#                       /api/login  /api/logout  /api/me
#   admin (login)     : /devices  /api/admin/...
#   faculty (login)   : /faculty  /api/faculty/...
#   devices (key)     : /api/device/...   (headers X-Device-Serial and X-Device-Key)

import http.server
import json
import mimetypes
import os
import ssl
import time
import traceback
import urllib.parse

import csv_store
import devices
import faculty
import logbook
import people
import registrations
import security
import settings
import setup_requests
import status
import timetables
from security import UserError

# The pages are the user's design, in pages/ (Main.dc.html is the home page, served at / ). A page file is served
# at /<file> (or /<folder>/<file>), the same layout as on disk, so the pages' relative links work both through the
# server and when an HTML file is opened by itself.
HOME_PAGE = "Main.dc.html"
SHORT_ADDRESSES = {"/search": "/Search.dc.html", "/devices": "/Devices.dc.html", "/login": "/Login.dc.html",
                   "/faculty": "/Faculty.dc.html", "/logins": "/AdminLogins.dc.html"}
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


# ---------- one login for the admin and faculty ----------
@route("POST", "/api/login")
def api_login_any(req, query, body):
    # One box: the admin's username, or a faculty member's username, server id or ID card number
    name, password = field(body, "username"), field(body, "password")
    if security.is_admin_name(name):
        req.new_cookie = security.login(name, password)
        logbook.event("admin", "logged in from " + req.client_address[0])
        return {"message": "Logged in", "role": "admin", "must_change": False}
    token, must_change = faculty.login(name, password)
    req.new_faculty_cookie = token
    return {"message": "Logged in", "role": "faculty", "must_change": must_change}


@route("POST", "/api/logout")
def api_logout_any(req, query, body):
    if req.admin:
        security.logout(req.cookie())
        req.new_cookie = ""
    if req.faculty:
        faculty.logout(req.cookie("faculty"))
        req.new_faculty_cookie = ""
    return {"message": "Logged out"}


@route("GET", "/api/me")
def api_me_any(req, query, body):
    account = faculty.account_of(req.faculty) if req.faculty else None
    return {"role": "admin" if req.admin else "faculty" if req.faculty else "",
            "username": req.admin or (account["username"] if account else ""), "person_id": req.faculty,
            "must_change": bool(account and account["must_change"] == "yes"),
            "admin_exists": security.admin_exists(), "from_this_laptop": req.is_local()}


# ---------- one faculty member's page (their own, or the admin's view of them) ----------
def person_page(person_id, for_admin):
    person = people.get(person_id)
    if person is None:
        raise UserError("No such person.")
    registration = registrations.current_for_person(person_id)
    result = status.status_for(person, registration, csv_store.read("status_now.csv"), devices.all_devices())
    result.update(role=person.get("role", ""), day=time.strftime("%A"),
                  periods={str(n): list(t) for n, t in settings.PERIODS.items()}, breaks=[list(b) for b in settings.BREAKS],
                  days=list(settings.DAYS), timetables=timetables.of_person(person_id))
    account = faculty.account_of(person_id)
    result["account"] = {"username": account["username"] if account else "",
                         "id_card_number": account["id_card_number"] if account else "",
                         "state": faculty.login_state(account)}
    result["registration"] = None
    if registration:
        device = devices.find(devices.all_devices(), "device", registration["device"]) or {}
        health = devices.health_of(registration["device"])
        details, person_data = devices.details_of(registration["device"])
        now = next((r for r in csv_store.read("status_now.csv") if r["person_id"] == person_id), {})
        last = float(device.get("last_seen") or 0)
        result["registration"] = {
            "device": registration["device"], "location": registration["location"], "from_time": registration["from_time"],
            "face_photos": registration["face_photos"], "cards": len([c for c in registration["card_hash"].split(";") if c]),
            "model": device.get("model", ""), "ip": device.get("ip", ""), "page_url": health.get("page_url", ""),
            "online": bool(last) and time.time() - last <= settings.SILENT_SECONDS,
            "seconds_since_seen": int(time.time() - last) if last else None,
            "in_cabin": now.get("in_cabin", ""), "confidence": now.get("confidence", ""), "headcount": now.get("headcount", ""),
            "card_in": now.get("card", ""), "temperature": health.get("temperature", ""), "cpu_percent": health.get("cpu_percent", ""),
            "parts": json.loads(health.get("parts") or "{}"), "details": details, "person_data": person_data}
        if for_admin:
            result["registration"]["recent"] = [
                {"time": r.get("time", ""), "headcount": r.get("headcount", ""), "confidence": r.get("confidence", ""),
                 "temperature": r.get("temperature", "")} for r in status.recent_presence(registration["device"])]
    return result


@route("GET", "/api/faculty/home", "faculty")
def api_faculty_home(req, query, body):
    return {"person": person_page(req.faculty, False)}


@route("POST", "/api/faculty/deactivate", "faculty")
def api_faculty_deactivate(req, query, body):
    # The faculty member's own cabin device broke or is being replaced: deactivate it, then register at the new one
    registration = registrations.current_for_person(req.faculty)
    if not registration:
        raise UserError("You are not registered at any device.")
    person = people.get(req.faculty) or {"name": req.faculty}
    devices.deactivate(registration["device"], "by " + person["name"])
    return {"message": registration["device"] + " is deactivated. Register at your new device (open its page)."}


@route("POST", "/api/faculty/first-password", "faculty")
def api_first_password(req, query, body):
    faculty.set_password(req.faculty, "", field(body, "new"), field(body, "again"), first_login=True)
    return {"message": "Password saved."}


@route("POST", "/api/faculty/change-password", "faculty")
def api_change_password(req, query, body):
    faculty.set_password(req.faculty, field(body, "current"), field(body, "new"), field(body, "again"))
    return {"message": "Password changed."}


@route("POST", "/api/faculty/timetable/save", "faculty")
def api_timetable_save(req, query, body):
    timetables.save(req.faculty, field(body, "old_name", False), field(body, "name"), body.get("week"))
    return {"message": "Timetable saved.", "timetables": timetables.of_person(req.faculty)}


@route("POST", "/api/faculty/timetable/use", "faculty")
def api_timetable_use(req, query, body):
    name = field(body, "name")
    timetables.use(req.faculty, name)
    return {"message": "\"" + name + "\" is now in use.", "timetables": timetables.of_person(req.faculty)}


@route("POST", "/api/faculty/timetable/delete", "faculty")
def api_timetable_delete(req, query, body):
    name = field(body, "name")
    timetables.delete(req.faculty, name)
    return {"message": "\"" + name + "\" deleted.", "timetables": timetables.of_person(req.faculty)}


# ---------- admin ----------
@route("GET", "/api/admin/person", "admin")
def api_admin_person(req, query, body):
    return {"person": person_page(field(query, "id"), True)}


@route("POST", "/api/admin/person/ids", "admin")
def api_admin_person_ids(req, query, body):
    faculty.save_names(field(body, "person_id"), field(body, "username"), field(body, "id_card_number", False))
    return {"message": "Saved."}


@route("POST", "/api/admin/person/reset-password", "admin")
def api_admin_reset_password(req, query, body):
    person_id = field(body, "person_id")
    faculty.reset_to_default(person_id, field(body, "password"), field(body, "days", False) or 7)
    return {"message": "Back on a default password; they must change it at the next login."}


@route("GET", "/api/admin/logins", "admin")
def api_admin_logins(req, query, body):
    suggested = faculty.suggestions()
    accounts = {a["person_id"]: a for a in faculty.accounts()}
    rows = []
    for p in people.all_people():
        a = accounts.get(p["id"])
        rows.append({"id": p["id"], "name": p["name"], "school": p["school"],
                     "username": a["username"] if a else suggested[p["id"]],
                     "id_card_number": a["id_card_number"] if a else "", "state": faculty.login_state(a)})
    return {"rows": rows, "days": list(settings.DEFAULT_PASSWORD_DAYS)}


@route("POST", "/api/admin/logins/create", "admin")
def api_admin_logins_create(req, query, body):
    rows = body.get("rows") if isinstance(body.get("rows"), list) else []
    rows = [{"person_id": str(r.get("id", "")), "username": str(r.get("username", "")),
             "id_card_number": str(r.get("id_card_number", ""))} for r in rows if isinstance(r, dict)]
    if not rows:
        raise UserError("No people sent.")
    count = faculty.create_all(rows, field(body, "password"), field(body, "days"))
    return {"message": "Logins ready for %d faculty. Each sets their own password at the first login." % count}


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
                       "deactivated": d["deactivated"],
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


@route("POST", "/api/admin/deactivate", "admin")
def api_admin_deactivate(req, query, body):
    device = field(body, "device")
    removed = devices.deactivate(device, "by the admin")
    return {"message": device + " is deactivated" + (" and " + removed + " removed from it" if removed else "") + "."}


@route("POST", "/api/admin/reactivate", "admin")
def api_admin_reactivate(req, query, body):
    device = field(body, "device")
    devices.reactivate(device)
    return {"message": device + " is active again. It gets a new key at its next hello; register someone there."}


@route("POST", "/api/admin/unregister", "admin")
def api_admin_unregister(req, query, body):
    removed = registrations.unregister(field(body, "device"))
    return {"message": (removed + " removed. The device forgets them at its next report.") if removed
            else "Nobody was registered there."}


@route("GET", "/api/admin/requests", "admin")
def api_requests(req, query, body):
    # Registrations made at a device that wait for the admin
    rows = setup_requests.pending()
    return {"requests": [{"id": r["id"], "time": r["time"], "device": r["device"], "person_id": r["person_id"],
                          "name": r["name"], "cabin": r["cabin"], "face_photos": r["face_photos"],
                          "card": bool(r["card_hash"]), "reason": r["reason"]} for r in rows],
            "message": str(len(rows)) + " waiting"}


@route("POST", "/api/admin/requests/decide", "admin")
def api_requests_decide(req, query, body):
    return {"message": setup_requests.decide(field(body, "id"), bool(body.get("approve")))}


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
    request = None if registration else setup_requests.latest_for_device(row["device"])
    return {"device": row["device"], "location": row["location"], "person": person,
            "setup_allowed": not problem, "setup_message": problem or "Setup allowed",
            "registered_at": registration["from_time"] if registration else "",
            "request": {"person_id": request["person_id"], "state": request["state"], "reason": request["reason"]}
            if request else None}


@route("POST", "/api/device/hello")
def api_hello(req, query, body):
    row, new_key = devices.hello(req.headers.get("X-Device-Serial", ""), field(body, "model", False),
                                 req.client_address[0], req.headers.get("X-Device-Key", ""))
    devices.save_health(row["device"], body.get("health"), field(body, "page_url", False))
    devices.save_details(row["device"], body.get("details"), body.get("person_data"))
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
    # Why this device may not register a person right now, or "" if it may (no admin needed first: see setup_requests)
    current = registrations.current_for_device(device["device"])
    if current:
        return current["name"] + " is already registered here. The admin must remove them first."
    return ""


@route("POST", "/api/device/setup-allowed", "device")
def api_setup_allowed(req, query, body):
    # Registration at the device is allowed while nobody is registered there
    problem = setup_problem(req.device)
    return {"allowed": not problem, "message": problem or "Setup allowed", "location": req.device["location"]}


@route("GET", "/api/device/people", "device")
def api_device_people(req, query, body):
    # A copy of the people list for registration at the device (only the public columns)
    rows = people.all_people()
    return {"people": [{"id": p["id"], "name": p["name"], "designation": p["designation"], "role": p.get("role", ""),
                        "school": p["school"], "department": p["department"]} for p in rows],
            "message": str(len(rows)) + " people"}


@route("GET", "/api/device/where", "device")
def api_device_where(req, query, body):
    # Where a person picked at registration is registered now (for "Replace my old device"); public fields only
    registration = registrations.current_for_person(str(query.get("id", "")))
    if not registration or registration["device"] == req.device["device"]:
        return {"device": "", "location": ""}
    return {"device": registration["device"], "location": registration["location"]}


@route("POST", "/api/device/register", "device")
def api_device_register(req, query, body):
    # Registered at once when the faculty login proves who it is, else a request that waits for the admin
    state, message = setup_requests.submit(req.device, field(body, "person_id"), field(body, "card_id", False),
                                           field(body, "face_photos", False) or 0, field(body, "cabin", False),
                                           field(body, "login", False), body.get("password", ""),
                                           replace=bool(body.get("replace")))
    row = devices.find(devices.all_devices(), "device", req.device["device"])
    return {"state": state, "message": message, "location": row["location"] if row else ""}


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

    def cookie(self, wanted="session"):
        # "session" = the admin's login, "faculty" = a faculty member's login
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == wanted:
                return value
        return ""

    def cookie_header(self, name, value, hours):
        return (name + "=" + value + "; Path=/; HttpOnly; SameSite=Strict; Max-Age=" + str(hours * 3600 if value else 0)
                + ("; Secure" if settings.USE_HTTPS else ""))

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
            self.send_header("Set-Cookie", self.cookie_header("session", self.new_cookie, settings.SESSION_HOURS))
        if getattr(self, "new_faculty_cookie", None) is not None:
            self.send_header("Set-Cookie", self.cookie_header("faculty", self.new_faculty_cookie, settings.FACULTY_SESSION_HOURS))
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
            self.faculty = faculty.session_person(self.cookie("faculty"))
            self.device = None
            if who == "admin" and not self.admin:
                return self.send(401, {"ok": False, "message": "Please log in as admin first.", "login": True})
            if who == "faculty":
                if not self.faculty:
                    return self.send(401, {"ok": False, "message": "Please log in first.", "login": True})
                account = faculty.account_of(self.faculty)
                if account and account["must_change"] == "yes" and path != "/api/faculty/first-password":
                    return self.send(403, {"ok": False, "message": "Set your own password first.", "login": True})
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
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
            pass                    # the browser left (or stopped reading) before the answer was sent: nothing to do
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


class Server(http.server.ThreadingHTTPServer):
    # The secure handshake happens in each connection's own thread, with a time limit - not while accepting
    # connections - so one browser or Pi that connects and then says nothing can't freeze the server for everyone.
    daemon_threads = True
    context = None                  # the https settings, or None with --http
    allow_reuse_address = os.name != "nt"   # on Windows this would let a second server start on the same port, unnoticed

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


def start():
    server = Server(("0.0.0.0", settings.PORT), Handler)
    if settings.USE_HTTPS:
        security.make_certificate()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(settings.CERT_FILE, settings.KEY_FILE)
        server.context = context
    return server
