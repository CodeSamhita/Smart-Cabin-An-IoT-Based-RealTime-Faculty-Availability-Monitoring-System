# Status rules

[← back to README](../README.md)

Two places, each with one job:
- **The Pi** (`presence.py`) turns raw sensor readings into evidence: *is the owner in?* and *how many people?*
- **The laptop** (`status_engine.py`) turns that evidence, the timetable and the manual buttons into the **one status** everyone sees.

## 1. In or out? (on the Pi)

```mermaid
stateDiagram-v2
    [*] --> Out
    Out --> In: face matched in 2 pictures in a row
    Out --> In: card tap (login)
    In --> In: face seen, or phone answers (keeps it alive)
    In --> Out: no face AND no phone for 180 s
    In --> Out: card tap (logout)
    In --> Out: card login not confirmed by face or phone within 120 s
    note right of Out
        After a logout tap the face is ignored for 60 s
        (they are still walking out of view).
        The phone alone never brings someone in.
    end note
```

| Rule | Value | Why |
|---|---|---|
| Picture every | 5 s, or 1.5 s for 30 s after a change | saves CPU on the Zero 2W, reacts fast when something happens |
| Arrive by face | 2 pictures in a row | one wrong match can't flip the status |
| Card confirm | 120 s | a card proves the card was there, not the person |
| Leave | 180 s without face and phone | looking down or turning away must not flip to red. Leaving waits longer than arriving on purpose |
| Phone | keeps "in", never makes "in" | phones reach through walls ("evidence, not trust") |
| Headcount | steady after 3 pictures agree; photos and posters removed | a visitor passing the door doesn't flip it |
| Headcount sent | `max(count, 1 if in)` | if the camera misses the owner but the card or phone says in, they still count |

## 2. The status (on the laptop)

```mermaid
flowchart TD
    START(["Report from the Pi, or the 5 s timer"]) --> O{"Manual button active?"}
    O -- yes --> OS["Show it, labelled 'set by them'"]
    O -- no --> S{"Device silent for 60 s?"}
    S -- yes --> K{"Timetable: class, lab, meeting now?"}
    K -- yes --> RK["Red: In class CSE301, J block 4th floor Room 3,<br/>back around 11:40"]
    K -- no --> G["Grey: Cabin device offline"]
    S -- no --> I{"Owner in the cabin?"}
    I -- yes --> H{"Headcount 2 or more?"}
    H -- yes --> Y["Yellow: In a meeting<br/>until 11:00, then Class ..."]
    H -- no --> GR["Green: Available<br/>until 11:00 / rest of the day"]
    I -- no --> T{"Timetable item now?"}
    T -- yes --> R1["Red: where + back around"]
    T -- no --> R2["Red: Not in the cabin<br/>next: Class at 14:00"]
    GR & Y & R1 & R2 & G & RK --> B["Buffer: a new automatic status<br/>must hold 10 s before it is shown"]
    OS --> SHOW["Shown on pages + the cabin light"]
    B --> SHOW
```

### Manual buttons and how they end

| Button | Ends when |
|---|---|
| **Available** (green) | the device saw them *in* and then *out*, or after 60 min |
| **In a meeting** (yellow) | the headcount was 2 or more and then drops to 1 or less for 20 s, or they leave, or after 60 min. *If the camera never saw 2 people (the reason it was pressed), only leaving or the 60 min end it* |
| **Not available** (red) + reason (busy / break / meeting outside / leave) + time | at that time, on a card **login** tap, or on **Auto** |
| **Auto** | clears the button: sensors and timetable decide again |

The hardware buttons work the same way. Pressing the active one again = Auto.

### Why grey during a break

When the device is silent:
- during a **class, lab or meeting** the page can still say where they are, because the timetable knows.
- during a **break or office hours** they may well be in the cabin, so the honest answer is *unknown*.

This was found by the automatic test on 24 Oct 2026 and fixed.

## Timing (worst case, by design)

![Arrival to public page](charts/update_delay.png)

Most of the 30 s is the 10 s buffer and the 10 s page refresh. Both are settings in `laptop/config.py` and `static/status.js`, and can be shortened once the real hardware has been measured.
