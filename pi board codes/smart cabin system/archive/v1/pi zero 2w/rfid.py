# Smart Cabin cabin device - the RC522 RFID card reader (same tested code as hardware test 1).
# Reads full card ids: 4 bytes for most cards, 7 bytes for NTAG stickers / Ultralight key tags.

import time

import config
import shared

reader = None
GPIO = None


def start():
    global reader, GPIO
    if config.SIMULATE:
        shared.set_sensor("rfid", "ok (simulated: use 'Tap card' on the page)")
        return
    import RPi.GPIO as gpio
    from mfrc522 import MFRC522
    GPIO = gpio
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)                               # so RFID_RST_PIN means GPIO25
    reader = MFRC522(pin_rst=config.RFID_RST_PIN)


def check():
    # The RC522 has a version number inside. If we can't read it, the reader is not connected.
    if config.SIMULATE:
        return True
    version = reader.Read_MFRC522(0x37)
    if version in (0x00, 0xFF):
        shared.set_sensor("rfid", "error: not responding - check the wires and 3.3 V")
        return False
    shared.set_sensor("rfid", "ok")
    return True


def _select(level, part):
    command = [level, 0x70] + list(part)
    command += reader.CalulateCRC(command)
    status, data, bits = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, command)
    return data[0] if status == reader.MI_OK and bits == 0x18 else None


def read_card():
    # Returns the card id like "A1B2C3D4" (or 14 characters for 7-byte ids), or None
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return None
    status, part1 = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return None
    sak = _select(0x93, part1)
    if sak is None:
        return None
    if part1[0] != 0x88 or not (sak & 0x04):
        return "".join("%02X" % b for b in part1[:4])
    # 0x88 = "the id goes on": ask for the second half
    reader.Write_MFRC522(reader.BitFramingReg, 0x00)
    status, part2, _ = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, [0x95, 0x20])
    if status != reader.MI_OK or len(part2) != 5:
        return None
    return "".join("%02X" % b for b in list(part1[1:4]) + list(part2[:4]))


def wait_for_cards(on_card):
    # Thread: calls on_card(card_id) once per tap, checks the reader every 5 s
    last_card, last_time, last_check = None, 0.0, 0.0
    while True:
        if config.SIMULATE:
            time.sleep(1)
            continue
        try:
            if time.time() - last_check > 5:
                last_check = time.time()
                if not check():
                    time.sleep(2)
                    continue
            card = read_card()
            if card and (card != last_card or time.time() - last_time > config.CARD_REPEAT_SECONDS):
                on_card(card)
            if card:
                last_card, last_time = card, time.time()
        except Exception as error:
            shared.set_sensor("rfid", "error: " + str(error))
            time.sleep(2)
        time.sleep(0.1)
