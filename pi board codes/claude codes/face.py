# Face registration: 10 photos of the one face in view -> 10 x 128 numbers (YuNet finds the face, SFace
# turns it into 128 numbers). Pictures are only taken while the page is on the Face step.
import os
import time
import urllib.request

import numpy as np

import config
import shared
import storage


def download(url):
    os.makedirs(config.MODEL_FOLDER, exist_ok=True)
    path = os.path.join(config.MODEL_FOLDER, url.split("/")[-1])
    if not os.path.exists(path):
        print("Downloading", os.path.basename(path), "...")
        urllib.request.urlretrieve(url, path + ".part")
        os.replace(path + ".part", path)      # only keep the file once it is complete
    return path


def open_camera_and_models():
    # Returns (camera, detector, recognizer). Raises an error with a hint if something is missing.
    import cv2
    from picamera2 import Picamera2
    if not Picamera2.global_camera_info():
        raise RuntimeError("no camera found - check the ribbon cable")
    camera = Picamera2()
    camera.configure(camera.create_still_configuration(main={"size": config.RESOLUTION, "format": "RGB888"}))
    camera.start()
    major, minor = [int(n) for n in cv2.__version__.split(".")[:2]]
    yunet = download(config.YUNET_NEW if (major, minor) >= (4, 8) else config.YUNET_OLD)
    detector = cv2.FaceDetectorYN.create(yunet, "", (640, 480), config.MIN_FACE_CONFIDENCE)
    recognizer = cv2.FaceRecognizerSF.create(download(config.SFACE), "")
    return camera, detector, recognizer


def who_matches(samples):
    # Name of an already registered user this face belongs to, or None
    vector = np.mean(np.array(samples, dtype=np.float32), axis=0)
    vector = vector / np.linalg.norm(vector)
    names = {u["user_id"]: u["name"] for u in storage.load_users()}
    for user_id, photos in storage.load_faces().items():
        if float(np.max(photos @ vector)) >= config.FACE_MATCH:
            return names.get(user_id, "another user")
    return None


def add_sample(samples, vector):
    # Called with the lock held. Keeps one photo; finishes the face step when there are enough.
    samples.append(vector)
    shared.state["face_text"] = "photo " + str(len(samples)) + " / " + str(config.FACE_SAMPLES)
    if len(samples) < config.FACE_SAMPLES:
        return samples
    shared.state["face_capturing"] = False
    owner = who_matches(samples)
    if owner:
        shared.say("This face is already registered as " + owner + ". Not kept.")
        shared.state["face_text"] = "already registered as " + owner
    else:
        shared.draft["face"] = samples
        shared.say("Face recorded (" + str(len(samples)) + " photos).")
        shared.state["face_text"] = "recorded"
    return []


def check_timeout(samples):
    # Called with the lock held. Gives up after FACE_SECONDS.
    if shared.state["face_capturing"] and time.time() - shared.state["face_started"] > config.FACE_SECONDS:
        shared.state["face_capturing"] = False
        shared.state["face_text"] = "timed out"
        shared.say("Only " + str(len(samples)) + " good photos in " + str(config.FACE_SECONDS) +
                   " s. Only one face, well lit, close to the camera. Try again.")
        return []
    return samples


def sim_loop():
    # --sim: pretend photos (random numbers, so they never match anyone)
    with shared.lock:
        shared.state.update(face_ok=True, face_text="simulated camera")
    samples = []
    while True:
        time.sleep(0.3)
        with shared.lock:
            if not shared.state["face_capturing"]:
                samples = []
                continue
            vector = np.random.randn(128)
            samples = add_sample(samples, (vector / np.linalg.norm(vector)).tolist())


def camera_loop():
    if config.SIM:
        return sim_loop()
    try:
        import cv2
        camera, detector, recognizer = open_camera_and_models()
    except Exception as error:
        with shared.lock:
            shared.state["face_text"] = "camera not working: " + str(error)
        return
    with shared.lock:
        shared.state.update(face_ok=True, face_text="ready")

    samples = []
    while True:
        with shared.lock:
            on_face_step = shared.draft["active"] and shared.draft["step"] == "face"
            capturing = shared.state["face_capturing"]
        if not on_face_step:
            samples = []
            time.sleep(0.5)                       # no pictures when nobody is on the Face step
            continue
        frame = camera.capture_array()
        detector.setInputSize((frame.shape[1], frame.shape[0]))
        faces = detector.detect(frame)[1]
        faces = [] if faces is None else faces
        for face in faces:
            x, y, w, h = [int(v) for v in face[:4]]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 220, 255) if capturing else (0, 200, 0), 4)
        vector = None
        if capturing and len(faces) == 1:
            vector = recognizer.feature(recognizer.alignCrop(frame, faces[0])).flatten()
            vector = (vector / np.linalg.norm(vector)).tolist()   # length 1: dot product = cosine score
        ok, jpeg = cv2.imencode(".jpg", cv2.resize(frame, (640, 480)), [cv2.IMWRITE_JPEG_QUALITY, 70])
        with shared.lock:
            shared.latest_jpeg = jpeg.tobytes()
            if not shared.state["face_capturing"]:
                samples = []
                shared.state["face_text"] = str(len(faces)) + " face(s) in view"
            else:
                if vector is not None:
                    samples = add_sample(samples, vector)
                elif len(faces) != 1:
                    shared.state["face_text"] = "photo " + str(len(samples)) + " / " + str(config.FACE_SAMPLES) + \
                                                (" - no face" if not faces else " - only one face, please")
                samples = check_timeout(samples)
        time.sleep(0.3 if capturing else 0.5)
