# ASTRA 1.0 — Control Room Dashboard

Live monitoring dashboard for the ASTRA 1.0 mine rescue rover (SIH26039 — Team Deck Mine).

## How to run

```bash
pip install -r requirements.txt
streamlit run app.py
```

It will open automatically in your browser at `http://localhost:8501`.

## What's inside

- `simulator.py` — generates realistic fake telemetry (gas readings, rover position,
  detection confidence, comms signal, battery, fail-safe status, per-miner registry,
  two-way comms log). This is a stand-in for real sensors and is built so you can
  swap each function's *body* for a real serial/MQTT read later without touching
  the dashboard code.
- `app.py` — the Streamlit dashboard itself: layout, styling, charts, and the
  "Fused Risk Score" logic. Split into two independent fragments — a fast-ticking
  telemetry fragment (refreshes every 1.2s) and a communication fragment (only
  reruns on user interaction, so recording audio is never interrupted).

## Panels included

1. **Gas + Flood Monitoring** — live 7-channel gas trend chart, slope-regression
   breach forecast, and simulated 4-sensor water-level array
2. **Victim Scan — Multi-Modal Fusion** — synthetic thermal heatmap, detection
   confidence, and explicit status chips for each sensing layer (Vision/YOLOv8n,
   Thermal/FLIR Boson, mmWave Radar/IWR6843, RFID/BLE)
3. **Miner Registry** — individual detection score + status (FOUND / WEAK SIGNAL /
   NOT DETECTED) for each registered RFID/BLE tag, not just one shared number
4. **Path Status / Rover Map** — live (x,y) trail with base marker
5. **Comms Status** — Primary (WiFi-Mesh/Fiber) vs Fallback (LoRa) toggle + signal bar
6. **Battery** — charge % and health status (LiFePO4 24V dual-redundant)
7. **Fail-Safe (IMU)** — STANDBY vs ACTIVE/AUTO-RETURN, automatically triggers when
   comms signal drops too low or conditions turn critical (dead-reckoning return)
8. **Live Camera Feed** — laptop webcam by default (see Camera section below)
9. **Two-Way Communication** — real two-way *voice* link with the trapped miner via
   the rover's 4-mic beamforming + DSP array: record and send a real voice clip to
   the miner, and record a reply as the miner (demo stand-in for a teammate roleplaying
   the miner) or use the one-click "Simulate Miner Reply" for quick canned-text testing
10. **Fused Risk Score** — single SAFE/CAUTION/CRITICAL banner combining gas + flood
    (the core sensor-fusion differentiator), with distinct automatic alert tones for
    CAUTION (soft single beep) and CRITICAL (urgent double-beep)
11. **Event Log** — scrolling timestamped system events

## Demo tips for judges

- Use **"Gas Spike"** / **"Flood"** live during your pitch — the breach forecast and
  Fused Risk Score banner update in real time, with an automatic alert tone.
- Use **"Victim Found"** to show the Miner Registry and Victim Scan panels light up
  for a specific tag.
- Use **"Toggle Comms Mode"** to show the dual-mode fail-safe story, and note how the
  Fail-Safe (IMU) card automatically switches to ACTIVE if signal drops too far.
- In the Two-Way Communication panel, record a real voice message live — it plays
  back exactly as the rover's mic-array link would carry it.
- **Browser autoplay note:** browsers block automatic sound until you've clicked
  something on the page once. Click any button early in the demo (e.g. Toggle Comms)
  so the automatic CAUTION/CRITICAL alert tones are unlocked for the rest of the session.
- The Live Camera Feed panel uses your laptop's webcam by default. When the rover's
  actual camera hardware is ready, open `app.py` and change the `CAMERA_SOURCE` value
  near the top of the file (currently `0`) to the rover camera's index or stream URL —
  nothing else in the code needs to change.

## Next steps to go further

- Replace `simulator.py` functions with real serial/MQTT reads once hardware sensors
  are wired to the Jetson Orin Nano.
- Wire `receive_message_from_miner()` to the real mic-array audio pipeline once
  hardware exists — the dashboard already calls this exact function shape.
- Swap the synthetic heatmap for actual FLIR Boson thermal camera frames.
- Add multi-rover / fleet support if scaling the demo beyond a single unit.

- ![Dashboard Screenshot](dashboard_screenshot.png)
