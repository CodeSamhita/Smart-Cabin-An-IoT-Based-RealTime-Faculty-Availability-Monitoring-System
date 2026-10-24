# Pi Camera live video in a window - bare code. Press q in the window to quit.
# Run:  python3 4_test_video_window.py
# Needs a screen: a monitor on the Pi, VNC, or SSH with X forwarding (ssh -X, and MobaXterm on Windows).
#
# Libraries (once):  sudo apt install -y python3-picamera2 python3-opencv

import os
import sys

import cv2
from picamera2 import Picamera2

if not os.environ.get("DISPLAY"):
    sys.exit("No screen found. Use a monitor, VNC, or connect with: ssh -X pi@<pi ip>")

if not Picamera2.global_camera_info():
    sys.exit("No camera found - check the ribbon cable")

camera = Picamera2()
# "RGB888" in picamera2 gives the colour order OpenCV uses (BGR)
camera.configure(camera.create_preview_configuration(main={"size": (640, 480), "format": "RGB888"}))
camera.start()

while True:
    frame = camera.capture_array()          # video input: one picture from the camera
    cv2.imshow("Pi Camera", frame)          # output window
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.stop()
cv2.destroyAllWindows()
