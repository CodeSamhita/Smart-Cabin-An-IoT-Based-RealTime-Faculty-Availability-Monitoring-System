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

## 2026-10-31 – canvas design built into v3

**Done:** the canvas design (26–31 Oct) merged into v3: one login for admin and faculty (username / server id / ID card number), faculty logins made in bulk with a default password and changed at the first login, new pages AdminPerson, AdminLogins and Faculty (My cabin), Devices page with count filters, newest device and the faculty browser, period-based timetables (several per person, one in use) that the status rules now read, and the Pi sending its details with each hello. New server files `faculty.py`, `timetables.py`; new CSV files `faculty_accounts.csv`, `faculty_sessions.csv`, `timetables.csv`, `timetable_in_use.csv`, `device_details.csv`.
**Tried / tested:** on a test copy of the server (port 8090, http, copied data, test admin): admin login, Devices (count filter, faculty browser), a faculty member's admin page (status, charts, registration, parts, maintenance confirm), Faculty logins for all 839 with a default password, faculty login by ID card number → set own password → My cabin, a timetable with a split lab and lunch (a class across a break refused), several timetables (use, delete; the in-use one can't be deleted), wrong current password refused. Found and fixed: a timetable saved with no entries was lost. No server errors. Not deployed to the Pi.
**What didn't / why:** the live camera picture and add face / card can't be done from the laptop pages (the server can't ask the Pi to act); those pages link to the device's own page instead.
**Next:** start the server, make the faculty logins, try each page; deploy the Pi change.

---

## 2026-10-27 – design canvas: admin and faculty pages

**Done:** on the canvas: Devices redesign (newest device, count filters, faculty browser), the admin's faculty member page, Faculty logins (default password for all), My cabin for faculty (status key, week timetable with periods, several timetables, account details, device details, maintenance), one-box login. Indication light renamed, dark-room flash every 2 minutes, "Staff id" → "Server id".

---

## 2026-10-26 – pages on a design canvas (v3)

**Done:** the 6 pages (Main, Search, Login, Devices, PiDevice, PiRegister) put on a Claude design canvas, "Smart Cabin Pages", one artboard per page, same look, sample AI School data. Written in `v3/PLAN.md` first.
**Next:** the user adds buttons, text boxes and other elements on the canvas; then the new elements are copied into the v3 `.dc.html` files and wired to the scripts and server.

---

## 2026-10-26 – diagrams, v2 frozen, v3 started

**Done:** add / delete face sets and RFID cards at the device (Pi page, Advanced → Registration details). Diagrams of the
whole v2 system in `v2/docs/diagrams.md` (system, how the files are linked, start-up, vision loop, presence rules,
server status, discovery, registration, face sets / cards, pages, data files). **v2 is frozen** (it works): from now on
all work happens in a copy, `v3/`. A full backup of the project was made outside the repository.
**What didn't / why:** the latest v2 changes (camera streams, live view stream, leave / timetable rules, face sets and
cards) are not yet run on the Pi - it was offline.
**Next:** run v3 on the Pi, test the new rules in a real cabin.

---

## 2026-10-25 (late) – after the first real test: leaving, timetable, camera, Pi 5, documents

