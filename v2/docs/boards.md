# Boards: Raspberry Pi Zero 2W, Pi 4, Pi 5

[← back to the v2 README](../README.md)

The v2 device app runs on all three. It notices the board by itself (`settings.BOARD`) and sets its timings.

## Measured on our boards

| | Pi Zero 2W (512 MB) | Pi 4 (4 GB) |
|---|---|---|
| Face check, one 640x480 picture (YuNet + SFace) | 354 ms | 161 ms |
| Sustained face recognition (60 s) | 1.9 pictures/s | 5.4 pictures/s |
| Temperature after 60 s of load | 67 °C, still rising | 59 °C, steady |
| v2 vision round on the real cabin (Oct 2026) | 4–8 s | not measured yet |
| Memory with the desktop on | ran out (swapping, then the app was killed) | plenty |
| Wi-Fi | 2.4 GHz only | 2.4 + 5 GHz |

Benchmarks: `pi board codes/Tried and working codes now on actual project/benchmark_results.md`.

**What we saw on the Zero 2W with the full v2 app:** it works (registration, face, card, headcount, server link), but
it is at its limit. With the desktop on, it ran out of memory and the kernel stopped the app; without the desktop it
runs, with about 100 MB to spare. CPU use is high while the camera runs.

## Which board

| | Zero 2W | Pi 4 (2 / 4 GB) | **Pi 5 (4 GB) - chosen** |
|---|---|---|---|
| Speed | enough for 1 picture every 5 s | 2–3× the Zero | about 2× a Pi 4 |
| Memory | 512 MB - tight | plenty | plenty |
| Size | smallest | credit card | credit card |
| Power | 5 V 2.5 A | 5 V 3 A | **5 V 5 A** (official supply) |
| Camera cable | Zero cable | standard 15-pin | **22-pin to 15-pin cable** |
| NeoPixel library | rpi_ws281x (GPIO18) | rpi_ws281x (GPIO18) | **pi5neo on SPI1 (GPIO20)** - rpi_ws281x does not work |
| RC522 (spidev + RPi.GPIO through rpi-lgpio) | works | works | works |
| picamera2, OpenCV, models | work | work | work |
| Cooling | heatsink | heatsink | **active cooler** recommended |
| Future projects | – | ok | best (also has a PCIe slot for an AI accelerator) |

**Decision (25 Oct 2026, user):** Raspberry Pi 5, 4 GB, also because it leaves room for future projects. The code is
ready for it; nothing has been run on a Pi 5 yet.

## Wiring

| Part | Zero 2W / Pi 4 | Pi 5 |
|---|---|---|
| RC522 | SDA GPIO8 (24), SCK GPIO11 (23), MOSI GPIO10 (19), MISO GPIO9 (21), RST GPIO25 (22), 3.3 V (1), GND (6) | same |
| NeoPixel DIN | GPIO18 (pin 12) | **GPIO20 (pin 38)** - SPI1 MOSI |
| NeoPixel 5 V / GND | pin 2 / pin 14 | pin 2 / pin 14 |
| Camera | ribbon in the CAMERA port | CAM port with the 22-pin cable |

On a Pi 5 the installer adds `dtoverlay=spi1-1cs` to `/boot/firmware/config.txt` (one reboot) and installs `pi5neo`
instead of `rpi_ws281x`.

## Settings that follow the board

| Setting | Zero 2W | Pi 4 / Pi 5 |
|---|---|---|
| Headcount picture every | 5 s (1.5 s after a change) | 2 s (1 s after a change) |
| Live view | 5 pictures / s | 10 pictures / s |
| People model | MobileNet-SSD | YOLOv8n (if `models/yolov8n.onnx` is there) |
