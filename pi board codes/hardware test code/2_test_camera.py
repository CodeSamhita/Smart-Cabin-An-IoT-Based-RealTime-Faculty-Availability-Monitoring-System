# Pi Camera test - bare-bone, step by step.
# Run:  python3 2_test_camera.py          (no sudo needed)
# Stop smartcabin_pi.py first: only one program can use the camera at a time.
#
# It saves in this folder: test_photo_full.jpg (full resolution) and test_video_10mbps.h264
# (copy them to the laptop to look at them, e.g. with WinSCP, or: scp pi@<pi ip>:~/smartcabin/test_* .)
#
# Library (once):  sudo apt install -y python3-picamera2

import logging
import os
import sys
import time

os.environ["LIBCAMERA_LOG_LEVELS"] = "3"       # hide libcamera's info messages

FOLDER = os.path.dirname(os.path.abspath(__file__))
FPS_TEST_SECONDS = 3
VIDEO_SECONDS = 4
BITRATES_MBPS = [5, 10, 17, 25]                # H.264 bitrates to try

CAMERA_NAMES = {"ov5647": "Camera Module v1 (5 MP)", "imx219": "Camera Module v2 (8 MP)",
                "imx708": "Camera Module 3 (12 MP, autofocus)", "imx477": "HQ Camera (12.3 MP)",
                "imx296": "Global Shutter Camera (1.6 MP)", "imx500": "AI Camera (12.3 MP)"}
PLACES = {0: "front", 1: "back", 2: "external (ribbon cable)"}

results = []


def step(text):
    print()
    print("[" + str(len(results) + 1) + "] " + text)


def passed(name, text):
    print("    PASS:", text)
    results.append((name, "PASS"))


def failed(name, text):
    print("    FAIL:", text)
    results.append((name, "FAIL"))


def info(name, text):
    print("    INFO:", text)
    results.append((name, "INFO"))


def summary():
    print()
    print("========== Summary ==========")
    for name, result in results:
        print(" ", result.ljust(5), name)


# ---------- Connection checks ----------
def check_library():
    step("Library installed?")
    try:
        import picamera2  # noqa: F401
    except ImportError:
        failed("Library", "picamera2 missing:  sudo apt install -y python3-picamera2")
        return False
    passed("Library", "picamera2")
    return True


def check_connected():
    step("Camera connected?")
    from picamera2 import Picamera2
    cameras = Picamera2.global_camera_info()
    if not cameras:
        failed("Connection", "no camera found. Check the ribbon cable: blue side, both clips pushed in, "
               "and the right port (CAMERA, not DISPLAY)")
        return False
    for number, cam in enumerate(cameras):
        print("    Camera", number, ":", cam.get("Model"), "| place:", PLACES.get(cam.get("Location"), "?"),
              "| id:", cam.get("Id"))
    passed("Connection", str(len(cameras)) + " camera(s) found")
    return True


def open_camera():
    step("Camera can be opened?")
    from picamera2 import Picamera2
    Picamera2.set_logging(logging.ERROR)
    try:
        camera = Picamera2(0)
    except Exception as error:
        failed("Open", str(error) + " - is another program (smartcabin_pi.py) using the camera?")
        return None
    passed("Open", "camera 0 opened")
    return camera


# ---------- Camera details ----------
def max_size(camera):
    # Largest picture the sensor gives. Some drivers (e.g. ov5647) don't report PixelArraySize,
    # so fall back to the biggest sensor mode.
    size = camera.camera_properties.get("PixelArraySize")
    if size and size[0] > 0:
        return tuple(size)
    return max((mode["size"] for mode in camera.sensor_modes), key=lambda s: s[0] * s[1])


def show_camera_type(camera):
    step("Camera type and sensor")
    p = camera.camera_properties
    model = p.get("Model", "?")
    name = CAMERA_NAMES.get(model.split("_")[0], "unknown camera")
    extra = []
    if "wide" in model:
        extra.append("wide lens")
    if "noir" in model:
        extra.append("NoIR (no infrared filter)")
    width, height = max_size(camera)
    print("    Sensor      :", model, "=", name, ("(" + ", ".join(extra) + ")") if extra else "")
    print("    Max size    :", width, "x", height, "=", round(width * height / 1e6, 1), "MP")
    if "UnitCellSize" in p:
        print("    Pixel size  :", round(p["UnitCellSize"][0] / 1000, 2), "x",
              round(p["UnitCellSize"][1] / 1000, 2), "um")
    print("    Rotation    :", p.get("Rotation", "?"), "degrees")
    info("Camera type", name + ", " + str(width) + " x " + str(height))


def show_sensor_modes(camera):
    step("Sensor modes (size and top speed the sensor can do)")
    modes = camera.sensor_modes
    for mode in modes:
        w, h = mode["size"]
        print("    {:>4} x {:<4}  {:>2}-bit  up to {:>5.1f} fps   {}".format(
            w, h, mode["bit_depth"], mode["fps"], str(mode["format"])))
    info("Sensor modes", str(len(modes)) + " modes")
    return modes


def show_controls(camera):
    step("Settings the camera supports")
    controls = camera.camera_controls
    for name in ["ExposureTime", "AnalogueGain", "FrameDurationLimits", "Brightness", "Contrast", "Saturation",
                 "Sharpness", "AwbEnable", "AeEnable"]:
        if name in controls:
            low, high, default = controls[name]
            print("    {:<20} min {}  max {}  default {}".format(name, low, high, default))
    if "ExposureTime" in controls:
        low, high, _ = controls["ExposureTime"]
        print("    Exposure range: " + str(low) + " us to " + str(round(high / 1e6, 1)) + " s")
    autofocus = "AfMode" in controls
    print("    Autofocus   :", "yes" if autofocus else "no (fixed focus)")
    info("Controls", str(len(controls)) + " settings, autofocus " + ("yes" if autofocus else "no"))


