# Smart Cabin cabin device - recognising the cabin owner's face (same tested steps as hardware test 8).
#   1. DETECT : find the faces in the picture        (YuNet model)
#   2. EMBED  : turn each face into 128 numbers       (SFace model)
#   3. MATCH  : cosine similarity with the owner's saved photos. Above FACE_THRESHOLD = the owner.
# Only the owner is registered, and the 128-number photos stay on this device (data/faces.json).

import os

import cv2
import numpy as np

import config
import storage

detector = None
recognizer = None


def load_models():
    global detector, recognizer
    major, minor = [int(n) for n in cv2.__version__.split(".")[:2]]
    yunet = "face_detection_yunet_2023mar.onnx" if (major, minor) >= (4, 8) else "face_detection_yunet_2022mar.onnx"
    detector = cv2.FaceDetectorYN.create(os.path.join(config.MODEL_FOLDER, yunet), "", (640, 480), 0.9)
    recognizer = cv2.FaceRecognizerSF.create(os.path.join(config.MODEL_FOLDER, "face_recognition_sface_2021dec.onnx"), "")


def find_faces(frame):
    # Each face row: x, y, w, h, 10 numbers for eyes / nose / mouth, confidence
    if detector is None:
        load_models()
    detector.setInputSize((frame.shape[1], frame.shape[0]))
    ok, faces = detector.detect(frame)
    return [] if faces is None else faces


def embed(frame, face):
    vector = recognizer.feature(recognizer.alignCrop(frame, face)).flatten()
    return vector / np.linalg.norm(vector)              # length 1, so dot product = cosine similarity


# ---------- The owner's saved face ----------
def saved_vectors():
    data = storage.load("faces.json", {})
    return np.array(data.get("vectors", []), dtype=np.float32)


def photo_count():
    return len(storage.load("faces.json", {}).get("vectors", []))


def save_owner(owner_id, vectors):
    old = storage.load("faces.json", {})
    keep = old.get("vectors", []) if old.get("owner_id") == owner_id else []   # registering again adds photos
    storage.save("faces.json", {"owner_id": owner_id, "vectors": keep + [v.tolist() for v in vectors]})


def forget_if_new_owner(owner_id):
    # The cabin got a new owner: the old owner's face must not stay here
    data = storage.load("faces.json", {})
    if data and data.get("owner_id") != owner_id:
        storage.delete("faces.json")
        return True
    return False


def owner_score(frame, faces):
    # The best match of any face in the picture with the owner (0 - 1), or -1 if nobody is registered
    vectors = saved_vectors()
    if not len(vectors) or not len(faces):
        return -1.0
    return max(float(np.max(vectors @ embed(frame, face))) for face in faces)
