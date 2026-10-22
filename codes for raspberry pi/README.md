# Codes for Raspberry Pi

| File | Runs on | What it does |
|---|---|---|
| `smartcabin_pi.py` | Pi | Face, RFID, Bluetooth, buttons, LEDs, hardware check, web page (port 8000) |
| `pi_sender.py` | Pi | Finds the laptop by mDNS and sends it the status every 2 s |
| `board_specs.md` | – | Specs of both boards: **Raspberry Pi 4 Model B (4 GB)** and **Pi Zero 2 W (512 MB)**, both trixie 64-bit with Camera v2. Both are named `pi` - rename one |
| `pi_system_info.py` | Pi | System report: model, OS, uptime, CPU use / speed / temperature, RAM, SD card, power (under-voltage), Wi-Fi signal, camera, SPI, I2C, Bluetooth, top processes. `--watch 5` refreshes, `--json` gives JSON. Standard library only |
| `pi_benchmark.py` | Pi | Benchmark using the real project code: camera FPS, face steps (detect / embed / match / JPEG) at 640x480 and 320x240, model RAM, 60 s sustained FPS + temperature + throttling, send time to the laptop (mDNS), update-delay estimate, suggested FPS. Saves `benchmarks/*.json`. Needs `smartcabin_pi.py` and `pi_sender.py` in the same folder; stop `smartcabin_pi.py` first |
| `../code/pi_receiver.py` | Laptop | Announces the laptop by mDNS, receives from one or more Pis, page on port 8500, saves `data/pi_status.json` |

## Sending data from the Pi to the laptop (mDNS)

1. **Laptop:**

       python code/pi_receiver.py

   The first time, Windows asks to allow Python on the network. Allow it on **Private** networks. Then open http://localhost:8500
2. **Pi**, in a second SSH window (`smartcabin_pi.py` keeps running in the first):

       cd ~/smartcabin && nano pi_sender.py     (paste, Ctrl+O, Enter, Ctrl+X)
       python3 pi_sender.py

How it works:

- The laptop announces the mDNS service `_smartcabin._tcp` with all its IP addresses and port 8500.
- The Pi listens for it and picks the laptop address on its own network. If the laptop's IP changes, the Pi finds it again.
- Every 2 s the Pi reads `http://localhost:8000/status.json` and POSTs it to the laptop with the header `X-Token`. The token must match in both files (`TOKEN = "smartcabin-2026"`).
- A Pi that sends nothing for 15 s shows as **OFFLINE**. If `smartcabin_pi.py` stops, the Pi still sends "app not running".
- Both must be on the same Wi-Fi or LAN. Some college / guest Wi-Fi networks block mDNS between devices. A phone hotspot or the laptop's Mobile Hotspot works.

---

`smartcabin_pi.py` does:

- **Face recognition**: the camera, the same steps as `face_app.py`, and register/delete from the web page
- **RFID**: an RC522 reader. Tap a card to check in, tap again to check out
- **Bluetooth phones**: pair a phone, and the person counts as in the cabin while the phone is near
- **Manual override per person**: Available / Busy / Back soon / Auto buttons on each person's row
- **Hardware buttons and NeoPixel LEDs** for one chosen person (the cabin owner)
- **Hardware check**: camera, RFID, buttons, LEDs, Bluetooth, power supply and temperature
- **Web page** on port 8000

## Status of each person

1. **Their own manual override wins.** It is set from their row on the web page, or with the hardware buttons if they are the chosen person. It ends after `OVERRIDE_MINUTES` (default 60), when the same button is pressed again, or when **Auto** is clicked.
2. Otherwise they are **Available** if any of these is true:
   - their face was seen in the last 15 s
   - their RFID card is tapped in
   - their phone answered in the last 60 s

   The "How we know" column shows which one.
3. Otherwise they are **Away**.

The status and reason are shown next to each name. The hardware buttons and LEDs belong to the person picked in "Hardware buttons and LEDs are for:" at the top of the page.

