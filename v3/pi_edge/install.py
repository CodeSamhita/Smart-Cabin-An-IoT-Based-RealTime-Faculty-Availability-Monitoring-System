# Smart Cabin edge device - installs what is missing (first start only), turns SPI on, gets the models.
#   On a Pi    : apt packages (camera, OpenCV, GPIO, SPI) + pip packages (RC522, NeoPixel)
#   On a laptop: OpenCV and numpy only (the hardware is simulated)
#   Models     : copied from the earlier test folders on the Pi if they are there, else downloaded.

import importlib
import os
import shutil
import subprocess
import sys
import urllib.request

import settings

APT = {"picamera2": "python3-picamera2", "cv2": "python3-opencv", "numpy": "python3-numpy",
       "RPi.GPIO": "python3-rpi-lgpio", "spidev": "python3-spidev"}
PIP = {"mfrc522": "mfrc522", "pi5neo": "pi5neo"} if settings.IS_PI5 else {"mfrc522": "mfrc522", "rpi_ws281x": "rpi_ws281x"}
BOOT_CONFIG = "/boot/firmware/config.txt"
SPI1_LINE = "dtoverlay=spi1-1cs"           # Pi 5: the second SPI bus, for the NeoPixel (data on GPIO20)

MODELS = {
    "mobilenet_ssd.prototxt": "https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master/deploy.prototxt",
    "mobilenet_ssd.caffemodel": "https://github.com/chuanqi305/MobileNet-SSD/raw/master/mobilenet_iter_73000.caffemodel",
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "face_detection_yunet_2022mar.onnx": "https://github.com/opencv/opencv_zoo/raw/4fb591053ba1201c07c68929cc324787d5afaa6c/models/face_detection_yunet/face_detection_yunet_2022mar.onnx",
    "face_recognition_sface_2021dec.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
EARLIER_MODEL_FOLDERS = ["/home/pi/hw/models", "/home/pi/claude/models",
                         os.path.join(settings.FOLDER, "..", "..", "pi board codes", "hardware test code", "models")]


def missing(module):
    try:
        importlib.import_module(module)
        return False
    except ImportError:
        return True


def libraries():
    if settings.SIMULATE:
        need = [pkg for module, pkg in (("cv2", "opencv-python"), ("numpy", "numpy")) if missing(module)]
        if need:
            print("Installing", ", ".join(need), "...")
            subprocess.run([sys.executable, "-m", "pip", "install"] + need, check=True)
        return
    apt = sorted({pkg for module, pkg in APT.items() if missing(module)})
    pip = [pkg for module, pkg in PIP.items() if missing(module)]
    if pip:
        apt += ["python3-pip", "python3-dev", "gcc"]
    if apt:
        print("First start: installing", " ".join(apt), "(10+ minutes on a Zero 2W)...")
        subprocess.run(["apt-get", "update"])
        subprocess.run(["apt-get", "install", "-y"] + apt)
    if pip:
        subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "--no-deps"] + pip)
    importlib.invalidate_caches()


def spi_ready():
    # The RC522 needs SPI (and on a Pi 5 the NeoPixel needs SPI1). False = it was just turned on: restart the Pi.
    if settings.SIMULATE:
        return True
    ready = True
    if not os.path.exists("/dev/spidev0.0"):
        subprocess.run(["raspi-config", "nonint", "do_spi", "0"])
        ready = False
    if settings.IS_PI5 and not os.path.exists(settings.LED_SPI_DEVICE):
        try:
            with open(BOOT_CONFIG) as f:
                text = f.read()
            if SPI1_LINE not in text:
                with open(BOOT_CONFIG, "a") as f:
                    f.write("\n# Smart Cabin: SPI1 for the NeoPixel on a Pi 5 (data on GPIO20)\n" + SPI1_LINE + "\n")
            ready = False
        except OSError as problem:
            print("Could not turn SPI1 on for the NeoPixel (" + str(problem) + "). Add '" + SPI1_LINE + "' to "
                  + BOOT_CONFIG + " by hand.")
    return ready


def models():
    os.makedirs(settings.MODEL_FOLDER, exist_ok=True)
    for name in list(MODELS) + ["yolov8n.onnx"]:
        target = os.path.join(settings.MODEL_FOLDER, name)
        if os.path.exists(target):
            continue
        for folder in EARLIER_MODEL_FOLDERS:
            if os.path.exists(os.path.join(folder, name)):
                shutil.copy(os.path.join(folder, name), target)
                print("Copied", name, "from", folder)
                break
        else:
            if name in MODELS:
                print("Downloading", name, "...")
                try:
                    urllib.request.urlretrieve(MODELS[name], target + ".part")
                    os.replace(target + ".part", target)             # keep only a complete file
                except OSError as problem:
                    print("  could not download", name + ":", problem, "- it is tried again at the next start")


def run():
    libraries()
    models()
