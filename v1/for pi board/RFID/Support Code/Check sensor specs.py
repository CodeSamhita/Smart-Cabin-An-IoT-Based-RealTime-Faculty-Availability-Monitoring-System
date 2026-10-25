# Sensor specs: which chip it is, antenna and receiver gain, how fast it can be read.
# run() returns a list of (check name, "PASS" / "FAIL" / "INFO").

import time

TX_CONTROL_REG = 0x14
RF_CFG_REG = 0x26
VERSION_REG = 0x37

CHIPS = {0x88: "clone (FM17522)", 0x90: "NXP MFRC522 v0.0", 0x91: "NXP MFRC522 v1.0",
         0x92: "NXP MFRC522 v2.0", 0xB2: "clone (FM17522E)", 0x12: "clone (counterfeit chip)"}


def chip(reader):
    version = reader.Read_MFRC522(VERSION_REG)
    print("  INFO  chip:", hex(version), "=", CHIPS.get(version, "unknown chip"))
    return "INFO"


def antenna(reader):
    tx = reader.Read_MFRC522(TX_CONTROL_REG)
    gain_code = (reader.Read_MFRC522(RF_CFG_REG) >> 4) & 0x07
    gain_db = [18, 23, 18, 23, 33, 38, 43, 48][gain_code]
    if tx & 0x03 == 0x03:
        print("  PASS  antenna on, receiver gain", gain_db, "dB")
        return "PASS"
    print("  FAIL  antenna is off (TxControlReg =", hex(tx) + "), so no tag can be read")
    return "FAIL"


def read_speed(reader):
    start = time.time()
    for _ in range(200):
        reader.Read_MFRC522(VERSION_REG)
    print("  INFO  SPI speed:", round(200 / (time.time() - start)), "register reads per second")
    return "INFO"


def run(reader):
    print("\n--- Check sensor specs ---")
    results = [("Chip", chip(reader)), ("Antenna", antenna(reader)), ("SPI speed", read_speed(reader))]
    print("  INFO  frequency: 13.56 MHz (MIFARE / NTAG cards, not 125 kHz cards)")
    return results
