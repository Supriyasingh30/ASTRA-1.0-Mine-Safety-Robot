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
  detection confidence, comms signal). This is a stand-in for real sensors and is
  built so you can swap each function's *body* for a real serial/MQTT read later
  without touching the dashboard code.
- `app.py` — the Streamlit dashboard itself: layout, styling, charts, and the
  "Fused Risk Score" logic.

## Panels included (matches PPT slide 3 mockup)

1. Gas Monitoring — live 7-channel trend chart + slope-regression breach forecast
2. Victim Scan — synthetic thermal heatmap + detection confidence + RFID/BLE ID
3. Path Status / Rover Map — live (x,y) trail with base marker
4. Comms Status — Primary (WiFi-Mesh/Fiber) vs Fallback (LoRa) toggle + signal bar
5. Live Camera Feed — laptop webcam for now (near-live, refreshes every ~1.2s);
   swap `CAMERA_SOURCE` in app.py to the rover's camera once hardware is ready
6. Event Log — scrolling timestamped system events
7. Fused Risk Score banner — single SAFE/CAUTION/CRITICAL score (the core USP)

## Demo tips for judges

- Use the **"Trigger Gas Spike"** button live during your pitch — it drives a
  realistic rising-gas scenario so the breach forecast and risk banner change
  in real time in front of the panel.
- Use **"Toggle Comms Mode"** to show the dual-mode fail-safe story.
- The Live Camera Feed panel uses your laptop's webcam by default so it looks
  and behaves like a genuine live feed during demos. When the rover's actual
  camera hardware is ready, open app.py and change the CAMERA_SOURCE
  value near the top of the file (currently 0) to the rover camera's
  index or stream URL — nothing else in the code needs to change.

## Next steps to go further

- Replace `simulator.py` functions with real serial/MQTT reads once hardware
  sensors are wired to the Jetson Orin Nano.
- Add authentication / multi-rover support if you want a fleet view.
- Swap the synthetic heatmap for actual FLIR Boson thermal camera frames.
