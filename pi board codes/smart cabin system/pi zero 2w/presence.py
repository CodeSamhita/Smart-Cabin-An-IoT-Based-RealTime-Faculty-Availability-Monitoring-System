# Smart Cabin cabin device - is the faculty member in the cabin? (BUILD_PLAN.md section 3)
#
#   ARRIVE : face matched in ARRIVE_PICTURES pictures in a row, or a card login tap
#   CARD   : after a card login, the camera or the phone must confirm within CARD_CONFIRM_SECONDS
#   PHONE  : keeps presence alive when the camera misses the face, but never makes an arrival on its own
#   LEAVE  : no face and no phone for LEAVE_SECONDS, or a card logout tap
#   After a logout tap the face is ignored for LOGOUT_IGNORE_SECONDS (they are still walking out of view).

import time

import config
import shared

LOGOUT_IGNORE_SECONDS = 60


def card_tap(now=None):
    # The owner's card was tapped: login if out, logout if in. Returns "login" or "logout".
    now = now or time.time()
    with shared.lock:
        s = shared.state
        if s["faculty_in"]:
            s["faculty_in"] = False
            s["logged_out_at"] = now
            s["face_streak"] = 0
            action = "logout"
        else:
            s["card_login_at"] = now
            action = "login"
    shared.add_event("card_" + action)
    if action == "logout":
        shared.add_event("leave", "card logout")
    shared.go_fast()
    update(now)
    return action


def face_counts(now=None):
    # Pictures shortly after a logout tap don't count (the person is still leaving)
    now = now or time.time()
    with shared.lock:
        return now - shared.state["logged_out_at"] > LOGOUT_IGNORE_SECONDS


def update(now=None):
    # Decides faculty_in from the latest evidence, and logs arrive / leave events
    now = now or time.time()
    with shared.lock:
        s = shared.state
        face_recent = now - s["face_seen_at"] < config.LEAVE_SECONDS and s["face_seen_at"] > s["logged_out_at"]
        phone_recent = s["phone_near"] or now - s["phone_seen_at"] < config.LEAVE_SECONDS
        card_open = s["card_login_at"] > s["logged_out_at"] and now - s["card_login_at"] < config.CARD_CONFIRM_SECONDS
        was_in = s["faculty_in"]

        if not was_in:
            if s["face_streak"] >= config.ARRIVE_PICTURES:
                s["faculty_in"], why = True, "face"
            elif card_open:
                s["faculty_in"], why = True, "card (waiting for camera / phone)"
        else:
            if not (face_recent or phone_recent or card_open):
                s["faculty_in"] = False
        now_in = s["faculty_in"]

    if now_in and not was_in:
        shared.add_event("arrive", why)
        shared.go_fast()
    elif was_in and not now_in:
        shared.add_event("leave", "no face and no phone for " + str(config.LEAVE_SECONDS) + " s")
        shared.go_fast()
    return now_in


def headcount():
    # People in the cabin as sent to the server: at least 1 when the faculty member is in
    with shared.lock:
        return max(shared.state["headcount"], 1 if shared.state["faculty_in"] else 0)


def local_status():
    # Used for the light when the laptop can't be reached (offline fallback)
    with shared.lock:
        if not shared.state["faculty_in"]:
            return "red"
    return "yellow" if headcount() >= 2 else "green"
