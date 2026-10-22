# Smart Cabin – Timeline

A day-by-day log of what was done, what was tried, and what worked. Newest entry first.

Template for each entry:

```
## YYYY-MM-DD – short title
**Done:**
**Tried / tested:**
**What worked:**
**What didn't / why:**
**Next:**
```

---

## 2026-10-21 – Demo web UI with real university data, research papers, Pi face recognition

### Summary of the day

1. **Scope:** started laptop-only with simple, modular Python (plain functions + one `main.py`). Later the same day the Pi Zero 2W came back for face recognition (part 9).
2. **Web UI:** built a plain HTML/CSS/JS dashboard that runs without a server and is fed by Python through `web/data.js`.
3. **Many faculty:** changed from one HOD to all faculty, with people and timetables in CSV files.
4. **Real data:** loaded **839 faculty** and **114 programmes** of Presidency University, Bengaluru from the university website.
5. **UI changes requested by the user:** flat look kept, quick select buttons instead of drop-downs, official school names, a header that stays at the top while scrolling, a footer, and programmes divided by degree.
6. **Install script** for the Python libraries.
7. **Research:** 5 more papers on faculty availability (2020+), with a comparison table and draft research gap.
8. **Raspberry Pi Zero 2W:** one self-installing face recognition file with a web page.

### 1. Scope and plan

- Review 1 is on 3–6 Nov 2026 and needs a working prototype, so scope was cut. No ESP32 hardware for now, and hardware comes back later.
- Code style agreed: small module files of plain functions and one `main.py` that calls them. No advanced patterns.
- Deferred: the standalone compact device (ESP32-S3 / ESP32-CAM vs Raspberry Pi). Decide after Review 1.

### 2. Demo web UI (first version)

- `web/` pages in plain HTML/CSS/JS that open by double-click, with no server needed.
- Python (`code/`): `config.py`, `demo_data.py`, `webpage.py`, `main.py`. Python writes `web/data.js`, and the page re-reads it every 10 s.
- First version: one HOD status page (status card, reason, expected return, timetable, "How we know", sensors, legend, demo buttons) and an HOD panel (demo login, override with expiry, timetable editor with CSV upload, history).
- The sensors panel lists face recognition, hardware buttons, RFID, fingerprint, BLE and thermal as "planned (future)", because hardware buttons and biometrics may be added later.
- Added `.gitignore` and this `timeline.md`.

### 3. Redesign for many HODs and faculty

- People and timetables moved to `data/people.csv` and `data/timetable.csv`, read by the new `code/people.py`.
- Pages:
  - `index.html`: grid of cards per person, grouped by department, with keyword search (every word must match)
  - `person.html?id=...`: one person's status, timetable and evidence
  - `staff.html`: any staff member picks their name and logs in (demo password `staff123`). Replaces `hod.html`.
  - `system.html`: health, sensors, demo buttons and recent changes, so the public pages show only status
- `web/common.js` holds the shared helpers, plus one small JS file per page.

### 4. Real Presidency University data

- New `code/fetch_presidency_data.py` reads the 11 school faculty pages and 10 department pages of presidencyuniversity.in. Results:
  - **839 faculty:** 11 Deans, 23 HODs, 805 faculty. Columns: id, name, designation, role, school, department, cabin.
  - **114 programmes:** columns school, program, degree, level, duration.
- The website has **no cabin numbers or timetables**, so cabin is empty and `data/timetable.csv` is a random **demo** timetable (2 classes a day, in time order).
- Demo: `main.py` changes 5 random people every 10 s. If the timetable says a person is in class now, they show as Away with the class as the reason.
- The timetable is grouped per person so lookups stay fast. Writing `data.js` for 839 people takes about 0.3 s, and the file is about 1 MB.

### 5. UI changes asked for by the user

- **Look:** the user likes the flat UI, so it stays as it is.
- **Quick select buttons** instead of drop-downs: a Role row (Everyone / Deans / HODs / Faculty), then a School row. The choice stays when the page auto-refreshes.
- **Official names:** my shortened names ("AI and Advanced Computing", "Physics - Engineering") confused the user. The data now stores the website's names, e.g. "Presidency School of Artificial Intelligence and Advanced Computing" and "Department of Physics". Buttons and headings drop "Presidency", e.g. "School of Law" or "Department of Physics - School of Engineering". Schools appear in the website's order.
  - The user asked to use the AI school's faculty page. Its 136 faculty were already included, so no one was removed.
