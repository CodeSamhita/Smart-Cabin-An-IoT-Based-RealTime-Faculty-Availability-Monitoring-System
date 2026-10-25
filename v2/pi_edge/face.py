# Smart Cabin edge device - recognising the registered person's face (same tested steps as hardware test 8).
#   1. find faces : YuNet
#   2. 128 numbers: SFace, one vector per face (length 1, so a dot product = cosine similarity)
#   3. match      : best similarity with the registered person's 10 saved vectors >= FACE_THRESHOLD
# Only numbers are kept (data/face.npy, 10 x 128), never photos, and they never leave this device.

import os

import cv2
import numpy as np

import settings
import shared

FACE_FILE = os.path.join(settings.DATA_FOLDER, "face.npy")

detector = None
recognizer = None
saved = None                   # the registered person's vectors, loaded once


def load_models():
    global detector, recognizer
    major, minor = [int(n) for n in cv2.__version__.split(".")[:2]]
    yunet = "face_detection_yunet_2023mar.onnx" if (major, minor) >= (4, 8) else "face_detection_yunet_2022mar.onnx"
    files = [os.path.join(settings.MODEL_FOLDER, n) for n in (yunet, "face_recognition_sface_2021dec.onnx")]
    if not all(os.path.exists(f) for f in files):
        shared.set_part("face model", False, "models/" + yunet + " or the SFace file is missing - start once with internet")
        raise RuntimeError("face model files missing in models/")
    detector = cv2.FaceDetectorYN.create(files[0], "", (DETECT_SIZE, DETECT_SIZE), 0.8)
    recognizer = cv2.FaceRecognizerSF.create(files[1], "")
    shared.set_part("face model", True, "YuNet + SFace")


DETECT_SIZE = 640             # the face finder always works on a 640x640 square (see find_faces)


def find_faces(picture):
    # Each row: x, y, w, h, 10 numbers for eyes / nose / mouth, confidence - in the picture's own pixels.
    # The picture is scaled into a fixed 640x640 square first (black edges), and the faces scaled back. A fixed size
    # matters: if the size changes every call, the face finder rebuilds its memory every time, and on a Zero 2W that
    # grew until the kernel killed the program (out of memory).
    import cv2 as cv
    if detector is None:
        load_models()
        detector.setInputSize((DETECT_SIZE, DETECT_SIZE))
    h, w = picture.shape[:2]
    scale = DETECT_SIZE / max(h, w)
    square = np.zeros((DETECT_SIZE, DETECT_SIZE, 3), dtype=np.uint8)
    square[:int(h * scale), :int(w * scale)] = cv.resize(picture, (int(w * scale), int(h * scale)))
    _, faces = detector.detect(square)
    if faces is None:
        return []
    found = []
    for f in faces:
        f = f.copy()
        f[:14] /= scale                                   # box and eye / nose / mouth points back to the picture
        found.append(f)
    return found


def vector(picture, face):
    v = recognizer.feature(recognizer.alignCrop(picture, face)).flatten()
    return v / np.linalg.norm(v)


def registered_vectors():
    global saved
    if saved is None and os.path.exists(FACE_FILE):
        saved = np.load(FACE_FILE)
    return saved


def save_vectors(vectors):
    global saved
    os.makedirs(settings.DATA_FOLDER, exist_ok=True)
    np.save(FACE_FILE, np.array(vectors, dtype=np.float32))
    if not settings.SIMULATE:
        os.chmod(FACE_FILE, 0o600)
    saved = None


def add_vectors(vectors):
    # One more face set: its vectors go after the ones already saved (person.json says which rows are which set)
    old = registered_vectors()
    save_vectors(list(old) + list(vectors) if old is not None else list(vectors))


def remove_rows(start, count):
    # Delete one face set: rows start .. start+count-1
    old = registered_vectors()
    if old is not None:
        save_vectors(list(old[:start]) + list(old[start + count:]))


def match_score(vectors):
    # How well new photos match the registered face: the middle value of each photo's best similarity
    old = registered_vectors()
    if old is None or not len(old) or not len(vectors):
        return -1.0
    best = sorted(float(np.max(old @ v)) for v in vectors)
    return best[len(best) // 2]


def forget():
    global saved
    if os.path.exists(FACE_FILE):
        os.remove(FACE_FILE)
    saved = None


def best_score(picture, regions):
    # The best match with the registered person among the faces found in the given regions of the picture.
    # regions: list of (x1, y1, x2, y2). Returns -1 if nobody is registered or no face was found.
    vectors = registered_vectors()
    if vectors is None or not len(vectors):
        return -1.0
    best = -1.0
    h, w = picture.shape[:2]
    for x1, y1, x2, y2 in regions:
        x1, y1, x2, y2 = max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2))
        if x2 - x1 < 40 or y2 - y1 < 40:
            continue
        part = picture[y1:y2, x1:x2]
        for found in find_faces(part):
            best = max(best, float(np.max(vectors @ vector(part, found))))
    return best
