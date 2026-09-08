# ASTRA 1.0 — Predictive AI Rescue Rover for Underground Mine Safety

**SIH26039** · Problem Statement: AI-Powered Underground Mine Safety, Monitoring and Rescue System
**Theme:** Smart Automation · **PS Category:** Hardware
**Team:** Deck Mine

## Problem

Underground coal mining is India's highest-risk manual-rescue industry. Post-collapse,
human rescue teams enter unstable, gas-laden, unmapped zones with no early warning,
no autonomous first-responder, and no way to confirm which specific miner is trapped
where. 226 deaths were recorded in coal & lignite mine accidents between 2020–2024
(Ministry of Coal, Rajya Sabha statement, March 2025).

## Our Solution

ASTRA 1.0 is a predictive, multi-sensor-fusion rescue rover built on a Rocker-Bogie
mobility platform (NASA Mars-rover suspension heritage). Unlike single-sensor systems,
it fuses four subsystems into one decision pipeline:

1. **Rocker-Bogie Mobility Platform** — clears obstacles up to 2× wheel diameter,
   6061-T6 Al/CFRP chassis, IP68+ATEX/IECEx rated
2. **7-Gas Predictive Sensor Fusion** — CH4, CO, O2, H2S, CO2, NO2, coal-dust PM;
   slope-regression forecasts hazard before threshold breach
3. **Multi-Modal Life Detection** — YOLOv8n vision + FLIR thermal + TI IWR6843
   mmWave radar + RFID/BLE identity reader
4. **Autonomous Fail-Safe Intelligence** — BNO055 IMU + wheel-encoder dead-reckoning
   return; Jetson Orin Nano running onboard AI

### What makes it different

- **Predictive, not reactive** — forecasts gas hazards before threshold crossing
- **True identity confirmation** — RFID/BLE gives exact miner ID, not generic "person detected"
- **Never goes fully blind** — dual-mode comms (WiFi-Mesh/Fiber + LoRa fallback)
- **Terrain-proven mobility** — Rocker-Bogie validated across 3 NASA Mars missions
- **Self-recovering asset** — autonomous return means the rover and its data are never lost

## Repository Structure

```
ASTRA-1.0-Mine-Safety-Robot/
├── robot_code/          # ESP32 firmware — rover motor control, obstacle handling
│   └── RC_Bot_Code_ESP32.ino
├── dashboard/            # Control-room dashboard (Streamlit)
│   ├── app.py
│   ├── simulator.py
│   ├── requirements.txt
│   └── README.md
└── README.md             # you are here
```

## Control Room Dashboard

A live monitoring dashboard for gas trends, victim detection, rover position,
comms status, and battery health — see [`dashboard/README.md`](dashboard/README.md)
for setup and run instructions.

## Tech Stack

| Subsystem | Components |
|---|---|
| Motors | 6× BLDC 24V + ODrive/VESC, spark-free |
| Battery | LiFePO4 24V, dual redundant + BMS |
| Compute | Jetson Orin Nano |
| Gas Array | 7-sensor NDIR/electrochemical fusion |
| Water | 4-sensor flood-predict array |
| Vision | HD + IR / FLIR Boson thermal |
| Radar | TI IWR6843 mmWave |
| Identity | RFID/BLE tag reader |
| Comms | LoRa + Leaky Feeder + Fiber (Future: TTE) |

## Team Deck Mine

Ayush Kumar · Supriya Singh · Vishali · Ayush Keshav · Nikita Devi · Harmeet Kaur

## Links

- Documentation, Budget Report, TAM-SAM-SOM — linked in the SIH idea submission PDF
