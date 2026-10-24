# RC522 RFID reader test - bare-bone, step by step.
# Run:  sudo python3 1_test_rfid.py
#
# Wiring (GPIO number, physical pin in brackets). 3.3 V only, never 5 V:
#   SDA -> GPIO8 (24)   SCK -> GPIO11 (23)   MOSI -> GPIO10 (19)   MISO -> GPIO9 (21)
#   RST -> GPIO25 (22)  3.3V -> 3.3V (1)     GND -> GND (6)        IRQ -> not used
#
# Libraries (once):
#   sudo apt install -y python3-spidev python3-rpi-lgpio
#   sudo pip3 install mfrc522 --break-system-packages --no-deps

import os
import sys
import time

RST_PIN = 25                  # GPIO25 = physical pin 22
CARD_WAIT_SECONDS = 30

# RC522 registers used here (from the MFRC522 datasheet)
COMMAND_REG = 0x01
FIFO_DATA_REG = 0x09
FIFO_LEVEL_REG = 0x0A
TX_CONTROL_REG = 0x14
MOD_WIDTH_REG = 0x24          # default value after reset = 0x26, safe to write for testing
RF_CFG_REG = 0x26
AUTO_TEST_REG = 0x36
VERSION_REG = 0x37

VERSIONS = {0x88: "clone (FM17522)", 0x90: "NXP MFRC522 v0.0", 0x91: "NXP MFRC522 v1.0",
            0x92: "NXP MFRC522 v2.0", 0xB2: "clone (FM17522E)", 0x12: "clone (counterfeit chip)"}

# Self-test result the datasheet gives for the original NXP chips (clones give other numbers)
SELF_TEST_V1 = [0x00, 0xC6, 0x37, 0xD5, 0x32, 0xB7, 0x57, 0x5C, 0xC2, 0xD8, 0x7C, 0x4D, 0xD9, 0x70, 0xC7, 0x73,
                0x10, 0xE6, 0xD2, 0xAA, 0x5E, 0xA1, 0x3E, 0x5A, 0x14, 0xAF, 0x30, 0x61, 0xC9, 0x70, 0xDB, 0x2E,
                0x64, 0x22, 0x72, 0xB5, 0xBD, 0x65, 0xF4, 0xEC, 0x22, 0xBC, 0xD3, 0x72, 0x35, 0xCD, 0xAA, 0x41,
                0x1F, 0xA7, 0xF3, 0x53, 0x14, 0xDE, 0x7E, 0x02, 0xD9, 0x0F, 0xB5, 0x5E, 0x25, 0x1D, 0x29, 0x79]
SELF_TEST_V2 = [0x00, 0xEB, 0x66, 0xBA, 0x57, 0xBF, 0x23, 0x95, 0xD0, 0xE3, 0x0D, 0x3D, 0x27, 0x89, 0x5C, 0xDE,
                0x9D, 0x3B, 0xA7, 0x00, 0x21, 0x5B, 0x89, 0x82, 0x51, 0x3A, 0xEB, 0x02, 0x0C, 0xA5, 0x00, 0x49,
                0x7C, 0x84, 0x4D, 0xB3, 0xCC, 0xD2, 0x1B, 0x81, 0x5D, 0x48, 0x76, 0xD5, 0x71, 0x61, 0x21, 0xA9,
                0x86, 0x96, 0x83, 0x38, 0xCF, 0x9D, 0x5B, 0x6D, 0xDC, 0x15, 0xBA, 0x3E, 0x7D, 0x95, 0x3B, 0x2F]

CARD_TYPES = {0x00: "MIFARE Ultralight / NTAG (sticker, key tag)", 0x08: "MIFARE Classic 1K",
              0x09: "MIFARE Mini", 0x18: "MIFARE Classic 4K", 0x10: "MIFARE Plus 2K", 0x11: "MIFARE Plus 4K",
              0x20: "ISO 14443-4 card (DESFire, bank card, phone)", 0x28: "MIFARE Classic emulated (JCOP)"}

DEFAULT_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

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


def to_hex(numbers):
    return " ".join(format(n, "02X") for n in numbers)


# ---------- Connection checks ----------
def check_spi():
    step("SPI turned on?")
    if os.path.exists("/dev/spidev0.0"):
        passed("SPI", "/dev/spidev0.0 exists")
        return True
    failed("SPI", "SPI is off. Turn it on:  sudo raspi-config nonint do_spi 0  then  sudo reboot")
    return False


def check_libraries():
    step("Libraries installed?")
    missing = []
    for module in ["spidev", "RPi.GPIO", "mfrc522"]:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        failed("Libraries", "missing: " + ", ".join(missing) + " - see the install lines at the top of this file")
        return False
    passed("Libraries", "spidev, RPi.GPIO, mfrc522")
    return True


def check_version(reader):
    step("Reader answers? (reads the chip version)")
    version = reader.Read_MFRC522(VERSION_REG)
    if version in (0x00, 0xFF):
        failed("Connection", "got " + hex(version) + " = no answer. Check 3.3V, GND, SDA, SCK, MOSI, MISO "
               "and that no solder joins two pins")
        return None
    passed("Connection", "chip version " + hex(version) + " = " + VERSIONS.get(version, "unknown chip"))
    return version