| Status | LED colour |
|---|---|
| Available | green |
| Busy | red |
| Back soon | amber |
| Away | dim white |
| Registering a face / linking a card / pairing a phone | blue |

## Hardware check (what each line means)

| Part | How it is checked | What it can catch |
|---|---|---|
| Camera | Opens the camera, then checks a new picture arrives every 10 s | No camera / loose ribbon cable, camera stopped or frozen. It reconnects by itself |
| RFID reader | Reads the RC522's version number every 5 s | Not wired, wrong wire, no 3.3 V, SPI off. It sets the reader up again when it comes back |
| Buttons | Watches the pins | A button held down for 10 s = stuck or wires touching. A loose button can't be detected until it is pressed, so the line shows the last press |
| LEDs | Library starts on GPIO18 | Missing sudo, library error. WS2812 LEDs can't report back, so look at them |
| Bluetooth | `bluetoothctl show` every 30 s | No adapter, Bluetooth switched off (it is turned back on), service not running |
| Power | `vcgencmd get_throttled` + CPU temperature every 5 s | Under-voltage now or since start (a weak supply, or LEDs drawing too much), over 80 °C |

## Bluetooth phones

- **Pair phone:** the Pi becomes visible for 60 s. On the phone, open Bluetooth settings and choose the Pi's name, which the page shows. The first phone that pairs is linked to that person.
- **iPhones** often don't list a Raspberry Pi. Type the phone's Bluetooth address instead (Settings → General → About → Bluetooth).
- Presence: every 15 s the Pi sends each phone a tiny `l2ping`. It works while the phone's Bluetooth is on, even when the phone is locked.
- Bluetooth reaches about 10 m, through walls, so a phone in the next room also counts. Treat it as weaker evidence than a face or a card.

## Wiring (Raspberry Pi 4 – same 40-pin header on any Pi)

GPIO numbers are used in the code. The physical pin number is in brackets. Bluetooth and the camera need no wiring.

**RC522 RFID reader**: use 3.3 V only, never 5 V.

| RC522 | Pi |
|---|---|
| SDA | GPIO8 (24) |
| SCK | GPIO11 (23) |
| MOSI | GPIO10 (19) |
| MISO | GPIO9 (21) |
| RST | GPIO25 (22) |
| 3.3V | 3.3V (1) |
| GND | GND (6) |
| IRQ | not connected |

**Buttons**: one leg goes to the GPIO pin and the other to GND. No resistor is needed.

| Button | Pi |
|---|---|
| Available | GPIO5 (29) |
| Busy | GPIO6 (31) |
| Back soon | GPIO26 (37) |
| other legs | GND (39) |

**NeoPixel / WS2812 LEDs**

| LED | Pi |
|---|---|
| DIN | GPIO18 (12) |
| 5V | 5V (2) |
| GND | GND (14) |

Keep `LED_BRIGHTNESS` low. For more than about 8 LEDs, use a separate 5 V supply and connect its GND to the Pi's GND.

## Run

    mkdir -p ~/smartcabin && cd ~/smartcabin && nano smartcabin_pi.py
    (paste the file, Ctrl+O, Enter, Ctrl+X)
    sudo python3 smartcabin_pi.py

- `sudo` is needed for the LEDs and Bluetooth `l2ping`.
- The first run installs the libraries and downloads the face models.
- If SPI was off, the script turns it on and asks for a reboot (`sudo reboot`). Then run it again.
- Anything not wired yet: set `USE_RFID`, `USE_BUTTONS`, `USE_LEDS` or `USE_BLUETOOTH` to `False` at the top of the file.

Open the page at the address it prints, or tunnel it to the laptop as localhost:

    ssh -L 8000:localhost:8000 <user>@<pi-address>

Then open http://localhost:8000. `/status.json` gives the status alone, without video.

Saved on the Pi, next to the file:

- `known_faces_pi.json`
- `cards_pi.json`
- `phones_pi.json`
- `settings_pi.json`
- `models/`
