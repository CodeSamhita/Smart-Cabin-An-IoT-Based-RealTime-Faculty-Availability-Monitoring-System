# Smart Cabin server - the status rules (BUILD_PLAN.md section 4). One place decides every status.
#
#   1. manual button active          -> show it
#   2. cabin device silent for 60 s  -> grey (unless the timetable says "in class": then red, that is known)
#   3. faculty in the cabin          -> yellow if headcount >= 2, else green
#   4. not in the cabin              -> red, with where (timetable) and when back
#   5. a new automatic status must stay the same for 10 s before it is shown (buttons show at once)

import time

import config
import database
import timetable

LABELS = {"green": "Available", "yellow": "In a meeting", "red": "Not available", "grey": "Unknown"}


def log_event(account_id, cabin_id, kind, detail=""):
    database.run("INSERT INTO events (time, account_id, cabin_id, kind, detail) VALUES (?, ?, ?, ?, ?)",
                 (time.time(), account_id, cabin_id, kind, detail))


def hhmm(seconds):
    return time.strftime("%H:%M", time.localtime(seconds))


def cabin_of(account_id):
    return database.row("SELECT * FROM cabins WHERE owner_id = ?", (account_id,))


def state_of(cabin):
    if cabin is None:
        return None
    return database.row("SELECT * FROM cabin_state WHERE cabin_id = ?", (cabin["id"],))


# ---------- Manual buttons ----------
def set_override(account_id, status, reason, minutes, source):
    now = time.time()
    database.run("DELETE FROM overrides WHERE account_id = ?", (account_id,))
    database.run("INSERT INTO overrides (account_id, status, reason, source, set_at, until) VALUES (?, ?, ?, ?, ?, ?)",
                 (account_id, status, reason, source, now, now + minutes * 60))
    log_event(account_id, None, "button", LABELS[status] + (" - " + reason if reason else "") + " (" + source + ")")
    refresh(account_id)


def clear_override(account_id, why):
    if database.row("SELECT 1 FROM overrides WHERE account_id = ?", (account_id,)):
        database.run("DELETE FROM overrides WHERE account_id = ?", (account_id,))
        log_event(account_id, None, "button_end", why)


def check_override(account_id, state, now):
    # Ends a manual button when its end rule is met. Returns the override that is still active, or None.
    o = database.row("SELECT * FROM overrides WHERE account_id = ?", (account_id,))
    if o is None:
        return None
    if now > o["until"]:
        clear_override(account_id, "time is up")
        return None
    if state is None or o["status"] == "red":
        return o                                  # "Not available" ends by time, card login or Auto only

    faculty_in = bool(state["faculty_in"])
    headcount = state["headcount"]
    saw_in, saw_meeting, low_since = o["saw_in"], o["saw_meeting"], o["low_since"]

    if faculty_in:
        saw_in = 1
    elif saw_in:
        clear_override(account_id, "left the cabin")      # seen in, then seen leaving
        return None

    if o["status"] == "yellow":
        if headcount >= 2:
            saw_meeting, low_since = 1, 0
        elif saw_meeting:
            low_since = low_since or now
            if now - low_since >= config.MEETING_END_SECONDS:
                clear_override(account_id, "meeting over (headcount back to 1)")
                return None

    database.run("UPDATE overrides SET saw_in = ?, saw_meeting = ?, low_since = ? WHERE account_id = ?",
                 (saw_in, saw_meeting, low_since, account_id))
    return o


# ---------- The rules ----------
def decide(account_id, now=None):
    # Returns (status, reason, until_text, manual)
    now = now or time.time()
    cabin = cabin_of(account_id)
    state = state_of(cabin)
    online = cabin is not None and state is not None and now - cabin["last_report"] < config.OFFLINE_SECONDS
    current = timetable.current_item(account_id, now)
    upcoming = timetable.next_item(account_id, now)

    # 1. manual button
    o = check_override(account_id, state if online else None, now)
    if o is not None:
        reason = o["reason"] or LABELS[o["status"]]
        if o["status"] == "red":
            until = "back around " + hhmm(o["until"]) if o["until"] - now < 12 * 3600 else ""
        else:
            until = "until " + hhmm(o["until"])
        return o["status"], reason, until, True

    # 2. device silent. Only a class, lab or meeting is "known" from the timetable; during a break or
    #    office hours they may well be in the cabin, so that stays grey (unknown).
    if not online:
        if current is not None and current["activity"] in ("Class", "Lab", "Meeting", "Other"):
            return "red", timetable.away_text(current), "back around " + timetable.back_at(account_id, now), False
        return "grey", "Cabin device offline" if cabin else "No cabin device yet", "", False

    # 3. in the cabin
    if state["faculty_in"]:
        status = "yellow" if state["headcount"] >= 2 else "green"
        reason = "In the cabin with visitors" if status == "yellow" else "In the cabin"
        if upcoming is not None:
            until = "until " + upcoming["start"] + ", then " + timetable.describe(upcoming)
        else:
            until = "for the rest of the day"
        return status, reason, until, False

    # 4. not in the cabin
    if current is not None:
        return "red", timetable.away_text(current), "back around " + timetable.back_at(account_id, now), False
    if upcoming is not None:
        return "red", "Not in the cabin", "next: " + timetable.describe(upcoming) + " at " + upcoming["start"], False
    return "red", "Not in the cabin", "", False


def refresh(account_id, now=None):
    # Work out the status, apply the 10 s buffer, save it, and fire "notify me" watches. Returns status_now.
    now = now or time.time()
    status, reason, until, manual = decide(account_id, now)
    shown = database.row("SELECT * FROM status_now WHERE account_id = ?", (account_id,))
    if shown is None:
        database.run("INSERT INTO status_now (account_id, status, reason, until_text, manual, since) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (account_id, status, reason, until, int(manual), now))
        log_event(account_id, None, "status", status + ": " + reason)
        return database.row("SELECT * FROM status_now WHERE account_id = ?", (account_id,))

    if status == shown["status"]:
        # Same colour: just keep the wording up to date, and forget any waiting change
        database.run("UPDATE status_now SET reason = ?, until_text = ?, manual = ?, pending_status = '' "
                     "WHERE account_id = ?", (reason, until, int(manual), account_id))
    elif manual or (shown["pending_status"] == status and now - shown["pending_since"] >= config.STATUS_BUFFER_SECONDS):
        # A button shows at once; an automatic change only after it held for the buffer time
        database.run("UPDATE status_now SET status = ?, reason = ?, until_text = ?, manual = ?, since = ?, "
                     "pending_status = '' WHERE account_id = ?", (status, reason, until, int(manual), now, account_id))
        log_event(account_id, None, "status", status + ": " + reason)
        if status == "green":
            database.run("UPDATE watches SET fired = ? WHERE target_id = ? AND fired = 0", (now, account_id))
    elif shown["pending_status"] != status:
        database.run("UPDATE status_now SET pending_status = ?, pending_since = ? WHERE account_id = ?",
                     (status, now, account_id))
    return database.row("SELECT * FROM status_now WHERE account_id = ?", (account_id,))


def refresh_all():
    # Called every few seconds: devices that stop reporting turn grey, buttons expire, buffers finish
    for account in database.rows("SELECT id FROM accounts WHERE role = 'faculty' AND active = 1"):
        refresh(account["id"])
