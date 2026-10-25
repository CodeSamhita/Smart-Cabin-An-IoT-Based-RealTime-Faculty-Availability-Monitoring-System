# Smart Cabin v2 – diagrams

[← back to the v2 README](../README.md)

All diagrams are Mermaid: GitHub draws them as pictures; in VS Code use a Mermaid preview extension.

1. [The whole system](#1-the-whole-system)
2. [The laptop server: files and how they are linked](#2-the-laptop-server-files-and-how-they-are-linked)
3. [The cabin device: files and how they are linked](#3-the-cabin-device-files-and-how-they-are-linked)
4. [The cabin device: start-up and threads](#4-the-cabin-device-start-up-and-threads)
5. [The vision loop](#5-the-vision-loop)
6. [In or out (presence rules)](#6-in-or-out-presence-rules)
7. [How the server decides what the pages show](#7-how-the-server-decides-what-the-pages-show)
8. [A device finds the server and reports](#8-a-device-finds-the-server-and-reports)
9. [Registration at the cabin](#9-registration-at-the-cabin)
10. [Adding / deleting face sets and cards](#10-adding--deleting-face-sets-and-cards)
11. [Pages and the calls they use](#11-pages-and-the-calls-they-use)
12. [Data files](#12-data-files)

---

## 1. The whole system

```mermaid
flowchart LR
    subgraph CABIN["Cabin (one per faculty member)"]
        CAM["Pi Camera"] --> PI
        RFID["RC522 card reader"] --> PI
        PI["Raspberry Pi<br/>pi_edge/main.py<br/>decides: in / out, headcount,<br/>confidence, status"]
        PI --> LED["NeoPixel at the door<br/>green / yellow / red"]
    end
    PI -- "HTTPS + device key<br/>status, confidence, headcount,<br/>health (no pictures)<br/>every 2 s" --> SV
    SV -- "UDP broadcast every 2 s<br/>'SMARTCABIN https://…:8080'" -.-> PI
    subgraph LAPTOP["Laptop (server)"]
        SV["laptop_server/main.py<br/>CSV files, timetable rules"]
    end
    SV --> PUB["Main / Search pages<br/>anyone, no login"]
    SV --> ADM["Devices page<br/>admin login"]
    PI --> DP["Device page :8000<br/>status, live view,<br/>registration"]
```

## 2. The laptop server: files and how they are linked

```mermaid
flowchart TB
    MAIN["main.py<br/>start, open the home page"] --> WEB["web.py<br/>HTTPS server, routes,<br/>try / except on every call"]
    MAIN --> DISC["discovery.py<br/>UDP announcement"]
    WEB --> SEC["security.py<br/>passwords, sessions,<br/>device keys, certificate"]
    WEB --> DEV["devices.py<br/>register of devices,<br/>health"]
    WEB --> REG["registrations.py<br/>who is at which device,<br/>cards (hashes), history"]
    WEB --> ST["status.py<br/>reports in, status out,<br/>timetable rules"]
    WEB --> PEO["people.py<br/>faculty list, filters"]
    ST --> TT["timetable.py<br/>today, now, next"]
    ST --> REG
    ST --> DEV
    TT --> PEO
    SEC & DEV & REG & ST & PEO --> CSV["csv_store.py<br/>safe CSV read / write"]
    WEB & DEV & REG & ST --> LOG["logbook.py<br/>server.log + events_log.csv"]
    CSV --> FILES[("data/*.csv")]
    WEB --> PAGES["pages/<br/>Main, Search, Login, Devices<br/>+ their scripts, api.js"]
```

## 3. The cabin device: files and how they are linked

```mermaid
flowchart TB
    MAIN["main.py<br/>install, start threads,<br/>card taps → who wants it"] --> INST["install.py<br/>libraries, SPI, models"]
    MAIN --> RFID["rfid.py<br/>RC522 taps"]
    MAIN --> VIS["vision.py<br/>picture → headcount → face"]
    MAIN --> PRES["presence.py<br/>in / out, confidence, status"]
    MAIN --> LINK["server_link.py<br/>hello, reports, discovery"]
    MAIN --> WEB["web.py<br/>device page :8000"]
    VIS --> CAM["camera.py<br/>640x480 + 1296x972"]
    VIS --> PC["people_count.py<br/>MobileNet-SSD / YOLOv8n"]
    VIS --> FACE["face.py<br/>YuNet + SFace"]
    VIS --> LIVE["live.py<br/>live view stream"]
    VIS --> PRES
    PRES --> LED["led.py<br/>NeoPixel (Pi 5: pi5neo)"]
    PRES --> REGI["registration.py<br/>the registered person,<br/>registration steps"]
    WEB --> REGI
    WEB --> PD["person_data.py<br/>add / delete face sets, cards"]
    WEB --> DET["details.py<br/>device details"]
    WEB --> LIVE
    PD --> FACE
    PD --> REGI
    LINK --> HEALTH["health.py<br/>temperature, CPU, memory"]
    LINK --> ID["identity.py<br/>serial, key, server certificate"]
    LINK --> REGI
    ALL["all parts"] -.-> SH["shared.py<br/>shared state + lock"]
    ALL -.-> LOG["logbook.py<br/>edge.log"]
    BB["blackbox.py<br/>(separate service)<br/>health every 2 s"] --> BBF[("data/blackbox.csv")]
```

## 4. The cabin device: start-up and threads

```mermaid
flowchart TB
    BOOT["Pi switched on"] --> SVC1["service smartcabin<br/>(main.py)"]
    BOOT --> SVC2["service smartcabin-blackbox<br/>(blackbox.py)"]
    SVC2 --> BB1{"last run ended<br/>normally?"}
    BB1 -- no --> BB2["write blackbox_report.txt<br/>(last readings, likely cause,<br/>kernel messages)"]
    BB1 -- yes --> BB3["record every 2 s"]
    BB2 --> BB3
    SVC1 --> I["install.py: what is missing?<br/>libraries, SPI, models"]
    I --> SPI{"SPI on?"}
    SPI -- "just turned on" --> RB["ask for one reboot"]
    SPI -- yes --> T["start the threads"]
    T --> T1["rfid: card taps"]
    T --> T2["vision: pictures"]
    T --> T3["presence: timeouts every 1 s"]
    T --> T4["server: hello + reports"]
    T --> T5["discovery: listen for the server"]
    T --> T6["main thread: device page :8000"]
```

## 5. The vision loop

```mermaid
flowchart TB
    S(["round starts"]) --> BUSY{"face photos being<br/>taken (registration /<br/>add face)?"}
    BUSY -- yes --> W1["wait 0.5 s"] --> S
    BUSY -- no --> HOT{"CPU ≥ 78 °C?<br/>(or paused and ≥ 70 °C)"}
    HOT -- yes --> PAUSE["pause vision 10 s"] --> S
    HOT -- no --> SMALL["take 640x480 picture"]
    SMALL --> DARK{"dark?<br/>(brightness < 40)"}
    DARK -- "yes, and no flash<br/>in the last minute" --> FLASH["white LED,<br/>take it again"] --> COUNT
    DARK -- no --> COUNT["headcount<br/>(steady after 3 agree)"]
    COUNT --> NEED{"face registered and<br/>a check useful?<br/>(out, or tap unconfirmed,<br/>or 30 s since last)"}
    NEED -- no --> UPD
    NEED -- yes --> BIG["take 1296x972 picture"]
    BIG --> FACES["find faces in the person boxes<br/>(fixed 640x640), compare<br/>with the registered vectors"]
    FACES --> FC["presence: face seen / not"]
    FC --> UPD["update headcount, live view data,<br/>presence"]
    UPD --> WAIT["wait 5 s (Zero) / 2 s (Pi 4, 5)<br/>1.5 s / 1 s for 30 s after a change<br/>×2 above 70 °C"]
    WAIT --> S
```

## 6. In or out (presence rules)

```mermaid
stateDiagram-v2
    [*] --> Out
    Out --> In: face matched in 2 checks in a row
    Out --> InUnconfirmed: registered card tapped
    InUnconfirmed --> In: face seen within 2 min<br/>(card-only person: anyone counted)
    InUnconfirmed --> Out: not confirmed in 2 min
    In --> Out: card tapped again (logout,<br/>then 60 s pause for the face)
    In --> Out: face not seen for 2 min<br/>(card-only person: nobody counted for 2 min)
    state In {
        [*] --> Available
        Available --> InAMeeting: 2 or more people counted
        InAMeeting --> Available: 1 or fewer counted
    }
```

Confidence = face (seen in the last 2 min) × card (tapped in): none 2 %, card 35 %, face 70 %, both 90 %;
+10 % while someone is counted (max 95 %).

## 7. How the server decides what the pages show

```mermaid
flowchart TB
    P(["a person on a page"]) --> R{"registered at<br/>a device?"}
    R -- no --> NS["Not set up"]
    R -- yes --> SIL{"device silent<br/>for 60 s?"}
    SIL -- yes --> UK["Unknown<br/>(+ what the timetable says now)"]
    SIL -- no --> ST{"status from the Pi"}
    ST -- "available / meeting" --> SOON{"class / lab / meeting<br/>within 5 min, and face<br/>not seen for 2 min?"}
    SOON -- yes --> LEAVE["Not available<br/>'Leaving for <class> at <time>'"]
    SOON -- no --> IN["Available / In a meeting<br/>'until <next item>'<br/>+ how: Seen and tapped in /<br/>Seen, not tapped in /<br/>Tapped in, not seen yet"]
    ST -- not_available --> OUT{"timetable item now?"}
    OUT -- yes --> CLS["Not available<br/>'<class>, back around <end>'"]
    OUT -- no --> NIC["Not available<br/>'Not in the cabin' + next item"]
```

## 8. A device finds the server and reports

```mermaid
sequenceDiagram
    participant S as Laptop server
    participant P as Pi (new)
    S-->>P: UDP broadcast every 2 s: "SMARTCABIN https://192.168.137.1:8080"
    P->>P: remember the address (data/device.json)
    P->>S: HTTPS hello (serial, model, health)
    Note over P,S: the Pi remembers the server's certificate the first time and refuses any other later
    S->>S: new serial → next number SC-00n + a secret key (only its hash kept)
    S-->>P: number, key (once), location, registered person, setup allowed?
    loop every 2 s (at once after a change)
        P->>S: report (status, in, confidence, headcount, face / card, face_age, health) + key
        S->>S: status_now.csv, presence_log.csv, device_health.csv
        S-->>P: location, person, setup allowed?
    end
```

## 9. Registration at the cabin

```mermaid
sequenceDiagram
    actor F as Faculty member (phone / laptop)
    participant P as Pi device page
    participant S as Laptop server
    F->>P: Start registration
    P->>S: setup allowed? (nobody registered, location set)
    S-->>P: yes
    P->>S: the people list
    P-->>F: Find your name (list copied from the server)
    F->>P: pick name → "Is this you?" → yes
    F->>P: Start camera
    loop 10 photos (live preview, one face only)
        P->>P: picture → face → 128 numbers
    end
    F->>P: I am ready → taps the card
    F->>P: Save registration
    P->>S: register (person, card id, number of photos)
    S->>S: registrations.csv (card id only as a hash, old rows kept as history)
    S-->>P: registered
    P->>P: keep face.npy + person.json on the device
    P-->>F: Registration complete
```

## 10. Adding / deleting face sets and cards

```mermaid
flowchart TB
    A(["Pi page → Advanced →<br/>Registration details"]) --> WHAT{"which button?"}
    WHAT -- "Add more face data" --> F1["10 more photos"] --> F2{"do they match<br/>the registered face?"}
    F2 -- no --> FNO["not added<br/>(message with the score)"]
    F2 -- yes --> SAVE
    WHAT -- "Add another card" --> AT{"the person at the device?<br/>(face or registered card<br/>in the last 2 min)"}
    WHAT -- "Delete (face set / card)" --> AT
    AT -- no --> ANO["'Show your face or tap<br/>your card first'"]
    AT -- yes --> KIND{"add card or delete?"}
    KIND -- "add card" --> TAP["tap the new card<br/>within 30 s"] --> SAVE
    KIND -- delete --> ONE{"more than one left?"}
    ONE -- no --> KEEP["'at least one is kept'"]
    ONE -- yes --> SAVE
    SAVE["tell the server first<br/>(card hashes, number of photos)"] --> OK{"saved?"}
    OK -- no --> NOCH["nothing changed on the device"]
    OK -- yes --> DEVSAVE["change face.npy / person.json"]
```

## 11. Pages and the calls they use

```mermaid
flowchart LR
    subgraph Laptop pages
        MAINP["Main.dc.html<br/>main.js"]
        SRCH["Search.dc.html<br/>search.js"]
        LOGN["Login.dc.html<br/>login.js"]
        DEVP["Devices.dc.html<br/>devices.js"]
    end
    MAINP & SRCH --> A1["/api/people-status<br/>(every 1 s)"]
    MAINP & SRCH --> A2["/api/person?id="]
    LOGN --> A3["/api/admin/me, create, login"]
    DEVP --> A4["/api/admin/devices, log,<br/>location, pin, logout"]
    subgraph Pi pages
        PID["PiDevice.dc.html<br/>pidevice.js"]
        PIR["PiRegister.dc.html<br/>piregister.js"]
    end
    PID --> B1["/api/state (every 1 s,<br/>details every 10 s)"]
    PID --> B2["/live.mjpg (Advanced, live view)"]
    PID --> B3["/api/person/add-face, add-card,<br/>delete-face, delete-card, stop"]
    PIR --> B4["/api/register/start, people, pick,<br/>face, card, save, cancel"]
    PIR --> B5["/preview.jpg"]
```

## 12. Data files

```mermaid
erDiagram
    people ||--o| registrations : "is registered as"
    devices ||--o| registrations : "has (current) person"
    devices ||--|| device_health : "latest health"
    registrations ||--o| status_now : "current status"
    registrations ||--o{ presence_log : "every report"
    people ||--o{ timetable : "has items"
    programs }o--o{ people : "school offers"
    people {
        text id
        text name
        text designation
        text role
        text school
        text department
    }
    devices {
        text device "SC-001"
        text serial
        text location
        text key_hash
        text ip
        time last_seen
    }
    registrations {
        text person_id
        text device
        text location
        text card_hash "hashes, ; separated"
        int face_photos
        time from_time
        time to_time "empty = current"
    }
    status_now {
        text person_id
        text status
        int confidence
        int headcount
        text face
        text card
        int face_age
    }
    presence_log {
        time time
        text device
        int face
        int card
        int headcount
        int confidence
        text status
        float temperature
    }
    timetable {
        text person_id
        text day
        text start
        text end
        text activity
    }
```

On the Pi (`pi_edge/data/`): `device.json` (number, key, server address and certificate), `person.json` (person,
face sets, cards), `face.npy` (128 numbers per face photo), `people_copy.csv`, `blackbox.csv`, `blackbox_report.txt`.
