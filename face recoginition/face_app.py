"""
Simple face recognition + enrollment of unregistered faces.

Pipeline (the 3 ideas you should understand):
  1. DETECT   : MTCNN finds where faces are in the frame.
  2. EMBED    : InceptionResnetV1 (pretrained on VGGFace2) turns each face into
                a 512-number vector ("embedding"). Same person -> vectors close together.
  3. MATCH    : compare a new embedding with the saved ones using cosine similarity.
                Below THRESHOLD -> "Unknown".

"Training" for a new person = ENROLLING: save a few embeddings of them.
No neural-network retraining is needed, so it takes seconds.

Keys in the video window:
    R = register the face currently shown (asks for a name in the console)
    D = delete a registered person (asks for a name in the console)
    Q = quit
"""

import pickle
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from facenet_pytorch import MTCNN, InceptionResnetV1
from facenet_pytorch.models.utils.detect_face import extract_face

# ---------------- Settings you can tune ----------------
DB_FILE = Path("known_faces.pkl")   # where embeddings are stored
SAMPLES_PER_PERSON = 15             # photos taken during registration
THRESHOLD = 0.60                    # higher = stricter matching (try 0.5 - 0.75)
MIN_FACE_CONFIDENCE = 0.92          # ignore weak detections
CAMERA_INDEX = 0                    # 0 = default webcam
# --------------------------------------------------------

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Running on: {device}")

detector = MTCNN(keep_all=True, device=device)
embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)


# ---------- Database helpers ----------
def load_db() -> dict:
    if DB_FILE.exists():
        with open(DB_FILE, "rb") as f:
            return pickle.load(f)
    return {}


def save_db(db: dict) -> None:
    with open(DB_FILE, "wb") as f:
        pickle.dump(db, f)


# ---------- Core functions ----------
def find_faces(frame_bgr):
    """Return list of (box, face_tensor) for confident detections."""
    img = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    boxes, probs = detector.detect(img)
    results = []
    if boxes is None:
        return results
    for box, p in zip(boxes, probs):
        if p is None or p < MIN_FACE_CONFIDENCE:
            continue
        face = extract_face(img, box, image_size=160, margin=20)  # 0-255 tensor
        face = (face - 127.5) / 128.0                              # model's expected scaling
        results.append((box, face))
    return results


@torch.no_grad()
def embed(face_tensor) -> np.ndarray:
    vec = embedder(face_tensor.unsqueeze(0).to(device))
    vec = F.normalize(vec, p=2, dim=1)  # length 1 so dot product == cosine similarity
    return vec.cpu().numpy()[0]


def identify(vec: np.ndarray, db: dict):
    """Return (name, score). Name is 'Unknown' if nobody is similar enough."""
    best_name, best_score = "Unknown", -1.0
    for name, vectors in db.items():
        score = float(np.max(np.array(vectors) @ vec))  # best match among that person's samples
        if score > best_score:
            best_name, best_score = name, score
    if best_score < THRESHOLD:
        return "Unknown", best_score
    return best_name, best_score


def register_person(cap, db: dict) -> None:
    name = input("\nName of the person to register: ").strip()
    if not name:
        print("Cancelled (empty name).")
        return
    print(f"Look at the camera and move your head slightly. Capturing {SAMPLES_PER_PERSON} samples...")
    samples = []
    last_capture = 0.0
    while len(samples) < SAMPLES_PER_PERSON:
        ok, frame = cap.read()
        if not ok:
            break
        faces = find_faces(frame)
        if len(faces) == 1 and time.time() - last_capture > 0.3:  # exactly one face, spaced out
            samples.append(embed(faces[0][1]))
            last_capture = time.time()
        cv2.putText(frame, f"Registering {name}: {len(samples)}/{SAMPLES_PER_PERSON}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Registration cancelled.")
            return
    if len(samples) == SAMPLES_PER_PERSON:
        db.setdefault(name, []).extend(samples)
        save_db(db)
        print(f"Saved {name}. Known people: {list(db.keys())}")


def main():
    db = load_db()
    print(f"Known people: {list(db.keys()) or 'none yet'}")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)  # CAP_DSHOW = faster/more reliable on Windows
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Try CAMERA_INDEX = 1.")

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        for box, face in find_faces(frame):
            name, score = identify(embed(face), db)
            x1, y1, x2, y2 = map(int, box)
            color = (0, 200, 0) if name != "Unknown" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{name} ({score:.2f})", (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            if name == "Unknown":
                cv2.putText(frame, "Press R to register", (x1, y2 + 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Face Recognition", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord("r"):
            register_person(cap, db)
        elif key == ord("d"):
            name = input("\nName to delete: ").strip()
            if db.pop(name, None) is not None:
                save_db(db)
                print(f"Deleted {name}.")
            else:
                print("No such person.")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
