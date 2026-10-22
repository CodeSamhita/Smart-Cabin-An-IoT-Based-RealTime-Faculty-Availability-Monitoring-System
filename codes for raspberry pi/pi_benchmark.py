# Smart Cabin - benchmark for the Raspberry Pi boards (Pi 4 and Pi Zero 2W).
#
# It measures what the project actually does, using the SAME code as smartcabin_pi.py and pi_sender.py:
#   1. System        : board, RAM, OpenCV version
#   2. CPU and SD    : simple Python / numpy speed, SD card write speed
#   3. Camera        : how many pictures per second the camera gives
#   4. Face pipeline : time for each step (detect, embed, match, JPEG) at 640x480 and 320x240
#   5. Memory        : RAM used once the face models are loaded
#   6. Sustained run : full pipeline for 60 s - real FPS, temperature, throttling
#   7. Network       : time to send the status to the laptop (finds pi_receiver.py by mDNS)
#   8. Update delay  : estimate of "change in the cabin -> shown on the page" (evaluation plan, README section 8)
# At the end it suggests an FPS for this board and saves everything to benchmarks/benchmark_<host>_<time>.json.
#
# Put it in the same folder as smartcabin_pi.py and pi_sender.py, STOP smartcabin_pi.py (it holds the camera), then:
#   python3 pi_benchmark.py              full run (about 2-3 minutes)
#   python3 pi_benchmark.py --quick      shorter run (about 1 minute)
#   python3 pi_benchmark.py --no-network skip the laptop test
#   python3 pi_benchmark.py --app smartcabin_pi2.py   benchmark one particular version
# Without --app it uses the newest smartcabin_pi*.py in the folder that has the hardware check.

import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import time
import urllib.request

import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)         # so pi_sender.py next to this file can be imported

# The benchmark needs a smartcabin_pi version with the hardware check (it has all of these)
NEEDED = ["load_models", "find_faces", "embed", "identify", "open_camera", "close_camera", "read_frame",
          "FOLDER", "MODEL_FOLDER", "ON_PI", "PRESENT_SECONDS"]


def load_app():
    # Use the file given with --app, otherwise try smartcabin_pi*.py in this folder, newest first,
    # and take the first one that has everything the benchmark needs.
    if "--app" in sys.argv:
        candidates = [sys.argv[sys.argv.index("--app") + 1]]
    else:
        candidates = [name for name in os.listdir(HERE) if name.startswith("smartcabin_pi") and name.endswith(".py")]
        candidates.sort(key=lambda name: os.path.getmtime(os.path.join(HERE, name)), reverse=True)
    if not candidates:
        sys.exit("No smartcabin_pi*.py found. Put pi_benchmark.py in the same folder as smartcabin_pi.py and run it there.")

    for name in candidates:
        spec = importlib.util.spec_from_file_location("smartcabin_app", os.path.join(HERE, name))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)          # installs missing libraries; gives the real face code
        missing = [item for item in NEEDED if not hasattr(module, item)]
        if not missing:
            print("Benchmarking the code in", name)
            return module
        print("Skipping", name, "- older version (no " + ", ".join(missing) + ")")
    sys.exit("None of these is the newest version: " + ", ".join(candidates) +
             ".\nPaste the newest smartcabin_pi.py from the laptop (nano smartcabin_pi.py), then run again.")


app = load_app()
import cv2                       # noqa: E402
import numpy as np               # noqa: E402

QUICK = "--quick" in sys.argv
RUNS = 10 if QUICK else 30                 # repeats for each timing
SUSTAINED_SECONDS = 20 if QUICK else 60
CAMERA_SECONDS = 3 if QUICK else 5
SAMPLE_FACE_URL = "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/lena.jpg"
RESULTS_FOLDER = os.path.join(app.FOLDER, "benchmarks")
SEND_SECONDS = 2          # pi_sender.py sends every 2 s
PI_PAGE_REFRESH = 1       # the Pi's own web page asks for the status every 1 s
LAPTOP_PAGE_REFRESH = 2   # pi_receiver.py's page asks every 2 s


# ---------- Helpers ----------
def run_command(args, timeout=5):
    # What a system command printed, or "" if it is missing or took too long
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def summary(times_ms):
    times_ms = sorted(times_ms)
    return {"mean_ms": round(statistics.mean(times_ms), 1),
            "median_ms": round(statistics.median(times_ms), 1),
            "p95_ms": round(times_ms[int(len(times_ms) * 0.95) - 1], 1),
            "runs": len(times_ms)}


def time_it(function, runs=RUNS):
    # Run twice to warm up, then time each run in milliseconds
    function()
    function()
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        function()
        times.append((time.perf_counter() - start) * 1000)
    return summary(times)


def temperature():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000, 1)
    except (OSError, ValueError):
        return None