- **Header and footer:** every page has a header that **stays at the top while scrolling**, with Smart Cabin, Presidency University, Bengaluru, and links (Faculty status / Programmes / Staff login / System, current page highlighted). The links moved there from the bottom. The same footer is on every page (privacy note + project line). On phones the subtitle hides so the 4 links fit on one row.

### 6. Programmes divided by degree

- `degree_of()` in the fetch script works out the degree and level from each programme name using a simple lookup list.
- All 114 were classified, none left as "Other":
  - 72 Bachelor's (B.Tech 19, B.A. 21, BBA 6, B.Com 6, ...)
  - 18 Master's (M.Tech 6, MBA 5, ...)
  - 18 Ph.D
  - 6 Diploma
- `programs.html` groups by degree, with Level and Degree quick select buttons. Picking a level shows only that level's degrees.

### 7. Install script

- `code/requirements.txt` (opencv-python, numpy, requests, ultralytics) and `code/install_requirements.py`. The script checks the Python version, installs with pip, then checks each library imports.
- **Not run yet.** The laptop has Python 3.15, and PyTorch (needed by ultralytics) may not support it yet. If it fails, use Python 3.11 or 3.12.

### 8. Research papers (`research/papers.md`)

- The first set of papers 7–10 was about counting people in buildings to save energy. **The user said they were not related to the topic**, and they were replaced.
- Agreed scope for papers: faculty availability systems, cabin/door status displays, faculty presence by face recognition, timetable-based availability, **2020 or newer**.
- Papers now:
  - 6: SILA 2024 (ESP32, lecturers update their own status)
  - 7: Soppari 2025 (faculty presence by webcam face recognition, OpenCV Haar, Flask)
  - 8: IJSRED 2026 (faculty tracking with RFID + ESP32 + mobile app)
  - 9: Saxena 2024 (RFID tracking of students and professors)
  - 10: CNLAS 2026 (lecturer availability app, weak source)
