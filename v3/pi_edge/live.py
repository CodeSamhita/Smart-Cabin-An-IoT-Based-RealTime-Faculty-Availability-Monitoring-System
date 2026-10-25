# Smart Cabin edge device - the Live view of the device page's Advanced view.
# A continuous picture stream (MJPEG: one JPEG after another) at LIVE_FPS, 640x480, only while a page watches it,
# with the person boxes and numbers of the latest vision round drawn on it. Nothing is saved.
#   latest       : what the vision loop found last (vision.py fills it in)
#   frame_jpeg() : one picture, as JPEG bytes
#   stream(out)  : writes pictures to a page until the page closes

import time

import cv2

import camera
import settings

latest = {"boxes": [], "people": 0, "face": None, "dark": False, "ms": 0, "at": ""}
GREEN = (76, 138, 30)


def frame_jpeg():
    picture = camera.take_small()
    if picture is None:
        return None
    for i, (x1, y1, x2, y2, conf) in enumerate(latest["boxes"]):
        cv2.rectangle(picture, (int(x1), int(y1)), (int(x2), int(y2)), GREEN, 2)
        cv2.putText(picture, "person %d  %d%%" % (i + 1, conf * 100), (int(x1) + 4, max(16, int(y1) + 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 1, cv2.LINE_AA)
    text = time.strftime("%H:%M:%S") + "  people: %d" % latest["people"]
    if latest["face"] is not None:
        text += "  face: %.2f" % latest["face"]
    if latest["dark"]:
        text += "  DARK"
    cv2.rectangle(picture, (0, 0), (picture.shape[1], 24), (48, 30, 20), -1)
    cv2.putText(picture, text, (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    return cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, 65])[1].tobytes()


def stream(out):
    # out: the page's connection. Ends when the page closes it (BrokenPipeError is raised to the caller).
    while True:
        started = time.time()
        jpeg = frame_jpeg()
        if jpeg:
            out.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode()
                      + b"\r\n\r\n" + jpeg + b"\r\n")
            out.flush()
        time.sleep(max(0.02, 1 / settings.LIVE_FPS - (time.time() - started)))