# ---------- Reader checks ----------
def check_write_read(reader):
    step("SPI write + read back (tests MOSI and MISO both ways)")
    old = reader.Read_MFRC522(MOD_WIDTH_REG)
    errors = []
    for value in [0x55, 0xAA, 0x00, 0xFF, 0x0F, 0xF0]:      # every bit as 0 and as 1
        reader.Write_MFRC522(MOD_WIDTH_REG, value)
        back = reader.Read_MFRC522(MOD_WIDTH_REG)
        if back != value:
            errors.append("wrote " + hex(value) + " read " + hex(back))
    reader.Write_MFRC522(MOD_WIDTH_REG, old)
    if errors:
        failed("Write / read", ", ".join(errors))
    else:
        passed("Write / read", "6 of 6 values came back the same")


def check_stability(reader, version):
    step("Stable connection? (reads the version 500 times)")
    bad = 0
    start = time.time()
    for _ in range(500):
        if reader.Read_MFRC522(VERSION_REG) != version:
            bad += 1
    seconds = time.time() - start
    speed = str(round(500 / seconds)) + " reads/s"
    if bad == 0:
        passed("Stability", "500 of 500 correct, " + speed)
    else:
        failed("Stability", str(bad) + " of 500 wrong - loose wire or wires too long, " + speed)


def check_reset_pin(reader, GPIO):
    step("RST pin works? (GPIO25 -> RST)")
    reader.Write_MFRC522(MOD_WIDTH_REG, 0x55)       # change a register...
    GPIO.output(RST_PIN, GPIO.LOW)                  # ...pull RST low = reset...
    time.sleep(0.05)
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.05)
    after = reader.Read_MFRC522(MOD_WIDTH_REG)      # ...and it should be back to the default 0x26
    reader.MFRC522_Init()
    if after == 0x26:
        passed("RST pin", "reader reset when GPIO25 went low")
    else:
        failed("RST pin", "reader did not reset (register still " + hex(after) + ") - check RST -> GPIO25 (pin 22)")


def check_antenna(reader):
    step("Antenna on and RF gain")
    tx = reader.Read_MFRC522(TX_CONTROL_REG)
    gain_code = (reader.Read_MFRC522(RF_CFG_REG) >> 4) & 0x07
    gain_db = [18, 23, 18, 23, 33, 38, 43, 48][gain_code]
    if tx & 0x03 == 0x03:
        passed("Antenna", "antenna on, receiver gain " + str(gain_db) + " dB")
    else:
        failed("Antenna", "antenna is off (TxControlReg = " + hex(tx) + ")")


def check_self_test(reader, version):
    step("Chip self-test (built into the RC522)")
    reader.Write_MFRC522(COMMAND_REG, 0x0F)         # soft reset
    time.sleep(0.05)
    reader.Write_MFRC522(FIFO_LEVEL_REG, 0x80)      # empty the FIFO
    for _ in range(25):
        reader.Write_MFRC522(FIFO_DATA_REG, 0x00)
    reader.Write_MFRC522(COMMAND_REG, 0x01)         # Mem: copy 25 zero bytes to the internal buffer
    reader.Write_MFRC522(AUTO_TEST_REG, 0x09)       # switch on self-test
    reader.Write_MFRC522(FIFO_DATA_REG, 0x00)
    reader.Write_MFRC522(COMMAND_REG, 0x03)         # CalcCRC starts the test

    end = time.time() + 1
    while reader.Read_MFRC522(FIFO_LEVEL_REG) < 64 and time.time() < end:
        time.sleep(0.01)
    result = [reader.Read_MFRC522(FIFO_DATA_REG) for _ in range(64)]

    reader.Write_MFRC522(AUTO_TEST_REG, 0x00)       # self-test off, set the reader up normally again
    reader.MFRC522_Init()

    print("    First bytes:", to_hex(result[:16]))
    reference = {0x91: SELF_TEST_V1, 0x92: SELF_TEST_V2}.get(version)
    if reference is None:
        info("Self-test", "no reference result for this chip (clone), so it can't be compared - this is normal")
    elif result == reference:
        passed("Self-test", "64 of 64 bytes match the datasheet")
    else:
        same = sum(1 for a, b in zip(result, reference) if a == b)
        failed("Self-test", str(same) + " of 64 bytes match the datasheet")


# ---------- Card checks ----------
def read_card(reader):
    # Returns the first 5 UID bytes (4 + check byte), or None if no card is on the reader
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return None
    status, uid = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return None
    return uid


def anticoll_level2(reader):
    # Second half of a 7-byte UID (the mfrc522 library only asks for the first half)
    reader.Write_MFRC522(reader.BitFramingReg, 0x00)
    status, data, _ = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, [0x95, 0x20])
    if status == reader.MI_OK and len(data) == 5 and (data[0] ^ data[1] ^ data[2] ^ data[3]) == data[4]:
        return data
    return None


