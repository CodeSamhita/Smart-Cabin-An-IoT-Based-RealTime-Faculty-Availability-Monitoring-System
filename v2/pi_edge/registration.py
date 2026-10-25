# Smart Cabin edge device - registering a person at this device, from their phone.
# Steps on the page (PiRegister.dc.html): pick your name -> register face (10 photos) -> tap card -> save.
#   start()          : the server says whether setup is allowed here (nobody registered yet, location set);
#                      the people list is copied from the server (data/people_copy.csv)
#   start_face()     : takes 10 photos with exactly one face in view (thread), shows progress
#   start_card()     : the next card tap (within 30 s) is the person's card
#   save()           : the server registers the person, then this device keeps the face and card
#   sync_person()    : the server says who is registered here (after an admin removal, the face is deleted)
# Only one registration at a time. It ends after REGISTRATION_MINUTES. The camera preview exists only during
# a registration and only for the phone that started it (its secret session key).

import csv
import json
import os
import secrets
import threading
import time

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
    global person_cache
    if person_cache is None:
        try:
            with open(PERSON_FILE) as f:
                person_cache = json.load(f)
        except (OSError, ValueError):
            person_cache = {}
    return person_cache or None


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


def sync_person(server_person):
    # The server's answer is the truth about who is registered at this device
    if session:
        return                                            # don't interfere with a registration going on
    local = local_person()
    if not server_person:
        if local:
            forget_person("the server says nobody is registered here (removed by the admin?)")
        shared.update(person=None)
        shared.set_part("registration", True, "nobody registered yet - press Start registration on this device's page")
        return
    if local and local.get("id") != server_person["id"]:
        forget_person("the server has someone else registered here")
        local = None
    shared.update(person=server_person)
    if not local:
        shared.set_part("registration", False, server_person["name"] + " is registered on the server, but this device "
                        "has no face or card for them (new SD card?). Register again here.")
    else:
        shared.set_part("registration", True, server_person["name"] + ": face photos " + str(local.get("face_photos", 0))
                        + ", card " + ("yes" if local.get("card_id") else "no"))


# ---------- the registration session ----------
def check(token):
    with lock:
        if not session or not secrets.compare_digest(session["token"], str(token or "")):
            raise PageError("No registration going on from this phone. Start again with the setup PIN.")
        if time.time() - session["started"] > settings.REGISTRATION_MINUTES * 60:
            end("timed out")
            raise PageError("The registration took longer than %d minutes and was stopped. Start again."
                            % settings.REGISTRATION_MINUTES)