def throttled():
    text = run_command(["vcgencmd", "get_throttled"])
    return text.strip().split("=")[1] if "=" in text else "not available"


def process_ram_mb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def available_ram_mb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def show(name, value):
    if isinstance(value, dict) and "median_ms" in value:
        value = str(value["median_ms"]) + " ms (mean " + str(value["mean_ms"]) + ", p95 " + str(value["p95_ms"]) + ")"
    print("  " + name.ljust(30) + ": " + str(value))


def heading(text):
    print("\n[" + text + "]")


# ---------- 1. System ----------
def system_info():
    heading("1. System")
    model = "not a Raspberry Pi (" + platform.node() + ")"
    try:
        with open("/proc/device-tree/model") as f:
            model = f.read().strip("\x00").strip()
    except OSError:
        pass
    info = {"model": model, "hostname": socket.gethostname(), "cores": os.cpu_count(),
            "python": platform.python_version(), "opencv": cv2.__version__, "numpy": np.__version__,
            "ram_available_mb": available_ram_mb(), "temperature_c": temperature(), "throttled": throttled(),
            "time": time.strftime("%Y-%m-%d %H:%M:%S")}
    for name, value in info.items():
        show(name, value)
    try:
        urllib.request.urlopen("http://localhost:8000/status.json", timeout=1)
        print("  WARNING: smartcabin_pi.py is running. Stop it (Ctrl+C) for fair results - it uses the camera and CPU.")
        info["smartcabin_running"] = True
    except Exception:
        info["smartcabin_running"] = False
    return info


# ---------- 2. CPU and SD card ----------
def cpu_and_storage():
    heading("2. CPU and SD card")
    results = {}

    def python_loop():
        total = 0
        for i in range(1_000_000):
            total += i * i
        return total
    results["python_loop_1M"] = time_it(python_loop, 5)
    show("Python loop (1 million)", results["python_loop_1M"])

    a = np.random.rand(256, 256).astype(np.float32)
    results["numpy_matmul_256"] = time_it(lambda: a @ a)
    show("numpy 256x256 multiply", results["numpy_matmul_256"])

    # SD card: write 32 MB and force it onto the card
    path = os.path.join(app.FOLDER, "benchmark_test.tmp")
    block = os.urandom(1024 * 1024)
    start = time.perf_counter()
    with open(path, "wb") as f:
        for _ in range(32):
            f.write(block)
        f.flush()
        os.fsync(f.fileno())
    seconds = time.perf_counter() - start
    os.remove(path)
    results["sd_write_mb_per_s"] = round(32 / seconds, 1)
    show("SD card write", str(results["sd_write_mb_per_s"]) + " MB/s")
    return results


# ---------- 3. Camera ----------
def camera_speed():
    heading("3. Camera")
    results = {}
    for width, height in [(640, 480), (320, 240)]:
        app.WIDTH, app.HEIGHT = width, height
        try:
            app.open_camera()
        except Exception as error:
            text = str(error)
            if "busy" in text.lower():
                text = "camera busy - stop smartcabin_pi.py first"
            results["error"] = text
            show("Camera", "not tested: " + text)
            app.WIDTH, app.HEIGHT = 640, 480
            return results
        app.read_frame()                     # first picture is slow, don't count it
        frames = 0
        start = time.perf_counter()
        while time.perf_counter() - start < CAMERA_SECONDS:
            if app.read_frame() is not None:
                frames += 1
        fps = round(frames / (time.perf_counter() - start), 1)
        app.close_camera()
        key = "capture_fps_" + str(width) + "x" + str(height)
        results[key] = fps
        show("Camera " + str(width) + "x" + str(height), str(fps) + " pictures/s")
    app.WIDTH, app.HEIGHT = 640, 480
    return results


# ---------- 4. Face pipeline ----------
def sample_picture(width, height):
    # A test photo with one face (OpenCV's standard sample), saved in models/
    path = os.path.join(app.MODEL_FOLDER, "benchmark_face.jpg")
    if not os.path.exists(path):
        print("  Downloading a sample face photo for the test...")
        urllib.request.urlretrieve(SAMPLE_FACE_URL, path)
    return cv2.resize(cv2.imread(path), (width, height))


