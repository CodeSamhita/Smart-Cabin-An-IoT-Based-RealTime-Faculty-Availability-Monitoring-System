# Head count: how many people are in the cabin right now.
# Uses the YOLOv8 nano model on webcam pictures and counts the "person" boxes.
# Run it on its own with:  python headcount.py

import time

import cv2
from ultralytics import YOLO

import camera
import config

PERSON_CLASS = 0   # in the YOLO (COCO) model, class 0 is "person"


def load_model():
    # Load the YOLOv8 nano model (the file is in the project folder)
    return YOLO(config.MODEL_FILE)


def count_people(model, frame):
    # Find people in one picture. Returns the count and the picture with boxes drawn.
    result = model(frame, classes=[PERSON_CLASS], conf=config.PERSON_CONFIDENCE, verbose=False)[0]
    count = len(result.boxes)
    picture = result.plot()
    return count, picture


def steady_count(recent_counts, last_steady):
    # Only accept a new count when the last few readings all agree.
    # This stops the number jumping when someone is half hidden for one frame.
    if len(recent_counts) < config.CONFIRM_READINGS:
        return last_steady
    last_few = recent_counts[-config.CONFIRM_READINGS:]
    if len(set(last_few)) == 1:
        return last_few[0]
    return last_steady


def run_headcount():
    model = load_model()
    cam = camera.open_camera()
    recent_counts = []
    steady = None
    print("Counting people. Press q in the window (or Ctrl+C) to stop.")

    try:
        while True:
            frame = camera.read_frame(cam)
            if frame is None:
                print("No picture from camera, trying again...")
                time.sleep(config.COUNT_SECONDS)
                continue

            count, picture = count_people(model, frame)
            recent_counts.append(count)
            recent_counts = recent_counts[-10:]   # keep only the last 10 readings

            new_steady = steady_count(recent_counts, steady)
            if new_steady != steady:
                steady = new_steady
                print(time.strftime("%H:%M:%S"), "Head count =", steady)

            if config.SHOW_WINDOW:
                text = "Seen: " + str(count) + "   Head count: " + str(steady)
                cv2.putText(picture, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.imshow("Smart Cabin - head count", picture)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(config.COUNT_SECONDS)
    except KeyboardInterrupt:
        pass

    camera.close_camera(cam)
    print("Stopped. Last head count =", steady)


if __name__ == "__main__":
    run_headcount()
