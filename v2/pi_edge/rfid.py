# Smart Cabin edge device - the RC522 card reader (same tested code as v1 RFID and hardware test 1).
#   loop(on_tap): thread. Calls on_tap(card_id) once each time a card is put on the reader.
#                 Card ids are 8 hex characters (4-byte cards) or 14 (7-byte NTAG / key tags).
#                 A card left on the reader is reported (warning on the page, LED blinks).
#                 Checks every 5 s that the reader still answers; reports PROBLEM if not.
# In simulation, cards are "tapped" with the box on the device's page (sim_tap).

import queue
import time

import settings
import shared

reader = None
sim_taps = queue.Queue()


def start():
    global reader
    if settings.SIMULATE:
        shared.set_part("rfid", False, "no card reader on this computer (" + settings.COMPUTER
                        + ") - use the 'Tap card' box on the device page", present=False)
        return
    import RPi.GPIO as GPIO
    from mfrc522 import MFRC522
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    reader = MFRC522(pin_rst=settings.RFID_RST_PIN)


def answers():
    version = reader.Read_MFRC522(0x37)
    if version in (0x00, 0xFF):
        shared.set_part("rfid", False, "the reader does not answer - check SDA, SCK, MOSI, MISO, RST and 3.3 V")
        return False
    shared.set_part("rfid", True, "RC522 version " + hex(version))
    return True


def select(level, part):
    command = [level, 0x70] + list(part)
    command += reader.CalulateCRC(command)
    status, data, bits = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, command)
    return data[0] if status == reader.MI_OK and bits == 0x18 else None


def read_card():
    # The card on the reader as "A1B2C3D4" (or 14 characters), or None
    reader.AntennaOff()                                   # restart the field, so a card lying still answers again
    time.sleep(0.02)
    reader.AntennaOn()
    time.sleep(0.02)
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return None
    status, part1 = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return None
    sak = select(0x93, part1)
    if sak is None:
        return None
    if part1[0] != 0x88 or not (sak & 0x04):
        return "".join("%02X" % b for b in part1[:4])
    reader.Write_MFRC522(reader.BitFramingReg, 0x00)      # 0x88 = the id goes on: ask for the second half
    status, part2, _ = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, [0x95, 0x20])
    if status != reader.MI_OK or len(part2) != 5 or select(0x95, part2) is None:
        return None
    return "".join("%02X" % b for b in list(part1[1:4]) + list(part2[:4]))


def sim_tap(card_id):
    sim_taps.put(card_id.strip().upper())


def loop(on_tap, on_left):
    current, placed_at, last_seen, last_check, warned = None, 0.0, 0.0, 0.0, False
    while True:
        try:
            if settings.SIMULATE:
                on_tap(sim_taps.get())
                continue
            if reader is None:
                start()
            now = time.time()
            if now - last_check > 5:
                last_check = now
                if not answers():
                    time.sleep(2)
                    continue
            card = read_card()
            now = time.time()
            if card:
                if card != current:                       # a new tap
                    current, placed_at, warned = card, now, False
                    on_tap(card)
                last_seen = now
                if not warned and now - placed_at > settings.CARD_LEFT_SECONDS:
                    warned = True
                    shared.update(card_warning="a card is lying on the reader - please take it off")
                    on_left(card)
            elif current and now - last_seen > 1:          # unseen for 1 s = taken off
                current = None
                shared.update(card_warning="")
            time.sleep(0.1)
        except Exception as problem:
            shared.set_part("rfid", False, str(problem))
            shared.error("rfid", problem)
            time.sleep(2)
