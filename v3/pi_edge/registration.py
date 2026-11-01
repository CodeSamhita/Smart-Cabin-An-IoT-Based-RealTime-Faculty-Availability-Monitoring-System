# Smart Cabin edge device - registering a person at this device, from their phone. No admin needed first.
# Steps on the page (PiRegister.dc.html): pick your name -> register face (10 photos) -> tap card -> confirm + send.
#   start()          : allowed while nobody is registered here; the people list is copied from the server
#                      (data/people_copy.csv), or the last copy is used when the server is out of reach
#   start_face()     : takes 10 photos with exactly one face in view (thread), shows progress
#   start_card()     : the next card tap (within 30 s) is the person's card
#   save()           : sends it with the faculty login: registered at once, or a request waiting for the admin.
#                      Server out of reach: kept on this device ("waiting") and sent later (without the password).
#                      The face and card are kept on this device in all three cases.
#   sync_person()    : the server says who is registered here (after an admin removal or a rejected request,
#                      the face is deleted)
#   send_waiting()   : sends a registration that was kept while the server was out of reach
# Only one registration at a time. It ends after REGISTRATION_MINUTES. The camera preview exists only during
# a registration and only for the phone that started it (its secret session key).

import csv
import json
import os
import secrets
import threading
import time
import urllib.parse

import buzzer
import camera
import face
import identity
import led
import settings
import shared
from logbook import log

PERSON_FILE = os.path.join(settings.DATA_FOLDER, "person.json")
PEOPLE_COPY = os.path.join(settings.DATA_FOLDER, "people_copy.csv")

lock = threading.RLock()
session = {}                  # the registration going on now (empty = none)
preview_jpeg = b""            # the newest preview picture, only during face registration
person_cache = None


class PageError(Exception):
    # A message for the person at the page (wrong PIN, no face found, ...)
    pass


# ---------- who is registered here ----------
def local_person():
    # The registered person: id, name, designation, face_sets [{id, added, photos}], cards [{uid, added}]
    global person_cache
    if person_cache is None:
        try:
            with open(PERSON_FILE) as f:
                person_cache = json.load(f)
        except (OSError, ValueError):
            person_cache = {}
        p = person_cache
        if p and "cards" not in p:                         # an older file: one card, one face set
            p["cards"] = [{"uid": p["card_id"], "added": p.get("registered", "")}] if p.get("card_id") else []
            p["face_sets"] = ([{"id": "set1", "added": p.get("registered", ""), "photos": p.get("face_photos", 0)}]
                              if p.get("face_photos") else [])
    return person_cache or None


def card_ids(person=None):
    person = person or local_person() or {}
    return [c["uid"] for c in person.get("cards", [])]


def face_photo_count(person=None):
    person = person or local_person() or {}
    return sum(s["photos"] for s in person.get("face_sets", []))


def write_person(person):
    global person_cache
    os.makedirs(settings.DATA_FOLDER, exist_ok=True)
    with open(PERSON_FILE + ".tmp", "w") as f:
        json.dump(person, f, indent=1)
    identity.replace_file(PERSON_FILE + ".tmp", PERSON_FILE)       # retries if Windows locks the file a moment
    if not settings.SIMULATE:
        os.chmod(PERSON_FILE, 0o600)
    person_cache = person


def forget_person(reason):
    global person_cache
    if os.path.exists(PERSON_FILE):
        os.remove(PERSON_FILE)
    face.forget()
    person_cache = {}
    shared.update(in_cabin=False, card_in=False)
    log.info("forgot the registered person: %s", reason)


def approval(person=None):
    # "approved" (registered on the server), "pending" (sent, the admin decides) or "waiting" (not sent yet)
    person = person or local_person() or {}
    return person.get("approval", "approved")             # files from before requests existed are approved


def sync_person(server_person, server_request=None):
    # The server's answer is the truth about who is registered at this device
    if session:
        return                                            # don't interfere with a registration going on
    local = local_person()
    if not server_person:
        if local and approval(local) != "approved":
            request = server_request or {}
            if request.get("person_id") == local.get("id") and request.get("state") == "rejected":
                forget_person("the admin rejected the registration request")
            else:
                if approval(local) == "pending" and request.get("person_id") != local.get("id"):
                    local["approval"] = "waiting"          # the server has no request from us: send it again
                    write_person(local)
                shared.update(person=None)
                shared.set_part("registration", True, local["name"] + ": " + (
                    "waiting for the admin's approval" if approval(local) == "pending"
                    else "saved here, sent when the server can be reached"))
                return
        elif local:
            forget_person("the server says nobody is registered here (removed by the admin?)")
        shared.update(person=None)
        shared.set_part("registration", True, "nobody registered yet - press Start registration on this device's page")
        return
    if local and approval(local) != "approved" and local.get("id") == server_person["id"]:
        local["approval"] = "approved"                     # the admin approved the request
        write_person(local)
        log.info("registration approved: %s", local["name"])
    if local and local.get("id") != server_person["id"]:
        forget_person("the server has someone else registered here")
        local = None
    shared.update(person=server_person)
    if not local:
        shared.set_part("registration", False, server_person["name"] + " is registered on the server, but this device "
                        "has no face or card for them (new SD card?). Register again here.")
    else:
        shared.set_part("registration", True, server_person["name"] + ": face photos " + str(face_photo_count(local))
                        + ", cards " + str(len(card_ids(local))))