def start(server_call):
    # The server allows a registration while nobody is registered at this device and it has a location
    if not shared.get("device"):
        raise PageError("This device is not connected to the server yet, so it cannot register anyone. "
                        "Check the 'server' line on the device page.")
    ok, answer = server_call("POST", "/api/device/setup-allowed", {})
    if not ok:
        raise PageError(answer["message"])
    if not answer.get("allowed"):
        raise PageError(answer["message"])
    ok, answer = server_call("GET", "/api/device/people")
    if not ok:
        raise PageError("Could not get the people list from the server: " + answer["message"])
    with open(PEOPLE_COPY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "designation", "role", "school", "department"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(answer["people"])
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


def pick(token, person_id):
    check(token)
    for p in people_list(token):
        if p["id"] == person_id:
            session["person"] = p
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


def take_face_photos():
    global preview_jpeg
    import cv2
    ends = time.time() + 30
    try:
        while time.time() < ends and len(session.get("vectors", [])) < settings.FACE_PHOTOS and session:
            picture = camera.take_picture()
            if picture is None:
                session["face_message"] = "The camera does not work - see the 'camera' line."
                time.sleep(1)
                continue
            small = cv2.resize(picture, (480, 360))
            preview_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()   # show it at once
            if cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).mean() < settings.DARK_LEVEL:
                session["face_message"] = "Too dark to see a face. Turn the cabin light on, or face a lamp."
                time.sleep(0.5)
                continue
            # Find the face on a 640x480 copy (the person is close, and it is 4x less work for a Zero 2W),
            # then scale the face back to the full picture for its 128 numbers
            scale = picture.shape[1] / 640
            faces = face.find_faces(cv2.resize(picture, (640, int(picture.shape[0] / scale))))
            faces = [f.copy() for f in faces]
            for f in faces:
                f[:14] *= scale
            sx = 480 / picture.shape[1]
            for f in faces:
                x, y, w, h = [int(v * sx) for v in f[:4]]
                cv2.rectangle(small, (x, y), (x + w, y + h), (0, 200, 0) if len(faces) == 1 else (0, 0, 220), 2)
            preview_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
            if len(faces) == 0:
                session["face_message"] = "No face found. Face the camera, closer, with light on your face."
            elif len(faces) > 1:
                session["face_message"] = str(len(faces)) + " faces in view. Only you, please."
            else:
                session["vectors"].append(face.vector(picture, faces[0]))
                session["face_message"] = "Photo %d of %d" % (len(session["vectors"]), settings.FACE_PHOTOS)
            time.sleep(0.3)
        if session and len(session["vectors"]) < settings.FACE_PHOTOS:
            session["face_message"] = ("Only %d of %d photos in 30 s. Try again with better light, facing the camera."
                                       % (len(session["vectors"]), settings.FACE_PHOTOS))
            session["vectors"] = []
        elif session:
            session["face_message"] = "Face registered (%d photos). Now link your card, or save." % settings.FACE_PHOTOS
    except Exception as problem:
        shared.error("face registration", problem)
        if session:
            session["face_message"] = "Face registration failed: " + str(problem)
            session["vectors"] = []
    finally:
        if session:
            session["face_busy"] = False
        preview_jpeg = b""


def start_card(token):
    check(token)
    session.update(card_until=time.time() + settings.CARD_WAIT_SECONDS, card_message="Tap your card on the reader now...")


def card_tapped(card_id):
    # Called by the RFID thread for every tap. Returns True if the registration took this card.
    with lock:
        if not session or time.time() > session.get("card_until", 0):
            return False
        session.update(card_id=card_id, card_until=0.0, card_message="Card " + card_id + " read.")
    led.flash("white", 0.15)
    return True


def save(token, server_call):
    check(token)
    if not session["person"]:
        raise PageError("Pick your name first.")
    if not session["vectors"] and not session["card_id"]:
        raise PageError("Register your face or a card (or both) first.")
    if session["face_busy"]:
        raise PageError("Wait until the photos are finished.")
    person = session["person"]
    ok, answer = server_call("POST", "/api/device/register", {"person_id": person["id"],
                                                              "card_id": session["card_id"],
                                                              "face_photos": len(session["vectors"])})
    if not ok:
        raise PageError("The server did not save it: " + answer["message"])
    face.forget()
    if session["vectors"]:
        face.save_vectors(session["vectors"])
    write_person({"id": person["id"], "name": person["name"], "designation": person["designation"],
                  "card_id": session["card_id"], "face_photos": len(session["vectors"]),
                  "registered": time.strftime("%Y-%m-%d %H:%M:%S")})
    shared.update(person={"id": person["id"], "name": person["name"], "designation": person["designation"]},
                  in_cabin=False, card_in=False)
    message = answer["message"]
    end("saved")
    shared.changed.set()
    return message


def remove(pin, server_call):
    ok, answer = server_call("POST", "/api/device/unregister", {"pin": str(pin).strip()})
    if not ok:
        raise PageError(answer["message"])
    forget_person("removed from the page with a setup PIN")
    shared.update(person=None)
    shared.changed.set()
    return answer["message"]


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
        return {"person": session["person"], "face_photos": len(session["vectors"]), "face_busy": session["face_busy"],
                "face_message": session["face_message"], "card_id": session["card_id"],
                "card_waiting": time.time() < session["card_until"], "card_message": session["card_message"],
                "seconds_left": max(0, int(left))}
