# Smart Cabin edge device - Step 1: register users (face, RFID card, Bluetooth device).
#
# Run on the Pi:   sudo python3 main.py           then open http://<pi>:8000
# Run anywhere:    python3 main.py --sim          no hardware, everything is pretended
#
# Threads: camera (face photos), RFID reader, Bluetooth guard, and the web page.
# Saved in data/: users.csv, devices.csv, faces/<user_id>.npy
#
# Libraries (once):  sudo apt install -y python3-picamera2 python3-opencv python3-numpy python3-spidev python3-rpi-lgpio bluez bluez-tools
#                    sudo pip3 install mfrc522 --break-system-packages --no-deps
import os
import sys
import threading

import config


def main():
    if not config.SIM:
        if sys.platform != "linux":
            sys.exit("Run this on the Raspberry Pi, or add --sim to try the page without hardware.")
        if os.geteuid() != 0:
            print("Note: not running with sudo, so the RC522 and Bluetooth may not work. Use: sudo python3 main.py")

    import bluetooth
    import face
    import rfid
    import web

    threading.Thread(target=face.camera_loop, daemon=True).start()
    threading.Thread(target=rfid.reader_loop, daemon=True).start()
    if bluetooth.start() and not config.SIM:
        threading.Thread(target=bluetooth.guard_loop, daemon=True).start()
    try:
        web.serve()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
