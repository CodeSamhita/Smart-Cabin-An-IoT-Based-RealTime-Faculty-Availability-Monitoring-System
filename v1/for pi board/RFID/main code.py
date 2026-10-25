# RFID (RC522) - main code. It only calls the files in "Support Code".
# Run on the Pi:  sudo python3 "main code.py"
#
# Wiring (GPIO number, physical pin in brackets). 3.3 V only, never 5 V:
#   SDA -> GPIO8 (24)   SCK -> GPIO11 (23)   MOSI -> GPIO10 (19)   MISO -> GPIO9 (21)
#   RST -> GPIO25 (22)  3.3V -> 3.3V (1)     GND -> GND (6)        IRQ -> not used
#
# Libraries (once):
#   sudo apt install -y python3-spidev python3-rpi-lgpio
#   sudo pip3 install mfrc522 --break-system-packages --no-deps

import importlib.util
import os
import sys

SUPPORT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Support Code")


def load(file_name):
    # The file names have spaces, so they can't be imported the normal way
    path = os.path.join(SUPPORT_FOLDER, file_name)
    spec = importlib.util.spec_from_file_location(file_name[:-3].replace(" ", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def has_fail(results):
    return "FAIL" in [result for _, result in results]


def summary(steps):
    # steps = list of (step name, results)
    print("\n========== Summary ==========")
    for step, results in steps:
        print(" ", "FAIL" if has_fail(results) else "PASS", " ", step)
        for name, result in results:
            print("       ", result.ljust(5), name)


def main():
    connection = load("test physical connection.py")
    specs = load("Check sensor specs.py")
    integrity = load("verify device integrity.py")
    tags = load("read tags.py")

    print("===== RFID reader (RC522) =====")
    reader, connection_results = connection.run()
    steps = [("Physical connection", connection_results)]
    if reader is None:
        summary(steps)
        print("\nStopped: fix the connection first.")
        return

    try:
        steps.append(("Sensor specs", specs.run(reader)))
        integrity_results = integrity.run(reader)
        steps.append(("Device integrity", integrity_results))
        summary(steps)

        if has_fail(integrity_results):
            print("\nRead tags skipped: the device integrity check failed. Fix it first.")
            return
        tags.run(reader)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        connection.close()


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Run this on the Raspberry Pi.")
    main()
