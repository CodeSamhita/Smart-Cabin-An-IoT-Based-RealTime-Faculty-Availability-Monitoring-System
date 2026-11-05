# Smart Cabin edge device - a sound and / or a light for every action and every change, all in one table, so the
# person at the cabin always gets an answer from the device. event(name) plays it in the background.
# The steady colour of the light (green available, yellow in a meeting, red not available, blue registration) is set
# by led.show_status(); the flashes below come on top of it and then the steady colour comes back.

import threading

import buzzer
import led
from logbook import log

# event: (buzzer sound, (flash colour, seconds, times) or None)   -  sounds are in buzzer.SOUNDS
EVENTS = {
    "ready":         ("done",    ("green", 0.3, 1)),     # the app has started
    "arrive":        ("arrive",  None),                   # face recognised: Available (light turns green)
    "meeting":       ("meeting", None),                   # 2 or more people counted: In a meeting (yellow)
    "alone":         ("ok",      None),                   # back to 1 person: Available (green)
    "leave":         ("leave",   None),                   # face not seen for 2 min: Not available (red)
    "people":        ("photo",   None),                   # the headcount changed (no change of status)
    "tap in":        ("ok",      ("green", 0.3, 1)),     # registered card tapped while out: waiting for the face
    "tap out":       ("ok",      ("red", 0.3, 1)),       # registered card tapped while in: out unless the face is seen
    "looking":       (None,      ("green", 0.15, 1)),    # after a tap in: looking for the face (every second)
    "not seen":      ("refused", ("red", 0.2, 2)),       # after a tap: the face was not seen in 2 min
    "unknown card":  ("refused", ("purple", 0.4, 1)),    # a card that is not registered here
    "card left":     ("warning", ("red", 0.25, 2)),      # a card lying on the reader
    "registration":  ("ok",      None),                   # registration started (light turns blue)
    "photo":         ("photo",   None),                   # a face photo taken
    "photos done":   ("done",    None),                   # 10 face photos taken
    "card linked":   ("ok",      ("white", 0.15, 1)),    # a card taken by the registration / Add another card
    "registered":    ("done",    ("green", 0.3, 2)),     # registration complete
    "sent":          ("ok",      ("green", 0.3, 1)),     # registration sent for the admin's approval / kept to send
    "approved":      ("done",    ("green", 0.3, 2)),     # the admin approved it
    "rejected":      ("refused", ("red", 0.3, 2)),       # the admin rejected it (face and card deleted)
    "changed":       ("ok",      ("green", 0.2, 1)),     # face set / card / Wi-Fi network saved or removed
    "refused":       ("refused", ("red", 0.2, 2)),       # an action was refused (e.g. card already linked)
    "server lost":   ("warning", ("red", 0.15, 3)),      # the server can't be reached any more
    "server back":   ("ok",      ("green", 0.15, 2)),    # connected to the server (again)
    "deactivated":   ("warning", ("purple", 0.3, 3)),    # this device was deactivated on the server
    "hot":           ("warning", ("yellow", 0.3, 2)),    # vision paused to cool down
}


def event(name):
    sound, light = EVENTS.get(name, (None, None))
    if name not in EVENTS:
        log.warning("notify: no signal for %s", name)
    if sound:
        buzzer.beep(sound)
    if light:
        colour, seconds, times = light
        threading.Thread(target=led.flash, args=(colour, seconds, times), name="flash", daemon=True).start()
