# RFID card registration: wait for a tap on the RC522 and keep the card's full UID (4 or 7 bytes).
# The reader is only asked while the page is waiting for a tap.
import os
import random
import time

import config
import shared
import storage


def open_reader():
    if not os.path.exists("/dev/spidev0.0"):
        raise RuntimeError("SPI is off (sudo raspi-config nonint do_spi 0, then reboot)")
    import RPi.GPIO as GPIO
    from mfrc522 import MFRC522
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    reader = MFRC522(pin_rst=config.RST_PIN)
    if reader.Read_MFRC522(0x37) in (0x00, 0xFF):    # chip version: no answer = not connected
        raise RuntimeError("RC522 doesn't answer - check the wiring")
    return reader


def select(reader, level, part):
    # Select the card at this level (0x93 = first, 0x95 = second). Returns its SAK byte, or None.
    command = [level, 0x70] + list(part)
    command += reader.CalulateCRC(command)
    status, data, bits = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, command)
    return data[0] if status == reader.MI_OK and bits == 0x18 else None


def read_uid(reader):
    # Returns the card's UID as text ("04 A2 1B 3C" or 7 bytes), or "" if no card.
    reader.AntennaOff()                        # restart the card, so one lying on the reader is read too
    time.sleep(0.02)
    reader.AntennaOn()
    time.sleep(0.02)
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return ""
    status, part1 = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return ""
    sak = select(reader, 0x93, part1)
    if sak is None:
        return ""
    uid = list(part1[:4])
    if part1[0] == 0x88 and sak & 0x04:        # 0x88 = "the UID goes on": a 7-byte UID (NTAG stickers, key tags)
        reader.Write_MFRC522(reader.BitFramingReg, 0x00)
        status, part2, _ = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, [0x95, 0x20])
        if status != reader.MI_OK or len(part2) != 5:
            return ""
        uid = list(part1[1:4]) + list(part2[:4])
    return " ".join(format(n, "02X") for n in uid)


def got_card(uid):
    # Called with the lock held, when a card was tapped during the card step
    shared.state["card_waiting"] = False
    owner = storage.card_owner(uid)
    if owner:
        shared.state["card_text"] = "card " + uid + " belongs to " + owner
        shared.say("Card " + uid + " is already registered to " + owner + ". Not kept.")
    else:
        shared.draft["card"] = uid
        shared.state["card_text"] = "card " + uid
        shared.say("Card " + uid + " recorded.")


def sim_tap():
    # --sim: the page's "Pretend a tap" button
    with shared.lock:
        if shared.state["card_waiting"]:
            got_card(" ".join(format(random.randrange(256), "02X") for _ in range(4)))


def reader_loop():
    if config.SIM:
        with shared.lock:
            shared.state.update(card_ok=True, card_text="simulated reader")
        return
    try:
        reader = open_reader()
    except Exception as error:
        with shared.lock:
            shared.state["card_text"] = "RFID not working: " + str(error)
        return
    with shared.lock:
        shared.state.update(card_ok=True, card_text="ready")
    while True:
        with shared.lock:
            waiting = shared.state["card_waiting"]
            if waiting and time.time() - shared.state["card_started"] > config.CARD_SECONDS:
                shared.state["card_waiting"] = waiting = False
                shared.state["card_text"] = "no card tapped"
                shared.say("No card tapped in " + str(config.CARD_SECONDS) + " s. Press Tap my card again.")
        if not waiting:
            time.sleep(0.3)
            continue
        uid = read_uid(reader)
        if uid:
            with shared.lock:
                if shared.state["card_waiting"]:
                    got_card(uid)
        time.sleep(0.15)
