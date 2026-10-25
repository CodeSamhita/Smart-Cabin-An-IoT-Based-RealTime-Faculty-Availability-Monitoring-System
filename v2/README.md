# Smart Cabin v2

Shows whether a faculty member is **in their cabin**, alone or with others, on a web page anyone can open.
Each cabin has a Raspberry Pi with a camera, an RC522 card reader and a NeoPixel light. The Pi works out on its own
whether the person is in (face recognition, card taps, headcount), and sends only the result to the laptop server,
which adds the timetable and shows it.

- Plan, rules and every change: [PLAN.md](PLAN.md)
- Boards (Zero 2W, Pi 4, Pi 5): [docs/boards.md](docs/boards.md)
- Decisions, and ideas we discussed but postponed or dropped: [docs/decisions-and-ideas.md](docs/decisions-and-ideas.md)
- Day-by-day log: [../timeline.md](../timeline.md)

```
v2/
├─ laptop_server/        the server: python main.py
│  ├─ pages/             the user's page designs: Main.dc.html (home, at /), Search.dc.html, Login.dc.html,
│  │                     Devices.dc.html, each with its script (main.js, search.js, login.js, devices.js) + api.js
│  ├─ data/              CSV files (people, programmes, timetable + everything the system writes)
│  └─ logs/server.log
├─ pi_edge/              the cabin device: sudo python3 main.py
│  ├─ pages/             PiDevice.dc.html (device page, at /), PiRegister.dc.html (registration) + scripts
│  ├─ data/              this device's own files (key, registered person, face numbers, black box record)
│  ├─ blackbox.py        records the board's health every 2 s (power, heat, memory) - finds why a board stopped
│  └─ logs/edge.log
└─ deploy_to_pi.ps1      copies pi_edge to a Pi and starts it
```

## 1. Run the laptop server

1. Turn on the Windows **Mobile hotspot**; the Pis join it. (The laptop is `192.168.137.1` on it.)
2. In `v2/laptop_server`: `python main.py`. The home page opens in the browser by itself (`--no-browser` to stop that).
   The first start makes an HTTPS certificate; the browser warns once (self-signed): *Advanced → Continue*.
3. Admin: **https://localhost:8080/login** on the laptop. The first time, the same form creates the admin account
   (only possible on the laptop itself).
4. If the Pis can't reach the server, allow port 8080 once in an admin PowerShell:
   `New-NetFirewallRule -DisplayName "Smart Cabin 8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -Profile Any`

The server **announces itself** on the network every 2 s (UDP port 50505), so the Pis find it without being told the
address. `python main.py --data <folder> --port 8091` runs a second copy on its own data (for trying things out).

## 2. Set up a Pi

1. Flash Raspberry Pi OS (trixie, 64-bit, **Lite / no desktop** on a Zero 2W) with the Wi-Fi and SSH set in Raspberry Pi Imager.
2. Copy the app (from the laptop):
   `scp -r "<repo>\v2\pi_edge" pi@<pi address>:~/smartcabin_v2`
3. Start it at every boot (installs what is missing the first time, turns SPI on - then asks for one reboot):
   `ssh pi@<pi address> "cd ~/smartcabin_v2 && sudo python3 main.py --autostart"`
   This installs two services: **smartcabin** (the app) and **smartcabin-blackbox** (the recorder).
4. The Pi appears on the **Devices** page as `SC-001`, `SC-002`, … (the next free number, from its hardware serial).
5. On the Devices page, **Save the location** of the device (e.g. *J block, 4th floor, cabin 412*).

## 3. Register the faculty member (at the cabin)

Open the device page `https://<pi address>:8000` (link on the Devices page). It says **One-time setup · Authorized by
server** (the server allows it while nobody is registered there and the location is set). **Start registration**:

1. **Find your name** (the list is copied from the server) → "Is this you?" → Yes.
2. **Your face:** Start camera → 10 photos with a live preview (only you in view, with light on your face).
3. **RFID card:** I am ready → tap the card.
4. **Save:** the server registers it; the device keeps the face (128 numbers per photo, no photos) and the card.

To register someone else at that device, the current person has to be removed first (for now: in
`registrations.csv`; a button is planned).

## 4. How the status is decided

| Light / page | Status | When |
|---|---|---|
| green | Available | the person is in, alone |
| yellow | In a meeting | the person is in, 2 or more people counted |
| red | Not available | not in (the pages add the timetable: "Class, back around 10:00" or "Leaving for <class> at 10:00") |
| grey (pages) | Unknown | the device sent nothing for 60 s |
| blue | – | registration going on at the device |
| white flash | – | dark room: light for one picture (at most once a minute) |

