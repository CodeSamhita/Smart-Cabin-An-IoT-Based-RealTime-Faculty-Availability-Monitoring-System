# Reads frames from the camera in the background and keeps the newest one as a JPEG.
# The web server just asks for get_jpeg() whenever it needs a picture.

import io
import threading
import time

import config

latest_jpeg = None
lock = threading.Lock()


def start_camera():
    # Start a background thread so the camera keeps running while the server answers requests
    if config.CAMERA_TYPE == "pi":
        loop = pi_camera_loop
    else:
        loop = usb_camera_loop
    threading.Thread(target=loop, daemon=True).start()

    # Wait (up to 10 s) for the first frame, so the page doesn't open on an empty picture
    for attempt in range(100):
        if get_jpeg() is not None:
            print("Camera started.")
            return
        time.sleep(0.1)
    print("Camera gave no picture yet. Check the cable / camera type in config.py.")


def save_frame(jpeg_bytes):
    global latest_jpeg
    with lock:
        latest_jpeg = jpeg_bytes


def get_jpeg():
    # Newest frame as JPEG bytes, or None if the camera hasn't given one yet
    with lock:
        return latest_jpeg


def pi_camera_loop():
    # Ribbon-cable Pi Camera. Install on the Pi with: sudo apt install python3-picamera2
    from picamera2 import Picamera2

    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (config.WIDTH, config.HEIGHT)}))
    picam2.options["quality"] = config.JPEG_QUALITY
    picam2.start()

    while True:
        buffer = io.BytesIO()
        picam2.capture_file(buffer, format="jpeg")
        save_frame(buffer.getvalue())
        time.sleep(1 / config.FPS)


def usb_camera_loop():
    # USB webcam. Install on the Pi with: sudo apt install python3-opencv
    import cv2

    cam = cv2.VideoCapture(0)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, config.WIDTH)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, config.HEIGHT)

    while True:
        ok, frame = cam.read()
        if not ok:
            time.sleep(0.5)
            continue
        ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY])
        if ok:
            save_frame(jpeg.tobytes())
        time.sleep(1 / config.FPS)