def select(reader, level, part):
    # Select the card at this level (0x93 = first, 0x95 = second). Returns its SAK byte, or None.
    command = [level, 0x70] + list(part)
    command += reader.CalulateCRC(command)
    status, data, bits = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, command)
    if status == reader.MI_OK and bits == 0x18:
        return data[0]
    return None


def read_full_card(reader):
    # Returns (first 5 bytes, full UID 4 or 7 bytes, SAK), or None.
    # A first byte of 0x88 means "the UID goes on": 7-byte UID (NTAG stickers, Ultralight key tags).
    part1 = read_card(reader)
    if not part1:
        return None
    sak = select(reader, 0x93, part1)
    if sak is None:
        return None
    if part1[0] != 0x88 or not (sak & 0x04):
        return part1, list(part1[:4]), sak
    part2 = anticoll_level2(reader)
    if not part2:
        return None
    sak = select(reader, 0x95, part2)
    if sak is None:
        return None
    return part1, list(part1[1:4]) + list(part2[:4]), sak


def reset_field(reader):
    # Antenna off and on again: the card restarts, so it can be read again
    reader.AntennaOff()
    time.sleep(0.02)
    reader.AntennaOn()
    time.sleep(0.02)


def wait_for_card(reader):
    step("Card read - tap a card or key tag (waiting " + str(CARD_WAIT_SECONDS) + " s)")
    end = time.time() + CARD_WAIT_SECONDS
    last_reset = 0.0
    while time.time() < end:
        if time.time() - last_reset > 1:
            reset_field(reader)                     # wakes a card that was already lying on the reader
            last_reset = time.time()
        card = read_full_card(reader)
        if card:
            return card
        time.sleep(0.05)
    failed("Card read", "no card seen. Hold it flat on the reader. The RC522 only reads 13.56 MHz cards, "
           "not 125 kHz ones")
    return None


def check_card(reader, card):
    part1, uid, sak = card
    check_byte_ok = (part1[0] ^ part1[1] ^ part1[2] ^ part1[3]) == part1[4]
    text = "UID " + to_hex(uid) + " (" + str(len(uid)) + " bytes)"
    if check_byte_ok:
        passed("Card read", text + ", check byte correct")
    else:
        failed("Card read", text + " but check byte wrong - bad read, try again")

    step("Card type")
    info("Card type", "SAK " + hex(sak) + " = " + CARD_TYPES.get(sak, "unknown type"))

    if sak in (0x08, 0x18, 0x09):
        step("Read card memory (sector 0, default key FF FF FF FF FF FF)")
        if reader.MFRC522_Auth(reader.PICC_AUTHENT1A, 3, DEFAULT_KEY, part1) != reader.MI_OK:
            info("Card memory", "card uses its own key, so its memory can't be read (normal for ID cards)")
        else:
            for block in range(4):
                data = reader.MFRC522_Read(block)
                print("    Block", block, ":", to_hex(data) if data else "can't read")
            passed("Card memory", "sector 0 read (block 0 = maker data, block 3 = keys)")
        reader.MFRC522_StopCrypto1()


def check_read_rate(reader):
    step("Read rate - keep the card on the reader for 5 s")
    input("    Put the card on the reader and press Enter...")
    good = tries = 0
    end = time.time() + 5
    while time.time() < end:
        reset_field(reader)
        tries += 1
        if read_card(reader):
            good += 1
    percent = round(100 * good / tries) if tries else 0
    text = str(good) + " of " + str(tries) + " reads worked (" + str(percent) + " %)"
    if percent >= 90:
        passed("Read rate", text)
    else:
        failed("Read rate", text + " - hold the card still and flat, close to the reader")


def live_mode(reader):
    print()
    print("Live mode: tap cards to see their UID. Ctrl+C to stop.")
    reset_field(reader)                             # so a card still lying on the reader shows too
    last_uid, last_time = None, 0.0
    while True:
        card = read_full_card(reader)
        if card:
            _, uid, sak = card
            if uid != last_uid or time.time() - last_time > 2:
                print("   ", time.strftime("%H:%M:%S"), " UID", to_hex(uid).ljust(20), CARD_TYPES.get(sak, hex(sak)))
            last_uid, last_time = uid, time.time()
        time.sleep(0.1)


# ---------- Main ----------
def main():
    print("RC522 RFID reader test")

    if not check_spi() or not check_libraries():
        summary()
        return

    import RPi.GPIO as GPIO
    from mfrc522 import MFRC522
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)                          # so RST_PIN means GPIO25
    reader = MFRC522(pin_rst=RST_PIN)

    try:
        version = check_version(reader)
        if version is None:
            summary()
            return
        check_write_read(reader)
        check_stability(reader, version)
        check_reset_pin(reader, GPIO)
        check_antenna(reader)
        check_self_test(reader, version)

        card = wait_for_card(reader)
        if card:
            check_card(reader, card)
            check_read_rate(reader)
        summary()
        live_mode(reader)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    if sys.platform != "linux":
        sys.exit("Run this on the Raspberry Pi.")
    main()