def face_pipeline():
    heading("4. Face pipeline (same code as smartcabin_pi.py)")
    results = {}
    ram_before = process_ram_mb()
    start = time.perf_counter()
    app.load_models()
    results["model_load_s"] = round(time.perf_counter() - start, 2)
    results["ram_for_models_mb"] = round(process_ram_mb() - ram_before, 1) if ram_before else None
    show("Load models", str(results["model_load_s"]) + " s")
    # The sample photo is an old scan, its face scores only about 0.90. A lower threshold makes sure
    # the face is found at both sizes; it doesn't change how long each step takes.
    app.detector.setScoreThreshold(0.5)

    # A pretend database: 20 people x 10 samples each, like a department
    fake_db = {}
    for i in range(20):
        vectors = np.random.rand(10, 128).astype(np.float32)
        fake_db["Person " + str(i)] = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

    for width, height in [(640, 480), (320, 240)]:
        size = str(width) + "x" + str(height)
        picture = sample_picture(width, height)
        faces = app.find_faces(picture)
        results["faces_found_" + size] = len(faces)
        if len(faces) == 0:
            detect = time_it(lambda: app.find_faces(picture))
            results[size] = {"detect": detect}
            print("  At " + size + ": no face found in the sample photo, only detection timed")
            show("  detect faces (YuNet)", detect)
            continue
        vec = app.embed(picture, faces[0])

        detect = time_it(lambda: app.find_faces(picture))
        embed = time_it(lambda: app.embed(picture, faces[0]))
        match = time_it(lambda: app.identify(vec, fake_db))
        jpeg = time_it(lambda: cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, 75]))

        def whole_frame():
            for face in app.find_faces(picture):
                app.identify(app.embed(picture, face), fake_db)
            cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, 75])
        total = time_it(whole_frame)

        results[size] = {"detect": detect, "embed_per_face": embed, "match_20_people": match,
                         "jpeg_encode": jpeg, "whole_frame_1_face": total,
                         "max_fps": round(1000 / total["median_ms"], 1)}
        print("  At " + size + ":")
        show("  detect faces (YuNet)", detect)
        show("  embed 1 face (SFace)", embed)
        show("  match vs 20 people", match)
        show("  JPEG for the video", jpeg)
        show("  whole frame, 1 face", total)
        show("  => max pipeline FPS", results[size]["max_fps"])
    results["process_ram_mb"] = process_ram_mb()
    results["ram_available_mb"] = available_ram_mb()
    heading("5. Memory")
    show("RAM used by face models", str(results["ram_for_models_mb"]) + " MB")
    show("This program in total", str(results["process_ram_mb"]) + " MB")
    show("RAM still free", str(results["ram_available_mb"]) + " MB")
    return results


# ---------- 6. Sustained run ----------
def sustained_run(camera_ok):
    heading("6. Sustained run (" + str(SUSTAINED_SECONDS) + " s, full pipeline as fast as possible)")
    picture = sample_picture(640, 480)
    use_camera = False
    if camera_ok:
        try:
            app.open_camera()
            use_camera = True
        except Exception:
            pass
    source = "camera + sample face" if use_camera else "sample face only"
    show("Picture source", source)

    temps = [temperature()]
    frames = 0
    start = time.perf_counter()
    next_note = start + 10
    while time.perf_counter() - start < SUSTAINED_SECONDS:
        if use_camera:
            app.read_frame()                  # the real capture cost; the sample face makes sure 1 face is processed
        for face in app.find_faces(picture):
            app.embed(picture, face)
        cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, 75])
        frames += 1
        if time.perf_counter() > next_note:
            temps.append(temperature())
            print("  ... " + str(int(time.perf_counter() - start)) + " s, " +
                  str(round(frames / (time.perf_counter() - start), 1)) + " FPS, " + str(temps[-1]) + " C")
            next_note += 10
    seconds = time.perf_counter() - start
    if use_camera:
        app.close_camera()
    temps.append(temperature())
    temps = [t for t in temps if t is not None]
    results = {"source": source, "fps": round(frames / seconds, 1),
               "temp_start_c": temps[0] if temps else None, "temp_max_c": max(temps) if temps else None,
               "temp_end_c": temps[-1] if temps else None, "throttled_after": throttled()}
    show("Sustained FPS", results["fps"])
    show("Temperature start / max / end", str(results["temp_start_c"]) + " / " + str(results["temp_max_c"]) +
         " / " + str(results["temp_end_c"]) + " C")
    show("Throttled after (0x0 = fine)", results["throttled_after"])
    return results


