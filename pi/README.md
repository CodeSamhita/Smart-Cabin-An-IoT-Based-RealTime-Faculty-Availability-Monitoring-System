# Pi camera stream

Live camera video from the Raspberry Pi Zero 2W, shown on a web page.

| File | What it does |
|---|---|
| `config.py` | Camera type (`pi` or `usb`), size, FPS, port |
| `camera.py` | Keeps the newest camera frame as a JPEG |
| `stream_server.py` | Web page `/`, live video `/stream.mjpg`, one picture `/snapshot.jpg` |
| `main.py` | Starts the camera, then the server |

## 1. Install (on the Pi, once)

Pi Camera (ribbon cable):

    sudo apt update
    sudo apt install -y python3-picamera2

USB webcam instead: `sudo apt install -y python3-opencv` and set `CAMERA_TYPE = "usb"` in `config.py`.

Check the Pi Camera is seen: `rpicam-hello --list-cameras` (older OS: `libcamera-hello --list-cameras`).

## 2. Copy the folder to the Pi (from the laptop)

    scp -r pi <user>@<pi-address>:~/smartcabin-pi

## 3. Run (on the Pi, over SSH)

    cd ~/smartcabin-pi
    python3 main.py

## 4. Open the page (on the laptop)

**Option A – as localhost (SSH tunnel).** In a new laptop terminal:

    ssh -L 8000:localhost:8000 <user>@<pi-address>

Keep it open, then browse to http://localhost:8000

**Option B – directly.** Find the Pi's IP with `hostname -I` and browse to `http://<pi-ip>:8000`.

Stop with Ctrl+C.