**Feedback from the real test:** card taps update at once; face → Available works; communication fine. But leaving did not switch back (3 minutes and "anyone counted" kept the person in), the live view stuttered, CPU and memory high.
**Done:**
- Leave rule (user's): the face decides - not seen for 2 minutes = out, even if others are counted (card-only registrations: nobody counted for 2 minutes).
- Timetable rule (user's): a class within 5 minutes and the face not seen for 2 minutes → "Leaving for <class> at <time>".
- Pages show how someone is in: Seen and tapped in / Seen, not tapped in / Tapped in, not seen yet.
- Camera: 640x480 stream for headcount and live view, 1296x972 only for face checks; the live view is a continuous stream (5 / s on a Zero, 10 / s on a Pi 4 / 5) only while open.
- Board-aware timings; Pi 5 support (NeoPixel through pi5neo on SPI1, GPIO20). Board chosen: **Pi 5, 4 GB**.
- Documents: v2 README rewritten, `docs/boards.md`, `docs/decisions-and-ideas.md` (every idea discussed, postponed or dropped), main README points to v2.
**Not tested:** none of today's last changes ran on the Pi (it was offline when copying); syntax-checked only.
**Next:** copy to the Pi, check leaving after 2 minutes and the live view; order the Pi 5 (5 V 5 A supply, camera cable, active cooler).

---

## 2026-10-25 (evening) – v2 on the real Pi Zero 2W: registration, crashes, black box, autostart

**Done:** the user's Pi designs (PiDevice, PiRegister) wired to live data; registration without a PIN (allowed while nobody is registered and the device has a location); the server announces itself (UDP 50505) so the Pi finds it by itself; all pages refresh every second; Live view (latest picture with person boxes + 2-minute charts) in the Pi's Advanced view; `blackbox.py` records the board's health every 2 s; `main.py --autostart` installs the app and the black box as boot services.
**Tried / tested on the real Zero 2W:** RC522 (0x92), LED, camera 1296x972, MobileNet-SSD, server connection all OK; Dr. Pravinthraja registered (10 face photos + card); face → Available, card tap out / in work; live.jpg served; both services active and enabled.
**What didn't / why:**
- Face registration hung: the desktop + app used up the 415 MB (170 MB swapped). Fixed by booting to the console (no desktop); registration now shows the preview at once, warns when too dark, finds faces on a 640x480 copy.
- The board / app "turned off": the kernel's **out-of-memory killer** stopped the app twice (power and heat were fine: throttled=0x0, 47 °C). Cause: the face finder was called on regions of a different size every time and rebuilt its memory each time. Now it always works on a fixed 640x640 square.
- The SSH connection closing also killed the app (it ran inside the SSH session); now it runs as a boot service.
**Next:** watch `app_mem_mb` in `data/blackbox.csv` over an hour to confirm the memory no longer grows; vision still takes 4–8 s per round on the Zero.

---

## 2026-10-25 – v2: landing page "who is available now"

**Done:**
- New landing page `laptop_server/pages/home/` at `/`: counts (Available / In a meeting / Not available / Unknown, each also a filter) and a card for everyone with a cabin device, available first, refreshed every 10 s. A card opens the person (details + today's timetable) on the search page, which moved to `/search`. New public call `/api/board` (public fields only).
- Server `--data <folder>`: a separate data folder for trying things out.
- **Fixed (found while testing):** a person registered with a card only could never be confirmed, so each tap-in ended after 120 s. Now confirmed when anyone is counted in the cabin.
- **Fixed (Windows):** saving the device key failed with "Access is denied" when Windows locked the just-written file; the key was lost and the device refused for good. Saves now retry and run one at a time.

**Tried / tested:** server 35 / 35 (incl. board), page addresses 22 / 22, three simulated cabins (Available, In a meeting, Not available) on the landing page at laptop and phone width (375 px, no sideways scroll), card → details.
**What didn't / why (my mistakes, both undone):**
- You were running the server yourself (admin made 15:12) while my test server used the same data folder; my test added a test device and 5 rows. Only those rows were removed; your admin account was not touched. Since then my tests use `--data` on a separate folder.
- One command started the device app instead of the server, without `--no-webcam`, so it switched the webcam on for about a minute (15:33–15:35). The pictures were black, only used in memory, never saved or sent.

---

## 2026-10-25 – v2: pages in their own folders, Pi app runs on Windows

**Done:**
- Every page has its own folder with its HTML and its script: `laptop_server/pages/public/`, `devices/`, `login/`, `pi_edge/pages/device/`; shared `app.js` + `style.css` in `pages/common/`. Links are relative, so each HTML file also opens by itself (it then shows its layout and a note that live data needs the server). The servers serve the files at `/<folder>/<file>`; `/`, `/devices`, `/login` redirect there.
- The Pi app notices when it is not on a Pi (Windows, Mac, PC) and runs as usual without `--sim`: missing hardware shows **NOT PRESENT** (grey, not an error); the camera is a `--picture` file, else the computer's webcam (`--no-webcam` to turn it off), else none; the card reader is the "Tap card" box; the LED colour is on the page.

**Tried / tested:** page addresses 19 / 19 (server) and 13 / 13 (device), including refused `../` and hidden-file tricks; server test 33 / 33; end-to-end 29 / 29 again; the app on Windows with no Pi flags (connected, parts NOT PRESENT, software parts OK); each HTML file opened directly from disk in headless Edge (styling and scripts load, the note shows).
**What didn't / why:** a bulk text replace in PowerShell turned every "l" into "o" in three page scripts (an array was flattened); found at once and the files were rewritten. The webcam path was not tried, so your webcam was not switched on without asking.
**Next:** hotspot on → deploy to the Pi.

---

## 2026-10-24/25 – v2: the whole system from scratch (laptop server + Pi edge)

**Done:**
- Plan first: `v2/PLAN.md`. Then `v2/laptop_server/` (Python's own HTTPS server, CSV files only) and `v2/pi_edge/` (Pi app), `v2/README.md`, `v2/deploy_to_pi.ps1`, `v2/.gitignore`.
- **Devices numbered like roll numbers:** a Pi's hardware serial → `SC-001`, `SC-002`… plus a secret key on its first hello. The location is set once on the server's Devices page (admin login), never on the Pi.
- **Registration at the device from a phone:** setup PIN from the admin → the Pi copies the people list from the server → school / department drop-downs + type-to-search → face (10 photos, live preview) → card → save. Moving cabin keeps the old row in `registrations.csv`.
- **On the Pi:** one picture every 5 s (1.5 s after a change), headcount (MobileNet-SSD on the Zero, YOLOv8n on a Pi 4), face only when useful, temperature guard (70 / 78 °C), white LED flash in a dark room (max once a minute), face × card confidence (2 / 35 / 70 / 90 %), presence rules (2 face checks, 120 s card confirm, 180 s leave). Bluetooth left out for now.
- **Security:** no video feed, HTTPS (self-signed; the Pi pins the server's certificate), device keys, admin login (PBKDF2), one-time setup PINs, card ids only hashed on the server, faces only on the Pi, public page limited to 10 fields.
- **Troubleshooting:** every button gives Working… → OK / error; 10 s request limit; red error bar for page errors; each part OK / PROBLEM with the reason; health and last error on the Devices page; `server.log` / `edge.log`.

**Tried / tested (laptop, simulated Pi, 24–25 Oct):**
- Server test: 33 / 33 (logins, wrong password, devices page needs login, device keys, location, PINs, registration, public fields only, bad requests).
- End-to-end with a simulated Pi (camera = swapped photo files), 29 / 29, plus device stopped → Unknown after 60 s: connect, location, wrong PIN, people copy (839), face registration (no face / 2 faces refused, 10 photos), card link, save, used PIN refused, face → Available, 3 people → In a meeting, card tap out / in, unknown card ignored, 60 s logout pause, dark room, unconfirmed tap out after 120 s, leave after 180 s.
- The pages in the browser: public grid + detail, Devices page, the device page's registration with live preview.

**What didn't / fixed:**
- OpenCV 5 (laptop Python 3.15) can't read MobileNet-SSD (Caffe) → the people count switches to YOLOv8n there. The Pi has OpenCV 4.10.
- Two simulated devices shared one data folder → the second overwrote the first's key and deleted its face. Each simulated serial now gets its own folder.
- Device page: a status refresh already on its way wiped the new registration key, so the steps didn't appear. Fixed (answers sent before the key changed are ignored).
- The in-app browser refuses self-signed HTTPS, so the pages were checked with `--http` copies.

**Not done yet:** nothing on the real Pi (the laptop hotspot was off). Machine learning, Bluetooth, the OLED are planned later.
**Next:** hotspot on → `v2/deploy_to_pi.ps1` → camera, RC522, LED, dark flash and a 30-minute temperature run on the Zero 2W.

---

## 2026-10-24 – RFID module in the new `v1/for pi board/`

**Done:** `v1/for pi board/RFID/main code.py` calls four files in `Support Code/`: test physical connection, check sensor specs, verify device integrity and read tags. The logic was split out of `1_test_rfid.py` (RC522, SPI, RST on GPIO25). Plan entry: BUILD_PLAN Step 12.
**Tried / tested:** all 5 files compile, and `main code.py` loads all 4 support files (their names have spaces, so it loads them by path).
- Copied to the Pi Zero 2W (`~/v1/RFID`) and run for 25 s: SPI and libraries OK, NXP MFRC522 v2.0 (0x92), 200 / 200 stable reads, antenna on at 33 dB, write / read-back 6 / 6, RST pin OK, self-test 64 / 64.
- Added on request ("what if any test fails?"): each support file returns PASS / FAIL / INFO per check, and `main code.py` prints a summary before reading tags. A connection failure stops the run, and an integrity failure skips tag reading. Tested on the laptop with a fake reader (6 cases: all good, SPI off, no answer, antenna off, MOSI broken, RST broken), all as intended. On the Pi: summary all PASS, then tag reading started. An older copy left running on the Pi was holding GPIO25 (`GPIO not allocated`) and was stopped first.
- Added on request ("user should not leave their card on reader by mistake"): `read tags.py` restarts the antenna field before each read, so a card lying still keeps answering. A card still there after 5 s is warned about, again every 10 s, and "taken off" shows once it has been unseen for 1 s. A card already there at the start is warned about straight away. Fake-clock test with 20 % missed reads: all 4 scenarios right, and it caught 2 bugs (a missed first read lost the start warning; 0 used as "not warned"), both fixed. On the Pi with a card (UID F3 CA E9 17) lying on the reader: all checks PASS (the RST pin and the self-test too), then "was already on the reader", a warning straight away and again every 10 s. Taking the card off was not seen during the 30 s run.
**What didn't / why:** live tag reading started, but no card was tapped during either run on the Pi.
**Next:** run it on the Pi and tap a card: `cd ~/v1/RFID && sudo python3 "main code.py"`.

---

## 2026-10-25 – v1 archived, ESP32 dropped

**Done:**
- `pi board codes/smart cabin system/archive/v1/` holds a frozen copy of the laptop server and the Pi app (Steps 0–10, with automatic pairing). The working folders `laptop/` and `pi zero 2w/` were removed (sent to the Recycle Bin).
- **ESP32 idea dropped.** The Raspberry Pi does everything the ESP32 boards were planned for, and it can run face recognition on the device. `esp32 codes/` was moved to `Documents/Archive - ESP32 (dropped)/`, kept only for the documentation and the report.
- New hardware test `10_presence_confidence.py` (port 8086): face × RFID × Bluetooth make 8 combinations (000–111), each with its own confidence (2 % to 99 %). Tested with `--sim` on the laptop: all 8 show the right row, and the page fits a phone. **Not yet run on the real Pi.**
  - Then added on request: **Register my face** (10 photos) and **Add a device** (Bluetooth pairing, up to 5, with Remove) on the same page, so tests 8 and 9 aren't needed first. Simulation test: 14 / 14 checks passed (register, delete, pair, 5-device limit, remove, cancel).
  - Bluetooth made detect-only: each check connects once (l2ping) and disconnects at once; a guard thread drops and untrusts any other connection every 3 s, so the Pi is never used as an input or output device. Tested with a fake `bluetoothctl`: 8 / 8. Still to check on the real Pi.
  - The same detect-only rule added to `9_bluetooth_presence.py`: fake `bluetoothctl` test 8 / 8, and its page loads without errors.
- **Deploying from the laptop:** `pi board codes/deploy_to_pi.ps1` copies the tests to `~/hw` and starts one as the systemd unit `hwtest`. Key login and password-free sudo were set up once. **Test 10 now runs on the real Pi** (http://192.168.137.207:8086): camera, RC522 and Bluetooth all started. Face register, card and phone pairing not tried yet.
- **New folder `pi board codes/claude codes/`**, built step by step (plan in its `PLAN.md`). **Step 1, register a user:** name → face (10 photos → `faces/<id>.npy`) → RFID card → Bluetooth devices → save, each skippable but at least one needed. Saved in `users.csv` and `devices.csv`. Simulation 26 / 26 + 3 / 3. Deployed and running on the Pi at http://192.168.137.207:8000 (camera, RFID and Bluetooth ready). Registering on the real hardware not tried yet.

---

## 2026-10-24 – The real product: `pi board codes/smart cabin system/`

**Done:**
- **Plan first:** `BUILD_PLAN.md` covers what, why, the expected outcome and a check for every step. Each new request was written into it before building, and boxes are ticked only when verified.
- **Laptop server** (`laptop/`, `python main.py`, installs FastAPI itself):
  - SQLite database, hashed passwords, sessions, device tokens.
  - Separate pages: public status (search + filters), person (more for logged-in staff + **Notify me when available**), login / first admin, **register** (admin; *Import AI School list*, Dean Dr. Shakkeera L), **admin** (cabins, 6-digit device codes, activity, CSV), **me** (status buttons, devices, password), **timetable** editor.
  - Timetable editor: templates A / B with lunch as hour 5 or 4, 8 numbered hours, Mon–Sat grid, Block A–T / floor / room drop-downs, lab = 2 numbered hours, several timetables per person merged, with clash warnings.
  - Status engine: buttons → silent (grey) → in (green / yellow) → away (red, where + back around), with a 10 s buffer. The "In a meeting" button ends when the headcount drops after being 2 or more.
- **Pi app** (`pi zero 2w/`, `sudo python3 main.py`, installs everything, `--autostart`):
  - Threads for the camera (people count + owner's face at 1296x972), RFID, Bluetooth, buttons, report and config.
  - Presence rules: arrive after 2 face matches or a card tap (confirmed within 120 s); leave after 180 s with no face and no phone; the phone only keeps presence.
  - Setup page on port 8000; offline fallback; simulation mode on a laptop.
- **Docs:** README with diagrams, plus `docs/` (server, status rules, timetable, edge device, vision with grades, sensors with wiring, technology choices), 8 charts from `docs/charts/make_charts.py`, and the animated 13-slide `docs/presentation/Smart_Cabin_vs_existing_work.pptx` (9 papers: drawback → answer).
**Tried / tested:**
- Server: automatic test with **80 / 80 checks passing**.
- Pi app in simulation against the real server: face register → green, 2 people → yellow, card logout → red, unknown card, pairing, offline fallback.
- The deck opens in PowerPoint, with 2–17 animation effects per slide.
**Found and fixed while testing:**
- A silent device during lunch said "On a lunch break". It now shows grey, because breaks aren't "known".
- A tea break inside a lab left a gap; the first lab hour now runs on to the second.
- Sliding sections on a phone stopped halfway; fixed.
**Not yet:** nothing has run on the real Pi hardware. Also not timed or tested yet: the 120 s / 180 s timers, code expiry, removing a device from `/me`, changing a password.
**Next:** copy `pi zero 2w/` to the Pi, run it, and work through the hardware checks in BUILD_PLAN Step 6.

---

## 2026-10-24 – Video scripts and people counter (`pi board codes/hardware test code/`)

**Done:**
- The scripts are now numbered in the order they were made: `1_test_rfid.py`, `2_test_camera.py`, `3_test_neopixel.py`, `4_test_video_window.py`, `5_test_video_web.py`, `6_people_count_web.py`.
- `4_test_video_window.py`: bare live video in an OpenCV window. Needs a screen: monitor, VNC or `ssh -X`.
- `5_test_video_web.py`: live MJPEG video on a web page (port 8081) with resolution, fps, bitrate, flip and picture controls, and the real fps / Mbps.
  - Preferred settings: 320x240, 640x480 and 1296x972, at 10–15 Mbps and 30–40 fps. Defaults are 640x480, 30 fps, 12 Mbps.
- `6_people_count_web.py`: people counter on a web page (port 8082), with boxes, the count, ms per detection and fps.
  - MobileNet-SSD and YOLOv8n can be switched on the page, so the two can be compared on the Pi.
  - Same steady-count rule as the laptop's `headcount.py`: 3 readings in a row must agree.
  - YOLOv8n needs `models/yolov8n.onnx`, exported once on the laptop (steps in the folder README).
- `.gitignore`: the folder's `models/`, test photo and `.h264` files are ignored.
**Tried / tested:** on the laptop with fake cameras, using OpenCV 4.10 as on the Pi.
- `5_test_video_web.py`: video, stats, and resolution / flip changes work.
- `6_people_count_web.py`, on a street test photo with 4 people:
  - MobileNet-SSD found 2 (it missed the two only partly in the picture), at 22 ms per detection on the laptop.
  - YOLOv8n (320) found 3, at 27 ms.
  - The fallback when the YOLO file is missing works.
- `yolov8n.onnx` (320, opset 12, 12 MB) was exported on the laptop with Python 3.12, because ultralytics can't install on Python 3.15. It is in `hardware test code/models/` (git-ignored), ready to `scp` to the Pi.
- Found: OpenCV 5 (on the laptop's Python 3.15) has dropped Caffe models, so MobileNet-SSD needs OpenCV 4.x. The Pi has 4.10.
**Also done – snapshot counter:**
- `7_people_count_snapshot.py`: same detectors and page as 6, but no live video. It takes a picture, counts, shows it, waits 1 s (changeable on the page) and repeats. Port 8083.
- Tested on the laptop with a fake camera and OpenCV 4.10: about 1 picture per second with a 1 s wait, the wait slider works, and the counts match 6 (MobileNet 2, YOLO 3).
**Also done – photos / posters of people (in 7):**
- Detection resolution: both models shrink the picture to 300 / 320 px, so 640x480 capture is enough. More pixels add nothing; raise YOLO's imgsz only if far-away people are missed. Picture interval: 1–2.5 s (default 1.5 s).
- Stillness check (on/off): each box is compared with its picture from when it last moved. Under the movement threshold (default 4 / 255) for "still for" seconds (default 60) = "still", not counted. Catches posters and photos, not videos on a screen.
- Ignore zones (on/off): drawn by dragging on the page, or made from the boxes seen in an empty room. Half a box inside a zone = "ignored". Saved in `ignore_zones.json` (git-ignored).
- Tested on the laptop (static test photo): both people turned "still" after 5 s; "Ignore boxes seen now" made 2 zones and both turned "ignored"; drawing a zone by dragging and deleting it work.
**Discussed and noted (in README 5.1 and Open):**
- **Video of a person:** it is never still, so the stillness check can't catch it. A wall TV is covered by an ignore zone, but a phone or laptop held up is not. Idea for later: a "screen check" that ignores people inside a `tv` / `laptop` / `cell phone` box.
- **PIR:** still rejected. It misses people sitting still and fires on sunlight, air and passers-by. It is only useful as a wake-up trigger.
- **mmWave radar (HLK-LD2410, about ₹300–500):** the favoured liveness sensor. It senses breathing, can ignore the doorway by distance, and can't be fooled by photos or screens. A test script will be written when one is bought.
**Also done – bare-bone face recognition:**
- `8_face_recognition.py` is a web page (port 8084) with the same YuNet + SFace steps and 0.36 threshold as `smartcabin_pi.py`, nothing else.
  - Every 1.5 s it shows a picture with a name and score on each face.
  - Register takes 10 photos of the one face in view, 0.3 s apart, within 30 s. Registered people can be deleted.
  - Resolution and threshold are set on the page. Faces are saved in `known_faces.json` (git-ignored).
- **Found: faces need more pixels than bodies.** In the test photo, YuNet found no face at 320x240 or 640x480, but one at 1296x972 (59 px wide, 63 ms on the laptop). So the default for faces is 1296x972, while people counting stays at 640x480.
- Tested on the laptop with a fake camera and OpenCV 4.10:
  - Registered one man from a 1-face crop.
  - In the full street photo he was named "Dr. Rao (0.60)" at 1296x972. At 640x480 no face was found.
  - Registering refuses when two faces are in view, and waits until the models are loaded. Delete works, and names with an apostrophe work.
**Also done – Bluetooth presence:**
- `9_bluetooth_presence.py`: users with 0 – 5 devices each, Near / Away per user, and when each device was last seen. Web page on port 8085.
- **Random addresses:** phones randomise their address only while advertising (Bluetooth Low Energy), and the classic address is fixed. Pairing once gives the real address and the IRK key, so nothing is typed.
- **Pairing only saves the identity:** the device is not trusted and is disconnected straight after pairing. The NoInputNoOutput agent runs only during the 60 s window, and the Pi is not visible the rest of the time. The check is an l2ping every 15 s, with no service used.
- Two ways to add a device: the Pi lists visible devices and the user presses Pair (for iPhones, which often won't list a Pi), or the device picks the Pi's name.
- Tested on the laptop with a fake bluetoothctl / l2ping:
  - Pairing from the Pi side saved "Pixel 7".
  - Pairing from the device side saved "Rao's iPhone" for the second user.
  - Nameless devices are hidden from the pairing list.
  - Both users turned Near when their devices answered.
  - Removing a device works, including names with an apostrophe.
  - Not tested with real Bluetooth yet.
**Next:** run 5 – 9 on the Zero 2W and Pi 4. Check real iPhone and Android pairing and l2ping with the screen locked. Tune the movement threshold with a real person sitting still and a printed photo. Check the time per picture at 1296x972 on the Zero for face recognition. Compare MobileNet-SSD with YOLOv8n (count accuracy, ms, fps) for Review 1.

---

## 2026-10-23 – Bare-bone tests per part (`pi board codes/hardware test code/`)

**Done:** the Pi folder was split into `hardware test code/`, `pi with laptop/` (empty for now) and `Tried and working codes now on actual project/`. Three terminal scripts in `hardware test code/`, each checking the connection first, then testing step by step with PASS / FAIL / INFO:
- `test_rfid.py`: SPI, libraries, chip version, write/read-back, 500-read stability, RST pin, antenna/gain, chip self-test, card UID + type + sector 0 memory, read rate, live mode.
- `test_camera.py`: detected / opened, camera type, max resolution, sensor modes, controls, full-resolution photo, real fps per mode, H.264 bitrate 5–25 Mbps.
- `test_neopixel.py`: sudo, board, audio/PWM clash, library, then one LED cycling 8 colours with Enter.
**Tried / tested:** all three run on the **Pi Zero 2W** (outputs in `hardware test code/pi 02w results/`):
- Camera: the Zero now has an **ov5647 = Camera Module v1 (5 MP)**, not the imx219 v2 from the benchmarks. 4 modes, each reaching 99–100 % of its rated fps (640x480 @ 62, 1296x972 @ 46, 1920x1080 @ 33, 2592x1944 @ 15.6). Full photo 2592x1944 in 0.29 s. H.264 1080p30 gave 4.8 / 9.6 / 16.2 / 24.0 Mbps for 5 / 10 / 17 / 25 asked.
- RFID: genuine NXP chip v2.0 (0x92). All wiring checks passed: write/read-back, 500/500 stable reads, RST pin, antenna 33 dB, and the self-test matched the datasheet 64/64. Cards were read in live mode, including 7-byte-UID tags (starting `88 04 11 ...`).
- NeoPixel: the single LED cycled all 8 colours correctly.
**What didn't / fixed:**
- Camera max size showed 0 x 0: the ov5647 driver doesn't report it. Now it is taken from the largest sensor mode.
- Fixed the deprecated logging warning, and the camera place is now shown as a name.
- RFID: the 30 s card step missed the card, while live mode saw it. The step now restarts the antenna field every second.
- RFID: 7-byte UIDs were cut to `88` + 3 bytes. The test now reads the full UID (second cascade level).
- NeoPixel: the audio warning is skipped on the Zero, since it has no 3.5 mm jack.
- `smartcabin_pi.py` also keeps only the first 4 bytes, so 7-byte tags would be stored as `88` + 3 bytes there too.
**Next:** run the fixed scripts again on the Zero, then on the Pi 4. Decide whether `smartcabin_pi.py` should read full 7-byte UIDs.

---

## 2026-10-23 – Hardware test script: camera, RFID, NeoPixel

**Done:** RC522 RFID reader, NeoPixel LEDs and Pi Camera connected to the Pi. New `pi board codes/test_hardware.py` is a web page (port 8080) that tests all three with the same pins and libraries as `smartcabin_pi.py`:
- Camera: live picture (one per second) and its brightness. Warns if the picture is black or the camera is busy.
- LEDs: Red / Green / Blue / White / Off buttons, and "Test all" (each colour, then each LED one at a time).
- RFID: checks the chip version every 2 s (shows if a wire comes loose), and lists the last 20 cards tapped.
- Each part has an OK / PROBLEM badge with a hint.
- (A first version was a terminal script; it was changed to the web page the same day.)
**Tried / tested:** on the laptop with fake LEDs and RFID: the page loads, the LED buttons work, it fits a phone screen, and the camera shows PROBLEM as expected (no picamera2). Not run on the Pi yet.
**Next:** run it on the Pi and note the results here.

---

## 2026-10-23 – Faculty page: school → department → faculty

**Done:** the faculty status page (`web/index.html`, `web/index.js`) now starts empty instead of loading all 839 faculty. You pick a school, then a department, then optionally one name from a drop-down. Schools with only one department skip the department step. The "All schools" button was removed. Added `web/README.md` explaining how Python feeds the page and how the selection works. Added a header comment to the ESP32-CAM headcount script (`ESP32 code/Headcount ESP32-CAM.py`, earlier `code/import time.py`).
**Tried / tested:** in the browser through a local test server: School of Engineering shows 10 department buttons; Civil Engineering shows 14 cards and 14 names; one name shows 1 card; School of Law skips the department step.
**Also done – folders split by hardware:**
- `laptop codes/`: needs only the laptop. `code/`, `web/`, `data/`, `yolov8n.pt` and `face recoginition/` moved in. The layout inside is unchanged, so `config.py` paths still work.
- `pi board codes/` (was `codes for raspberry pi/`): everything that uses a Pi. `pi_receiver.py` moved here from `code/` and now saves `pi_status.json` in this folder.
- `esp32 codes/` (was `ESP32 code/`): ESP32-CAM + laptop. Added its own `README.md` and `requirements.txt`. `requests` and `zeroconf` were removed from the laptop `requirements.txt`.
- The two `known_faces.pkl` files were different, so the one from the repo root was kept as `laptop codes/face recoginition/known_faces_from_repo_root.pkl`.
- Checked: dashboard modules load 839 people and write `web/data.js` from the new place; moved scripts compile.
**Next:** commit the change. Older entries below still use the old folder names.

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

## 2026-10-22 – Laptop webcam head count

**Done:**
- New `code/camera.py` (open webcam, read a picture, close) and `code/headcount.py` (YOLOv8n counts "person" boxes). Run with `python headcount.py`.
- Settings added to `code/config.py`: camera index, model file (`yolov8n.pt` in the project folder), confidence 0.4, 1 count per second, 3 matching readings before a count is accepted, show window on/off.
- Same idea as Iteration 0 (`import time.py`), but it uses the laptop webcam instead of the ESP32-CAM and is split into small modules.

**Tried / tested:**
- Installing `ultralytics` on the default Python 3.15 failed. There is no ready-made numpy for 3.15 that ultralytics accepts, so pip tried to build numpy from source, and that needs a C compiler.
- Installed it on Python 3.12 instead (`py -3.12 -m pip install ultralytics ...`), and that worked (ultralytics 8.4.183).
- Sample photo `bus.jpg`: counted 3 people. The photo has 4, but one is cut off at the edge and scores below the 0.4 cutoff.
- Steady filter with the readings 1,2,2,2,3,2: it accepted 2 after three matching readings and ignored the single 3.
- Laptop webcam (640x480), 10 pictures: seen 1,2,2,2,2,2,2,2,1,1, steady count 2. About 60 ms per picture on the CPU (the first one takes 3.5 s while the model loads).

**What worked:** webcam + YOLOv8n + steady filter, fast enough on the laptop CPU.
**What didn't / why:** Python 3.15 is too new for ultralytics / PyTorch. Run the code with `py -3.12`.
**Next:** test with 0 to 3 people in the cabin and note the real vs counted numbers (accuracy for Review 1). Then feed the steady count into `main.py` and the dashboard.

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
- **First real benchmark: Pi Zero 2W** (full run, code `smartcabin_pi2.py`), saved in the new `codes for raspberry pi/benchmark_results.md`:
  - camera 30 pictures/s at 640x480 and 320x240
  - detect 170 ms + embed 164 ms → whole frame 354 ms (max 2.8 FPS); at 320x240, 274 ms (3.7 FPS)
  - **sustained 1.9 FPS**; 54.8 → 66.6 °C in 60 s, no throttling
  - models 42.6 MB, 113 MB free with the desktop running
  - suggested **`FPS = 1`** on the Zero
  - worst-case arrive → Pi page 2.35 s, → laptop page 5.35 s
  - Findings: the face check is the bottleneck (about 22× slower than the laptop), not the camera. SFace time doesn't drop at 320x240 (fixed 112x112 crop). Matching 20 people costs 1.3 ms.
  - Network test skipped: the laptop receiver wasn't found.
  - Still to do: Pi 4 run, network test on both, 10-min heat run on the Zero, Zero without the desktop.
- **Pi 4 benchmark** (full run, `smartcabin_pi2.py`), added to `benchmark_results.md` next to the Zero:
  - camera 30 pictures/s
  - detect 90.7 ms + embed 64.9 ms → whole frame 160.5 ms (max 6.2 FPS); at 320x240, 93 ms (max 10.8 FPS)
  - **sustained 5.4 FPS**; 54.5 → 58.9 °C, steady, no throttling
  - models 49.6 MB, 3.2 GB free
  - suggested **`FPS = 3`**
  - worst-case arrive → Pi page 1.49 s, → laptop page 4.49 s
  - Pi 4 vs Zero: about 2.2× faster per frame, 2.8× sustained. The laptop is about 10× faster than the Pi 4.
  - 320x240 helps the Pi 4 much more (detection is a bigger share there).
  - **The current default `FPS = 6` is above the Pi 4's sustained 5.4**, so the loop never rests. Use 3 (max about 4).
  - **Comparison graph:**
    - New `codes for raspberry pi/compare_benchmarks.py` (laptop, installs matplotlib). It reads two `benchmarks/*.json`, prints a table with "x better", and saves `benchmarks/board_comparison.png`.
    - The graph has 6 panels, each with one unit: step times, whole frame at both sizes, FPS, temperature over 60 s with an 80 °C line, update delay, and "x faster".
    - Colours: palette blue / orange, plus stripes on the second board for print. The palette checker couldn't run (no Node on the laptop); the two colours are the palette's documented defaults.
    - Both runs were copied from the pasted outputs into `benchmarks/benchmark_pi_zero2w_20261022_1423.json` and `benchmark_pi4_20261022_1441.json`, in the same format `pi_benchmark.py` saves.
    - Checked the graph visually and fixed crowded FPS labels. The graph is embedded in `benchmark_results.md`.
  - Network test skipped again on the Pi 4: the laptop receiver wasn't found (receiver not running, or the firewall blocking mDNS / port 8500).
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