# ---------- the registration session ----------
def check(token):
    with lock:
        if not session or not secrets.compare_digest(session["token"], str(token or "")):
            raise PageError("No registration going on from this browser. Start it again on the device page.")
        if time.time() - session["started"] > settings.REGISTRATION_MINUTES * 60:
            end("timed out")
            raise PageError("The registration took longer than %d minutes and was stopped. Start again."
                            % settings.REGISTRATION_MINUTES)


def start(server_call):
    # Allowed while nobody is registered at this device (a request still waiting may be replaced)
    local = local_person()
    if local and approval(local) == "approved":
        raise PageError(local["name"] + " is registered at this device. The admin must remove them first.")
    ok, answer = server_call("GET", "/api/device/people")
    if ok:
        with open(PEOPLE_COPY, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "name", "designation", "role", "school", "department"],
                                    extrasaction="ignore")
            writer.writeheader()
            writer.writerows(answer["people"])
    elif not answer.get("unreachable"):
        raise PageError(answer["message"])
    elif not os.path.exists(PEOPLE_COPY):
        raise PageError("The server can't be reached and this device has no copy of the people list yet. "
                        "Connect it to the server once (" + answer["message"] + ").")
    with lock:
        session.clear()
        session.update({"token": secrets.token_urlsafe(24), "started": time.time(),
                        "person": None, "vectors": [], "face_busy": False, "face_message": "",
                        "card_id": "", "card_until": 0.0, "card_message": ""})
    led.show("blue")
    log.info("registration started")
    return session["token"]


