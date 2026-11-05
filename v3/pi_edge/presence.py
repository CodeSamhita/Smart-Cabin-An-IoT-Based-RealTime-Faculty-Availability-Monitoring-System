# Smart Cabin edge device - is the registered person in the cabin? (PLAN.md section 3)
#   face_checked(matched) : after every face check
#   card_tapped(card_id)  : a card was put on the reader
#   update()              : every picture and every second: timeouts, confidence, status, LED
# Rules (person with a registered face): the CAMERA decides, a card tap is only a hint.
#   arrive  = face recognised in 2 checks in a row (1 is enough while a card tap is being checked)
#   tap while out = tap in: look for the face for CARD_CONFIRM_SECONDS (green flash, then a green blink every second);
#                   recognised -> in, not -> nothing changes
#   tap while in  = tap out: the face not seen for TAP_OUT_SECONDS after the tap -> out (red flash); still seen -> stays in
#   leave   = face not seen for LEAVE_SECONDS (even if others are counted)
# Someone registered with a card only (no face to check): a tap is the only way in, confirmed when anyone is counted
# in the cabin; a tap while in = out; nobody counted for LEAVE_SECONDS = out.
# Confidence = face (seen in the last 2 min) x card (tapped) table: card only 35, face 70, both 90; +10 while someone is
# counted. The server is told "in" only after REPORT_IN_AFTER_SECONDS in (see server_link.report); out at once.

import threading
import time

import face
import led
import notify
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
card_confirmed = True          # False while a card tap waits for the face (vision then checks every picture)
tap_out_at = 0.0               # a tap while in: out if the face is not seen for TAP_OUT_SECONDS after it (0 = none)


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


def has_face():
    return face.registered_vectors() is not None


def checking():
    # A card tap is waiting for the face
    return bool(shared.get("card_in")) and not card_confirmed


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
        tap_waiting = checking()
        if tap_waiting:
            card_confirmed = True
            log.info("card tap confirmed by the face")
        needed = 1 if tap_waiting else settings.ARRIVE_FACE_CHECKS
        if not shared.get("in_cabin") and matches_in_a_row >= needed:
            set_in(True, "face recognised" + (" after a card tap" if tap_waiting else " in %d checks in a row" % matches_in_a_row))
    update()


def card_tapped(card_id):
    # Returns a message for the page / log
    global card_in_at, card_confirmed, tap_out_at
    person = registration.local_person()
    if not person or not registration.card_ids(person):
        notify.event("unknown card")
        return "card " + card_id + " read, but no card is registered at this device"
    if card_id not in registration.card_ids(person):
        notify.event("unknown card")
        log.warning("unknown card %s", card_id)
        return "unknown card " + card_id
    now = time.time()
    shared.update(known_tap_at=now)                        # the registered person is at the device (see person_data)
    with lock:
        tapping_out = bool(shared.get("in_cabin"))
        if not has_face():                                 # card-only registration: the card is all there is
            if tapping_out:
                shared.update(card_in=False)
                set_in(False, "card tapped out (card-only registration)")
                message = "tapped out"
            else:
                shared.update(card_in=True)
                card_in_at, card_confirmed = now, False
                set_in(True, "card tapped in (card-only registration)")
                message = "tapped in - confirmed when someone is counted in the cabin"
        elif tapping_out:                                  # tap out: the camera has the last word in 30 s
            tap_out_at = now
            message = "tapped out - not available if your face is not seen for %d s" % settings.TAP_OUT_SECONDS
            log.info("card tapped while in: out if the face is not seen for %d s", settings.TAP_OUT_SECONDS)
        else:                                              # tap in: look for the face now
            shared.update(card_in=True)
            card_in_at, card_confirmed, tap_out_at = now, False, 0.0
            message = "card tapped - looking for your face for %d s" % settings.CARD_CONFIRM_SECONDS
            log.info("card tapped: looking for the face for %d s", settings.CARD_CONFIRM_SECONDS)
    notify.event("tap out" if tapping_out else "tap in")
    update()
    return message


def update():
    global last_someone_at, card_confirmed, tap_out_at
    now = time.time()
    with lock:
        s = shared.snapshot()
        if s["headcount"] >= 1:
            last_someone_at = now
        if not registration.local_person():
            shared.update(in_cabin=False, card_in=False)
        elif not has_face():
            # Card-only registration: confirmed by anyone counted; nobody counted for LEAVE_SECONDS = gone
            if s["card_in"] and not card_confirmed and s["headcount"] >= 1:
                card_confirmed = True
                log.info("card tap confirmed: no face registered, and someone is counted in the cabin")
            if s["in_cabin"] and s["card_in"] and not card_confirmed and now - card_in_at > settings.CARD_CONFIRM_SECONDS:
                shared.update(card_in=False)
                set_in(False, "card tap not confirmed (nobody counted) within %d s" % settings.CARD_CONFIRM_SECONDS)
            elif s["in_cabin"] and now - max(last_someone_at, arrived_at) > settings.LEAVE_SECONDS:
                shared.update(card_in=False)
                set_in(False, "nobody counted for %d s (card-only registration)" % settings.LEAVE_SECONDS)
        else:
            # The face decides
            if checking() and now - card_in_at > settings.CARD_CONFIRM_SECONDS:
                shared.update(card_in=False)
                card_confirmed = True
                log.info("card tap: the face was not seen within %d s, so nothing changes", settings.CARD_CONFIRM_SECONDS)
                notify.event("not seen")
            if tap_out_at and now - tap_out_at >= settings.TAP_OUT_SECONDS:
                if s["in_cabin"] and last_face_at <= tap_out_at:    # no face after the tap: gone
                    shared.update(card_in=False)
                    set_in(False, "tapped out, face not seen for %d s" % settings.TAP_OUT_SECONDS)
                else:
                    log.info("tap out cancelled: the face is still seen")
                tap_out_at = 0.0
            if s["in_cabin"] and now - max(last_face_at, arrived_at) > settings.LEAVE_SECONDS:
                shared.update(card_in=False)
                set_in(False, "face not seen for %d s" % settings.LEAVE_SECONDS)
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
        shared.update(status=status, confidence=confidence,
                      checking_until=card_in_at + settings.CARD_CONFIRM_SECONDS if checking() else 0.0)
    led.show_status(status)
    if status != old:
        log.info("status: %s -> %s (confidence %d %%)", old, status, confidence)
        shared.changed.set()
        notify.event("leave" if status == "not_available" else "arrive" if old == "not_available"
                     else "meeting" if status == "meeting" else "alone")
    signal_headcount(s["headcount"], status != old)


last_headcount = None


def signal_headcount(headcount, status_changed):
    # A tick when the number of people changes and the status didn't already say so
    global last_headcount
    if last_headcount is not None and headcount != last_headcount and not status_changed:
        notify.event("people")
    last_headcount = headcount


def loop():
    # Thread: re-check the timeouts every second, even when no picture comes in
    while True:
        try:
            update()
            if checking():
                notify.event("looking")                  # a blue blink every second while looking for the face
        except Exception as problem:
            shared.error("presence", problem)
        time.sleep(1)
