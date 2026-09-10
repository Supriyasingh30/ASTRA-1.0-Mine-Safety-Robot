"""
ASTRA 1.0 — Sensor Data Simulator
----------------------------------
This module generates realistic fake telemetry so the dashboard can be
demoed before real hardware sensors are wired in. Every function here
is designed to be swapped later for a real serial/MQTT feed without
changing the dashboard code — just replace the body of each function.
"""

import random
import time
import numpy as np

# Gas channel baseline "safe" values and danger thresholds (illustrative units)
GAS_CHANNELS = {
    "CH4":  {"baseline": 0.5,  "threshold": 5.0,  "unit": "%LEL"},
    "CO":   {"baseline": 5,    "threshold": 50,   "unit": "ppm"},
    "O2":   {"baseline": 20.9, "threshold": 19.5, "unit": "%",  "inverted": True},
    "H2S":  {"baseline": 2,    "threshold": 10,   "unit": "ppm"},
    "CO2":  {"baseline": 400,  "threshold": 5000, "unit": "ppm"},
    "NO2":  {"baseline": 1,    "threshold": 5,    "unit": "ppm"},
    "PM":   {"baseline": 10,   "threshold": 150,  "unit": "µg/m³"},
}

# Mock RFID/BLE registry — in the final system this maps to the mine's
# actual shift-log database of miner tags checked in that day.
MINER_DATABASE = ["#2401", "#2407", "#2413", "#2417", "#2419"]


