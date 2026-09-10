"""
ASTRA 1.0 — Mine Rescue Rover Control Room Dashboard
------------------------------------------------------
Team Deck Mine | SIH26039

Run with:  streamlit run app.py
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import cv2
import time
import io
import wave
from simulator import ASTRASimulator, GAS_CHANNELS


def make_beep_bytes(freq=880, duration=0.35, repeats=1, gap=0.12):
    """Generates a WAV tone as raw bytes. repeats>1 creates a pulsed alarm
    (e.g. double-beep for critical) by inserting silence between tones."""
    sr = 44100
    t_arr = np.linspace(0, duration, int(sr * duration), False)
    tone = 0.4 * np.sin(freq * t_arr * 2 * np.pi)
    silence = np.zeros(int(sr * gap))
    parts = []
    for i in range(repeats):
        parts.append(tone)
        if i < repeats - 1:
            parts.append(silence)
    full = np.concatenate(parts)
    audio_arr = (full * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_arr.tobytes())
    return buf.getvalue()


# ------------------------------------------------------------------
# CAMERA SOURCE CONFIG
# ------------------------------------------------------------------
# For now: 0 = laptop's built-in webcam (used for live demo purposes).
# LATER (once hardware is ready): change this single value to the
# rover camera's index/URL, e.g. 1 for a USB camera, or an IP stream
# URL like "http://<jetson-ip>:8080/video" — nothing else needs to change.
CAMERA_SOURCE = 0

# ------------------------------------------------------------------
# PAGE CONFIG + THEME
# ------------------------------------------------------------------
st.set_page_config(
    page_title="ASTRA 1.0 — Control Room",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
:root {
    --bg-main: #0b0e14;
    --bg-panel: #12161f;
    --bg-panel-border: #232a38;
    --text-primary: #e6e9ef;
    --text-dim: #8b94a7;
    --green: #2ecc71;
    --orange: #f39c12;
    --red: #e74c3c;
    --blue: #3498db;
}

.stApp {
    background-color: var(--bg-main);
    color: var(--text-primary);
    font-family: 'Segoe UI', Roboto, sans-serif;
}

#MainMenu, footer, header {visibility: hidden;}

.panel {
    background-color: var(--bg-panel);
    border: 1px solid var(--bg-panel-border);
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 14px;
}

.panel-title {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 8px;
}

.status-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.03em;
}
.status-safe { background-color: rgba(46,204,113,0.15); color: var(--green); border: 1px solid var(--green); }
.status-caution { background-color: rgba(243,156,18,0.15); color: var(--orange); border: 1px solid var(--orange); }
.status-critical { background-color: rgba(231,76,60,0.15); color: var(--red); border: 1px solid var(--red); animation: pulse 1.2s infinite; }

@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(231,76,60,0.5); }
    70% { box-shadow: 0 0 0 8px rgba(231,76,60,0); }
    100% { box-shadow: 0 0 0 0 rgba(231,76,60,0); }
}

.big-metric {
    font-size: 30px;
    font-weight: 800;
    margin: 2px 0;
}

.small-label {
    font-size: 12px;
    color: var(--text-dim);
}

/* Style Streamlit's native bordered containers to match the dark panel look */
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--bg-panel);
    border: 1px solid var(--bg-panel-border) !important;
    border-radius: 10px !important;
    padding: 6px 10px;
}

.event-line {
    font-size: 12.5px;
    font-family: 'Consolas', monospace;
    color: var(--text-dim);
    padding: 3px 0;
    border-bottom: 1px solid var(--bg-panel-border);
}

.risk-banner {
    text-align: center;
    padding: 22px;
    border-radius: 12px;
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------
# STATE
# ------------------------------------------------------------------
if "sim" not in st.session_state:
    st.session_state.sim = ASTRASimulator()

@st.cache_resource
def get_camera(source):
    """One camera handle shared across every browser tab / session.
    Opening cv2.VideoCapture per-session (the old behavior) means each
    open tab grabs an exclusive OS-level lock on the webcam — the second
    tab (or a rerun after a crash) then fails with 'could not access
    camera'. st.cache_resource makes this a true singleton for the whole
    Streamlit process, so only one lock is ever taken."""
    # CAP_DSHOW is generally more reliable than the default MSMF backend
    # on Windows and avoids a lot of spurious "access denied" failures.
    cam = cv2.VideoCapture(source, cv2.CAP_DSHOW)
    if not cam.isOpened():
        # Fall back to default backend if DSHOW isn't available.
        cam = cv2.VideoCapture(source)
    try:
        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cam

# Bumping this key forces a fresh st.audio_input widget instance after a
# message is sent, effectively "clearing" the recorder for the next take.
if "audio_key_counter" not in st.session_state:
    st.session_state.audio_key_counter = 0

sim = st.session_state.sim
camera = get_camera(CAMERA_SOURCE)


# ====================================================================
# FRAGMENT 1 — fast-ticking telemetry (gas, victim scan, camera, map).
# Runs every 1.2s on its own timer. Deliberately does NOT contain the
# audio recorder: reruns here must never touch that widget's DOM node.
# ====================================================================
@st.fragment(run_every=1.2)
def render_dashboard():
    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------
    h1, h2, h3 = st.columns([3, 2, 3])
    with h1:
        st.markdown("### ⛏️ ASTRA 1.0 — Mine Rescue Rover Control Room")
        st.markdown(
            '<span class="small-label">SIH26039 · Team Deck Mine · Live Prototype Feed</span> '
            '&nbsp;&nbsp;<span class="status-badge status-safe" style="font-size:10px; padding:2px 10px;">'
            'DGMS / ATEX / IECEx — Compliant Design</span>',
            unsafe_allow_html=True,
        )
    with h3:
        colA, colB, colC, colD = st.columns(4)
        with colA:
            if st.button("⚠ Gas Spike"):
                sim.trigger_spike("CH4")
        with colB:
            if st.button("🌊 Flood"):
                sim.trigger_flood()
        with colC:
            if st.button("🧍 Victim Found"):
                sim.trigger_victim_found()
        with colD:
            if st.button("↺ Reset"):
                sim.reset_scenario()
        if st.button("📡 Toggle Comms Mode", use_container_width=True):
            sim.toggle_comms()

    # ------------------------------------------------------------------
    # PULL LATEST DATA
    # ------------------------------------------------------------------
    gas_readings = sim.get_gas_readings()
    gas_status = sim.overall_gas_status()
    rover_path = sim.get_rover_position()
    confidence = sim.get_detection_confidence()
    miner_id = sim.get_miner_id()
    comms_signal = sim.get_comms_signal()
    flood_level = sim.get_flood_level()
    flood_status = sim.flood_status()
    battery_pct = sim.get_battery()
    failsafe_status = sim.get_failsafe_status(comms_signal, gas_status, flood_status)

    status_class = {"SAFE": "status-safe", "CAUTION": "status-caution", "CRITICAL": "status-critical"}[gas_status]
    risk_colors = {"SAFE": "rgba(46,204,113,0.12)", "CAUTION": "rgba(243,156,18,0.12)", "CRITICAL": "rgba(231,76,60,0.15)"}
    risk_text_colors = {"SAFE": "#2ecc71", "CAUTION": "#f39c12", "CRITICAL": "#e74c3c"}

    # Combine gas + flood into the single fused banner (worst of the two wins)
    severity_rank = {"SAFE": 0, "CAUTION": 1, "CRITICAL": 2}
    fused_status = gas_status if severity_rank[gas_status] >= severity_rank[flood_status] else flood_status

    # ------------------------------------------------------------------
    # SOUND ALERT — distinct tones when the fused status *worsens* into
    # CAUTION or CRITICAL (fires automatically, no manual trigger needed)
    # ------------------------------------------------------------------
    if "prev_status" not in st.session_state:
        st.session_state.prev_status = "SAFE"

    severity_rank_local = {"SAFE": 0, "CAUTION": 1, "CRITICAL": 2}
    got_worse = severity_rank_local[fused_status] > severity_rank_local[st.session_state.prev_status]

    if got_worse and fused_status == "CAUTION":
        st.audio(make_beep_bytes(freq=600, duration=0.3, repeats=1), format="audio/wav", autoplay=True)
    elif got_worse and fused_status == "CRITICAL":
        st.audio(make_beep_bytes(freq=1000, duration=0.25, repeats=2, gap=0.1), format="audio/wav", autoplay=True)

    st.session_state.prev_status = fused_status

    # ------------------------------------------------------------------
    # OVERALL RISK SCORE (fusion banner — the differentiator)
    # ------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="risk-banner" style="background-color:{risk_colors[fused_status]}; color:{risk_text_colors[fused_status]}; border: 1px solid {risk_text_colors[fused_status]};">
            FUSED RISK SCORE: {fused_status}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------
    # TOP ROW — 6 STATUS CARDS
    # ------------------------------------------------------------------
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    with c1:
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Gas + Flood Monitoring</div>
            <span class="status-badge {status_class}">{gas_status}</span>
            <div class="small-label" style="margin-top:8px;">All 7 gas channels · Water level: {flood_level}% ({flood_status})</div>
            </div>''',
            unsafe_allow_html=True,
        )

    with c2:
        label = f"Miner ID {miner_id} detected" if miner_id else "Scanning..."
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Victim Scan</div>
            <div class="big-metric">{confidence}%</div>
            <div class="small-label">{label}</div>
            </div>''',
            unsafe_allow_html=True,
        )

    with c3:
        last_x, last_y = rover_path[-1]
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Path Status</div>
            <span class="status-badge status-safe">CLEAR</span>
            <div class="small-label" style="margin-top:8px;">Position: ({last_x:.1f}, {last_y:.1f})</div>
            </div>''',
            unsafe_allow_html=True,
        )

    with c4:
        mode_label = "PRIMARY" if sim.comms_mode == "primary" else "FALLBACK (LoRa)"
        badge_class = "status-safe" if sim.comms_mode == "primary" else "status-caution"
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Comms Status</div>
            <span class="status-badge {badge_class}">{mode_label}</span>
            <div class="small-label" style="margin-top:8px;">Signal: {comms_signal}%</div>
            </div>''',
            unsafe_allow_html=True,
        )

    with c5:
        batt_class = "status-safe" if battery_pct > 30 else ("status-caution" if battery_pct > 15 else "status-critical")
        batt_label = "OK" if battery_pct > 30 else ("LOW" if battery_pct > 15 else "CRITICAL")
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Battery</div>
            <span class="status-badge {batt_class}">{batt_label}</span>
            <div class="small-label" style="margin-top:8px;">{battery_pct}% · LiFePO4 24V dual-redundant</div>
            </div>''',
            unsafe_allow_html=True,
        )

    with c6:
        fs_active = failsafe_status.startswith("ACTIVE")
        fs_class = "status-critical" if fs_active else "status-safe"
        fs_label = "AUTO-RETURN" if fs_active else "STANDBY"
        st.markdown(
            f'''<div class="panel">
            <div class="panel-title">Fail-Safe (IMU)</div>
            <span class="status-badge {fs_class}">{fs_label}</span>
            <div class="small-label" style="margin-top:8px;">{failsafe_status}</div>
            </div>''',
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # MIDDLE ROW — GAS CHART + VICTIM SCAN VISUAL
    # ------------------------------------------------------------------
    m1, m2 = st.columns([2, 1])

    with m1:
        panel = st.container(border=True)
        panel.markdown('<div class="panel-title">Gas Trend (Last 60 Readings)</div>', unsafe_allow_html=True)

        fig = go.Figure()
        colors = ["#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c", "#e67e22"]
        for i, (gas, hist) in enumerate(sim.gas_history.items()):
            if hist:
                fig.add_trace(go.Scatter(
                    y=hist, mode="lines", name=gas,
                    line=dict(color=colors[i % len(colors)], width=2),
                ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#8b94a7", size=11),
            margin=dict(l=10, r=10, t=10, b=10),
            height=280,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=10)),
            xaxis=dict(showgrid=False, title="ticks"),
            yaxis=dict(showgrid=True, gridcolor="#1c212c"),
        )
        panel.plotly_chart(fig, use_container_width=True)

        forecasts = []
        for gas in GAS_CHANNELS:
            f = sim.predict_breach(gas)
            if f is not None:
                forecasts.append(f"⚠ {gas} predicted to breach threshold in ~{f:.0f} ticks")
        if forecasts:
            for f in forecasts:
                panel.markdown(f'<div class="small-label" style="color:#f39c12;">{f}</div>', unsafe_allow_html=True)
        else:
            panel.markdown('<div class="small-label">No breach predicted — all trends stable</div>', unsafe_allow_html=True)

    with m2:
        panel2 = st.container(border=True)
        panel2.markdown('<div class="panel-title">Victim Scan — Multi-Modal Fusion</div>', unsafe_allow_html=True)

        layers = sim.get_detection_layers()
        chips_html = "".join(
            f'<span class="status-badge status-safe" style="font-size:9px; padding:2px 8px; margin-right:5px;">{name} ✓</span>'
            for name in layers
        )
        panel2.markdown(f'<div style="margin-bottom:8px;">{chips_html}</div>', unsafe_allow_html=True)

        np.random.seed(int(sim.t / 3))
        heat = np.random.rand(15, 20) * 0.3
        hot_x, hot_y = 10 + int(3 * np.sin(sim.t / 6)), 7 + int(2 * np.cos(sim.t / 6))
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                xi, yi = hot_x + dx, hot_y + dy
                if 0 <= yi < 15 and 0 <= xi < 20:
                    heat[yi][xi] += max(0, 1 - (dx**2 + dy**2) / 6) * (confidence / 100)

        fig2 = go.Figure(data=go.Heatmap(z=heat, colorscale="Inferno", showscale=False))
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            height=200,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
        )
        panel2.plotly_chart(fig2, use_container_width=True)

        id_display = miner_id if miner_id else "—"
        panel2.markdown(f'<div class="small-label">Detection confidence: <b>{confidence}%</b></div>', unsafe_allow_html=True)
        panel2.markdown(f'<div class="small-label">RFID/BLE Miner ID: <b>{id_display}</b></div>', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # MINER REGISTRY
    # ------------------------------------------------------------------
    registry_panel = st.container(border=True)
    registry_panel.markdown('<div class="panel-title">Miner Registry — Individual Tag Scores</div>', unsafe_allow_html=True)

    registry = sim.get_miner_registry()
    reg_cols = registry_panel.columns(len(registry))

    reg_badge_class = {
        "FOUND": "status-safe",
        "WEAK SIGNAL": "status-caution",
        "NOT DETECTED": "status-critical",
    }

    for col, miner in zip(reg_cols, registry):
        badge_class = reg_badge_class[miner["status"]]
        col.markdown(
            f'''<div style="text-align:center; padding:8px 4px;">
            <div style="font-weight:700; font-size:14px; margin-bottom:6px;">{miner["id"]}</div>
            <span class="status-badge {badge_class}" style="font-size:10px; padding:3px 10px;">{miner["status"]}</span>
            <div class="small-label" style="margin-top:6px;">Score: <b>{miner["score"]}%</b></div>
            </div>''',
            unsafe_allow_html=True,
        )

    # ------------------------------------------------------------------
    # BOTTOM ROW — LIVE CAMERA + ROVER MAP
    # ------------------------------------------------------------------
    b1, b2 = st.columns(2)

    with b1:
        panel3 = st.container(border=True)
        panel3.markdown('<div class="panel-title">Live Camera Feed</div>', unsafe_allow_html=True)

        if camera.isOpened():
            # Flush any stale queued frames so we render the current one.
            camera.grab()
            ret, frame = camera.retrieve()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                panel3.image(frame_rgb, channels="RGB", use_container_width=True)
            else:
                panel3.warning("⚠ Camera connected but no frame received.")
        else:
            panel3.warning("⚠ Could not access camera. Check permissions or CAMERA_SOURCE in app.py.")

    with b2:
        panel4 = st.container(border=True)
        panel4.markdown('<div class="panel-title">Rover Position / Path</div>', unsafe_allow_html=True)

        xs = [p[0] for p in rover_path]
        ys = [p[1] for p in rover_path]

        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#3498db", width=2), name="Path"))
        fig3.add_trace(go.Scatter(x=[xs[-1]], y=[ys[-1]], mode="markers",
                                   marker=dict(size=14, color="#2ecc71", symbol="circle"), name="Rover"))
        fig3.add_trace(go.Scatter(x=[xs[0]], y=[ys[0]], mode="markers",
                                   marker=dict(size=10, color="#8b94a7", symbol="square"), name="Base"))

        fig3.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=240,
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor="#1c212c", zeroline=False),
            yaxis=dict(showgrid=True, gridcolor="#1c212c", zeroline=False),
        )
        panel4.plotly_chart(fig3, use_container_width=True)


# ====================================================================
# FRAGMENT 2 — Two-way communication panel.
# Deliberately has NO run_every: it only reruns when *you* interact
# with something inside it (recording, Send, Simulate Reply). That is
# what lets st.audio_input's browser recorder actually finish capturing
# audio instead of being torn down mid-recording every 1.2 seconds.
# ====================================================================
@st.fragment
def render_comms_panel():
    comm_panel = st.container(border=True)
    miner_id = sim.get_miner_id()
    link_active = miner_id is not None
    link_label = "AUDIO LINK: ACTIVE" if link_active else "AUDIO LINK: OUT OF RANGE"
    link_class = "status-safe" if link_active else "status-caution"
    comm_panel.markdown(
        f'<div class="panel-title">Two-Way Communication (4-Mic Beamforming + DSP)</div>'
        f'<span class="status-badge {link_class}" style="font-size:10px;">{link_label}</span>',
        unsafe_allow_html=True,
    )

    if sim.comm_log:
        for msg in sim.comm_log[-6:]:
            is_team = msg["from"] == "Rescue Team"
            comm_panel.markdown(
                f'<div style="margin:6px 0;">'
                f'<span class="small-label">[{msg["time"]}] {msg["from"]}'
                f'{" (simulated reply)" if not is_team else ""}</span></div>',
                unsafe_allow_html=True,
            )
            if msg.get("type") == "audio":
                comm_panel.audio(msg["audio"], format="audio/wav")
            else:
                comm_panel.markdown(
                    f'<div class="small-label" style="padding-left:8px;">💬 {msg["text"]}</div>',
                    unsafe_allow_html=True,
                )
    else:
        comm_panel.markdown(
            '<div class="small-label">No communication yet — link opens once a miner is detected.</div>',
            unsafe_allow_html=True,
        )

    comm_panel.markdown(
        '<div class="small-label" style="margin-top:10px;">Record a voice message to send to the miner</div>',
        unsafe_allow_html=True,
    )

    # Native Streamlit mic recorder (requires streamlit>=1.38.0, already
    # pinned in requirements.txt). Keyed with a counter so we can hand it
    # a brand-new key after each send, which clears it for the next take.
    audio_value = comm_panel.audio_input(
        "Record a voice message",
        label_visibility="collapsed",
        key=f"mic_input_{st.session_state.audio_key_counter}",
    )

    bcol1, bcol2 = comm_panel.columns(2)
    with bcol1:
        if st.button("📤 Send Voice Message", use_container_width=True):
            if audio_value is not None:
                sim.send_message_to_miner(audio_bytes=audio_value.read())
                st.session_state.audio_key_counter += 1
            else:
                st.warning("Record a message first, then press Send.")
    with bcol2:
        if st.button("🗣 Simulate Miner Reply (canned text)", use_container_width=True):
            sim.simulate_miner_reply()

    # ------------------------------------------------------------------
    # MINER-SIDE CAPTURE — real audio, not the canned-text placeholder.
    # There's no rover mic hardware yet, so this input is a demo stand-in:
    # have a teammate role-play the trapped miner ~20 m away and record
    # here. It calls the exact same receive_message_from_miner() hook the
    # real rover mic array will call once wired in — see the HARDWARE
    # HOOK note in simulator.py. Nothing else in the app needs to change
    # when the real hardware arrives.
    # ------------------------------------------------------------------
    comm_panel.markdown(
        '<div class="small-label" style="margin-top:14px; border-top:1px solid var(--bg-panel-border); padding-top:10px;">'
        'Record as the miner (demo stand-in for the rover\'s mic array)</div>',
        unsafe_allow_html=True,
    )
    miner_audio_value = comm_panel.audio_input(
        "Record as the miner",
        label_visibility="collapsed",
        key=f"miner_mic_input_{st.session_state.audio_key_counter}",
    )
    if st.button("📥 Send as Miner", use_container_width=True):
        if miner_audio_value is not None:
            sim.receive_message_from_miner(audio_bytes=miner_audio_value.read())
            st.session_state.audio_key_counter += 1
        else:
            st.warning("Record a message first, then press Send.")


# ====================================================================
# FRAGMENT 3 — Event log. Fast-ticking like fragment 1, but kept
# separate so it never shares a rerun with the audio recorder either.
# ====================================================================
@st.fragment(run_every=1.2)
def render_event_log():
    log_panel = st.container(border=True)
    log_panel.markdown('<div class="panel-title">Event Log</div>', unsafe_allow_html=True)
    for line in sim.event_log[:15]:
        log_panel.markdown(f'<div class="event-line">{line}</div>', unsafe_allow_html=True)


render_dashboard()
render_comms_panel()
render_event_log()