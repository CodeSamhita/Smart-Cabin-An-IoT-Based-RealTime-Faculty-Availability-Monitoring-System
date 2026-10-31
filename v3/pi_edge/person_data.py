# Smart Cabin edge device - the registered person's face sets and RFID cards, after registration
# (the Pi page, Advanced view, "Registration details").
#   add_face()       : 10 more photos (thread). They must match the registered face, so nobody else can add theirs.
#   add_card()       : the next new card tapped within 30 s is added (the person must be at the device)
#   delete_face(id)  : delete one face set  } the person must be at the device;
#   delete_card(i)   : delete one card      } at least one face set and one card always stay
#   stop()           : cancel adding
# "At the device" = the registered face seen, or a registered card tapped, in the last 2 minutes.
# After every change the server is told (card ids only as hashes there) - if it can't be reached, nothing is changed.

import threading
import time

import buzzer
import face
import led
import registration
import settings
import shared
from logbook import log
from registration import PageError

job = {"kind": "", "message": "", "until": 0.0}   # kind: "face" / "card" / "" (nothing going on)
lock = threading.Lock()


def at_device():
    s = shared.snapshot()
    now = time.time()
    return now - s["face_seen_at"] < settings.FACE_RECENT_SECONDS or now - s["known_tap_at"] < settings.FACE_RECENT_SECONDS


def need_person():
    person = registration.local_person()
    if not person:
        raise PageError("Nobody is registered at this device.")
    return person


def need_at_device():
    if not at_device():
        raise PageError("Show your face to the camera, or tap your registered card, first - so the device knows it is you.")


def face_busy():
    return job["kind"] == "face"


def tell_server(person, server_call):
    ok, answer = server_call("POST", "/api/device/credentials", {"person_id": person["id"],
                                                                 "card_ids": registration.card_ids(person),
                                                                 "face_photos": registration.face_photo_count(person)})
    if not ok:
        raise PageError("The server did not save it, so nothing was changed: " + answer["message"])


def say(text):
    job["message"] = text


# ---------- face sets ----------
def add_face(server_call):
    person = need_person()
    if face.registered_vectors() is None:
        raise PageError("No face is registered yet, so new photos can't be checked against it.")
    with lock:
        if job["kind"]:
            raise PageError("Already adding something. Wait, or press Cancel.")
        job.update(kind="face", message="Look at the camera…", until=0.0)
    threading.Thread(target=take_more_photos, args=(server_call,), name="add-face", daemon=True).start()


def take_more_photos(server_call):
    try:
        vectors = registration.collect_face(say, lambda: job["kind"] == "face")
        if not vectors:
            return
        score = face.match_score(vectors)
        if score < settings.FACE_THRESHOLD:
            say("These photos don't match the registered face (score %.2f), so they were not added." % score)
            return
        person = dict(registration.local_person())
        sets = list(person.get("face_sets", []))
        new_id = "set%d" % (max([int(s["id"][3:]) for s in sets if s["id"][3:].isdigit()] or [0]) + 1)
        sets.append({"id": new_id, "added": time.strftime("%d %b, %H:%M"), "photos": len(vectors)})
        person["face_sets"] = sets
        tell_server(person, server_call)
        face.add_vectors(vectors)
        registration.write_person(person)
        say("Added %d more photos (face set %d, match %.2f)." % (len(vectors), len(sets), score))
        log.info("face set added (%d photos, match %.2f)", len(vectors), score)
    except PageError as problem:
        say(str(problem))
    except Exception as problem:
        shared.error("add face", problem)
        say("Adding face data failed: " + str(problem))
    finally:
        job["kind"] = ""


def delete_face(set_id, server_call):
    person = dict(need_person())
    need_at_device()
    sets = list(person.get("face_sets", []))
    if len(sets) <= 1:
        raise PageError("At least one face set is always kept.")
    start = 0
    for s in sets:
        if s["id"] == set_id:
            sets.remove(s)
            person["face_sets"] = sets
            tell_server(person, server_call)
            face.remove_rows(start, s["photos"])
            registration.write_person(person)
            log.info("face set %s deleted", set_id)
            return "Face set deleted."
        start += s["photos"]
    raise PageError("No such face set.")


# ---------- cards ----------
def add_card():
    need_person()
    need_at_device()
    with lock:
        if job["kind"]:
            raise PageError("Already adding something. Wait, or press Cancel.")
        job.update(kind="card", message="Hold the new card on the reader until it beeps.",
                   until=time.time() + settings.CARD_WAIT_SECONDS)


def card_tapped(card_id, server_call):
    # Called for every tap. Returns True if it was taken as the new card.
    if job["kind"] != "card":
        return False
    if time.time() > job["until"]:
        job.update(kind="", message="No card was tapped in %d s." % settings.CARD_WAIT_SECONDS)
        return False
    person = dict(registration.local_person() or {})
    try:
        if card_id in registration.card_ids(person):
            buzzer.beep("refused")
            say("This card is already linked. Tap a different card.")
            return True
        person["cards"] = list(person.get("cards", [])) + [{"uid": card_id, "added": time.strftime("%d %b, %H:%M")}]
        tell_server(person, server_call)
        registration.write_person(person)
        buzzer.beep("ok")
        led.flash("white", 0.15)
        say("Card •••• %s added." % card_id[-4:])
        log.info("card added")
    except PageError as problem:
        say(str(problem))
    job["kind"] = ""
    return True


def delete_card(index, server_call):
    person = dict(need_person())
    need_at_device()
    cards = list(person.get("cards", []))
    if len(cards) <= 1:
        raise PageError("At least one card is always kept.")
    if not 0 <= index < len(cards):
        raise PageError("No such card.")
    cards.pop(index)
    person["cards"] = cards
    tell_server(person, server_call)
    registration.write_person(person)
    log.info("card deleted")
    return "Card deleted."


def stop():
    job.update(kind="", message="")


def view():
    # For the page: the face sets and cards (only the last 4 characters of a card id) and what is going on
    person = registration.local_person() or {}
    if job["kind"] == "card" and time.time() > job["until"]:
        job.update(kind="", message="No card was tapped in %d s." % settings.CARD_WAIT_SECONDS)
    return {"face_sets": person.get("face_sets", []),
            "cards": [{"index": i, "tail": c["uid"][-4:], "added": c.get("added", "")} for i, c in enumerate(person.get("cards", []))],
            "adding": job["kind"], "adding_message": job["message"], "at_device": at_device()}
