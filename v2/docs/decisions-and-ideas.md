# Decisions, and ideas we discussed

[← back to the v2 README](../README.md)

Everything that was decided for the prototype, and every idea that was discussed but postponed or dropped, with the
reason - so the report and the paper can explain the choices, and nothing is lost.

## How we got to v2

| When | Version | What it was | Where it is now |
|---|---|---|---|
| Sep–Oct 2026 | ESP32 | ESP32-CAM / ESP32-C3 door node | dropped 25 Oct (the Pi does it all, and can run face recognition); kept in `Documents/Archive - ESP32 (dropped)/` |
| 21–23 Oct | laptop demos, Pi scripts | web dashboard with demo statuses, face recognition on laptop and Pi, hardware tests 1–10 | `laptop codes/`, `pi board codes/hardware test code/` |
| 24 Oct | v1 | FastAPI + SQLite server and a Pi app, simulation-tested | `pi board codes/smart cabin system/archive/v1/` |
| 24 Oct | v1 modules | module-by-module rebuild started with an RFID module | `v1/for pi board/RFID/` |
| 24–25 Oct | **v2 (current)** | from scratch: CSV files only, the user's page designs, edge processing, run on the real Pi Zero 2W | `v2/` |

## Decisions in v2

| Decision | Why |
|---|---|
| **CSV files, no database** | the user's choice; easy to open and change, edits show up live |
| **Processing on the Pi (edge)** | the project's topic; pictures never leave the cabin; tiny network use |
| **The device gets its number from the server** (serial → SC-001) | nothing is typed on the device; works for many devices |
| **The server announces itself** (UDP 50505) | the Pis find the server by themselves, wherever it is on the network |
| **Registration at the device**, allowed while nobody is registered there and its location is set | simple for the prototype; a PIN was used before and dropped because the user's design has none |
| **Face decides "out"**: not seen for 2 minutes | the user's rule; the headcount alone can't tell who is there |
| **Timetable rule**: class in 5 minutes + face not seen 2 minutes → "Leaving for …" | the user's rule |
| **Two picture sizes**: 640x480 for headcount and live view, 1296x972 only for faces | less work for the board; faces need the pixels |
| **Face finder at a fixed 640x640** | a changing size made the memory grow until the Zero 2W ran out |
| **Black box** (`blackbox.py`) | the board stopped by itself; the record showed the kernel's out-of-memory killer, not power or heat |
| **Autostart as services** | the app was killed whenever the SSH connection closed |
| **The user's page designs** (design tool files) kept as the front end | the user designs the pages; the code only fills in the data |
| **Pages refresh every second** | the user wants live pages |
| **Live view on the Pi page** (no login) | the user accepted it for the prototype: faculty photos are public anyway |
| **Raspberry Pi 5, 4 GB** | the Zero 2W works but is at its limit; Pi 5 also for future projects |

## Ideas discussed and postponed (may come back)

| Idea | Why not now | What it would need |
|---|---|---|
| **Wi-Fi setup on the device**: the Pi makes its own hotspot, the person enters the college Wi-Fi, then the Pi switches over | the Wi-Fi is set when flashing the SD card; prototype first | NetworkManager hotspot + switch-over with fallback |
| **OLED display** (0.96" SSD1306) with a one-time pairing code (and a QR code) during registration, then status and return time | hardware not fitted yet; registration works without it | I²C (GPIO2 / GPIO3), `luma.oled`, pairing codes valid 10 minutes, one use, only while not linked |
| **Registration through the web portal**: the faculty member logs in, the server sends commands to the Pi (take 10 photos, wait for a card) | the device page works for now | a command queue the Pi checks, progress shown in the portal |
| **Faculty logins** (username from the name, password `123` at first): see and manage their own device; admin sees all | core first | accounts from `people.csv`, a "My device" page from the PiDevice design |
| **Adding / deleting extra face sets and cards**, **Maintenance** (restart, reboot, shut down, factory reset) | shown in the design, not active | protected by the admin or the registered person (card / face / password) |
| **"Remove person" and "Reset key" buttons** on the Devices page | not in the user's design | two buttons + the server calls that already exist |
| **A copy of face data on the server** (encrypted numbers, never photos) | not needed while one Pi = one cabin | restore to a replacement Pi, move with a person who changes cabin |
| **Bluetooth presence** (the person's phone) | dropped for the first build: least reliable, most setup | the tested code from hardware test 9 |
| **Machine learning** on `presence_log.csv`: learned confidence (Naive Bayes / logistic regression), steady status (hysteresis / HMM), predictions ("usually back around 11:40") | needs real logs first | logging days with ground truth |
| **Posters and photos of people** (stillness check, ignore zones) | not in the first build | tested in hardware test 7 |
| **Timetable editor** in the portal | the demo `timetable.csv` is used for now | a page to enter a weekly timetable |
| **Real push notifications**, HTTPS with a real certificate, more than one admin | prototype on a private network | for a deployment |

## Ideas dropped

| Idea | Why dropped |
|---|---|
| **v3: the Pi sends video to the server, all processing on the server** (raised 25 Oct, the user then chose to stay with v2) | 900 video streams would be 1–2 Gbit/s; a live cabin camera also sees students and visitors; v2's edge processing is the project's topic. Kept as a possible *comparison experiment* (edge vs server) for the paper |
| **Laptop hotspot named like the Pi's setup network** | replaced by setting the Wi-Fi when flashing |
| **Printed labels with device codes** | not dynamic; codes come from the server |
| **SQL database** | the user wants CSV files |
| **Setup PIN typed on the Pi** | the user's design has no PIN; the server allows setup by itself instead |
| **ESP32 boards** | the Pi does everything, including face recognition |
