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

    # ---------------- Comms ----------------
    def toggle_comms(self):
        self.comms_mode = "fallback" if self.comms_mode == "primary" else "primary"
        label = "LoRa Fallback" if self.comms_mode == "fallback" else "Primary (WiFi-Mesh/Fiber)"
        self._log(f"Comms switched to {label}")

    def get_comms_signal(self):
        if self.comms_mode == "primary":
            return random.randint(70, 95)
        return random.randint(30, 55)

    # ---------------- Event log ----------------
    def _log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.event_log.insert(0, f"[{timestamp}] {message}")
        if len(self.event_log) > 30:
            self.event_log.pop()

    def log_event(self, message):
        self._log(message)