# ---------- 7. Network to the laptop ----------
def network_test():
    heading("7. Network: Pi -> laptop (pi_receiver.py, found by mDNS)")
    if not os.path.exists(os.path.join(app.FOLDER, "pi_sender.py")):
        show("Skipped", "pi_sender.py is not in this folder")
        return {"skipped": "pi_sender.py missing"}
    import pi_sender
    zc = pi_sender.Zeroconf()
    pi_sender.ServiceBrowser(zc, pi_sender.SERVICE_TYPE, handlers=[pi_sender.on_service_change])
    start = time.perf_counter()
    while not pi_sender.laptops and time.perf_counter() - start < 8:
        time.sleep(0.2)
    found_s = round(time.perf_counter() - start, 2)
    if not pi_sender.laptops:
        zc.close()
        show("Skipped", "no laptop found in 8 s - is pi_receiver.py running on the laptop?")
        return {"skipped": "no laptop found"}
    url = list(pi_sender.laptops.values())[0]
    message = pi_sender.build_message(pi_sender.read_pi_status())
    size = len(json.dumps(message))
    times = []
    failures = 0
    for _ in range(RUNS):
        t = time.perf_counter()
        if pi_sender.send(url, message) is True:
            times.append((time.perf_counter() - t) * 1000)
        else:
            failures += 1
        time.sleep(0.2)
    zc.close()
    results = {"laptop_url": url, "mdns_found_s": found_s, "message_bytes": size, "failures": failures}
    show("Laptop found by mDNS in", str(found_s) + " s at " + url)
    show("Message size", str(size) + " bytes")
    if times:
        results["send"] = summary(times)
        show("Send to laptop", results["send"])
    show("Failed sends", str(failures) + " of " + str(RUNS))
    return results


# ---------- 8. Update delay estimate + recommendation ----------
def update_delay(face, sustained, network):
    heading("8. Update delay estimate (cabin change -> page), worst case")
    frame_ms = face.get("640x480", {}).get("whole_frame_1_face", {}).get("median_ms")
    if frame_ms is None:
        show("Skipped", "no face pipeline result")
        return {}
    recommended = max(1, min(10, int(sustained["fps"] * 0.7)))   # keep 30 % spare for web, RFID, Bluetooth
    wait_ms = 1000 / recommended                                    # waiting for the next picture to be checked
    send_ms = network.get("send", {}).get("median_ms", 0)
    pi_page = wait_ms + frame_ms + PI_PAGE_REFRESH * 1000
    laptop_page = wait_ms + frame_ms + SEND_SECONDS * 1000 + send_ms + LAPTOP_PAGE_REFRESH * 1000
    results = {"recommended_fps": recommended,
               "pi_page_worst_s": round(pi_page / 1000, 2),
               "laptop_page_worst_s": round(laptop_page / 1000, 2),
               "note": "Arriving is shown after 1 matching frame. Leaving shows after PRESENT_SECONDS (" +
                       str(app.PRESENT_SECONDS) + " s) more, by design, so one missed frame doesn't flip the status."}
    show("Suggested FPS for this board", str(recommended) + "   (set FPS = " + str(recommended) + " in smartcabin_pi.py)")
    show("Arrive -> Pi page", str(results["pi_page_worst_s"]) + " s")
    show("Arrive -> laptop page", str(results["laptop_page_worst_s"]) + " s")
    show("Leave -> any page", "+ " + str(app.PRESENT_SECONDS) + " s (PRESENT_SECONDS)")
    return results


def main():
    print("=" * 66)
    print(" Smart Cabin - Pi benchmark" + (" (quick)" if QUICK else ""))
    print("=" * 66)
    results = {"system": system_info()}
    results["cpu_storage"] = cpu_and_storage()
    results["camera"] = camera_speed()
    results["face"] = face_pipeline()
    results["sustained"] = sustained_run("error" not in results["camera"] and app.ON_PI)
    results["network"] = {"skipped": "--no-network"} if "--no-network" in sys.argv else network_test()
    results["update_delay"] = update_delay(results["face"], results["sustained"], results["network"])

    os.makedirs(RESULTS_FOLDER, exist_ok=True)
    path = os.path.join(RESULTS_FOLDER, "benchmark_" + socket.gethostname() + "_" + time.strftime("%Y%m%d_%H%M") + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)

    # Short summary to paste back into the chat / the report
    face640 = results["face"].get("640x480", {})
    print("\n" + "=" * 66)
    print(" SUMMARY - " + results["system"]["model"])
    print("=" * 66)
    print("  Camera 640x480         :", results["camera"].get("capture_fps_640x480", results["camera"].get("error")), "fps")
    print("  Detect / embed / whole :", face640.get("detect", {}).get("median_ms"), "/",
          face640.get("embed_per_face", {}).get("median_ms"), "/",
          face640.get("whole_frame_1_face", {}).get("median_ms"), "ms")
    print("  Sustained FPS          :", results["sustained"]["fps"], "| temp max", results["sustained"]["temp_max_c"],
          "C | throttled", results["sustained"]["throttled_after"])
    print("  RAM for models / free  :", results["face"]["ram_for_models_mb"], "/", results["face"]["ram_available_mb"], "MB")
    send = results["network"].get("send")
    print("  Send to laptop         :", str(send["median_ms"]) + " ms" if send else "skipped (" + str(results["network"].get("skipped")) + ")")
    print("  Suggested FPS          :", results["update_delay"].get("recommended_fps"))
    print("  Arrive -> laptop page  :", results["update_delay"].get("laptop_page_worst_s"), "s (worst case)")
    print("\nAll results saved to", path)


if __name__ == "__main__":
    main()
