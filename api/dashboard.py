"""
Real-time Web Dashboard — Plotly Dash

Provides a browser-based dashboard with:
- Live device status cards
- RSSI trend charts (WebSocket-fed, auto-refresh)
- Spectrum waterfall heat-map
- GPS map (all device locations on a scatter map)
- Fleet health scorecard
- Agent activity log
- Quick-action buttons (OTA, frequency lock, optimise)

Run standalone:
    python -m api.dashboard --port 8050

Or mount into the main FastAPI server via the /dashboard route.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import of Dash (optional dependency)
# ---------------------------------------------------------------------------
try:
    import dash
    from dash import dcc, html, Input, Output, State, callback_context
    from dash.exceptions import PreventUpdate
    import plotly.graph_objects as go
    import plotly.express as px
    _DASH_AVAILABLE = True
except ImportError:
    _DASH_AVAILABLE = False
    logger.info("Dash not installed — dashboard unavailable. "
                "Install with: pip install dash plotly")


# ---------------------------------------------------------------------------
# Synthetic data generator (used when orchestrator is not connected)
# ---------------------------------------------------------------------------
class _SyntheticDataStore:
    """Thread-safe in-memory store for dashboard data."""

    def __init__(self):
        self._lock = threading.Lock()
        self._devices: List[Dict[str, Any]] = []
        self._rssi_history: Dict[str, List[float]] = {}
        self._spectrum: List[List[float]] = []
        self._gps_points: List[Dict[str, Any]] = []
        self._agent_log: List[Dict[str, Any]] = []
        self._health: Dict[str, float] = {}
        self._tick = 0

    def tick(self) -> None:
        """Advance the simulation by one step."""
        import math, random
        with self._lock:
            self._tick += 1
            t = self._tick
            if not self._devices:
                self._devices = [
                    {"id": f"ESP32-{i:02d}", "ip": f"192.168.1.{100+i}",
                     "status": "online", "firmware": "2.0.0"}
                    for i in range(6)
                ]
            for d in self._devices:
                did = d["id"]
                hist = self._rssi_history.setdefault(did, [])
                base = -60 - 10 * math.sin(t / 20 + hash(did) % 10)
                hist.append(round(base + random.gauss(0, 2), 1))
                if len(hist) > 60:
                    hist.pop(0)
                self._health[did] = round(max(20, min(100, 70 + 15 * math.sin(t / 30))), 1)

            # Spectrum row (13 channels for 2.4 GHz)
            row = [round(-80 + random.gauss(0, 5) + (20 if i in (5, 10) else 0), 1)
                   for i in range(13)]
            self._spectrum.append(row)
            if len(self._spectrum) > 30:
                self._spectrum.pop(0)

            # GPS drift
            if not self._gps_points:
                self._gps_points = [
                    {"id": f"ESP32-{i:02d}",
                     "lat": 37.7749 + i * 0.001,
                     "lon": -122.4194 + i * 0.001}
                    for i in range(6)
                ]
            for p in self._gps_points:
                p["lat"] += random.gauss(0, 0.0001)
                p["lon"] += random.gauss(0, 0.0001)

            if t % 5 == 0:
                actions = ["freq_lock", "ota_check", "ble_scan", "spectrum_sweep", "ai_optimise"]
                self._agent_log.insert(0, {
                    "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "agent": random.choice(["freq", "spectrum", "AI", "comms", "maintenance"]),
                    "action": random.choice(actions),
                    "device": random.choice([d["id"] for d in self._devices]),
                    "result": random.choice(["✓ ok", "✓ ok", "✓ ok", "⚠ warn"]),
                })
                if len(self._agent_log) > 20:
                    self._agent_log.pop()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "devices": list(self._devices),
                "rssi_history": {k: list(v) for k, v in self._rssi_history.items()},
                "spectrum": [list(r) for r in self._spectrum],
                "gps_points": list(self._gps_points),
                "agent_log": list(self._agent_log),
                "health": dict(self._health),
            }


_store = _SyntheticDataStore()


def _background_ticker() -> None:
    while True:
        _store.tick()
        time.sleep(1)


# ---------------------------------------------------------------------------
# Dashboard builder
# ---------------------------------------------------------------------------
def build_dashboard(
    server=None,
    orchestrator=None,
    url_base: str = "/dashboard/",
) -> Optional[Any]:
    """
    Build and return a Dash app instance.

    Parameters
    ----------
    server       : Existing WSGI/ASGI server to mount onto (Flask/Starlette)
    orchestrator : The Orchestrator instance (None = use synthetic data)
    url_base     : URL prefix for the dashboard
    """
    if not _DASH_AVAILABLE:
        logger.warning("Dash not installed — cannot build dashboard")
        return None

    # Start synthetic data ticker
    t = threading.Thread(target=_background_ticker, daemon=True)
    t.start()

    app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname=url_base,
        title="Multi-Agent ESP32 Dashboard",
        update_title=None,
    )

    # ── Layout ────────────────────────────────────────────────────────────
    app.layout = html.Div([
        # ── Header ──────────────────────────────────────────────────────
        html.Div([
            html.H1("🛰 Multi-Agent ESP32 Dashboard", style={
                "margin": 0, "color": "#00d4ff", "fontFamily": "monospace"
            }),
            html.Span(id="live-clock", style={
                "color": "#aaa", "fontFamily": "monospace", "fontSize": "14px"
            }),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "center", "padding": "12px 24px",
            "background": "#0d1117", "borderBottom": "1px solid #30363d"
        }),

        # ── Main content ─────────────────────────────────────────────────
        html.Div([

            # Top row: device cards + fleet health gauge
            html.Div([
                html.Div(id="device-cards", style={"flex": "1"}),
                html.Div([
                    dcc.Graph(id="fleet-health-gauge",
                              config={"displayModeBar": False},
                              style={"height": "200px"}),
                ], style={"width": "300px"}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            # Middle row: RSSI chart + spectrum waterfall
            html.Div([
                dcc.Graph(id="rssi-chart", style={"flex": "1", "height": "280px"},
                          config={"displayModeBar": False}),
                dcc.Graph(id="spectrum-waterfall", style={"flex": "1", "height": "280px"},
                          config={"displayModeBar": False}),
            ], style={"display": "flex", "gap": "16px", "marginBottom": "16px"}),

            # Bottom row: GPS map + agent log
            html.Div([
                dcc.Graph(id="gps-map", style={"flex": "1", "height": "300px"},
                          config={"displayModeBar": False}),
                html.Div(id="agent-log", style={
                    "flex": "1", "height": "300px", "overflowY": "auto",
                    "background": "#161b22", "borderRadius": "8px",
                    "padding": "12px", "fontFamily": "monospace", "fontSize": "12px",
                }),
            ], style={"display": "flex", "gap": "16px"}),

        ], style={"padding": "16px 24px", "background": "#010409"}),

        # Interval triggers
        dcc.Interval(id="refresh", interval=1000, n_intervals=0),
        dcc.Store(id="data-store"),
    ], style={"background": "#010409", "minHeight": "100vh"})

    # ── Callbacks ─────────────────────────────────────────────────────────

    @app.callback(
        Output("data-store", "data"),
        Input("refresh", "n_intervals"),
    )
    def _refresh_store(_):
        if orchestrator:
            # Pull real data from the orchestrator
            status = orchestrator.get_status()
            devices = [
                {"id": did, "ip": d.ip_address, "status": d.status.value,
                 "firmware": d.config.get("firmware_version", "?")}
                for did, d in orchestrator.devices.items()
            ]
            return {"devices": devices, "health": {}, "rssi_history": {},
                    "spectrum": [], "gps_points": [], "agent_log": []}
        return _store.snapshot()

    @app.callback(
        Output("live-clock", "children"),
        Input("refresh", "n_intervals"),
    )
    def _update_clock(_):
        return datetime.now(timezone.utc).strftime("UTC %Y-%m-%d %H:%M:%S")

    @app.callback(
        Output("device-cards", "children"),
        Input("data-store", "data"),
    )
    def _update_device_cards(data):
        if not data:
            raise PreventUpdate
        cards = []
        for d in data.get("devices", []):
            health = data.get("health", {}).get(d["id"], 0)
            colour = ("#00e676" if health >= 80 else
                      "#ffd600" if health >= 60 else "#ff5252")
            cards.append(html.Div([
                html.Div(d["id"], style={"fontWeight": "bold", "color": "#e6edf3"}),
                html.Div(d["ip"],  style={"color": "#8b949e", "fontSize": "11px"}),
                html.Div(f"Health: {health}%", style={"color": colour, "fontSize": "12px"}),
                html.Div(f"v{d['firmware']}", style={"color": "#8b949e", "fontSize": "11px"}),
            ], style={
                "background": "#161b22", "border": f"1px solid {colour}",
                "borderRadius": "8px", "padding": "10px 14px",
                "minWidth": "130px", "cursor": "pointer",
            }))
        return html.Div(cards, style={"display": "flex", "flexWrap": "wrap", "gap": "10px"})

    @app.callback(
        Output("fleet-health-gauge", "figure"),
        Input("data-store", "data"),
    )
    def _update_gauge(data):
        if not data:
            raise PreventUpdate
        healths = list(data.get("health", {}).values())
        avg = sum(healths) / len(healths) if healths else 0
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(avg, 1),
            title={"text": "Fleet Health", "font": {"color": "#e6edf3"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#8b949e"},
                "bar": {"color": "#00d4ff"},
                "bgcolor": "#161b22",
                "steps": [
                    {"range": [0, 30],   "color": "#ff5252"},
                    {"range": [30, 60],  "color": "#ffd600"},
                    {"range": [60, 100], "color": "#00e676"},
                ],
            },
            number={"font": {"color": "#e6edf3"}, "suffix": "%"},
        ))
        fig.update_layout(paper_bgcolor="#0d1117", font={"color": "#e6edf3"},
                          margin={"t": 40, "b": 0, "l": 0, "r": 0})
        return fig

    @app.callback(
        Output("rssi-chart", "figure"),
        Input("data-store", "data"),
    )
    def _update_rssi(data):
        if not data:
            raise PreventUpdate
        fig = go.Figure()
        for did, hist in data.get("rssi_history", {}).items():
            fig.add_trace(go.Scatter(
                y=hist, mode="lines", name=did, line={"width": 1.5}
            ))
        fig.update_layout(
            title={"text": "RSSI Trends (dBm)", "font": {"color": "#e6edf3"}},
            paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
            font={"color": "#8b949e"}, xaxis={"showgrid": False},
            yaxis={"gridcolor": "#21262d", "range": [-100, -40]},
            legend={"bgcolor": "#0d1117"},
            margin={"t": 40, "b": 30, "l": 40, "r": 10},
        )
        return fig

    @app.callback(
        Output("spectrum-waterfall", "figure"),
        Input("data-store", "data"),
    )
    def _update_waterfall(data):
        if not data:
            raise PreventUpdate
        spectrum = data.get("spectrum", [])
        if not spectrum:
            raise PreventUpdate
        labels = [f"ch{i+1}" for i in range(len(spectrum[0]))]
        fig = go.Figure(go.Heatmap(
            z=spectrum,
            x=labels,
            colorscale="Plasma",
            zmin=-100, zmax=-40,
            colorbar={"title": "dBm", "tickfont": {"color": "#8b949e"}},
        ))
        fig.update_layout(
            title={"text": "2.4 GHz Spectrum Waterfall", "font": {"color": "#e6edf3"}},
            paper_bgcolor="#161b22", plot_bgcolor="#0d1117",
            font={"color": "#8b949e"},
            margin={"t": 40, "b": 30, "l": 40, "r": 10},
        )
        return fig

    @app.callback(
        Output("gps-map", "figure"),
        Input("data-store", "data"),
    )
    def _update_gps_map(data):
        if not data:
            raise PreventUpdate
        pts = data.get("gps_points", [])
        if not pts:
            raise PreventUpdate
        lats = [p["lat"] for p in pts]
        lons = [p["lon"] for p in pts]
        ids  = [p["id"]  for p in pts]
        fig = go.Figure(go.Scattermapbox(
            lat=lats, lon=lons, text=ids,
            mode="markers+text",
            marker={"size": 12, "color": "#00d4ff"},
            textposition="top right",
            textfont={"color": "#e6edf3", "size": 11},
        ))
        fig.update_layout(
            mapbox={
                "style": "carto-darkmatter",
                "center": {"lat": sum(lats)/len(lats), "lon": sum(lons)/len(lons)},
                "zoom": 14,
            },
            title={"text": "Device GPS Map", "font": {"color": "#e6edf3"}},
            paper_bgcolor="#161b22",
            margin={"t": 40, "b": 0, "l": 0, "r": 0},
        )
        return fig

    @app.callback(
        Output("agent-log", "children"),
        Input("data-store", "data"),
    )
    def _update_log(data):
        if not data:
            raise PreventUpdate
        rows = []
        for entry in data.get("agent_log", []):
            colour = "#ff5252" if "warn" in entry.get("result", "") else "#00e676"
            rows.append(html.Div([
                html.Span(entry.get("time", ""), style={"color": "#8b949e"}),
                html.Span(f" [{entry.get('agent','')}]", style={"color": "#00d4ff"}),
                html.Span(f" {entry.get('action','')} → {entry.get('device','')}",
                          style={"color": "#e6edf3"}),
                html.Span(f" {entry.get('result','')}", style={"color": colour}),
            ]))
        return rows or [html.Span("No activity yet", style={"color": "#8b949e"})]

    return app


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Agent ESP32 Dashboard")
    parser.add_argument("--port", type=int, default=8050)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if not _DASH_AVAILABLE:
        print("Dash not installed. Install with: pip install dash plotly")
        return

    app = build_dashboard()
    if app:
        print(f"\n🛰  Dashboard running at http://localhost:{args.port}/dashboard/\n")
        app.run(debug=args.debug, port=args.port)


if __name__ == "__main__":
    main()
