# Smart Cabin cabin device - run this on the Raspberry Pi:   sudo python3 main.py
#                                     start at every boot:   sudo python3 main.py --autostart
# (On a laptop it runs in simulation:   python main.py)
# Terminal tests:  sudo python3 main.py --check          can it reach the laptop?
#                  sudo python3 main.py --connect 123456  connect to a cabin without the page
#
# What it does:
#   1. installs everything that is missing, turns SPI on, downloads the models (install.py)
#   2. starts one thread per job:
#        camera    : a picture every 5 s (1.5 s after any change) -> people count + owner's face
#        rfid      : waits for card taps (login / logout / link)
#        bluetooth : l2pings the owner's phones every 15 s
#        buttons   : the 3 hardware buttons
#        report    : sends the evidence to the laptop every 3 s, gets the status back, sets the light
#        config    : gets the owner, cards and phones from the laptop every minute
#        pairing   : until connected, finds the laptop by its broadcast and waits for the admin to add it
#   3. serves the setup page on port 8000 (web.py) in the main thread

import os
import sys
import time

import config
import install


def make_autostart():
    # A systemd service: the program starts at every boot, and restarts if it ever stops
    service = ("[Unit]\nDescription=Smart Cabin cabin device\nAfter=network-online.target bluetooth.target\n"
               "Wants=network-online.target\n\n[Service]\nWorkingDirectory=" + config.FOLDER + "\n"
               "ExecStart=" + sys.executable + " " + os.path.join(config.FOLDER, "main.py") + "\n"
               "Restart=always\nRestartSec=5\nUser=root\n\n[Install]\nWantedBy=multi-user.target\n")
    with open("/etc/systemd/system/smartcabin.service", "w") as f:
        f.write(service)
    os.system("systemctl daemon-reload && systemctl enable --now smartcabin.service")
    print("Done. It now starts at every boot. See it with:  systemctl status smartcabin")
    print("Stop it with:  sudo systemctl disable --now smartcabin")


def argument_after(flag, default=""):
    # sudo python3 main.py --connect 123456 --server http://192.168.137.1:8080  ->  "123456" for "--connect"
    if flag in sys.argv and sys.argv.index(flag) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(flag) + 1]
    return default


if "--check" in sys.argv or "--connect" in sys.argv:
    # Terminal tests, no web page needed:
    #   sudo python3 main.py --check                 can this device reach the laptop server?
    #   sudo python3 main.py --connect 123456        connect to a cabin with the 6-digit code
    # Both take  --server http://<laptop>:8080  (default: the address saved before, or config.SERVER_URL)
    import server_link
    import storage
    server = argument_after("--server")
    if server:
        saved = storage.load("device.json", {})
        saved["server"] = server.rstrip("/")
        storage.save("device.json", saved)
    print("Laptop server:", server_link.server_url())
    ok, answer = server_link.call("GET", "/api/people")
    print("Reach the server:", "OK (" + str(len(answer.get("people", []))) + " people)" if ok else "FAILED - " + answer.get("detail", ""))
    if ok and "--connect" in sys.argv:
        ok, answer = server_link.claim(argument_after("--connect"))
        print("Connect:", "OK - this device is now the cabin " + answer["cabin"] if ok else "FAILED - " + answer.get("detail", ""))
    sys.exit(0 if ok else 1)

if "--autostart" in sys.argv:
    if not config.ON_PI or os.geteuid() != 0:
        sys.exit("Run on the Pi with sudo:  sudo python3 main.py --autostart")
    install.install_libraries()
    make_autostart()
    sys.exit()

if config.ON_PI and os.geteuid() != 0:
    sys.exit("Run it with sudo (needed for the LED, Bluetooth and installing):  sudo python3 main.py")
install.install_libraries()
if not install.spi_ready():
    sys.exit("SPI (for the RFID reader) was off and is now turned on. Restart the Pi (sudo reboot) and run this again.")
install.download_models()

import threading                                   # noqa: E402

import cv2                                         # noqa: E402

