# ESP32 codes (archived, idea dropped 25 Oct 2026)

**Not used any more.** The project uses a Raspberry Pi in each cabin instead (see `pi board codes/smart cabin system/`). This folder is kept only for the documentation and the report: why the ESP32-CAM was tried and why it was dropped (it can't run face recognition, so pictures would have to leave the cabin).

Everything that needed an ESP32 board together with the laptop was in this folder.

| File | Runs on | What it does |
|---|---|---|
| `Headcount ESP32-CAM.py` | Laptop | Every 10 s asks the ESP32-CAM for a JPEG (`GET /capture` with an `X-Token` header), counts people with YOLOv8 nano, and prints the head count once 3 readings in a row agree |
| `requirements.txt` | – | Libraries the script needs |

Run on the laptop:

```
cd "Documents/Archive - ESP32 (dropped)/esp32 codes"
pip install -r requirements.txt
python "Headcount ESP32-CAM.py"
```

Before running, set `CAM_URL` (the ESP32-CAM's IP) and `TOKEN` at the top of the script. `yolov8n.pt` is downloaded on the first run if it is not in this folder.

**Not here yet:** the Arduino sketch for the ESP32-CAM itself, which serves `/capture` and checks the token.
