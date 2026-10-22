# Board specs – Smart Cabin Pis

There are **two boards**. Both specs were recorded on 2026-10-22 with `python3 pi_system_info.py`.

## Side by side

| Item | Board 1: Pi 4 | Board 2: Pi Zero 2W |
|---|---|---|
| Model | Raspberry Pi 4 Model B Rev 1.5 | Raspberry Pi Zero 2 W Rev 1.0 |
| Serial | 10000000b76e9a42 | 0000000011933149 |
| CPU | 4 cores, max 1800 MHz | 4 cores, max 1000 MHz |
| RAM | 3.7 GB (4 GB board) | **415 MB (512 MB board)** |
| GPU memory | 76 MB | 64 MB |
| Swap | 2.0 GB | 415 MB |
| SD card | 28.7 GB, 8.4 GB used | 28.7 GB, 6.6 GB used |
| OS | Debian 13 trixie 64-bit (desktop) | Debian 13 trixie 64-bit (desktop) |
| Kernel / Python | 6.18.50+rpt-rpi-v8 / 3.13.5 | 6.18.50+rpt-rpi-v8 / 3.13.5 |
| Hostname | `pi` | `pi` (**same name**) |
| IP / Wi-Fi | 192.168.137.72 on laptop hotspot `ROG-StrixG16` | 192.168.137.72 on laptop hotspot `ROG-StrixG16` |
| Camera | imx219 (Camera v2) | imx219 (Camera v2) |
| SPI / I2C / Bluetooth | enabled / disabled / on | enabled / disabled / on |
| Power supply needed | 5 V 3 A USB-C | 5 V 2.5 A micro-USB |
| Suggested `FPS` in `smartcabin_pi.py` | 6 (5–10) | 2–3 |

## Benchmark results (`pi_benchmark.py`)

Still to run on both boards. Stop `smartcabin_pi.py`, keep `pi_receiver.py` running on the laptop, then run `python3 pi_benchmark.py`. Paste the SUMMARY block here.

| Measure | Pi 4 | Pi Zero 2W |
|---|---|---|
| Camera 640x480 (pictures/s) | – | – |
| Detect / embed / whole frame at 640x480 (ms) | – | – |
| Whole frame at 320x240 (ms) | – | – |
| Sustained FPS (60 s) | – | – |
| Max temperature / throttled | – | – |
| RAM for models / RAM free (MB) | – | – |
| Send to laptop (ms) | – | – |
| Suggested FPS | – | – |
| Arrive → laptop page, worst case (s) | – | – |

For comparison, the Windows laptop gave about 16 ms for a whole 640x480 frame (≈ 60 FPS) and 5 ms to send to the receiver.

## Board 1 – Raspberry Pi 4 Model B (recorded 12:43, 6 min after boot)

| Item | Value |
|---|---|
| CPU at the time | 21 % use, load 0.12 / 0.34 / 0.19, 700 MHz idle, 57.9 °C |
| RAM | 598.9 MB used of 3.7 GB (16 %); swap unused |
| Power | OK (`throttled=0x0`), core 0.86 V |
| Wi-Fi signal | −40 dBm (good) |
| Busiest program | `python3` (PID 1893) at 112 % CPU, 7.8 % RAM – most likely `smartcabin_pi.py` |

## Board 2 – Raspberry Pi Zero 2 W (recorded 12:57, 1 min after boot)

| Item | Value |
|---|---|
| CPU at the time | 0 % use, load 1.83 / 0.81 / 0.30 (still starting up), 1000 MHz, 41.9 °C |
| RAM | **224.6 MB used of 415.1 MB (54 %)** with only the desktop running; **swap already in use, 114.3 MB (28 %)** |
| Power | OK (`throttled=0x0`), core 1.26 V |
| Wi-Fi signal | −44 dBm (good) |
| Biggest programs | the desktop: wf-panel-pi 8.7 %, pcmanfm 8.5 %, packagekitd 5.8 %, xdg-desktop-portal 3.4 %; then `python3` 3.0 % |

## What this means for the project

- **Pi 4:** it has plenty of power for `smartcabin_pi.py`. Keep `FPS = 6`.
- **Zero 2W:** memory is the limit.
  - The desktop alone uses over half the RAM, and it's already swapping one minute after boot. Swapping to the SD card is slow and wears the card.
  - Before running face recognition on it, switch it to boot to the console instead of the desktop:

        sudo raspi-config nonint do_boot_behaviour B1
        sudo reboot

    This frees roughly 100 MB. The Lite OS would free even more.
  - Set `FPS = 2` or `3` in `smartcabin_pi.py` on this board.
  - Power: use a good 5 V 2.5 A supply, and power the LEDs separately.
- **Both boards are called `pi`, and both show up as `pi.local`.**
  - If both are on at the same time, mDNS renames one to `pi-2.local`, and SSH may reach the wrong board.
  - `pi_sender.py` sends the hostname as the device name, so the laptop's receiver would **mix both boards into one card**.
  - Give them different names (then reboot), for example:

        sudo raspi-config nonint do_hostname cabin-pi4      (on the Pi 4)
        sudo raspi-config nonint do_hostname cabin-zero     (on the Zero 2W)

- Both show the same IP (192.168.137.72) because they were used one at a time, and the laptop hotspot gave the same address. If they're on together, they'll get different IPs, which is another reason to use mDNS names instead of IPs.
- Both have the camera connected and SPI on, and the wiring in `README.md` is the same on both (same 40-pin header).