- **In:** the face recognised in 2 checks in a row, or a card tap. A card tap-in must be confirmed by the face within
  2 minutes (someone registered with a card only: by anyone being counted).
- **Out:** a card tap while in, or **the face not seen for 2 minutes** - even if other people are still counted.
- **Before a class:** a class / lab / meeting starting within 5 minutes and the face not seen for 2 minutes →
  "Leaving for <class>". Being seen in the cabin always wins.
- The pages also say **how** someone is in: *Seen and tapped in*, *Seen, not tapped in*, *Tapped in, not seen yet*.
- **Confidence:** face × card table (2 / 35 / 70 / 90 %), +10 % while someone is counted.

**Camera:** a 640x480 picture for the headcount (every 5 s on a Zero 2W, 2 s on a Pi 4 / 5; faster for 30 s after a
change), and a 1296x972 picture only when a face has to be checked. People: MobileNet-SSD (Zero) or YOLOv8n (Pi 4 / 5).
Faces: YuNet + SFace, always at a fixed 640x640 size (a changing size made the memory grow until the Zero ran out).
Above 70 °C half as many pictures, above 78 °C vision pauses.

## 5. The pages

All pages refresh every second.

| Page | Who | Shows |
|---|---|---|
| `/` Main | anyone | choose a school, search, role / status filters, each person's status, cabin, last report, today's timetable |
| `/search` | anyone | search with school / department / programme / status filters |
| `/login`, `/devices` | admin | every device: location, person, health, parts, setup; recent events; the server log |
| Pi `:8000` | anyone on the network | Simple: the status. Advanced: live fields, **Live view** (camera stream at 5–10 pictures a second, with the counted people boxed, only while open), live charts (people, confidence, temperature, CPU), registration details, device details, parts |

**Face sets and cards** (Pi page, Advanced → Registration details): *Add more face data* (10 more photos, which must
match the registered face), *Add another RFID card*, and *Delete* for each (at least one of each stays). Adding a card
and deleting need the registered person at the device: face seen or a registered card tapped in the last 2 minutes.
The server is updated each time (card ids only as hashes).

Not active yet (shown, but say so): the Maintenance buttons on the Pi page.

## 6. Troubleshooting

| You see | Do this |
|---|---|
| A red bar at the top of a page | The error in words. Full details: `laptop_server/logs/server.log` or `pi_edge/logs/edge.log` |
| "No answer from the server in 10 s" | The server is not running, or this device is not on the same network |
| Pi page: Server not connected | Read the reason. The Pi listens for the server's announcement and also tries `SERVER_URL` in `settings.py` |
| "The server's certificate changed" | Only after setting the server up again: delete `server_fingerprint` from `pi_edge/data/device.json` |
| A part says Problem | The reason is next to it; the rest keeps working. *Not present* = that hardware is not on this computer |
| The board / app stopped by itself | `python3 blackbox.py --report` on the Pi: last readings before the stop and the likely cause (power, heat, memory, Wi-Fi) |
| The app stops when SSH closes | Use the service (`--autostart`); logs: `sudo journalctl -u smartcabin -f` |

**On a computer without Pi hardware** (e.g. Windows) the device app runs as usual: missing parts show *Not present*,
the camera is the webcam (or `--picture photo.jpg`, or `--no-webcam`), cards are typed on the page. `--serial SIM-2
--port 8001` pretends to be a second device. `--http` (server and device) turns HTTPS off, for troubleshooting only.

## 7. Security (prototype)

- HTTPS everywhere (self-signed). The Pi remembers the server's certificate and refuses any other.
- Each device has its own secret key; reports without it are refused. Admin login (PBKDF2 hash) for every change.
- Registration is allowed only while nobody is registered at a device and the admin has set its location.
- The server keeps only a hash of card ids; faces (128 numbers each, no photos) stay on the Pi.
- The public pages show only name, designation, school, department, status, cabin and the timetable.
- Known limits: self-signed certificates, one admin, the device page has no login (its Live view can be seen by anyone
  on the network - accepted for the prototype).

## 8. Data files

`laptop_server/data/`: `people.csv`, `programs.csv`, `timetable.csv` (the existing lists; edits show up live) ·
`admin_account.csv`, `admin_sessions.csv`, `setup_pins.csv` · `devices.csv`, `device_health.csv` · `registrations.csv`
(with history) · `status_now.csv` · `presence_log.csv` (every report - the data for the paper and the machine learning) ·
`events_log.csv`.

`pi_edge/data/`: `device.json` (number, key, server address and certificate), `person.json`, `face.npy`,
`people_copy.csv`, `page_cert.pem` / `page_key.pem`, `blackbox.csv`, `blackbox_report.txt`.