def people_list(token):
    check(token)
    with open(PEOPLE_COPY, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pick(token, person_id, server_call):
    check(token)
    for p in people_list(token):
        if p["id"] == person_id:
            session["person"] = p
            # Registered at another device already? Then the page offers "Replace my old device"
            ok, answer = server_call("GET", "/api/device/where?id=" + urllib.parse.quote(person_id))
            session["elsewhere"] = {"device": answer.get("device", ""), "location": answer.get("location", "")} if ok else None
            return p
    raise PageError("That person is not in the list.")


def camera_busy():
    return bool(session and session.get("face_busy"))


def start_face(token):
    check(token)
    if not session["person"]:
        raise PageError("Pick your name first.")
    if session["face_busy"]:
        raise PageError("Already taking photos.")
    session.update(vectors=[], face_busy=True, face_message="Look at the camera...")
    threading.Thread(target=take_face_photos, name="face-registration", daemon=True).start()


def collect_face(say, keep_going):
    # Takes FACE_PHOTOS photos with exactly one face in view, within 30 s. Returns the list of face vectors, or None.
    # say(text) shows progress; keep_going() returning False stops early. Also used by person_data.py ("Add more").
    global preview_jpeg
    import cv2
    vectors = []
    ends = time.time() + 30
    try:
        while time.time() < ends and len(vectors) < settings.FACE_PHOTOS and keep_going():
            picture = camera.take_picture()
            if picture is None:
                say("The camera does not work - see the 'camera' line.")
                time.sleep(1)
                continue
            small = cv2.resize(picture, (480, 360))
            preview_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()   # show it at once
            if cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean() < settings.DARK_LEVEL:
                say("Too dark to see a face. Turn the cabin light on, or face a lamp.")
                time.sleep(0.5)
                continue
            faces = face.find_faces(picture)
            sx = 480 / picture.shape[1]
            for f in faces:
                x, y, w, h = [int(v * sx) for v in f[:4]]
                cv2.rectangle(small, (x, y), (x + w, y + h), (0, 200, 0) if len(faces) == 1 else (0, 0, 220), 2)
            preview_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
            if len(faces) == 0:
                say("No face found. Face the camera, closer, with light on your face.")
            elif len(faces) > 1:
                say(str(len(faces)) + " faces in view. Only you, please.")
            else:
                vectors.append(face.vector(picture, faces[0]))
                buzzer.beep("done" if len(vectors) == settings.FACE_PHOTOS else "photo")
                say("Photo %d of %d" % (len(vectors), settings.FACE_PHOTOS))
            time.sleep(0.3)
        if len(vectors) < settings.FACE_PHOTOS:
            if keep_going():
                say("Only %d of %d photos in 30 s. Try again with better light, facing the camera."
                    % (len(vectors), settings.FACE_PHOTOS))
            return None
        return vectors
    except Exception as problem:
        shared.error("face photos", problem)
        say("Taking the face photos failed: " + str(problem))
        return None
    finally:
        preview_jpeg = b""


def take_face_photos():
    def say(text):
        if session:
            session["face_message"] = text

    vectors = collect_face(say, lambda: bool(session))
    if session:
        session["vectors"] = vectors or []
        session["face_busy"] = False
        if vectors:
            session["face_message"] = "Face registered (%d photos). Now link your card, or save." % len(vectors)


def start_card(token):
    check(token)
    session.update(card_until=time.time() + settings.CARD_WAIT_SECONDS, card_message="Tap your card on the reader now...")


def card_tapped(card_id):
    # Called by the RFID thread for every tap. Returns True if the registration took this card.
    with lock:
        if not session or time.time() > session.get("card_until", 0):
            return False
        session.update(card_id=card_id, card_until=0.0, card_message="Card " + card_id + " read.")
    buzzer.beep("ok")
    led.flash("white", 0.15)
    return True


def save(token, server_call, login="", password="", cabin="", replace=False):
    # Returns (state, message): "registered", "pending" (the admin decides) or "waiting" (kept until the server is reachable)
    check(token)
    if not session["person"]:
        raise PageError("Pick your name first.")
    if not session["vectors"] and not session["card_id"]:
        raise PageError("Register your face or a card (or both) first.")
    if session["face_busy"]:
        raise PageError("Wait until the photos are finished.")
    person = session["person"]
    cabin = " ".join(str(cabin or "").split())[:60]
    ok, answer = server_call("POST", "/api/device/register", {
        "person_id": person["id"], "card_id": session["card_id"], "face_photos": len(session["vectors"]),
        "cabin": cabin, "login": str(login or "").strip(), "password": str(password or ""), "replace": bool(replace)})
    if ok:
        state = "registered" if answer.get("state") == "registered" else "pending"
        message = answer["message"]
    elif answer.get("unreachable"):
        state = "waiting"                                  # sent later, without the password: the admin decides then
        message = ("The server can't be reached right now, so this is kept on the device and sent as soon as it can "
                   "be reached. The admin then approves it.")
    else:
        raise PageError(answer["message"])                 # e.g. a wrong password: fix it and send again
    face.forget()
    if session["vectors"]:
        face.save_vectors(session["vectors"])
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    write_person({"id": person["id"], "name": person["name"], "designation": person["designation"], "registered": now,
                  "approval": "approved" if state == "registered" else state, "cabin": cabin,
                  "face_sets": [{"id": "set1", "added": "at setup", "photos": len(session["vectors"])}] if session["vectors"] else [],
                  "cards": [{"uid": session["card_id"], "added": "at setup"}] if session["card_id"] else []})
    if state == "registered":
        shared.update(person={"id": person["id"], "name": person["name"], "designation": person["designation"]},
                      in_cabin=False, card_in=False)
    end("saved: " + state)
    shared.changed.set()
    return state, message


def send_waiting(server_call):
    # A registration kept while the server was out of reach: send it now (no password was kept, so the admin decides)
    local = local_person()
    if session or not local or approval(local) != "waiting":
        return
    ok, answer = server_call("POST", "/api/device/register", {
        "person_id": local["id"], "card_id": (card_ids(local) or [""])[0], "face_photos": face_photo_count(local),
        "cabin": local.get("cabin", "")})
    if ok:
        local["approval"] = "approved" if answer.get("state") == "registered" else "pending"
        write_person(local)
        log.info("waiting registration sent: %s", answer["message"])
    elif not answer.get("unreachable"):
        log.warning("waiting registration refused by the server: %s", answer["message"])
        shared.set_part("registration", False, local["name"] + ": the server refused the registration: " + answer["message"])


def end(reason):
    global preview_jpeg
    with lock:
        session.clear()
        preview_jpeg = b""
    led.show_status(shared.get("status"), force=True)
    log.info("registration ended: %s", reason)


def view(token):
    # What the page shows about the registration (only to the phone that started it)
    with lock:
        if not session or not secrets.compare_digest(session.get("token", ""), str(token or "")):
            return None
        left = settings.REGISTRATION_MINUTES * 60 - (time.time() - session["started"])
        if session["card_message"].startswith("Tap") and time.time() > session["card_until"] and not session["card_id"]:
            session["card_message"] = "No card was tapped in %d s. Press 'Link my card' again." % settings.CARD_WAIT_SECONDS
        return {"person": session["person"], "elsewhere": session.get("elsewhere"),
                "face_photos": len(session["vectors"]), "face_busy": session["face_busy"],
                "face_message": session["face_message"], "card_id": session["card_id"],
                "card_waiting": time.time() < session["card_until"], "card_message": session["card_message"],
                "seconds_left": max(0, int(left))}
