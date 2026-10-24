# Smart Cabin cabin device - installs everything it needs, the first time only, and turns SPI on.
# On a Pi:     apt packages (camera, OpenCV, GPIO, SPI, Bluetooth tools) + pip packages (RFID, LED)
# On a laptop: only OpenCV and numpy (the hardware is simulated)
# Then it downloads the vision models into models/.

import importlib
import os
import subprocess
import sys
import urllib.request

import config

APT = {"picamera2": "python3-picamera2", "cv2": "python3-opencv", "numpy": "python3-numpy",
       "RPi.GPIO": "python3-rpi-lgpio", "spidev": "python3-spidev"}
PIP = {"mfrc522": "mfrc522", "rpi_ws281x": "rpi_ws281x"}
COMMANDS = {"bluetoothctl": "bluez", "l2ping": "bluez", "bt-agent": "bluez-tools"}

MODELS = {
    # people counting
    "mobilenet_ssd.prototxt": "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
    "mobilenet_ssd.caffemodel": "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel",
    # faces (the 2022 detector also works on the older OpenCV of Raspberry Pi OS)
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_detection_yunet_2022mar.onnx": "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def is_missing(module):
    try:
        importlib.import_module(module)
        return False
    except ImportError:
        return True


def command_missing(name):
    return subprocess.run(["which", name], capture_output=True).returncode != 0


def install_libraries():
    if not config.ON_PI:
        missing = [name for module, name in (("cv2", "opencv-python"), ("numpy", "numpy")) if is_missing(module)]
        if missing:
            print("Installing", ", ".join(missing), "...")
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        return

    apt = sorted({pkg for module, pkg in APT.items() if is_missing(module)} |
                 {pkg for cmd, pkg in COMMANDS.items() if command_missing(cmd)})
    pip = [pkg for module, pkg in PIP.items() if is_missing(module)]
    if pip:
        apt += ["python3-pip", "python3-dev", "gcc"]           # needed to build the LED library
    if apt:
        print("First run: installing", " ".join(apt), "- this can take 10+ minutes on a Zero 2W...")
        subprocess.run(["apt-get", "update"])
        subprocess.run(["apt-get", "install", "-y"] + apt)
    if pip:
        # --no-deps: the GPIO and SPI libraries already came from apt
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "--no-deps"] + pip)
    importlib.invalidate_caches()


def spi_ready():
    # The RFID reader needs SPI. Returns False if it was just turned on (a reboot is needed).
    if not config.ON_PI or not config.USE_RFID or os.path.exists("/dev/spidev0.0"):
        return True
    subprocess.run(["raspi-config", "nonint", "do_spi", "0"])
    return False


def download_models():
    os.makedirs(config.MODEL_FOLDER, exist_ok=True)
    for name, url in MODELS.items():
        path = os.path.join(config.MODEL_FOLDER, name)
        if not os.path.exists(path):
            print("Downloading", name, "...")
            try:
                urllib.request.urlretrieve(url, path + ".part")
                os.replace(path + ".part", path)               # only keep the file once it is complete
            except OSError as error:
                print("  could not download", name + ":", error, "- will try again next start")
