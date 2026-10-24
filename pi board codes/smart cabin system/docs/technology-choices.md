# Technology choices: what, why, and the alternatives

[← back to README](../README.md)

## Laptop server

| Choice | Why | Alternatives (and why not now) |
|---|---|---|
| **Python 3.12** | the AI / IoT libraries are Python; one language on both sides | Node.js (two languages), Java (heavier) |
| **FastAPI** + **uvicorn** | one server for pages and the Pi's JSON; request checking (Pydantic); free `/docs` page; many connections at once | **Flask** (simpler, but checking by hand, no docs page), Django (much larger), Node / Express |
| **Jinja2** templates | the same template system Flask uses; plain HTML files | React / Vue (a build step, more to learn), Streamlit (not for multi-page apps with logins) |
| **SQLite** (`sqlite3`, plain SQL) | built into Python, one file, safe writes, real SQL, no install | **PostgreSQL** (for a real deployment: many servers), MySQL, MongoDB; **CSV** only for export |
| `hashlib.pbkdf2_hmac` | standard password hashing, no extra library | bcrypt / argon2 (stronger, an extra library) |
| own session table | easy to read and explain | JWT tokens, Starlette sessions (`itsdangerous`) |
| HTTP polling (pages every 10 s, Pi every 3 s) | simple, works everywhere | WebSocket / SSE (instant updates), MQTT (for many devices) |
| plain CSS + vanilla JS | no build step; mobile-first; sliding sections with CSS scroll-snap | Bootstrap / Tailwind (look "framework-made"), React |

## Cabin device

| Choice | Why | Alternatives |
|---|---|---|
| **Raspberry Pi Zero 2W** (or Pi 4) | runs face recognition locally, so pictures never leave the cabin; cheap; Wi-Fi + Bluetooth built in | ESP32-CAM (too weak for faces), Pi 5, Jetson (see below) |
| **picamera2** | the official Raspberry Pi camera library | OpenCV `VideoCapture` (USB webcams) |
| **OpenCV DNN** (`cv2.dnn`, `FaceDetectorYN`, `FaceRecognizerSF`) | one library for detection, faces and drawing; no PyTorch (too big for 512 MB) | PyTorch / Ultralytics (heavy), TensorFlow Lite, ONNX Runtime |
| **MobileNet-SSD / YOLOv8n** | fast / accurate, switchable | MediaPipe, NanoDet, YOLOv8s |
| **YuNet + SFace** | tiny, accurate enough, in OpenCV | InsightFace / ArcFace, FaceNet, dlib |
| **mfrc522** + **spidev** + **RPi.GPIO (lgpio)** | the RC522 library, tested in `1_test_rfid.py` | pi-rc522, a PN532 reader (more card types) |
| **BlueZ** (`bluetoothctl`, `l2ping`, `bt-agent`) | the Linux Bluetooth stack; pairing once solves random addresses | bleak (BLE scanning only), a dedicated BLE tag |
| **rpi_ws281x** | the standard NeoPixel driver (DMA + PWM) | Adafruit NeoPixel (Blinka), an SPI driver (needed on the Pi 5) |
| Python's built-in `http.server` for the setup page | nothing to install on the Pi | FastAPI on the Pi (more RAM) |
| `urllib` to talk to the laptop | built in | requests |
| **systemd** service (`--autostart`) | starts at boot, restarts on failure | cron `@reboot`, rc.local |

## Which board is better for what

| Board | Price (approx.) | Face recognition | People count | Verdict |
|---|---|---|---|---|
| ESP32-CAM / ESP32-S3 | ₹500–1,500 | ❌ | weak (tiny models only) | a camera that sends pictures to a server: pictures leave the cabin |
| **Pi Zero 2W** | ₹1,800 | ✅ 1 picture / 5 s | ✅ | **the cheapest that keeps pictures in the cabin** |
| **Pi 4 (4 GB)** | ₹5,000 | ✅✅ 2–3× the Zero | ✅✅ | **best for the demo**: fast, cool, room for YOLOv8n |
| Pi 5 | ₹7,000 | ✅✅✅ | ✅✅✅ | fastest Pi; needs a different LED driver |
| Jetson Orin Nano | ₹40,000+ | GPU, real time | real time | for many cameras or video, overkill for one cabin |
| Laptop only | – | ✅✅✅ | ✅✅✅ | the lab demo; not a product (one laptop per cabin) |

## Communication

| Choice | Why | Alternatives |
|---|---|---|
| **HTTP + JSON** with a device token | simple, testable on `/docs`, works through any Wi-Fi | **MQTT** (better for many devices, needs a broker), CoAP, WebSocket |
| Windows **Mobile hotspot** | a private network whose laptop address (192.168.137.1) never changes | college Wi-Fi (often blocks device-to-device), a dedicated router |
| Plain HTTP | fine on a private hotspot for a prototype | **HTTPS** with certificates: planned for deployment |

## Presence sensors

| Sensor | Role | Alternatives |
|---|---|---|
| Camera (face + count) | the main evidence | thermal array, depth camera |
| RFID | quick login / logout, needs confirming | NFC on the phone, a fingerprint reader |
| Bluetooth phone | keeps presence alive | BLE tag, Wi-Fi presence (address randomisation) |
| Buttons (hardware + web) | a human correction | voice, a touch screen |
| *(later)* mmWave radar | liveness: real person vs photo / video | thermal array; PIR rejected |
