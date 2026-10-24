# Hardware test code

Bare-bone scripts, numbered in the order they were made. 1 – 3 test one part each: they first check that the part is connected, then test it step by step and print PASS / FAIL / INFO with a hint. 4 – 6 show the camera video, 6 – 7 count people (6 on live video, 7 on one picture every 1.5 s), 8 recognises faces, and 9 finds users' phones and laptops over Bluetooth.

**Resolution:** people counting works at 640x480 (the models shrink the picture to 300 / 320 px anyway). Faces are much smaller than bodies, so face recognition needs more pixels: in a test photo no face was found at 640x480, but one was at 1296x972 (59 px wide). Run them on the Pi, one at a time, with `smartcabin_pi.py` stopped.

| File | Run | What it does |
|---|---|---|
| `1_test_rfid.py` | `sudo python3 1_test_rfid.py` | SPI on, libraries, chip version (original or clone), SPI write + read back, 500 reads for a stable connection, RST pin, antenna and gain, the chip's own self-test, card UID + check byte, card type, card memory (sector 0, default key), read rate over 5 s, then a live mode that prints every tapped card |
| `2_test_camera.py` | `python3 2_test_camera.py` | Library, camera detected, camera can be opened (not busy), camera type and sensor (model, max resolution, pixel size), all sensor modes with top fps, supported settings (exposure range, autofocus), full-resolution photo (time, exposure, lux, brightness), real fps of each mode, H.264 hardware encoder at 5 / 10 / 17 / 25 Mbps |
| `3_test_neopixel.py` | `sudo python3 3_test_neopixel.py` | sudo, board supported, audio off (it shares the PWM), LED library starts, then one LED: Enter = next colour (red, green, blue, yellow, cyan, magenta, white, off), q = quit |
| `4_test_video_window.py` | `python3 4_test_video_window.py` | Bare code: live camera video (640x480) in a window, q to quit. Needs a screen: monitor, VNC, or `ssh -X` (MobaXterm on Windows) |
| `5_test_video_web.py` | `python3 5_test_video_web.py` | Live camera video on a web page (port 8081, MJPEG from the hardware encoder). Controls: resolution (320x240, 640x480, 1296x972), fps (default 30), bitrate (1 – 25 Mbps, default 12), flip, and brightness / contrast / saturation / sharpness / exposure (these change straight away). Shows the real fps and Mbps |
| `6_people_count_web.py` | `python3 6_people_count_web.py` | People counter on a web page (port 8082): live video with a box around each person, a big count, the time per detection and fps. Switch between MobileNet-SSD (fast, downloads itself) and YOLOv8n (accurate, needs `models/yolov8n.onnx`, see below) and set the confidence. The count only changes after 3 readings in a row agree |
| `7_people_count_snapshot.py` | `python3 7_people_count_snapshot.py` | Same counter, but snapshots instead of live video (port 8083): take a picture, count the people, show it, wait 1.5 s (0.5 – 5 s on the page), repeat. Much lighter on the CPU, best for the Zero 2W. A change in the count shows after 3 pictures agree. Two on/off checks against photos and posters of people (see below) |
| `8_face_recognition.py` | `python3 8_face_recognition.py` | Bare-bone face recognition on a web page (port 8084), same 3 steps as `smartcabin_pi.py` (YuNet detect → SFace 128 numbers → cosine match). Every 1.5 s: a picture with a name (or "Unknown") and score on each face. **Register**: type a name, it takes 10 photos of the one face in view. List of registered people with Delete. Resolution (320x240 / 640x480 / 1296x972, default 1296x972) and threshold (default 0.36) on the page. Faces saved in `known_faces.json` (git-ignored) |
| `9_bluetooth_presence.py` | `sudo python3 9_bluetooth_presence.py` | Bluetooth presence on a web page (port 8085): users with 0 – 5 devices each (phone, laptop, watch), **Near** / **Away** per user, and when each device was last seen. **Add device** pairs once with no typing, and only saves the device's identity (see below). Every 15 s the Pi l2pings each user's devices. Saved in `bluetooth_devices.json` (git-ignored) |

The camera test saves `test_photo_full.jpg` and `test_video_10mbps.h264` next to the script.

## Photos and posters of people (`7_people_count_snapshot.py`)

A camera can't tell a photo, poster or screen of a person from a real one. There are two checks, each with an on/off switch on the page:

- **Stillness check:** a real person is never perfectly still. Each box shows its *change*, which is how much the picture inside it differs from when it last moved (0 – 255). If the change stays under the *movement threshold* (default 4) for *still for* seconds (default 60), the box turns orange ("still") and is not counted.
  - Raise the threshold if a poster still counts. Lower it, or raise *still for*, if a person sitting very still drops out.
  - A video playing on a screen moves, so this check can't catch it.
