# Smart Cabin edge device - the camera. Two sizes from one camera setup:
#   take_small()   : 640x480 (LIVE_SIZE) - for the headcount and the live view. Light, can be taken often.
#   take_picture() : 1296x972 (CAMERA_SIZE) - only when a face has to be checked or registered (faces need the pixels).
#   On a Pi              : the Pi Camera through picamera2, with a "main" stream (big) and a "lores" stream (small).
#   Not a Pi (e.g. Windows): a --picture file if one was given (a missing file = a dark empty room), else this
#                          computer's webcam, else no camera (vision waits, the rest keeps running).
# A lock makes sure two parts never use the camera at the same moment.

import logging
import os
import threading
import time

import settings
import shared

lock = threading.Lock()
camera = None                  # the open camera: picamera2 object, OpenCV webcam, or "picture"
has_small_stream = False       # picamera2 gave us the 640x480 "lores" stream
next_try = 0.0                 # no camera found: don't look again before this time


class NoCamera(Exception):
    pass


def open_camera():
    global camera, has_small_stream
    import cv2
    if settings.SIMULATE:
        if settings.TEST_PICTURE_GIVEN:
            camera = "picture"
            return
        if settings.USE_WEBCAM:
            webcam = cv2.VideoCapture(0, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
            if webcam.isOpened():
                webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                camera = webcam
                return
            webcam.release()
        raise NoCamera("no camera on this computer (" + settings.COMPUTER + "). Vision waits; card taps on the page "
                       "still work. Start with --picture photo.jpg to test with a picture.")
    from picamera2 import Picamera2
    if not Picamera2.global_camera_info():
        raise RuntimeError("no camera found - check the ribbon cable and that it is pushed in fully")
    Picamera2.set_logging(logging.ERROR)
    camera = Picamera2()
    try:
        # "RGB888" in picamera2 gives the colour order OpenCV uses (BGR). "lores" = the small stream (YUV420).
        config = camera.create_video_configuration(main={"size": settings.CAMERA_SIZE, "format": "RGB888"},
                                                   lores={"size": settings.LIVE_SIZE, "format": "YUV420"},
                                                   buffer_count=3)
        camera.configure(config)
        has_small_stream = True
    except Exception as problem:
        shared.error("camera", "no small stream (%s) - the small picture is made by shrinking the big one" % problem)
        camera.configure(camera.create_still_configuration(main={"size": settings.CAMERA_SIZE, "format": "RGB888"},
                                                           buffer_count=1))
        has_small_stream = False
    camera.start()
    time.sleep(1)                                          # let the exposure settle


def grab(small):
    # One picture from the camera that is open (inside the lock)
    import cv2
    import numpy as np
    size = settings.LIVE_SIZE if small else settings.CAMERA_SIZE
    if camera == "picture":
        picture = cv2.imread(settings.SIM_PICTURE) if os.path.exists(settings.SIM_PICTURE) else None
        if picture is None:
            shared.set_part("camera", True, "test picture missing, so a dark empty room")
            return np.zeros((size[1], size[0], 3), dtype=np.uint8)
        shared.set_part("camera", True, "test picture " + os.path.basename(settings.SIM_PICTURE))
        return cv2.resize(picture, size)
    if hasattr(camera, "grab"):                            # the computer's webcam
        camera.grab()                                      # drop an old buffered frame
        ok, picture = camera.read()
        if not ok or picture is None:
            raise RuntimeError("the webcam gave no picture (is another program using it?)")
        shared.set_part("camera", True, "webcam of this computer")
        return cv2.resize(picture, size) if small else picture
    if small and has_small_stream:
        yuv = camera.capture_array("lores")
        # picamera2's YUV420 is I420 (U plane before V). Not COLOR_YUV420p2BGR: in OpenCV that means YV12 (V before U),
        # which swaps the colours (orange shows as blue).
        picture = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)[:, :settings.LIVE_SIZE[0]]
    else:
        picture = camera.capture_array("main")
        if small:
            picture = cv2.resize(picture, size)
    shared.set_part("camera", True, "%dx%d + %dx%d" % (settings.CAMERA_SIZE + settings.LIVE_SIZE))
    return picture


def take(small):
    # Returns a BGR picture (numpy array), or None if there is no working camera (the reason is on the page)
    global next_try
    with lock:
        if camera is None and time.time() < next_try:
            return None
        try:
            if camera is None:
                open_camera()
            return grab(small)
        except NoCamera as problem:
            shared.set_part("camera", False, str(problem), present=False)
            next_try = time.time() + 60                    # look for a webcam again in a minute
            return None
        except Exception as problem:
            shared.set_part("camera", False, str(problem))
            close_camera()
            return None


def take_small():
    return take(True)


def take_picture():
    return take(False)


def close_camera():
    global camera
    try:
        if hasattr(camera, "release"):
            camera.release()
        elif camera not in (None, "picture"):
            camera.close()
    except Exception:
        pass
    camera = None
