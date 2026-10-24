# Headcount from an ESP32-CAM using YOLOv8.
#
# What it does:
#   1. Every INTERVAL seconds, grabs one JPEG snapshot from the ESP32-CAM
#      (sends TOKEN in the "X-Token" header so only we can fetch it).
#   2. Runs YOLOv8-nano on the frame and counts only "person" detections.
#   3. Keeps the last CONFIRM counts; the headcount is only "confirmed"
#      (and printed as [CONFIRMED]) when all of them agree and differ from
#      the previous confirmed value. This filters out one-off misdetections.
#   4. If DEBUG is on, shows the frame with boxes drawn in a window
#      (press "q" to quit). Frames are never saved to disk.
#   5. Camera/Wi-Fi errors are printed and the loop just tries again.

import time
from collections import deque

import cv2
import numpy as np
import requests
from ultralytics import YOLO

CAM_URL  = "http://192.168.137.149/capture"      # your ESP32-CAM IP
TOKEN    = "change-me-to-something-long"
INTERVAL = 10          # seconds between snapshots
CONFIRM  = 3           # same count N times in a row before we trust it
DEBUG    = True        # shows annotated frame; never saved to disk

model = YOLO("yolov8n.pt")   # smallest model, downloads on first run


def get_frame():
    r = requests.get(CAM_URL, headers={"X-Token": TOKEN}, timeout=5)
    r.raise_for_status()
    img = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("could not decode JPEG")
    return img


def count_people(frame, conf=0.4):
    result = model(frame, classes=[0], conf=conf, verbose=False)[0]  # class 0 = person
    return len(result.boxes), result


def main():
    recent = deque(maxlen=CONFIRM)
    confirmed = None

    while True:
        try:
            frame = get_frame()
            n, result = count_people(frame)
            recent.append(n)

            # Only accept a change when the last CONFIRM readings agree
            if len(recent) == CONFIRM and len(set(recent)) == 1 and recent[0] != confirmed:
                confirmed = recent[0]
                print(f"[CONFIRMED] headcount = {confirmed}")
            else:
                print(f"raw count = {n}")

            if DEBUG:
                cv2.imshow("headcount", result.plot())
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        except Exception as e:
            print("snapshot failed:", e)   # camera offline, Wi-Fi drop, etc.

        time.sleep(INTERVAL)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()