# ---------- Picture and speed tests ----------
def test_full_photo(camera):
    step("Full-resolution photo")
    camera.configure(camera.create_still_configuration())
    camera.start()
    time.sleep(2)                                   # let exposure and white balance settle
    path = os.path.join(FOLDER, "test_photo_full.jpg")
    start = time.time()
    metadata = camera.capture_file(path)
    seconds = time.time() - start
    picture = camera.capture_array()
    camera.stop()

    brightness = round(picture.mean())              # 0 = black, 255 = white
    print("    Size        :", picture.shape[1], "x", picture.shape[0])
    print("    Took        :", round(seconds, 2), "s,", round(os.path.getsize(path) / 1e6, 2), "MB")
    print("    Exposure    :", metadata.get("ExposureTime"), "us, gain", round(metadata.get("AnalogueGain", 0), 2))
    print("    Light       :", round(metadata.get("Lux", 0)), "lux, colour temp", metadata.get("ColourTemperature"), "K")
    print("    Brightness  :", brightness, "(0 - 255)")
    print("    Saved       :", path)
    if brightness < 10:
        failed("Photo", "picture is almost black - lens cap on, or the room is dark")
    elif brightness > 245:
        failed("Photo", "picture is almost white - too much light")
    else:
        passed("Photo", str(picture.shape[1]) + " x " + str(picture.shape[0]) + " taken in " +
               str(round(seconds, 2)) + " s")


def measure_fps(camera):
    # Count how many frames arrive in FPS_TEST_SECONDS
    camera.start()
    for _ in range(5):
        camera.capture_metadata()                   # skip the first frames, they are slow
    frames = 0
    start = time.time()
    while time.time() - start < FPS_TEST_SECONDS:
        camera.capture_metadata()
        frames += 1
    camera.stop()
    return frames / (time.time() - start)


def test_mode_speeds(camera, modes):
    step("Real speed of each sensor mode (" + str(FPS_TEST_SECONDS) + " s each)")
    for mode in modes:
        w, h = mode["size"]
        frame_time = int(1e6 / mode["fps"])
        try:
            config = camera.create_video_configuration(
                main={"size": (min(w, 640), min(h, 480))},
                sensor={"output_size": mode["size"], "bit_depth": mode["bit_depth"]},
                controls={"FrameDurationLimits": (frame_time, frame_time)})
            camera.configure(config)
            fps = measure_fps(camera)
        except Exception as error:
            print("    {:>4} x {:<4} {:>2}-bit : can't test ({})".format(w, h, mode["bit_depth"], error))
            continue
        percent = round(100 * fps / mode["fps"])
        print("    {:>4} x {:<4} {:>2}-bit : {:>5.1f} fps of {:>5.1f} ({}%)".format(
            w, h, mode["bit_depth"], fps, mode["fps"], percent))
    info("Mode speeds", "see the list above (90% or more = fine)")


def test_bitrates(camera, width, height):
    step("H.264 video bitrate (hardware encoder)")
    if not os.path.exists("/dev/video11"):
        failed("H.264", "no hardware H.264 encoder on this board (e.g. Pi 5 has none)")
        return
    print("    Hardware encoder found (/dev/video11)")

    from picamera2.encoders import H264Encoder
    size = (min(width, 1920), min(height, 1080))    # the encoder handles up to 1920 x 1080
    camera.configure(camera.create_video_configuration(main={"size": size},
                                                       controls={"FrameDurationLimits": (33333, 33333)}))
    print("    Video", size[0], "x", size[1], "at 30 fps,", VIDEO_SECONDS, "s each")
    best = 0
    for mbps in BITRATES_MBPS:
        path = os.path.join(FOLDER, "test_video_" + str(mbps) + "mbps.h264")
        try:
            camera.start_recording(H264Encoder(bitrate=mbps * 1000000), path)
            time.sleep(VIDEO_SECONDS)
            camera.stop_recording()
        except Exception as error:
            print("    {:>2} Mbps asked : failed ({})".format(mbps, error))
            continue
        real = os.path.getsize(path) * 8 / VIDEO_SECONDS / 1e6
        print("    {:>2} Mbps asked : got {:>5.1f} Mbps".format(mbps, real))
        if real > 0.5 * mbps:
            best = mbps
        if mbps != 10:
            os.remove(path)                         # keep only the 10 Mbps video
    if best:
        passed("H.264", "works up to " + str(best) + " Mbps at " + str(size[0]) + " x " + str(size[1]) +
               " (a still scene needs less, so 'got' can be lower than asked)")
    else:
        failed("H.264", "no video could be recorded")


# ---------- Main ----------
def main():
    print("Pi Camera test")
    if not check_library() or not check_connected():
        summary()
        return
    camera = open_camera()
    if camera is None:
        summary()
        return

    try:
        show_camera_type(camera)
        modes = show_sensor_modes(camera)
        show_controls(camera)
        test_full_photo(camera)
        test_mode_speeds(camera, modes)
        width, height = max_size(camera)
        test_bitrates(camera, width, height)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        camera.close()
    summary()


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Run this on the Raspberry Pi.")
    main()
