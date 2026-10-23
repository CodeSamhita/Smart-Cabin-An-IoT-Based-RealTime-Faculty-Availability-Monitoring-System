# Camera functions: open the webcam, read one picture, close it.

import cv2

import config


def open_camera():
    # Open the webcam given in config.py
    camera = cv2.VideoCapture(config.CAMERA_INDEX)
    if not camera.isOpened():
        raise RuntimeError("Could not open camera " + str(config.CAMERA_INDEX))
    return camera


def read_frame(camera):
    # Take one picture. Returns None if the camera gave nothing.
    ok, frame = camera.read()
    if not ok:
        return None
    return frame


def close_camera(camera):
    camera.release()
    cv2.destroyAllWindows()
