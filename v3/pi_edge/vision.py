# Smart Cabin edge device - the vision loop (PLAN.md section 4). Snapshots only.
# Each round: temperature check -> one small picture (640x480) -> (dark? white light for one picture) -> headcount ->
# only when a face check is useful: one big picture (1296x972) -> face -> presence update.
# Then it waits PICTURE_SECONDS, or FAST_PICTURE_SECONDS for 30 s after a change (shorter on a Pi 4 / 5).

import threading
import time

import cv2

import camera
import face
import health
import led
import live
import notify
import people_count
import person_data
import presence
import registration
import settings
import shared
from logbook import log

wake_event = threading.Event()
fast_until = 0.0
last_tap_at = 0.0


def wake(card_tap=False):
    # Something happened (card tap): look again soon, and keep looking fast for a while
    global fast_until, last_tap_at
    fast_until = time.time() + settings.FAST_SECONDS
    if card_tap:
        last_tap_at = time.time()
    wake_event.set()


def brightness_of(picture):
    return float(cv2.cvtColor(cv2.resize(picture, (160, 120)), cv2.COLOR_BGR2GRAY).mean())


def face_regions(boxes, scale):
    # The top part of each person box (found on the small picture), a little wider, in the big picture's pixels
    regions = []
    for x1, y1, x2, y2, _ in boxes:
        w, h = x2 - x1, y2 - y1
        regions.append(((x1 - 0.15 * w) * scale, (y1 - 0.1 * h) * scale, (x2 + 0.15 * w) * scale, (y1 + 0.6 * h) * scale))
    return regions


def loop():
    global fast_until
    cv2.setNumThreads(settings.OPENCV_THREADS)
    last_flash = last_face_check = last_whole_check = 0.0
    while True:
        try:
            if registration.camera_busy() or person_data.face_busy():   # face photos are being taken
                time.sleep(0.5)
                continue
            temp = health.temperature()
            paused = shared.get("vision_paused")
            if temp is not None and (temp >= settings.HOT_TEMPERATURE or (paused and temp >= settings.WARM_TEMPERATURE)):
                if not paused:
                    log.warning("vision paused: %.1f °C", temp)
                    notify.event("hot")
                shared.update(vision_paused="paused to cool down (%.1f °C)" % temp)
                shared.set_part("vision", False, "paused to cool down at %.1f °C" % temp)
                time.sleep(10)
                continue
            shared.update(vision_paused="")
            started = time.time()

            small = camera.take_small()                     # 640x480: headcount (cheap)
            if small is None:
                no_camera = shared.get("parts").get("camera", {}).get("present") is False
                shared.set_part("vision", False, "no camera here, so no headcount or face (card taps still work)" if no_camera
                                else "waiting for the camera (see the camera line)", present=not no_camera)
                time.sleep(5)
                continue
            level = brightness_of(small)
            dark = level < settings.DARK_LEVEL
            lit_room = False
            if dark and (started - last_flash > settings.FLASH_EVERY_SECONDS or started - last_tap_at < 10):
                last_flash = started
                led.light_on()
                try:
                    time.sleep(settings.FLASH_SECONDS)       # the camera adjusts to the light
                    lit = camera.take_small()
                finally:
                    led.light_off()
                if lit is not None:
                    small, lit_room = lit, True
                    log.info("dark room (%.0f): took a picture with the white light (%.0f)", level, brightness_of(lit))

            steady, raw, boxes = people_count.count(small)

            score = None
            if face.registered_vectors() is not None:
                now = time.time()
                in_cabin = shared.get("in_cabin")
                tap_waiting = presence.checking()                  # a card tap: look for the face on every picture
                needed = not in_cabin or tap_waiting or now - last_face_check >= settings.FACE_RECHECK_SECONDS
                wanted = needed and (boxes or tap_waiting or now - last_whole_check >= settings.WHOLE_PICTURE_FACE_SECONDS)
                big = camera.take_picture() if wanted and (not dark or lit_room) else None    # 1296x972, only now
                if big is not None and boxes:
                    score = face.best_score(big, face_regions(boxes, big.shape[1] / small.shape[1]))
                    last_face_check = now
                elif big is not None:
                    h, w = big.shape[:2]
                    score = face.best_score(big, [(0, 0, w, h)])
                    last_face_check = last_whole_check = now
                if score is not None:
                    presence.face_checked(score >= settings.FACE_THRESHOLD)
                    shared.update(face_score=round(score, 2))

            if dark and time.time() - shared.get("face_seen_at") > settings.FACE_RECENT_SECONDS:
                people_count.set_empty()                    # dark room and no face: nobody is working there
                steady = 0

            old = shared.snapshot()
            shared.update(headcount=steady, headcount_raw=raw, dark=dark, brightness=round(level),
                          last_picture_at=time.time(), picture_ms=int((time.time() - started) * 1000))
            shared.set_part("vision", True, "%s, %d ms per round" % (people_count.model_name, (time.time() - started) * 1000))
            live.latest.update(boxes=boxes, people=steady, face=score, dark=dark,
                               ms=int((time.time() - started) * 1000), at=time.strftime("%H:%M:%S"))
            if steady != old["headcount"] or (score is not None and score >= settings.FACE_THRESHOLD and not old["in_cabin"]):
                fast_until = time.time() + settings.FAST_SECONDS
                shared.changed.set()
            presence.update()

            interval = settings.FAST_PICTURE_SECONDS if time.time() < fast_until else settings.PICTURE_SECONDS
            if temp is not None and temp >= settings.WARM_TEMPERATURE:
                interval *= 2
            wake_event.wait(max(0.2, interval - (time.time() - started)))
            wake_event.clear()
        except Exception as problem:
            shared.set_part("vision", False, str(problem))
            shared.error("vision", problem)
            time.sleep(5)
