# Physical connection: SPI on, libraries installed, the reader answers, reads are stable.
# run() returns (reader, results). reader is None if the reader can't be used.
# results is a list of (check name, "PASS" / "FAIL").

import os
import time

RST_PIN = 25          # GPIO25 = physical pin 22
VERSION_REG = 0x37


def check_spi():
    if os.path.exists("/dev/spidev0.0"):
        print("  PASS  SPI is on (/dev/spidev0.0)")
        return "PASS"
    print("  FAIL  SPI is off. Turn it on:  sudo raspi-config nonint do_spi 0  then  sudo reboot")
    return "FAIL"


def check_libraries():
    missing = []
    for name in ["spidev", "RPi.GPIO", "mfrc522"]:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        print("  FAIL  missing libraries:", ", ".join(missing), "- see the install lines in main code.py")
        return "FAIL"
    print("  PASS  libraries: spidev, RPi.GPIO, mfrc522")
    return "PASS"


def check_answer(reader):
    version = reader.Read_MFRC522(VERSION_REG)
    if version in (0x00, 0xFF):
        print("  FAIL  no answer (got", hex(version) + "). Check 3.3V, GND, SDA, SCK, MOSI, MISO")
        return "FAIL", None
    print("  PASS  reader answers, chip version", hex(version))
    return "PASS", version


def check_stable(reader, version):
    bad = 0
    for _ in range(200):
        if reader.Read_MFRC522(VERSION_REG) != version:
            bad += 1
    if bad == 0:
        print("  PASS  200 of 200 reads stable")
        return "PASS"
    print("  FAIL ", bad, "of 200 reads wrong - loose wire or wires too long")
    return "FAIL"


def run():
    print("\n--- Test physical connection ---")
    results = [("SPI on", check_spi()), ("Libraries", check_libraries())]
    if "FAIL" in [result for _, result in results]:
        return None, results

    import RPi.GPIO as GPIO
    from mfrc522 import MFRC522
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    reader = MFRC522(pin_rst=RST_PIN)
    time.sleep(0.05)

    answer, version = check_answer(reader)
    results.append(("Reader answers", answer))
    if version is None:
        close()
        return None, results
    results.append(("Stable reads", check_stable(reader, version)))
    return reader, results


def close():
    import RPi.GPIO as GPIO
    GPIO.cleanup()