- **Ignore zones:** areas of the picture that are never counted. A box that is at least half inside a zone turns grey ("ignored").
  - **Draw a zone:** press the button, then drag on the picture (works with a mouse or a finger).
  - **Ignore boxes seen now:** with the room empty, every box still found (the poster) becomes a zone.
  - The zones are saved in `ignore_zones.json` next to the script, so they stay after a restart. Move the camera, and they need redrawing.

Test it: stand next to a printed photo of a person. You should count, and the photo should turn orange after a minute or grey once its zone is made. A thermal sensor (README iteration 8) is the stronger fix, if this ever isn't enough.

## Bluetooth presence (`9_bluetooth_presence.py`)

**Random addresses:**
- When phones and laptops (iPhone, Android, Mac, Windows) just *advertise* (Bluetooth Low Energy), they use a **random address that changes about every 15 minutes**. An unpaired device can't be recognised again.
- The **classic Bluetooth address is fixed**. Pairing once gives the Pi that real address, plus the key (IRK) that links the random addresses back to the device. So pairing once fixes it, and nothing needs typing.

**Pairing only saves the identity:**
- The device is **not trusted**, and it is **disconnected straight after pairing**, so no service can attach (keyboard, speaker, file transfer).
- The pairing helper (`bt-agent`, NoInputNoOutput) only runs during the 60 s window. The rest of the time the Pi is not visible and not pairable.
- The check is an **l2ping**, a tiny "are you there?" at the Bluetooth link level. No service and no data are used. It works while the device's Bluetooth is on, even with the screen locked.

**Adding a device** (press **Add device** on a user, then within 60 s):
1. On the device, open the **Bluetooth settings** screen and keep it open. That makes it visible.
2. On the page, press **Pair** next to it, and accept on the device. This works for **iPhones**, which often don't list a Pi themselves. Or choose the Pi's name in the device's own list (Android, laptops).

**Notes:**
- A device is "near" if it answered in the last 60 s. As soon as one of a user's devices answers, their other devices are skipped for that round.
- Turning Bluetooth off on the device makes it "away". Removing it on the page also deletes the pairing on the Pi. On the device, you can "forget" the Pi too.
- Range is about 10 m and goes through walls, so a phone in the next room can count as near. Use it as a supporting signal, not alone.

## YOLOv8n for the people counter (once)

The Pi can't make the YOLO file itself (that needs PyTorch, which is too big for the Pi), so it is made on the laptop and copied over. **It has already been made:** `models/yolov8n.onnx` in this folder (12 MB, not in git), so only step 2 is needed. To make it again:

1. Laptop, in `laptop codes/` (where `yolov8n.pt` is), with Python 3.12 or 3.13 (Python 3.15 can't install ultralytics yet):

       pip install ultralytics onnx
       yolo export model=yolov8n.pt format=onnx imgsz=320 opset=12

   This makes `yolov8n.onnx` (about 12 MB). `imgsz=320` must match `YOLO_SIZE` in `6_people_count_web.py`.
2. Copy it to the Pi, into a `models` folder next to the script:

       cd "pi board codes/hardware test code"
       ssh pi@<pi ip> "mkdir -p ~/hw/models"
       scp models/yolov8n.onnx pi@<pi ip>:~/hw/models/

Without the file, the page says so and keeps using MobileNet-SSD.

## Wiring (GPIO number, physical pin in brackets)

| RC522 | Pi |
|---|---|
| SDA | GPIO8 (24) |
| SCK | GPIO11 (23) |
| MOSI | GPIO10 (19) |
| MISO | GPIO9 (21) |
| RST | GPIO25 (22) |
| 3.3V | 3.3V (1), never 5 V |
| GND | GND (6) |
| IRQ | not connected |

| NeoPixel | Pi |
|---|---|
| DIN | GPIO18 (12) |
| 5V | 5V (2) |
| GND | GND (14) |

Camera: ribbon cable in the CAMERA port.

## Libraries (once)

    sudo apt install -y python3-picamera2 python3-opencv python3-spidev python3-rpi-lgpio python3-pip python3-dev gcc
    sudo pip3 install mfrc522 --break-system-packages --no-deps
    sudo pip3 install rpi_ws281x --break-system-packages

## Notes

- Clone RC522 boards (chip version 0x88 or 0xB2) work fine. Only the self-test can't be compared for them.
- College ID cards usually have their own key, so the memory read says INFO, not FAIL. The UID still reads.
- The RC522 only reads 13.56 MHz cards. 125 kHz cards never show up.
- A WS2812 can't report back, so for the LED test you have to look at it.
