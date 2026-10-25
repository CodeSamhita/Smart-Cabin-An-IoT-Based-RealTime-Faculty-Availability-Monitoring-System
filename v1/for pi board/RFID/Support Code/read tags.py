# Read tags: live mode, shows each tag's full UID (4 or 7 bytes) and its type. Ctrl+C to stop.
# Warns when a card is left lying on the reader.

import time

LEFT_SECONDS = 5        # a card still there after this long was left on the reader
REMIND_SECONDS = 10     # repeat the warning this often until it is taken off
GONE_SECONDS = 1        # not seen for this long = taken off

CARD_TYPES = {0x00: "MIFARE Ultralight / NTAG (sticker, key tag)", 0x08: "MIFARE Classic 1K",
              0x09: "MIFARE Mini", 0x18: "MIFARE Classic 4K", 0x10: "MIFARE Plus 2K", 0x11: "MIFARE Plus 4K",
              0x20: "ISO 14443-4 card (DESFire, bank card, phone)", 0x28: "MIFARE Classic emulated (JCOP)"}


def to_hex(numbers):
    return " ".join(format(n, "02X") for n in numbers)


def first_part(reader):
    # First 5 UID bytes (4 + check byte), or None if no tag is there
    status, _ = reader.MFRC522_Request(reader.PICC_REQIDL)
    if status != reader.MI_OK:
        return None
    status, uid = reader.MFRC522_Anticoll()
    if status != reader.MI_OK:
        return None
    return uid


def second_part(reader):
    # Second half of a 7-byte UID (the mfrc522 library only asks for the first half)
    reader.Write_MFRC522(reader.BitFramingReg, 0x00)
    status, data, _ = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, [0x95, 0x20])
    if status == reader.MI_OK and len(data) == 5 and (data[0] ^ data[1] ^ data[2] ^ data[3]) == data[4]:
        return data
    return None


def select(reader, level, part):
    # Select the tag at this level (0x93 = first, 0x95 = second). Returns its SAK (type) byte, or None.
    command = [level, 0x70] + list(part)
    command += reader.CalulateCRC(command)
    status, data, bits = reader.MFRC522_ToCard(reader.PCD_TRANSCEIVE, command)
    if status == reader.MI_OK and bits == 0x18:
        return data[0]
    return None


def read_tag(reader):
    # Returns (full UID, SAK), or None. A first byte of 0x88 means the UID is 7 bytes long.
    part1 = first_part(reader)
    if not part1:
        return None
    sak = select(reader, 0x93, part1)
    if sak is None:
        return None
    if part1[0] != 0x88 or not (sak & 0x04):
        return list(part1[:4]), sak
    part2 = second_part(reader)
    if not part2:
        return None
    sak = select(reader, 0x95, part2)
    if sak is None:
        return None
    return list(part1[1:4]) + list(part2[:4]), sak


def reset_field(reader):
    # Antenna off and on: a tag already lying on the reader restarts and can be read again
    reader.AntennaOff()
    time.sleep(0.02)
    reader.AntennaOn()
    time.sleep(0.02)


def warn_left(uid):
    print("  ", time.strftime("%H:%M:%S"), " WARNING  card", to_hex(uid), "left on the reader, please take it off")


def card_already_there(reader):
    # Looks 5 times (one read can miss). Returns the tag lying on the reader, or None.
    for _ in range(5):
        reset_field(reader)
        tag = read_tag(reader)
        if tag:
            return tag
    return None


def run(reader):
    print("\n--- Read tags ---")
    print("  Tap a card or key tag. Ctrl+C to stop.")
    current_uid = None      # the card on the reader now
    placed_at = 0.0         # when it was put there
    last_seen = 0.0
    last_warning = None     # None = not warned yet

    tag = card_already_there(reader)
    if tag:
        current_uid = tag[0]
        placed_at = last_seen = time.time() - LEFT_SECONDS     # so it is warned about straight away
        print("  ", time.strftime("%H:%M:%S"), " UID", to_hex(current_uid).ljust(20), "was already on the reader")

    while True:
        reset_field(reader)                 # restart the card each time, so one lying still keeps answering
        tag = read_tag(reader)
        now = time.time()
        if tag:
            uid, sak = tag
            if uid != current_uid:          # a new tap (or a different card)
                current_uid, placed_at, last_warning = uid, now, None
                print("  ", time.strftime("%H:%M:%S"), " UID", to_hex(uid).ljust(20), CARD_TYPES.get(sak, hex(sak)))
            last_seen = now
            if now - placed_at >= LEFT_SECONDS and (last_warning is None or now - last_warning >= REMIND_SECONDS):
                warn_left(uid)
                last_warning = now
        elif current_uid and now - last_seen > GONE_SECONDS:
            if last_warning is not None:
                print("  ", time.strftime("%H:%M:%S"), " OK  card taken off the reader")
            current_uid, last_warning = None, None
        time.sleep(0.1)
