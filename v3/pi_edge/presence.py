# Smart Cabin edge device - is the registered person in the cabin? (PLAN.md section 3)
#   face_checked(matched) : after every face check
#   card_tapped(card_id)  : a card was put on the reader
#   update()              : every picture and every second: timeouts, confidence, status, LED
# Rules:
#   arrive  = face matched in 2 checks in a row, or a card tap
#   tap while in = out at once; for 60 s after it the face can't bring them back
#   a tap-in must be confirmed by the face within 120 s, or they are out again
#   (someone registered with a card only: confirmed when anyone is counted in the cabin)
#   leave = face not seen for 120 s (even if others are counted); card-only person: nobody counted for 120 s
# Confidence = face (seen in the last 30 s) x card (tapped in) table, +10 while someone is counted.

import threading
import time

import face
import led
import registration
import settings
import shared
from logbook import log

lock = threading.RLock()
matches_in_a_row = 0
arrived_at = 0.0
last_face_at = 0.0
last_someone_at = 0.0
card_in_at = 0.0
card_confirmed = True
logout_at = 0.0


def set_in(value, reason):
    global arrived_at
    with lock:
        if shared.get("in_cabin") == value:
            return
        shared.update(in_cabin=value)
        if value:
            arrived_at = time.time()
        log.info("person %s: %s", "IN" if value else "OUT", reason)
        shared.update(presence_reason=reason)
    shared.changed.set()


def face_checked(matched):
    global matches_in_a_row, last_face_at, card_confirmed
    now = time.time()
    with lock:
        if not matched:
            matches_in_a_row = 0
            return
        matches_in_a_row += 1
        last_face_at = now
        shared.update(face_seen_at=now)
        if shared.get("card_in") and not card_confirmed:
            card_confirmed = True
            log.info("card tap confirmed by the face")
        if not shared.get("in_cabin") and matches_in_a_row >= settings.ARRIVE_FACE_CHECKS:
            if now - logout_at < settings.LOGOUT_PAUSE_SECONDS:
                return
            set_in(True, "face recognised in %d checks in a row" % matches_in_a_row)
    update()


def card_tapped(card_id):
    # Returns a message for the page / log
    global card_in_at, card_confirmed, logout_at
    person = registration.local_person()
    if not person or not registration.card_ids(person):
        led.flash("purple")
        return "card " + card_id + " read, but no card is registered at this device"
    if card_id not in registration.card_ids(person):
        led.flash("purple")
        log.warning("unknown card %s", card_id)
        return "unknown card " + card_id
    now = time.time()
    shared.update(known_tap_at=now)                        # the registered person is at the device (see person_data)
    with lock:
        if shared.get("in_cabin"):
            shared.update(card_in=False)
            logout_at = now
            set_in(False, "card tapped out")
            message = "tapped out"
        else:
            shared.update(card_in=True)
            card_in_at = now
            card_confirmed = now - last_face_at < settings.FACE_RECENT_SECONDS
            set_in(True, "card tapped in")
            message = "tapped in" + ("" if card_confirmed else " - the face must confirm within %d s" % settings.CARD_CONFIRM_SECONDS)
    led.flash("white", 0.15)
    update()
    return message


def update():
    global last_someone_at, card_confirmed
    now = time.time()
    with lock:
        s = shared.snapshot()
        if s["headcount"] >= 1:
            last_someone_at = now
            if s["card_in"] and not card_confirmed and face.registered_vectors() is None:
                card_confirmed = True                     # card-only person: someone is really in the cabin
                log.info("card tap confirmed: no face registered, and someone is counted in the cabin")
        if not registration.local_person():
            shared.update(in_cabin=False, card_in=False)
        elif s["in_cabin"]:
            if s["card_in"] and not card_confirmed and now - card_in_at > settings.CARD_CONFIRM_SECONDS:
                shared.update(card_in=False)
                set_in(False, "card tap not confirmed by the face within %d s" % settings.CARD_CONFIRM_SECONDS)
            elif face.registered_vectors() is not None:
                # The face decides: not seen for LEAVE_SECONDS = gone, even if other people are still counted
                if now - max(last_face_at, arrived_at) > settings.LEAVE_SECONDS:
                    shared.update(card_in=False)
                    set_in(False, "face not seen for %d s" % settings.LEAVE_SECONDS)
            elif now - max(last_someone_at, arrived_at) > settings.LEAVE_SECONDS:
                # Registered with a card only: nobody counted for LEAVE_SECONDS = gone
                shared.update(card_in=False)
                set_in(False, "nobody counted for %d s (card-only registration)" % settings.LEAVE_SECONDS)
        s = shared.snapshot()
        face_recent = now - last_face_at < settings.FACE_RECENT_SECONDS
        confidence = settings.CONFIDENCE[(int(face_recent), int(s["card_in"]))]
        if s["in_cabin"] and s["headcount"] >= 1:
            confidence = min(settings.CONFIDENCE_MAX, confidence + settings.SOMEONE_COUNTED_BONUS)
        if s["in_cabin"]:
            status = "meeting" if s["headcount"] >= 2 else "available"
        else:
            status = "not_available"
        old = s["status"]
        shared.update(status=status, confidence=confidence)
    led.show_status(status)
    if status != old:
        log.info("status: %s -> %s (confidence %d %%)", old, status, confidence)
        shared.changed.set()


def loop():
    # Thread: re-check the timeouts every second, even when no picture comes in
    while True:
        try:
            update()
        except Exception as problem:
            shared.error("presence", problem)
        time.sleep(1)
