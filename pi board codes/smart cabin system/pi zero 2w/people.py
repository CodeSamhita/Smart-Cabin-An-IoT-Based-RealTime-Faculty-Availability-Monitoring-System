# Smart Cabin cabin device - counting people (same tested logic as hardware test 7_people_count_snapshot.py).
#   1. find people          : MobileNet-SSD (fast) or YOLOv8n (accurate), both run by OpenCV
#   2. drop the fake ones   : ignore zones (posters on the wall) and the stillness check (a box whose
#                             picture hasn't changed for STILL_SECONDS is a photo, not a person)
#   3. steady count         : the count changes only after STEADY_PICTURES pictures agree

import os
import time

import cv2

import config
import storage

MOBILENET_PERSON = 15         # class number of "person" in MobileNet-SSD (VOC classes)
YOLO_PERSON = 0               # class number of "person" in YOLO (COCO classes)
YOLO_SIZE = 320               # yolov8n.onnx was exported with imgsz=320

net = None
model_name = ""
tracks = []                   # stillness check: one per box seen recently
recent = []                   # last counts
steady = 0


def load_model():
    global net, model_name
    yolo = os.path.join(config.MODEL_FOLDER, "yolov8n.onnx")
    if config.PEOPLE_MODEL == "yolo" and os.path.exists(yolo):
        net, model_name = cv2.dnn.readNetFromONNX(yolo), "yolo"
    else:
        net = cv2.dnn.readNetFromCaffe(os.path.join(config.MODEL_FOLDER, "mobilenet_ssd.prototxt"),
                                       os.path.join(config.MODEL_FOLDER, "mobilenet_ssd.caffemodel"))
        model_name = "mobilenet"


# ---------- 1. find people ----------
def detect(frame):
    # Returns boxes (x1, y1, x2, y2, score)
    h, w = frame.shape[:2]
    if model_name == "mobilenet":
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
        net.setInput(blob)
        return [(int(r[3] * w), int(r[4] * h), int(r[5] * w), int(r[6] * h), float(r[2]))
                for r in net.forward()[0, 0] if int(r[1]) == MOBILENET_PERSON and r[2] >= config.PEOPLE_CONFIDENCE]

    blob = cv2.dnn.blobFromImage(frame, 1 / 255, (YOLO_SIZE, YOLO_SIZE), swapRB=True)
    net.setInput(blob)
    rows = net.forward()[0].T                         # each row: centre x, centre y, width, height, 80 class scores
    sx, sy = w / YOLO_SIZE, h / YOLO_SIZE
    found, scores = [], []
    for r in rows:
        if r[4 + YOLO_PERSON] >= config.PEOPLE_CONFIDENCE:
            found.append([int((r[0] - r[2] / 2) * sx), int((r[1] - r[3] / 2) * sy), int(r[2] * sx), int(r[3] * sy)])
            scores.append(float(r[4 + YOLO_PERSON]))
    keep = cv2.dnn.NMSBoxes(found, scores, config.PEOPLE_CONFIDENCE, 0.45)   # one box per person
    return [(found[i][0], found[i][1], found[i][0] + found[i][2], found[i][1] + found[i][3], scores[i])
            for i in (keep.flatten() if len(keep) else [])]


# ---------- 2. drop the fake ones ----------
def in_ignore_zone(box, w, h):
    # At least half of the box inside a zone (zones are 0 - 1 coordinates, see storage zones.json)
    x1, y1, x2, y2 = box[:4]
    area = max(1, (x2 - x1) * (y2 - y1))
    for zx1, zy1, zx2, zy2 in storage.load("zones.json", []):
        ow = min(x2, zx2 * w) - max(x1, zx1 * w)
        oh = min(y2, zy2 * h) - max(y1, zy1 * h)
        if ow > 0 and oh > 0 and ow * oh / area >= 0.5:
            return True
    return False


def overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def box_picture(frame, box):
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])
    if x2 - x1 < 4 or y2 - y1 < 4:
        return None
    return cv2.resize(cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY), (32, 64))


def seconds_still(frame, boxes, now):
    # For each box: how long its picture hasn't changed (compared with when it last moved)
    global tracks
    results, used = [], set()
    for box in boxes:
        best, best_overlap = None, 0.0
        for i, t in enumerate(tracks):
            o = overlap(box, t["box"])
            if i not in used and o > best_overlap:
                best, best_overlap = i, o
        picture = box_picture(frame, box)
        if best is None or best_overlap < 0.4 or picture is None:
            tracks.append({"box": box, "ref": picture, "moved_at": now, "seen_at": now})
            used.add(len(tracks) - 1)
            results.append(0.0)
            continue
        t = tracks[best]
        used.add(best)
        change = float(cv2.absdiff(picture, t["ref"]).mean()) if t["ref"] is not None else 255.0
        if change > config.MOVE_THRESHOLD or best_overlap < 0.8:
            t["moved_at"], t["ref"] = now, picture
        t["box"], t["seen_at"] = box, now
        results.append(now - t["moved_at"])
    tracks = [t for t in tracks if now - t["seen_at"] < 10]
    return results


# ---------- 3. count ----------
def count(frame):
    # Returns (steady count, [(box, "counted" / "still" / "ignored")]) for one picture
    global recent, steady
    if net is None:
        load_model()
    now = time.time()
    h, w = frame.shape[:2]
    boxes = detect(frame)
    labelled = []
    for box, still in zip(boxes, seconds_still(frame, boxes, now)):
        if in_ignore_zone(box, w, h):
            labelled.append((box, "ignored"))
        elif still >= config.STILL_SECONDS:
            labelled.append((box, "still"))
        else:
            labelled.append((box, "counted"))
    counted = sum(1 for _, s in labelled if s == "counted")
    recent = (recent + [counted])[-10:]
    last = recent[-config.STEADY_PICTURES:]
    if len(last) == config.STEADY_PICTURES and len(set(last)) == 1:
        steady = last[0]
    return steady, labelled


def zones_from_boxes(labelled, w, h):
    # "Ignore what is seen now" (use it in an empty room): every box becomes an ignore zone
    zones = storage.load("zones.json", [])
    for box, status in labelled:
        if status != "ignored":
            pad_x, pad_y = (box[2] - box[0]) * 0.05, (box[3] - box[1]) * 0.05
            zones.append([max(0.0, (box[0] - pad_x) / w), max(0.0, (box[1] - pad_y) / h),
                          min(1.0, (box[2] + pad_x) / w), min(1.0, (box[3] + pad_y) / h)])
    storage.save("zones.json", zones)
    return len(zones)