class ASTRASimulator:
    """Holds simulated rover + sensor state across dashboard refreshes."""

    def __init__(self):
        self.t = 0
        self.gas_history = {g: [] for g in GAS_CHANNELS}
        self.rover_path = [(0.0, 0.0)]
        self.spike_active = {g: False for g in GAS_CHANNELS}
        self.spike_ticks_left = {g: 0 for g in GAS_CHANNELS}
        self.comms_mode = "primary"  # "primary" or "fallback"
        self.event_log = []
        self.flood_level = 0.0          # 0-100, simulated water sensor array
        self.flood_active = False
        self.flood_ticks_left = 0
        self.victim_found_override = None  # None, or forced high-confidence event
        self.victim_ticks_left = 0
        self.comm_log = []  # two-way audio comms transcript with trapped miner
        self.battery_pct = 92.0
        self._log("System initialized — ASTRA 1.0 online")

    # ---------------- Scenario controls ----------------
    def trigger_flood(self, duration=25):
        self.flood_active = True
        self.flood_ticks_left = duration
        self._log("⚠ Manual scenario triggered — flood-prediction alert started")

    def trigger_victim_found(self, duration=15):
        self.victim_found_override = "#2417"
        self.victim_ticks_left = duration
        self._log("🟢 Manual scenario triggered — high-confidence victim signature acquired")

    def reset_scenario(self):
        """Reset all manually-triggered demo scenarios back to a normal baseline."""
        for gas in GAS_CHANNELS:
            self.spike_active[gas] = False
            self.spike_ticks_left[gas] = 0
        self.flood_active = False
        self.flood_ticks_left = 0
        self.flood_level = 0.0
        self.victim_found_override = None
        self.victim_ticks_left = 0
        self._log("System reset — all scenarios cleared, returning to baseline")

    def get_flood_level(self):
        if self.flood_active and self.flood_ticks_left > 0:
            progress = 1 - (self.flood_ticks_left / 25)
            self.flood_level = min(95, progress * 90 + random.uniform(-2, 2))
            self.flood_ticks_left -= 1
            if self.flood_ticks_left <= 0:
                self.flood_active = False
                self._log("Flood level trend stabilizing")
        else:
            self.flood_level = max(0, self.flood_level - random.uniform(0.5, 1.5))
        return round(self.flood_level, 1)

    def flood_status(self):
        level = self.flood_level
        if level >= 70:
            return "CRITICAL"
        elif level >= 30:
            return "CAUTION"
        return "SAFE"

    def get_battery(self):
        # Slow steady drain + tiny noise, resets aren't meant to refill it —
        # this simulates real runtime depletion during a mission.
        self.battery_pct = max(5, self.battery_pct - random.uniform(0.01, 0.04))
        return round(self.battery_pct, 1)

    # ---------------- Gas readings ----------------
    def trigger_spike(self, gas="CH4", duration=25):
        """Manually trigger a rising-gas scenario for live demo purposes."""
        self.spike_active[gas] = True
        self.spike_ticks_left[gas] = duration
        self._log(f"⚠ Manual scenario triggered — {gas} rising trend started")

    def get_gas_readings(self):
        self.t += 1
        readings = {}
        for gas, cfg in GAS_CHANNELS.items():
            base = cfg["baseline"]
            noise = np.random.normal(0, base * 0.03 + 0.05)
            value = base + noise

            if self.spike_active[gas] and self.spike_ticks_left[gas] > 0:
                progress = 1 - (self.spike_ticks_left[gas] / 25)
                direction = -1 if cfg.get("inverted") else 1
                value = base + direction * progress * (cfg["threshold"] - base) * 1.3
                self.spike_ticks_left[gas] -= 1
                if self.spike_ticks_left[gas] <= 0:
                    self.spike_active[gas] = False
                    self._log(f"{gas} trend returning to baseline")

            value = max(0, value)
            readings[gas] = round(value, 2)
            self.gas_history[gas].append(value)
            if len(self.gas_history[gas]) > 60:
                self.gas_history[gas].pop(0)

        return readings

    def predict_breach(self, gas):
        """Simple slope-regression forecast: fit a line to recent history,
        estimate minutes until threshold is crossed."""
        hist = self.gas_history[gas]
        if len(hist) < 6:
            return None
        y = np.array(hist[-10:])
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        cfg = GAS_CHANNELS[gas]
        threshold = cfg["threshold"]
        inverted = cfg.get("inverted", False)

        if inverted:
            if slope >= -1e-6:
                return None
            steps_to_breach = (threshold - y[-1]) / slope
        else:
            if slope <= 1e-6:
                return None
            steps_to_breach = (threshold - y[-1]) / slope

        if steps_to_breach <= 0 or steps_to_breach > 120:
            return None
        return round(steps_to_breach, 1)  # in "ticks" — treat as minutes for demo

    def overall_gas_status(self):
        worst = "SAFE"
        for gas, cfg in GAS_CHANNELS.items():
            latest = self.gas_history[gas][-1] if self.gas_history[gas] else cfg["baseline"]
            threshold = cfg["threshold"]
            inverted = cfg.get("inverted", False)
            ratio = (threshold - latest) / threshold if inverted else latest / threshold

            forecast = self.predict_breach(gas)
            if (inverted and latest <= threshold) or (not inverted and latest >= threshold):
                return "CRITICAL"
            elif forecast is not None and forecast <= 10:
                worst = "CAUTION" if worst != "CRITICAL" else worst
            elif ratio > 0.7 and worst == "SAFE":
                worst = "CAUTION"
        return worst

    # ---------------- Rover position / path ----------------
    def get_rover_position(self):
        last_x, last_y = self.rover_path[-1]
        dx = random.uniform(-0.5, 0.8)
        dy = random.uniform(-0.4, 0.4)
        new_pos = (last_x + dx, last_y + dy)
        self.rover_path.append(new_pos)
        if len(self.rover_path) > 100:
            self.rover_path.pop(0)
        return self.rover_path

    # ---------------- Victim detection ----------------
    def get_detection_confidence(self):
        if self.victim_found_override and self.victim_ticks_left > 0:
            self.victim_ticks_left -= 1
            confidence = 90 + random.uniform(-3, 5)
            if self.victim_ticks_left <= 0:
                self.victim_found_override = None
                self._log("Victim scenario ended — resuming normal scan")
            self.last_confidence = round(min(99, confidence), 1)
        else:
            base = 40 + 30 * abs(np.sin(self.t / 8))
            noise = random.uniform(-5, 5)
            self.last_confidence = round(min(99, max(0, base + noise)), 1)
        return self.last_confidence

    def get_miner_id(self):
        # Uses the confidence already computed this tick (avoids re-rolling randomness)
        confidence = getattr(self, "last_confidence", 0)
        if self.victim_found_override or confidence > 60:
            return "#2417" if self.victim_found_override else f"#{2400 + (self.t % 20)}"
        return None

    def get_miner_registry(self):
        """Per-miner detection scores — each tag gets its own confidence
        curve (phase-shifted) so the registry feels like independent,
        real detections rather than one shared number."""
        registry = []
        for i, miner_id in enumerate(MINER_DATABASE):
            phase = i * 2.1
            base = 30 + 25 * abs(np.sin((self.t + phase * 10) / 9))
            noise = random.uniform(-4, 4)
            score = round(min(99, max(0, base + noise)), 1)

            # The manually-triggered "Victim Found" scenario boosts one tag
            if self.victim_found_override and miner_id == "#2417":
                score = round(min(99, 90 + random.uniform(-3, 5)), 1)

            if score >= 70:
                status = "FOUND"
            elif score >= 40:
                status = "WEAK SIGNAL"
            else:
                status = "NOT DETECTED"

            registry.append({"id": miner_id, "score": score, "status": status})
        return registry

    # ---------------- Comms ----------------
    def toggle_comms(self):
        self.comms_mode = "fallback" if self.comms_mode == "primary" else "primary"
        label = "LoRa Fallback" if self.comms_mode == "fallback" else "Primary (WiFi-Mesh/Fiber)"
        self._log(f"Comms switched to {label}")

    def get_comms_signal(self):
        if self.comms_mode == "primary":
            return random.randint(70, 95)
        return random.randint(30, 55)

    # ---------------- Autonomous fail-safe (IMU dead-reckoning return) ----------------
    def get_failsafe_status(self, comms_signal, gas_status, flood_status):
        """Simulates the rover's autonomous fail-safe logic: if comms drops
        too low OR conditions turn critical, the onboard AI would trigger
        an autonomous dead-reckoning return using the BNO055 IMU."""
        if comms_signal < 35 or gas_status == "CRITICAL" or flood_status == "CRITICAL":
            return "ACTIVE — AUTO-RETURN ENGAGED"
        return "STANDBY — MANUAL/AI PATH CONTROL"

    # ---------------- Multi-modal detection layers ----------------
    def get_detection_layers(self):
        """Status of each sensing modality feeding the victim-scan fusion.
        All layers stay active in this simulation; on real hardware each
        would reflect actual sensor health."""
        return {
            "Vision (YOLOv8n)": True,
            "Thermal (FLIR Boson)": True,
            "mmWave Radar (IWR6843)": True,
            "RFID/BLE": True,
        }

    # ---------------- Event log ----------------
    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.event_log.insert(0, f"[{timestamp}] {message}")
        if len(self.event_log) > 30:
            self.event_log.pop()

    def log_event(self, message):
        self._log(message)

    # ---------------- Two-way audio communication with trapped miner ----------------
    # comm_log can grow without bound over a long demo/mission (especially
    # once real audio clips are involved, which are much bigger than text).
    # Cap it so memory use — and therefore UI responsiveness — stays flat
    # no matter how long the session runs.
    MAX_COMM_LOG = 100

    def _append_comm_log(self, entry):
        self.comm_log.append(entry)
        if len(self.comm_log) > self.MAX_COMM_LOG:
            self.comm_log.pop(0)

    def send_message_to_miner(self, text=None, audio_bytes=None):
        """Rescue team -> miner, via the rover's 4-mic beamforming + DSP
        audio array (only possible once the rover is within acoustic
        range, i.e. a miner has been located). Accepts either a typed
        note or a real recorded voice clip."""
        timestamp = time.strftime("%H:%M:%S")
        entry = {"from": "Rescue Team", "time": timestamp}
        if audio_bytes is not None:
            entry["type"] = "audio"
            entry["audio"] = audio_bytes
        else:
            entry["type"] = "text"
            entry["text"] = text
        self._append_comm_log(entry)
        self._log("Voice message sent to trapped miner via rover audio link")

    def receive_message_from_miner(self, audio_bytes=None, text=None):
        """Miner -> rescue team, real audio captured from the rover's
        onboard mic array once within acoustic range (~20 m in quiet
        conditions; expect roughly 3-8 m of reliably intelligible range
        inside a noisy tunnel unless amplification/noise suppression is
        added on top of the beamforming array).

        HARDWARE HOOK: on the real rover, call this whenever the onboard
        mic array / DSP pipeline has a finished utterance ready (e.g. a
        callback from your audio-streaming client over WiFi-mesh/LoRa).
        Until that hardware exists, the dashboard calls this same
        function from its own "record as miner" input as a stand-in —
        so during a live demo, a teammate role-playing the trapped miner
        can record a real clip and it appears here exactly the way a
        genuine rover capture would.
        """
        timestamp = time.strftime("%H:%M:%S")
        entry = {"from": "Miner", "time": timestamp}
        if audio_bytes is not None:
            entry["type"] = "audio"
            entry["audio"] = audio_bytes
        else:
            entry["type"] = "text"
            entry["text"] = text
        self._append_comm_log(entry)
        self._log("Incoming audio from trapped miner — transcript logged")

    def simulate_miner_reply(self):
        """Canned-text acknowledgement — a one-click stand-in for quick
        rehearsal. For an actual demo of the two-way audio link, prefer
        receive_message_from_miner() with a real recorded clip instead."""
        timestamp = time.strftime("%H:%M:%S")
        replies = [
            "We can hear you. Two of us are here, conscious.",
            "Air feels okay for now. No visible flooding here.",
            "One person injured, leg — needs help fast.",
            "Understood, we'll stay near the marked position.",
        ]
        text = random.choice(replies)
        self._append_comm_log({"from": "Miner", "type": "text", "text": text, "time": timestamp})
        self._log("Incoming audio from trapped miner — transcript logged (simulated)")