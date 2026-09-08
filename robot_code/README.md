# Robot Code — ESP32 Firmware

This folder contains the ESP32 firmware for ASTRA 1.0's motor control and
obstacle-handling logic — validated through robo-race and robo-war trials
for drivetrain and obstacle-clearing performance.

## File

- `RC_Bot_Code_ESP32.ino` — main firmware controlling motor drivers,
  obstacle response, and manual/RC-assisted navigation for the current
  proof-of-concept build.

## How to flash

1. Open `RC_Bot_Code_ESP32.ino` in the Arduino IDE (with ESP32 board
   support installed via Boards Manager)
2. Select the correct ESP32 board and COM port under **Tools**
3. Click **Upload**

## Current scope vs. final design

This firmware reflects the **current low-cost prototype build** (~₹20K)
used for internal-round demonstration. The final mine-grade version
(~₹60K, per the project budget) will run on the Jetson Orin Nano for
onboard AI (gas-trend prediction, multi-sensor fusion, path planning,
fail-safe return) — see the main [README](../README.md) for the full
system architecture.
