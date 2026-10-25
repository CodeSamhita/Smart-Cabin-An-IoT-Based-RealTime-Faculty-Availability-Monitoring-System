# Device integrity: SPI write + read-back, the RST pin, and the chip's built-in self-test.
# run() returns a list of (check name, "PASS" / "FAIL" / "INFO").

import time

RST_PIN = 25
COMMAND_REG = 0x01
FIFO_DATA_REG = 0x09
FIFO_LEVEL_REG = 0x0A
MOD_WIDTH_REG = 0x24          # default 0x26 after reset, safe to write for testing
AUTO_TEST_REG = 0x36
VERSION_REG = 0x37

# Self-test result from the datasheet for the original NXP chips (clones give other numbers)
SELF_TEST_V1 = [0x00, 0xC6, 0x37, 0xD5, 0x32, 0xB7, 0x57, 0x5C, 0xC2, 0xD8, 0x7C, 0x4D, 0xD9, 0x70, 0xC7, 0x73,
                0x10, 0xE6, 0xD2, 0xAA, 0x5E, 0xA1, 0x3E, 0x5A, 0x14, 0xAF, 0x30, 0x61, 0xC9, 0x70, 0xDB, 0x2E,
                0x64, 0x22, 0x72, 0xB5, 0xBD, 0x65, 0xF4, 0xEC, 0x22, 0xBC, 0xD3, 0x72, 0x35, 0xCD, 0xAA, 0x41,
                0x1F, 0xA7, 0xF3, 0x53, 0x14, 0xDE, 0x7E, 0x02, 0xD9, 0x0F, 0xB5, 0x5E, 0x25, 0x1D, 0x29, 0x79]
SELF_TEST_V2 = [0x00, 0xEB, 0x66, 0xBA, 0x57, 0xBF, 0x23, 0x95, 0xD0, 0xE3, 0x0D, 0x3D, 0x27, 0x89, 0x5C, 0xDE,
                0x9D, 0x3B, 0xA7, 0x00, 0x21, 0x5B, 0x89, 0x82, 0x51, 0x3A, 0xEB, 0x02, 0x0C, 0xA5, 0x00, 0x49,
                0x7C, 0x84, 0x4D, 0xB3, 0xCC, 0xD2, 0x1B, 0x81, 0x5D, 0x48, 0x76, 0xD5, 0x71, 0x61, 0x21, 0xA9,
                0x86, 0x96, 0x83, 0x38, 0xCF, 0x9D, 0x5B, 0x6D, 0xDC, 0x15, 0xBA, 0x3E, 0x7D, 0x95, 0x3B, 0x2F]


def write_read_back(reader):
    old = reader.Read_MFRC522(MOD_WIDTH_REG)
    wrong = 0
    for value in [0x55, 0xAA, 0x00, 0xFF, 0x0F, 0xF0]:      # every bit as 0 and as 1
        reader.Write_MFRC522(MOD_WIDTH_REG, value)
        if reader.Read_MFRC522(MOD_WIDTH_REG) != value:
            wrong += 1
    reader.Write_MFRC522(MOD_WIDTH_REG, old)
    if wrong == 0:
        print("  PASS  write / read-back: 6 of 6 values came back the same")
        return "PASS"
    print("  FAIL  write / read-back:", wrong, "of 6 values wrong - check MOSI and MISO")
    return "FAIL"


def reset_pin(reader):
    import RPi.GPIO as GPIO
    reader.Write_MFRC522(MOD_WIDTH_REG, 0x55)       # change a register,
    GPIO.output(RST_PIN, GPIO.LOW)                  # reset the chip,
    time.sleep(0.05)
    GPIO.output(RST_PIN, GPIO.HIGH)
    time.sleep(0.05)
    after = reader.Read_MFRC522(MOD_WIDTH_REG)      # and it should be back to 0x26
    reader.MFRC522_Init()
    if after == 0x26:
        print("  PASS  RST pin: the reader reset when GPIO25 went low")
        return "PASS"
    print("  FAIL  RST pin: no reset (register", hex(after) + ") - check RST -> GPIO25 (pin 22)")
    return "FAIL"


def self_test(reader):
    version = reader.Read_MFRC522(VERSION_REG)
    reader.Write_MFRC522(COMMAND_REG, 0x0F)         # soft reset
    time.sleep(0.05)
    reader.Write_MFRC522(FIFO_LEVEL_REG, 0x80)      # empty the FIFO
    for _ in range(25):
        reader.Write_MFRC522(FIFO_DATA_REG, 0x00)
    reader.Write_MFRC522(COMMAND_REG, 0x01)         # copy 25 zero bytes to the internal buffer
    reader.Write_MFRC522(AUTO_TEST_REG, 0x09)       # self-test on
    reader.Write_MFRC522(FIFO_DATA_REG, 0x00)
    reader.Write_MFRC522(COMMAND_REG, 0x03)         # CalcCRC starts the test

    end = time.time() + 1
    while reader.Read_MFRC522(FIFO_LEVEL_REG) < 64 and time.time() < end:
        time.sleep(0.01)
    result = [reader.Read_MFRC522(FIFO_DATA_REG) for _ in range(64)]

    reader.Write_MFRC522(AUTO_TEST_REG, 0x00)       # self-test off, normal set-up again
    reader.MFRC522_Init()

    reference = {0x91: SELF_TEST_V1, 0x92: SELF_TEST_V2}.get(version)
    if reference is None:
        print("  INFO  self-test: no datasheet result for this chip (clone), can't compare - normal")
        return "INFO"
    if result == reference:
        print("  PASS  self-test: 64 of 64 bytes match the datasheet")
        return "PASS"
    same = sum(1 for a, b in zip(result, reference) if a == b)
    print("  FAIL  self-test:", same, "of 64 bytes match the datasheet")
    return "FAIL"


def run(reader):
    print("\n--- Verify device integrity ---")
    return [("Write / read-back", write_read_back(reader)),
            ("RST pin", reset_pin(reader)),
            ("Self-test", self_test(reader))]
