# Smart Cabin edge device - talking to the laptop server.
#   call()  : one HTTPS request with this device's serial and key. Never throws: returns (ok, answer).
#             The server's certificate is self-signed, so the device remembers its fingerprint the first
#             time and refuses any other certificate later (no one can pretend to be the server).
#   loop()  : thread. Says hello at the start and every HELLO_SECONDS ("who am I, where am I, who is
#             registered here?"), and sends a report every REPORT_SECONDS or straight after a change.
#   listen(): thread. Finds the server by itself: the server announces its address on UDP port 50505; while this
#             device can't reach the server, it switches to the announced address and remembers it.

import hashlib
import http.client
import json
import socket
import ssl
import sys
import time
import urllib.parse

import health
import identity
import registration
import settings
import shared
from logbook import log


DISCOVERY_PORT = 50505


def current_url():
    # The server address: given with --server (always wins), else the one heard / used last time, else settings.py
    if "--server" in sys.argv:
        return settings.SERVER_URL
    return identity.load().get("server_url") or settings.SERVER_URL


def listen():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", DISCOVERY_PORT))
    except OSError as problem:
        log.warning("can't listen for the server's announcement on port %d: %s", DISCOVERY_PORT, problem)
        return
    while True:
        try:
            data, sender = s.recvfrom(256)
            text = data.decode("utf-8", errors="replace").split()
            if len(text) != 2 or text[0] != "SMARTCABIN" or not text[1].startswith(("https://", "http://")):
                continue
            heard = text[1]
            if heard != current_url() and not shared.get("server_ok") and "--server" not in sys.argv:
                identity.save({"server_url": heard})
                log.info("found the server by its announcement: %s (from %s)", heard, sender[0])
                shared.changed.set()                              # try it straight away
        except Exception as problem:
            log.warning("server announcement: %s", problem)
            time.sleep(2)


def call(method, path, body=None):
    url = urllib.parse.urlparse(current_url())
    saved = identity.load()
    headers = {"Content-Type": "application/json", "X-Device-Serial": identity.serial(),
               "X-Device-Key": saved.get("key", "")}
    connection = None
    try:
        if url.scheme == "https":
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE          # self-signed: checked by fingerprint just below
            connection = http.client.HTTPSConnection(url.hostname, url.port or 443, timeout=settings.SERVER_TIMEOUT,
                                                     context=context)
            connection.connect()
            fingerprint = hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest()
            if not saved.get("server_fingerprint"):
                identity.save({"server_fingerprint": fingerprint})
                log.info("remembered the server's certificate %s...", fingerprint[:16])
            elif saved["server_fingerprint"] != fingerprint:
                return False, {"ok": False, "message": "The server's certificate changed, so this device refuses it "
                               "(someone may be pretending to be the server). If the laptop server was set up again, "
                               "delete 'server_fingerprint' from data/device.json on the Pi."}
        else:
            connection = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=settings.SERVER_TIMEOUT)
        connection.request(method, url.path.rstrip("/") + path,
                           body=json.dumps(body) if body is not None else None, headers=headers)
        answer = connection.getresponse()
        text = answer.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(text) if text else {}
        except ValueError:
            data = {"message": "the server answered HTTP " + str(answer.status) + " without JSON"}
        data.setdefault("ok", answer.status == 200)
        data.setdefault("message", "HTTP " + str(answer.status))
        return bool(data["ok"]), data
    except socket.timeout:
        return False, {"ok": False, "message": "the server did not answer in " + str(settings.SERVER_TIMEOUT) + " s"}
    except ConnectionRefusedError:
        return False, {"ok": False, "message": "the laptop is reachable but the server is not running"}
    except OSError as problem:
        return False, {"ok": False, "message": "cannot reach the server at " + current_url() + " (" + str(problem)
                       + "). Is the laptop's hotspot on and the server running?"}
    finally:
        if connection:
            connection.close()


def my_address():
    # This device's IP address as the server sees it (for the link to its page)
    try:
        url = urllib.parse.urlparse(current_url())
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((url.hostname, 9))                       # nothing is sent, it only picks the right network
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def page_url():
    return ("https" if shared.get("page_https") else "http") + "://" + my_address() + ":" + str(settings.PAGE_PORT)


def use_answer(answer):
    # The server tells us our number, location and who is registered here
    shared.update(device=answer.get("device", ""), location=answer.get("location", ""),
                  server_ok=True, server_message="connected", setup_allowed=bool(answer.get("setup_allowed")),
                  setup_message=answer.get("setup_message", ""), registered_at=answer.get("registered_at", ""))
    registration.sync_person(answer.get("person"))
    shared.set_part("server", True, "connected to " + current_url())


def hello():
    ok, answer = call("POST", "/api/device/hello", {"model": identity.model(), "health": health.report(),
                                                    "page_url": page_url()})
    if ok:
        if answer.get("key"):
            identity.save({"key": answer["key"], "device": answer["device"]})
            log.info("the server registered this device as %s and gave it a key", answer["device"])
        use_answer(answer)
    else:
        shared.update(server_ok=False, server_message=answer["message"])
        shared.set_part("server", False, answer["message"])
    return ok


def report():
    s = shared.snapshot()
    person = s["person"] or {}
    body = {"status": s["status"], "in_cabin": s["in_cabin"], "confidence": s["confidence"],
            "headcount": s["headcount"], "face": time.time() - s["face_seen_at"] < settings.FACE_RECENT_SECONDS,
            "card": s["card_in"], "dark": s["dark"], "person_id": person.get("id", ""),
            "face_age": int(min(86400, time.time() - s["face_seen_at"])),
            "health": health.report(), "page_url": page_url()}
    ok, answer = call("POST", "/api/device/report", body)
    if ok:
        use_answer(answer)
    else:
        shared.update(server_ok=False, server_message=answer["message"])
        shared.set_part("server", False, answer["message"])
        if "device key" in answer["message"].lower():
            hello()                                            # the server forgot us or reset our key
    return ok


def loop():
    last_hello = 0.0
    while True:
        try:
            if not identity.load().get("key") or time.time() - last_hello > settings.HELLO_SECONDS:
                if hello():
                    last_hello = time.time()
            else:
                report()
        except Exception as problem:
            shared.error("server link", problem)
        shared.changed.wait(settings.REPORT_SECONDS if shared.get("server_ok") else 10)
        shared.changed.clear()