import actions                                     # noqa: E402
import bluetooth                                   # noqa: E402
import buttons                                     # noqa: E402
import camera                                      # noqa: E402
import faces                                       # noqa: E402
import leds                                        # noqa: E402
import pairing                                     # noqa: E402
import people                                      # noqa: E402
import presence                                    # noqa: E402
import rfid                                        # noqa: E402
import server_link                                 # noqa: E402
import shared                                      # noqa: E402
import storage                                     # noqa: E402
import web                                         # noqa: E402

BOX_COLOURS = {"counted": (0, 220, 0), "still": (0, 140, 255), "ignored": (150, 150, 150)}


def draw(frame, labelled, owner_found):
    # Boxes for the setup page only (the picture never leaves this device)
    small = cv2.resize(frame, (640, 480))
    sx, sy = 640 / frame.shape[1], 480 / frame.shape[0]
    for box, status in labelled:
        cv2.rectangle(small, (int(box[0] * sx), int(box[1] * sy)), (int(box[2] * sx), int(box[3] * sy)), BOX_COLOURS[status], 2)
    text = "people " + str(sum(1 for _, s in labelled if s == "counted")) + ("  owner seen" if owner_found else "")
    cv2.putText(small, text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
    return cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()


# ---------- Thread: camera ----------
def camera_loop():
    samples = []
    last_count = None
    while True:
        start = time.time()
        frame = camera.take_picture() if config.USE_CAMERA else None
        if frame is None:
            time.sleep(5)
            continue
        try:
            count, labelled = people.count(frame)
            found = faces.find_faces(frame)
            with shared.lock:
                registering = shared.state["register_face"]
                owner = shared.state["owner"]

            owner_found = False
            if registering:
                # Registering: one face only, one photo per picture
                if len(found) == 1:
                    samples.append(faces.embed(frame, found[0]))
                with shared.lock:
                    shared.state["face_progress"] = len(samples)
                if len(samples) >= config.FACE_SAMPLES:
                    faces.save_owner(owner["id"], samples)
                    samples = []
                    with shared.lock:
                        shared.state["register_face"] = False
                    shared.add_event("face_registered", str(faces.photo_count()) + " photos")
                    shared.set_message("Face saved (" + str(faces.photo_count()) + " photos, only on this device).")
            else:
                samples = []
                score = faces.owner_score(frame, found)
                owner_found = score >= config.FACE_THRESHOLD and presence.face_counts()
                with shared.lock:
                    if owner_found:
                        shared.state["face_seen_at"] = time.time()
                        shared.state["face_streak"] += 1
                    else:
                        shared.state["face_streak"] = 0

            with shared.lock:
                shared.state["headcount"] = count
                shared.state["last_boxes"] = labelled
                shared.state["last_size"] = (frame.shape[1], frame.shape[0])
                if time.time() < shared.state["enrol_until"]:
                    shared.state["last_jpeg"] = draw(frame, labelled, owner_found)
                else:
                    shared.state["last_jpeg"] = None
            if count != last_count:
                if last_count is not None:
                    shared.add_event("headcount", str(count))
                    shared.go_fast()
                last_count = count
            presence.update()
        except Exception as error:
            shared.set_sensor("camera", "error: " + str(error))

        with shared.lock:
            fast = time.time() < shared.state["fast_until"] or shared.state["register_face"]
        wait = (0.3 if shared.state["register_face"] else config.FAST_PICTURE_SECONDS) if fast else config.PICTURE_SECONDS
        time.sleep(max(0.1, wait - (time.time() - start)))


# ---------- Thread: Bluetooth ----------
def bluetooth_loop():
    while True:
        with shared.lock:
            pairing = shared.state["pairing"]
        phones = [p["address"] for p in storage.load("cache.json", {}).get("phones", [])]
        if not pairing and phones and bluetooth.check():
            near = any(bluetooth.is_near(a) for a in phones)       # stops at the first one that answers
            with shared.lock:
                was = shared.state["phone_near"]
                shared.state["phone_near"] = near
                if near:
                    shared.state["phone_seen_at"] = time.time()
            if near != was:
                shared.add_event("phone", "near" if near else "away")
                shared.go_fast()
            presence.update()
        time.sleep(config.PHONE_CHECK_SECONDS if not config.SIMULATE else 2)


# ---------- Thread: report to the laptop, set the light ----------
def report_loop():
    last = 0.0
    while True:
        with shared.lock:
            due = shared.state["report_now"] or time.time() - last >= config.REPORT_SECONDS
            connected = shared.state["connected"]
        if not due:
            time.sleep(0.2)
            continue
        last = time.time()
        presence.update()
        with shared.lock:
            s = shared.state
            evidence = {"faculty_in": s["faculty_in"], "headcount": presence.headcount(), "phone_near": s["phone_near"],
                        "face_photos": faces.photo_count(), "sensors": dict(s["sensors"]), "button": s["button"],
                        "events": list(s["events"])}
            s["report_now"] = False
        ok, answer = server_link.report(evidence) if connected else (False, {})
        if not ok and answer.get("http_status") == 401:
            # The server no longer accepts our token (device reset on the server, or moved to another cabin):
            # forget it and go back to pairing. A device still linked to a cabin reconnects by itself.
            saved = storage.load("device.json", {})
            saved.pop("token", None)
            storage.save("device.json", saved)
            with shared.lock:
                shared.state["connected"] = False
            shared.set_message("The laptop no longer knows this device's key. Reconnecting...")
            connected = False
        with shared.lock:
            shared.state["server_ok"] = ok
            if ok:
                shared.state["events"] = shared.state["events"][len(evidence["events"]):]   # sent: forget them
                if shared.state["button"] == evidence["button"]:
                    shared.state["button"] = ""
                shared.state.update(status=answer["status"], reason=answer["reason"], until=answer["until"])
            else:
                shared.state["events"] = shared.state["events"][-200:]   # keep the newest while offline
            setup = shared.state["register_face"] or shared.state["link_card"] or shared.state["pairing"]
        if setup:
            leds.show("blue")
        elif ok:
            leds.show(answer.get("led", "red"))
        elif connected:
            leds.show(presence.local_status())                 # laptop not reachable: the device's own guess
        else:
            leds.show("blue")                                  # not connected to a cabin yet
        time.sleep(0.2)


# ---------- Thread: owner, cards and phones from the laptop ----------
def config_loop():
    while True:
        if shared.state["connected"]:
            if actions.sync_config():
                shared.set_sensor("server", "ok")
            else:
                shared.set_sensor("server", "error: can't reach " + server_link.server_url())
        time.sleep(config.CONFIG_SECONDS)


def start(name, target):
    threading.Thread(target=target, name=name, daemon=True).start()


def main():
    print("Smart Cabin cabin device" + (" (SIMULATION - no Pi hardware)" if config.SIMULATE else ""))
    device = storage.load("device.json", {})
    cached = storage.load("cache.json", {})
    with shared.lock:
        shared.state["connected"] = bool(device.get("token"))
        shared.state["cabin"] = device.get("cabin", "")
        shared.state["owner"] = cached.get("owner")
    if not shared.state["connected"]:
        print("Not connected yet: waiting for the admin to add this device (Cabins -> Add a new device), PIN", pairing.PIN)

    for part, use, begin in (("led", config.USE_LEDS, leds.start), ("rfid", config.USE_RFID, rfid.start),
                             ("bluetooth", config.USE_BLUETOOTH, bluetooth.start), ("buttons", config.USE_BUTTONS, buttons.start)):
        if not use:
            shared.set_sensor(part, "off (switched off in config.py)")
            continue
        try:
            begin()
        except Exception as error:
            shared.set_sensor(part, "error: " + str(error))

    start("camera", camera_loop)
    if config.USE_RFID and not config.SIMULATE and rfid.reader is not None:
        start("rfid", lambda: rfid.wait_for_cards(actions.card_tapped))
    if config.USE_BLUETOOTH:
        start("bluetooth", bluetooth_loop)
    if config.USE_BUTTONS and buttons.GPIO is not None:
        start("buttons", buttons.watch)
    start("report", report_loop)
    start("config", config_loop)
    start("pairing", pairing.pairing_loop)                     # connects by itself once the admin adds it
    try:
        web.serve()                                            # main thread: the setup page
    except KeyboardInterrupt:
        print("\nStopped.")
        leds.show("off")


if __name__ == "__main__":
    main()