- Wrote a comparison table and draft research gap for the Review 1 slides. None of the 2020+ papers uses timetables, and none reports measured accuracy.
- Confirmed the title of README paper 2 (Za'bah & Mohamad 2021, IIUM).

### 9. Raspberry Pi Zero 2W – face recognition (later in the day)

- The user is using the Pi Zero 2W again over SSH.
- First a `pi/` folder with a live camera stream (`config.py`, `camera.py`, `stream_server.py`, `main.py`). It was tested on the laptop with a fake frame: page, snapshot and stream all worked.
- Then **replaced by one self-installing file**, `codes for raspberry pi/smartcabin_pi.py`. The user doesn't copy files to the Pi; they paste one file into `nano`, so it's one file on purpose.
  - It does what `face recoginition/face_app.py` does (detect → embed → match, register, delete), but with a web page instead of an OpenCV window and keys.
  - It uses OpenCV **YuNet** (detect) + **SFace** (128-number embedding) instead of PyTorch MTCNN + FaceNet, because torch is too heavy for 512 MB RAM. Faces registered on the laptop (`known_faces.pkl`) don't carry over, so people must re-register on the Pi.
  - On first run it installs missing libraries (apt on the Pi: python3-opencv, python3-numpy, python3-picamera2) and downloads the models into `models/`. OpenCV below 4.8 (the Pi has 4.6) gets the older 2022mar YuNet model.
  - The web page shows live video, "In view now", and a table of each person: In cabin / Not seen (seen in the last 15 s) and last seen time. It also has Register (name box) and Delete. `/status.json` is for status-only use later. FPS can be set from 1 to 10, default 3.
  - `.gitignore` now skips the downloaded models and saved faces (`codes for raspberry pi/models/`, `known_faces_pi.json`).
- **Tested on the laptop** with a sample face photo in place of the camera:
  - 1 face found (0 in a blank picture)
  - registered → recognised → "In cabin"
  - snapshot, stream and delete all work
  - the old 2022mar model downloads as a real ONNX file

### 10. Pi: RFID, manual override buttons, NeoPixel LEDs (same file)

- Added to `smartcabin_pi.py`, so it's still one file to paste:
  - **RC522 RFID** (`mfrc522` library, SPI). Tap a card to check in, tap again to check out. Holding the card counts once (3 s repeat guard). New cards are linked to a name from the web page: Link card, then tap within 30 s.
  - **3 buttons** (Available / Busy / Back soon) on GPIO 5 / 6 / 26 with internal pull-ups. Pressing the same button again goes back to automatic. An override ends after 60 min. The same override buttons and **Auto** are on the web page.
  - **NeoPixel / WS2812** (`rpi_ws281x`) on GPIO18, 8 LEDs: green Available, red Busy, amber Back soon, dim white Away, blue while registering a face or linking a card.
- **Status rules:** override first; otherwise Available if a known person's face was seen in the last 15 s or their card is tapped in; otherwise Away.
- Each part can be switched off (`USE_RFID` / `USE_BUTTONS` / `USE_LEDS`). If a part fails or isn't a Pi, the rest still runs, and the web page shows each part's state.
- Install: apt `python3-rpi-lgpio python3-spidev`, pip `mfrc522 rpi_ws281x` (`--no-deps --break-system-packages`). If SPI is off, the script turns it on and asks for a reboot. Run with `sudo` (the LEDs need it).
- New `codes for raspberry pi/README.md` with the wiring tables. Card links are saved in `cards_pi.json` (git-ignored).
- **Tested on the laptop** with fake GPIO / RFID reader / LED strip and the face photo: unknown card → linked → tap in = Available (held 1 s counted once) → tap out = Away; Busy button on/off; web Back soon / Auto; face → Available, gone 20 s → Away; delete removes the face and cards; LED colours matched every step.
- **Not tested:** real RC522, buttons and LEDs on the Pi.

### 11. Pi: per-person override, hardware check, Bluetooth phones (same file)

- **User feedback:** the override must be per person, not for everyone, and shown next to the person's name. Changes:
  - Every person's row has Available / Busy / Back soon / Auto, and the status + reason are shown next to the name.
  - The hardware buttons and LEDs belong to one person, chosen on the page ("Hardware buttons and LEDs are for:"), saved in `settings_pi.json`.
- **Hardware check panel** (green / amber / red / grey per part):
  - camera: not connected, stopped, or no new picture for 10 s. It reconnects by itself.
  - RFID: reads the RC522 version register every 5 s, so an unplugged reader is caught and set up again when it's back.
  - buttons: stuck pressed for 10 s, last press shown. A loose wire can't be detected until pressed.
  - LEDs: start errors / missing sudo. WS2812 has no feedback.
  - Bluetooth: no adapter, or switched off (turned back on).
  - power: under-voltage now / since boot, and CPU temperature.
- **Bluetooth:** "Pair phone" makes the Pi discoverable for 60 s with `bt-agent` (NoInputNoOutput) and links the first newly paired phone to the name. A typed Bluetooth address also works (for iPhones). Presence: `l2ping` every 15 s, and the phone counts for 60 s. Saved in `phones_pi.json`. Note: about 10 m range through walls, so it's weaker evidence than a face or a card.
- Person status: their own override first, otherwise Available if face (15 s), card tapped in, or phone (60 s), otherwise Away.
- **Tested on the laptop** with fake GPIO / RFID / LEDs / Bluetooth:
  - web override for one person didn't change the other
  - the button went to the chosen person
  - a stuck button was caught after 10 s and cleared when released
  - pairing linked the new phone; phone near → Available, gone 70 s → Away
  - a bad typed address was rejected, and `aa-bb-cc-dd-ee-ff` → `AA:BB:CC:DD:EE:FF`
  - RFID unplugged → error, back → ok + set up again
  - camera pulled → error → reconnected; camera frozen → "no new picture for 30 s"
  - delete removed the person's card and phone
- Bug found in testing: just after start, the camera showed "no new picture for 1792601630 s" before the first frame. Fixed by setting the frame time when the camera connects.
- **Not tested:** real Bluetooth pairing, `l2ping` with real phones (Android / iPhone), `vcgencmd` on the Pi.

### 12. Pi → laptop data link with mDNS

- New `codes for raspberry pi/pi_sender.py` (Pi) and `code/pi_receiver.py` (laptop). Both install `zeroconf` themselves (apt `python3-zeroconf` on the Pi, pip on the laptop). Added to `code/requirements.txt`.
- The laptop announces the mDNS service `_smartcabin._tcp` (all its IPv4 addresses, port 8500). The Pi finds it with no IP typed, reads `smartcabin_pi.py`'s `/status.json` every 2 s and POSTs it with an `X-Token` header.
- Push from the Pi (not pull from the laptop), so many cabin Pis can report to one laptop.
- Receiver page: one card per Pi (online / OFFLINE after 15 s, people with status / how / last seen, only hardware problems listed, link to the Pi's own page). Saved to `data/pi_status.json` (git-ignored), ready to feed the dashboard.
- **Tested on the laptop** (sender + fake status server + receiver on one machine): found by mDNS, "app not running" sent while the status server was down, people arrived once it was up, wrong token → 403, OFFLINE 18 s after stopping, page renders with no JS errors.
- Bug found: the laptop also has a Windows Mobile Hotspot adapter (192.168.137.1), and the Pi switched to that address. Fixed: the receiver announces all addresses, and the sender prefers the one on its own subnet.
- **Not tested:** real Pi → laptop over Wi-Fi (college Wi-Fi may block mDNS; a phone hotspot works).

### Bugs found and fixed today

- CSS `.hidden` was overridden by `.tag`, so "Set manually" always showed. Fixed with `!important`.
- On Windows, replacing `data.js` failed with "Access is denied" when the browser had it open, which crashed `main.py`. It now retries for up to 2 s, then skips that cycle instead of crashing.
- Some programme names from the website contained HTML (`<br> <span ...>`). `clean()` now removes tags, and the CSV files have no `<` left.
- Demo timetable rows weren't in time order. Fixed by sorting.

### Tried / tested

- Search on 839 people takes 1–11 ms. Examples: "physics" → 21, HODs → 23, Deans → 11, School of Engineering → 229, HODs + School of CSE → 4, AI school → 136.
- Programmes: Master's → 18 (7 degree buttons), M.Tech → 6, "data" → 8.
- Staff override ("In a meeting, back at 15:00") shows on the person's card and page with "Set manually".
- Python wrote a new status while the page was open → the page updated within 10 s, with no reload and no server.
- The header stays at the top after scrolling. All pages have the header and footer, with no sideways scroll at phone width (375 px).
- `main.py` loop run without a browser for a few cycles: changes written to `data.js` and history.

### What worked

- Loading data with `<script src="data.js">` instead of `fetch()`. Browsers block `fetch()` on files opened directly, but a script tag works.
- Writing `data.js` to a temp file and then swapping it in, so the page never reads a half-written file.
- Reading the faculty lists straight from the website's HTML with Python's standard library only.

### What didn't / why

- Staff overrides and timetable edits are saved only in the browser (localStorage), so Python can't see them yet. A small database or server is needed (SQLite was discussed: Python has it built in).
- Cabin numbers and real timetables are not on the website, so the demo uses placeholders. The statuses shown next to real names are random demo data.
- Research papers were checked from journal pages only. Full PDFs of papers 6–10 are still to be read, and paper 8's author list needs confirming.

### Not yet done / not tested

- `install_requirements.py` not run (Python 3.15 concern).
- `smartcabin_pi.py` not yet run on the real Pi Zero 2W + Pi Camera (the install step and real FPS), and RFID / buttons / LEDs not yet wired and tried.
- Nothing committed to Git yet. `yolov8n.pt` is still tracked; run `git rm --cached yolov8n.pt`.

### Next

- Run `smartcabin_pi.py` on the Pi and note the real FPS and recognition quality.
- Connect the Pi's `/status.json` (or the laptop face recognition) to `write_status()`, so the dashboard shows real status instead of demo data.
- Add SQLite to log every status change, giving data for the Review 2 results.
- Summarise papers 1–5 from README section 9 in `research/papers.md`. Read the full PDFs of 6–10.
- Get real cabin numbers and timetables (at least for one department) to replace the demo data.

### Deferred (decide after Review 1)

- Final standalone compact device (Pi Zero 2W vs ESP32-S3 / ESP32-CAM) and which models can run on it.

---

## 2026-10-22 – Pi system information script

**Done:**
- New `codes for raspberry pi/pi_system_info.py`. It uses only the standard library and the Pi's own files and commands (`/proc`, `/sys`, `vcgencmd`, `rpicam-hello`, `bluetoothctl`, `iwgetid`, `ps`).
- Sections:
  - board: model, serial, OS, kernel, Python
  - uptime
  - CPU: use, load, speed, temperature with a HOT warning at 80 °C
  - RAM / swap / GPU memory
  - SD card, with a warning at 90 % full
  - power: every `get_throttled` bit explained in words, plus core voltage
  - network: IP, Wi-Fi name and signal in dBm, `.local` mDNS name
  - hardware: camera model or "NOT connected", SPI, I2C, Bluetooth
  - top 5 processes by memory
- Modes: plain report, `--watch N` (refresh), `--json` (to send to the laptop later).

**Tried / tested:** ran on the Windows laptop. No crash, and the Pi-only items show "not available". Fixed `hostname -I`, which printed a Windows error.

**Not tested:** on the real Pi (all the Pi-specific sections).

**Later – ran on the real Pi, specs saved to `codes for raspberry pi/board_specs.md`:**
- The board is a **Raspberry Pi 4 Model B Rev 1.5, 4 GB** (not the Zero 2W as noted before).
  - OS: Debian 13 trixie 64-bit, kernel 6.18, Python 3.13.5, desktop OS
  - Camera v2 (imx219) connected; SPI enabled; Bluetooth on
  - 32 GB SD (29 % used); power OK (`0x0`); 57.9 °C
- The Pi is on the laptop's Mobile Hotspot `ROG-StrixG16` (192.168.137.72, −40 dBm), mDNS name `pi.local`.
- `pi_system_info.py` worked on the Pi: every section was filled in, and the camera model was read correctly.
- Effect: with 4 cores / 4 GB, `FPS` can go up to 5–10.
- Updated `smartcabin_pi.py` for the Pi 4:
  - `FPS` 3 → 6
  - comments no longer say Zero 2W / 512 MB
  - the under-voltage message now says a 5 V 3 A USB-C supply
  - README wiring heading changed to Pi 4
  - **Not yet run on the Pi** at 6 FPS: check the fps on the page and the CPU temperature.
- **There are two boards.** Also recorded the **Pi Zero 2 W Rev 1.0** (serial 0000000011933149) in `board_specs.md`, with a side-by-side table.
  - Same OS (trixie 64-bit desktop), same camera (imx219), SPI on.
  - **RAM 415 MB**: the desktop already uses 54 %, and 114 MB of swap is in use 1 min after boot.
  - Advice: boot it to the console (`raspi-config nonint do_boot_behaviour B1`) and use `FPS` 2–3 on it.
- **New `pi_benchmark.py`**, made for the evaluation plan (README section 8, "Update delay"). It imports `smartcabin_pi.py` and `pi_sender.py`, so it times the real code.
  - It measures: Python / numpy / SD write speed; camera capture FPS at 640x480 and 320x240; YuNet detect, SFace embed, match vs 20 people, and JPEG times; RAM for the models; a 60 s sustained run with temperature and throttling; send time to the laptop by mDNS.
  - It works out the worst-case update delay (arrive → Pi page / laptop page; leaving adds `PRESENT_SECONDS`) and suggests an FPS (70 % of sustained, 1–10). Results are saved to `benchmarks/benchmark_<host>_<time>.json`.
  - Tested on the laptop: 640x480 whole frame 16 ms (detect 8.8, embed 6.6), 320x240 7.3 ms, mDNS found the receiver in 1.2 s, send 4.8 ms, 0 failures.
  - Found while testing: the OpenCV sample photo's face scores only 0.90 (just at the 0.9 threshold). The benchmark uses 0.5 for its own timing, and detection is still timed if no face is found.
  - **Not yet run on the Pi 4 or the Zero 2W.** `board_specs.md` has an empty results table for both.
  - First run on the Pi crashed: `smartcabin_pi has no attribute run_command`. The user keeps versions (`smartcabin_pi.py`, `smartcabin_pi1.py`, `smartcabin_pi2.py` in `~`), and `smartcabin_pi.py` was an old one.
    - Fix: the benchmark has its own `run_command`.
    - It tries `smartcabin_pi*.py` newest first and uses the first with everything it needs (e.g. `close_camera`). `--app <file>` picks one version.
    - If no file is new enough, it says to paste the newest one.
    - Tested both cases on the laptop.
- **Problem found: both boards have hostname `pi`**, so both are `pi.local`, and `pi_sender.py` would merge both into one card on the laptop. Fix: give them different hostnames (e.g. `cabin-pi4`, `cabin-zero`).

---

## 2026-10 (before 21 Oct) – Raspberry Pi Zero 2W tried

**Tried / tested:** Raspberry Pi Zero 2W as the camera / processing device.
**What didn't / why:** Remote sessions (SSH / remote desktop) were troublesome to work with.
**Decision:** Pi set aside for now. Build the prototype on the laptop first.
**Also found:** the ESP32 with camera can both send and receive (snapshots over HTTP), so it remains an option.

---

## 2026-10 – Iteration 0: snapshot → headcount

**Done:** `code/import time.py`: the laptop asks the ESP32-CAM for a JPEG every 10 s (`GET /capture` with an `X-Token` header), and YOLOv8n counts the people in it.
**What worked:** counting with the YOLOv8 nano model (person class, confidence 0.4). A new count is only accepted after 3 readings in a row agree, which stops flicker.
**What didn't / notes:** the camera IP and token are hardcoded, and debug mode needs a screen. To be cleaned up when the camera code is restructured.

---

## 2026-10-08 – Design document v0.1

**Done:** wrote the full design in `README.md`: problem and aim, design principles, architecture, status model, technology register, security and privacy, iteration roadmap, evaluation plan, references.

---

## 2026-09-29 to 10-02 – Review 0

**Done:** topic, problem identification and literature survey presented. Review 0 complete.
