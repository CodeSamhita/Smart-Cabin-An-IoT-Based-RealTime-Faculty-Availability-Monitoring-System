# Smart Cabin edge device - counting people in a picture (same tested logic as hardware test 7, without
# the poster checks for now).
#   1. find people  : MobileNet-SSD (light, for the Zero 2W) or YOLOv8n (more accurate, for a Pi 4)
#   2. steady count : the count changes only after STEADY_PICTURES pictures agree
# Both models run in OpenCV. count() returns the steady count, the raw count and the person boxes.

import os

import cv2

import identity
import settings
import shared

MOBILENET_PERSON = 15          # "person" in MobileNet-SSD (VOC classes)
YOLO_PERSON = 0                # "person" in YOLO (COCO classes)
YOLO_SIZE = 320                # yolov8n.onnx was exported with imgsz=320

net = None
model_name = ""
recent = []
steady = 0


def load_model():
    global net, model_name
    yolo = os.path.join(settings.MODEL_FOLDER, "yolov8n.onnx")
    want_yolo = settings.PEOPLE_MODEL == "yolo" or (settings.PEOPLE_MODEL == "auto" and identity.is_pi4_or_newer())
    if not hasattr(cv2.dnn, "readNetFromCaffe"):
        want_yolo = True                                  # OpenCV 5 can't read MobileNet-SSD (Caffe) any more
    if want_yolo and os.path.exists(yolo):
        net, model_name = cv2.dnn.readNetFromONNX(yolo), "YOLOv8n"
    else:
        files = [os.path.join(settings.MODEL_FOLDER, n) for n in ("mobilenet_ssd.prototxt", "mobilenet_ssd.caffemodel")]
        if not all(os.path.exists(f) for f in files):
            shared.set_part("people model", False, "models/mobilenet_ssd files missing - start once with internet to download them")
            raise RuntimeError("people model files missing in models/")
        net = cv2.dnn.readNetFromCaffe(*files)
        model_name = "MobileNet-SSD"
    shared.set_part("people model", True, model_name)


def detect(frame):
    # Person boxes (x1, y1, x2, y2, score) in the picture's own pixels
    h, w = frame.shape[:2]
    if model_name == "MobileNet-SSD":
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        return [(int(r[3] * w), int(r[4] * h), int(r[5] * w), int(r[6] * h), float(r[2]))
                for r in net.forward()[0, 0] if int(r[1]) == MOBILENET_PERSON and r[2] >= settings.PEOPLE_CONFIDENCE]
    blob = cv2.dnn.blobFromImage(frame, 1 / 255, (YOLO_SIZE, YOLO_SIZE), swapRB=True)
    net.setInput(blob)
    rows = net.forward()[0].T                   # each row: centre x, centre y, width, height, 80 class scores
    sx, sy = w / YOLO_SIZE, h / YOLO_SIZE
    found, scores = [], []
    for r in rows:
        if r[4 + YOLO_PERSON] >= settings.PEOPLE_CONFIDENCE:
            found.append([int((r[0] - r[2] / 2) * sx), int((r[1] - r[3] / 2) * sy), int(r[2] * sx), int(r[3] * sy)])
            scores.append(float(r[4 + YOLO_PERSON]))
    keep = cv2.dnn.NMSBoxes(found, scores, settings.PEOPLE_CONFIDENCE, 0.45)      # one box per person
    return [(found[i][0], found[i][1], found[i][0] + found[i][2], found[i][1] + found[i][3], scores[i])
            for i in (keep.flatten() if len(keep) else [])]


def count(frame):
    # Returns (steady count, raw count in this picture, boxes)
    global recent, steady
    if net is None:
        load_model()
    boxes = detect(frame)
    recent = (recent + [len(boxes)])[-settings.STEADY_PICTURES:]
    if len(recent) == settings.STEADY_PICTURES and len(set(recent)) == 1:
        steady = recent[0]
    return steady, len(boxes), boxes


def set_empty():
    # A dark room with no face: count it as empty, and start the steadiness again
    global recent, steady
    recent, steady = [], 0
