import time
from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
import requests
import streamlit as st

API_BASE = "https://api.daxplr.com/measurements"

METRICS = [
    {"key": "co2",         "label": "CO₂",        "unit": "ppm", "color": "#2a78d6"},
    {"key": "temperature", "label": "Temperature", "unit": "°C",  "color": "#1baf7a"},
    {"key": "humidity",    "label": "Humidity",    "unit": "%",   "color": "#eda100"},
    {"key": "battery",     "label": "Battery",     "unit": "%",   "color": "#008300"},
]

REFRESH_INTERVAL = 60  # seconds


def fetch(metric_key: str, start_iso: str | None, end_iso: str | None) -> list[dict]:
    params: dict = {"metric": metric_key}
    if start_iso:
        params["start"] = start_iso
    if end_iso:
        params["end"] = end_iso
    try:
        r = requests.get(API_BASE, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=REFRESH_INTERVAL)
def fetch_all(start_iso: str | None, end_iso: str | None) -> dict[str, list[dict]]:
    return {m["key"]: fetch(m["key"], start_iso, end_iso) for m in METRICS}


def make_chart(data: list[dict], metric: dict) -> go.Figure:
    fig = go.Figure()
    if not data:
        fig.add_annotation(
            text="No data", xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color="#898781", size=14),
        )
    else:
        timestamps = [datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")) for d in data]
        values = [d["value"] for d in data]
        fig.add_trace(go.Scatter(
            x=timestamps, y=values,
            mode="lines",
            line=dict(color=metric["color"], width=2),
            hovertemplate=f"%{{x|%Y-%m-%d %H:%M:%S}}<br><b>%{{y:.1f}} {metric['unit']}</b><extra></extra>",
        ))

    fig.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        plot_bgcolor="#fcfcfb",
        paper_bgcolor="#fcfcfb",
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', color="#52514e", size=12),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color="#898781", size=11), linecolor="#c3c2b7"),
        yaxis=dict(showgrid=True, gridcolor="#e1e0d9", gridwidth=1, zeroline=False,
                   tickfont=dict(color="#898781", size=11), ticksuffix=f" {metric['unit']}"),
        hoverlabel=dict(bgcolor="white", bordercolor="#e1e0d9", font_color="#0b0b0b"),
        showlegend=False,
        height=220,
    )
    return fig


def stat_tile(label: str, value: float | None, unit: str, delta: float | None, color: str):
    val_str = f"{value:.1f}" if value is not None else "—"
    delta_html = ""
    if delta is not None:
        sign = "▲" if delta >= 0 else "▼"
        delta_color = "#006300" if delta >= 0 else "#d03b3b"
        delta_html = f'<span style="color:{delta_color};font-size:0.8rem;">{sign} {abs(delta):.2f} {unit}</span>'

    st.markdown(f"""
<div style="background:#fcfcfb;border:1px solid #e1e0d9;border-top:3px solid {color};
            border-radius:6px;padding:16px 20px 12px;min-height:90px;">
  <div style="color:#898781;font-size:0.75rem;font-weight:600;letter-spacing:0.05em;
              text-transform:uppercase;margin-bottom:4px;">{label}</div>
  <div style="color:#0b0b0b;font-size:2rem;font-weight:700;line-height:1;font-variant-numeric:tabular-nums;">
    {val_str}<span style="font-size:1rem;font-weight:400;color:#52514e;margin-left:4px;">{unit}</span>
  </div>
  <div style="margin-top:6px;min-height:1.1rem;">{delta_html}</div>
</div>""", unsafe_allow_html=True)


def main():
    st.set_page_config(page_title="Daxplr", page_icon="📊", layout="wide")

    st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
  [data-testid="stAppViewContainer"] { background: #f9f9f7; }
  [data-testid="stStatusWidget"]     { display: none !important; }
  [data-testid="stDecoration"]       { display: none !important; }
</style>""", unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    col_title, col_refresh = st.columns([5, 1])
    with col_title:
        st.markdown("## Daxplr")
    with col_refresh:
        st.write("")
        if st.button("↻ Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── Time range controls ───────────────────────────────────────────────────
    PRESETS = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}

    preset_col, custom_col = st.columns([2, 5])
    with preset_col:
        preset = st.segmented_control(
            "Range",
            list(PRESETS) + ["Custom"],
            default="24h",
            label_visibility="collapsed",
        )

    if not preset:
        preset = "24h"

    now = datetime.now(timezone.utc)

    if preset == "Custom":
        with custom_col:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                start_date = st.date_input("Start date", value=(now - timedelta(hours=24)).date())
            with c2:
                start_time = st.time_input("Start time", value=(now - timedelta(hours=24)).time().replace(second=0, microsecond=0))
            with c3:
                end_date = st.date_input("End date", value=now.date())
            with c4:
                end_time = st.time_input("End time", value=now.time().replace(second=0, microsecond=0))
        start_dt = datetime.combine(start_date, start_time, tzinfo=timezone.utc)
        end_dt   = datetime.combine(end_date,   end_time,   tzinfo=timezone.utc)
    else:
        end_dt   = now
        start_dt = now - timedelta(hours=PRESETS[preset])

    start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso   = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    st.caption(f"Showing {start_dt.strftime('%Y-%m-%d %H:%M')} → {end_dt.strftime('%Y-%m-%d %H:%M')} UTC · auto-refreshes every {REFRESH_INTERVAL}s")

    # ── Fetch ─────────────────────────────────────────────────────────────────
    all_data = fetch_all(start_iso, end_iso)

    # ── Stat tiles ────────────────────────────────────────────────────────────
    cols = st.columns(4)
    for i, metric in enumerate(METRICS):
        data    = all_data.get(metric["key"], [])
        current = data[-1]["value"] if data else None
        prev    = data[-2]["value"] if len(data) >= 2 else None
        delta   = (current - prev) if (current is not None and prev is not None) else None
        with cols[i]:
            stat_tile(metric["label"], current, metric["unit"], delta, metric["color"])

    st.write("")

    # ── Charts ────────────────────────────────────────────────────────────────
    cols = st.columns(2)
    for i, metric in enumerate(METRICS):
        data = all_data.get(metric["key"], [])
        with cols[i % 2]:
            st.markdown(
                f'<p style="color:#0b0b0b;font-size:0.9rem;font-weight:600;margin-bottom:2px;">'
                f'{metric["label"]} <span style="color:#898781;font-weight:400;">({metric["unit"]})</span>'
                f' <span style="color:#898781;font-weight:400;font-size:0.8rem;">· {len(data)} pts</span></p>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(make_chart(data, metric), use_container_width=True, config={"displayModeBar": False})

    # ── Auto-refresh (preset ranges only) ────────────────────────────────────
    if preset != "Custom":
        time.sleep(REFRESH_INTERVAL)
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
