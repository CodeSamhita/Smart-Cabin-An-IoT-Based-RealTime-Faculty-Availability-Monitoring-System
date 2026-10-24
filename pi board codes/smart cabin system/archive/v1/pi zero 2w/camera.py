# Smart Cabin cabin device - the camera. Pi Camera through picamera2; in simulation, a picture file.

import logging
import os
import time

import config
import shared

camera = None


def open_camera():
    global camera
    if config.SIMULATE:
        camera = "simulated"
        return
    from picamera2 import Picamera2
    if not Picamera2.global_camera_info():
        raise RuntimeError("no camera found - check the ribbon cable")
    Picamera2.set_logging(logging.ERROR)
    camera = Picamera2()
    # "RGB888" in picamera2 gives the colour order OpenCV uses (BGR)
    camera.configure(camera.create_still_configuration(main={"size": config.CAMERA_SIZE, "format": "RGB888"}))
    camera.start()
    time.sleep(1)                                    # let exposure and white balance settle


def take_picture():
    # Returns a BGR picture (numpy array), or None if the camera doesn't work
    import cv2
    import numpy as np
    if camera is None:
        try:
            open_camera()
        except Exception as error:
            shared.set_sensor("camera", "error: " + str(error))
            return None
    if config.SIMULATE:
        picture = cv2.imread(config.SIM_PICTURE) if os.path.exists(config.SIM_PICTURE) else None
        if picture is None:
            picture = np.zeros((config.CAMERA_SIZE[1], config.CAMERA_SIZE[0], 3), dtype=np.uint8)   # empty, dark room
        shared.set_sensor("camera", "ok (simulated: " + os.path.basename(config.SIM_PICTURE) + ")")
        return cv2.resize(picture, config.CAMERA_SIZE)
    try:
        picture = camera.capture_array()
        shared.set_sensor("camera", "ok")
        return picture
    except Exception as error:
        shared.set_sensor("camera", "error: " + str(error))
        close_camera()
        return None


def close_camera():
    global camera
    try:
        if camera not in (None, "simulated"):
            camera.close()
    except Exception:
        pass
    camera = None
