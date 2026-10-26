"""Aurora Weather — a Python-first weather dashboard with an interactive 3D globe.

Weather data is requested from Open-Meteo. Streamlit renders the dashboard in Python;
a small embedded JavaScript widget powers Globe.gl's 3D interaction.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any

import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# Page configuration and constants
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Aurora Weather | Forecast & Earth Explorer",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded",
)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
REQUEST_TIMEOUT = 18

# These are the quick-select markers displayed on the interactive globe.
GLOBE_CITIES: list[dict[str, Any]] = [
    {"name": "Bengaluru", "country": "India", "lat": 12.9716, "lng": 77.5946},
    {"name": "Mumbai", "country": "India", "lat": 19.0760, "lng": 72.8777},
    {"name": "Dubai", "country": "United Arab Emirates", "lat": 25.2048, "lng": 55.2708},
    {"name": "London", "country": "United Kingdom", "lat": 51.5072, "lng": -0.1276},
    {"name": "Reykjavík", "country": "Iceland", "lat": 64.1466, "lng": -21.9426},
    {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lng": 36.8219},
    {"name": "Cape Town", "country": "South Africa", "lat": -33.9249, "lng": 18.4241},
    {"name": "São Paulo", "country": "Brazil", "lat": -23.5505, "lng": -46.6333},
    {"name": "New York", "country": "United States", "lat": 40.7128, "lng": -74.0060},
    {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lng": 139.6503},
    {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lng": 103.8198},
    {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lng": 151.2093},
]

# WMO weather interpretation codes. Open-Meteo returns these code values.
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "☀"),
    1: ("Mainly clear", "☀"),
    2: ("Partly cloudy", "◐"),
    3: ("Overcast", "☁"),
    45: ("Fog", "≋"),
    48: ("Depositing rime fog", "≋"),
    51: ("Light drizzle", "☂"),
    53: ("Moderate drizzle", "☂"),
    55: ("Dense drizzle", "☂"),
    56: ("Light freezing drizzle", "❄"),
    57: ("Dense freezing drizzle", "❄"),
    61: ("Slight rain", "☂"),
    63: ("Moderate rain", "☂"),
    65: ("Heavy rain", "☂"),
    66: ("Light freezing rain", "❄"),
    67: ("Heavy freezing rain", "❄"),
    71: ("Slight snow", "❄"),
    73: ("Moderate snow", "❄"),
    75: ("Heavy snow", "❄"),
    77: ("Snow grains", "❄"),
    80: ("Slight rain showers", "☂"),
    81: ("Moderate rain showers", "☂"),
    82: ("Violent rain showers", "☂"),
    85: ("Slight snow showers", "❄"),
    86: ("Heavy snow showers", "❄"),
    95: ("Thunderstorm", "ϟ"),
    96: ("Thunderstorm with slight hail", "ϟ"),
    99: ("Thunderstorm with heavy hail", "ϟ"),
}


def weather_description(code: Any) -> str:
    """Convert a WMO weather code to a readable description."""
    try:
        return WEATHER_CODES.get(int(code), ("Conditions unavailable", "•"))[0]
    except (TypeError, ValueError):
        return "Conditions unavailable"


def weather_symbol(code: Any) -> str:
    """Return a simple typographic weather icon."""
    try:
        return WEATHER_CODES.get(int(code), ("", "•"))[1]
    except (TypeError, ValueError):
        return "•"


def display_temperature(value: Any, unit: str = "°C") -> str:
    """Format a Celsius value in the selected temperature unit."""
    if value is None:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    if unit == "°F":
        number = number * 9 / 5 + 32
    return f"{round(number)}°"


def safe_number(value: Any, suffix: str = "", digits: int = 0) -> str:
    """Format an API number without showing 'None' or raising an error."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "—"


def readable_day(date_string: str, pattern: str = "%a") -> str:
    try:
        return datetime.fromisoformat(date_string).strftime(pattern)
    except (ValueError, TypeError):
        return date_string


# -----------------------------------------------------------------------------
# API functions — Python handles the real weather requests
# -----------------------------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def fetch_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch current, hourly and 7-day forecast data. Cached for 15 minutes."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "is_day",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "pressure_msl",
        ]),
        "hourly": ",".join([
            "temperature_2m",
            "precipitation_probability",
            "weather_code",
            "relative_humidity_2m",
        ]),
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "sunrise",
            "sunset",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "uv_index_max",
        ]),
        "timezone": "auto",
        "forecast_days": 7,
        "wind_speed_unit": "kmh",
    }
    response = requests.get(FORECAST_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if "current" not in payload or "hourly" not in payload or "daily" not in payload:
        raise ValueError("The weather service returned an incomplete forecast.")
    return payload


@st.cache_data(ttl=3600, show_spinner=False)
def search_locations(query: str) -> list[dict[str, Any]]:
    """Search world cities using Open-Meteo's GeoNames-based geocoding service."""
    params = {"name": query, "count": 8, "language": "en", "format": "json"}
    response = requests.get(GEOCODING_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get("results", [])


# -----------------------------------------------------------------------------
# Styling — glass panels, storm atmosphere, and motion
# -----------------------------------------------------------------------------

CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Inter+Tight:wght@500;600&display=swap');
:root { --ink:#f6fbff; --muted:rgba(235,246,255,.72); --line:rgba(255,255,255,.18); --glass:rgba(255,255,255,.105); --aqua:#9bf5ec; }
html, body, [class*="css"] { font-family:Inter,system-ui,-apple-system,sans-serif; }
.stApp { color:var(--ink); background:linear-gradient(110deg,rgba(3,15,24,.94),rgba(4,24,35,.76) 48%,rgba(5,25,37,.84)),url('https://images.unsplash.com/photo-1534088568595-a066f410bcda?auto=format&fit=crop&w=2200&q=85') center 26% / cover fixed; }
[data-testid="stHeader"] { background:rgba(0,0,0,0); }
[data-testid="stToolbar"] { right:1rem; }
.main .block-container { max-width:1500px; padding-top:1.6rem; padding-bottom:3.4rem; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,rgba(255,255,255,.12),rgba(255,255,255,.065)); border-right:1px solid rgba(255,255,255,.14); }
[data-testid="stSidebar"] > div:first-child { padding-top:1.2rem; }
[data-testid="stSidebar"] * { color:#f5fbff; }
[data-testid="stMarkdownContainer"] p { color:inherit; }
h1,h2,h3 { letter-spacing:-.045em; color:white; }
.stCaption, [data-testid="stCaptionContainer"] { color:var(--muted)!important; }
.stTextInput input, [data-baseweb="select"] > div, .stSelectbox input { background:rgba(6,20,31,.52)!important; color:#fff!important; border-color:rgba(255,255,255,.18)!important; }
.stTextInput label, .stSelectbox label, .stRadio label { color:rgba(255,255,255,.83)!important; }
.stButton button, .stFormSubmitButton button { border-radius:999px; border:1px solid rgba(255,255,255,.22); color:white; background:rgba(255,255,255,.13); transition:transform .22s ease,background .22s ease,border-color .22s ease; }
.stButton button:hover, .stFormSubmitButton button:hover { transform:translateY(-2px); background:rgba(255,255,255,.22); border-color:rgba(255,255,255,.38); color:white; }
.stRadio [data-testid="stMarkdownContainer"] p { color:#fff!important; }
hr { border-color:rgba(255,255,255,.12)!important; }
.brand-mark { display:flex;align-items:center;gap:10px;font-size:1.06rem;font-weight:800;letter-spacing:-.035em;margin:.2rem 0 1.5rem; }
.brand-icon { width:37px;height:37px;border:1px solid rgba(255,255,255,.42);border-radius:13px;display:grid;place-items:center;background:rgba(255,255,255,.13);box-shadow:inset 0 1px rgba(255,255,255,.25);color:#b4fff4;font-size:1.1rem; }
.eyebrow { text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:700;color:rgba(228,246,255,.68); }
.topbar { display:flex;justify-content:space-between;align-items:center;gap:18px;margin-bottom:1.4rem;animation:rise-in .72s cubic-bezier(.16,1,.3,1) both; }
.welcome { color:rgba(245,251,255,.72);font-size:.9rem; }
.top-title { font-size:1.45rem;font-weight:750;letter-spacing:-.055em;margin-top:3px; }
.live-pill { display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.19);background:rgba(255,255,255,.09);padding:8px 13px;border-radius:999px;color:rgba(255,255,255,.84);font-size:.75rem;white-space:nowrap; }
.live-dot { display:inline-block;width:7px;height:7px;background:#8cf3d2;border-radius:50%;box-shadow:0 0 12px #8cf3d2;animation:pulse 2.2s infinite; }
.glass { background:linear-gradient(155deg,rgba(255,255,255,.19),rgba(255,255,255,.085) 56%,rgba(255,255,255,.12));border:1px solid rgba(255,255,255,.19);backdrop-filter:blur(23px) saturate(125%);-webkit-backdrop-filter:blur(23px) saturate(125%);border-radius:26px;box-shadow:inset 0 1px 0 rgba(255,255,255,.17);position:relative;overflow:hidden; }
.glass:after { content:"";position:absolute;top:0;left:-40%;width:32%;height:100%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.09),transparent);transform:skewX(-18deg);pointer-events:none;animation:sheen 1.15s cubic-bezier(.22,.61,.36,1) 2.3s 1 both; }
.hero-card { min-height:320px;padding:clamp(22px,3vw,42px);animation:slide-left .85s cubic-bezier(.16,1,.3,1) both; }
.hero-location { font-size:.92rem;color:rgba(255,255,255,.78);margin-bottom:1rem;display:flex;gap:9px;align-items:center; }
.hero-card h1 { font-family:'Inter Tight',Inter,sans-serif;font-weight:500;font-size:clamp(2.8rem,5.7vw,5rem);line-height:.98;letter-spacing:-.075em;margin:.8rem 0 .65rem; }
.hero-condition { color:rgba(255,255,255,.86);font-size:1rem;font-weight:500; }
.hero-temp-row { display:flex;align-items:flex-start;gap:10px;margin-top:.5rem; }
.hero-temp { font-size:clamp(4.7rem,8vw,7.7rem);line-height:.98;font-weight:500;letter-spacing:-.105em; }
.hero-unit { font-size:1.65rem;color:rgba(255,255,255,.8);margin-top:.8rem; }
.hero-symbol { font-size:3rem;color:#d9fff8;line-height:1;filter:drop-shadow(0 0 18px rgba(167,255,245,.25)); }
.hero-note { color:rgba(241,249,255,.72);max-width:34rem;font-size:.9rem;line-height:1.7;margin-top:1.2rem; }
.right-card { min-height:320px;padding:25px;animation:slide-right .95s cubic-bezier(.16,1,.3,1) .1s both; }
.section-heading {display:flex;justify-content:space-between;align-items:flex-end;gap:12px;margin:1.7rem 0 .85rem;}
.section-heading h2 {font-size:1.25rem;margin:0;font-weight:650;letter-spacing:-.05em;}
.section-heading p {font-size:.78rem;color:var(--muted);margin:0;}
.metric-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:1.15rem;}
.metric-card {padding:19px 19px 18px;min-height:115px;animation:rise-in .7s cubic-bezier(.16,1,.3,1) both;}
.metric-name {font-size:.78rem;color:rgba(235,246,255,.72);display:flex;align-items:center;gap:8px;}
.metric-value {font-size:1.8rem;font-weight:600;letter-spacing:-.06em;margin-top:12px;}
.metric-sub {font-size:.7rem;color:rgba(235,246,255,.58);margin-top:3px;}
.hourly-grid {display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:.6rem 0 1.6rem;}
.hour-card {text-align:center;padding:15px 6px 16px;border-radius:19px;background:rgba(255,255,255,.085);border:1px solid rgba(255,255,255,.12);transition:transform .22s ease,background .22s ease;animation:rise-in .65s cubic-bezier(.16,1,.3,1) both;}
.hour-card:hover {transform:translateY(-4px);background:rgba(255,255,255,.15);}
.hour-time {font-size:.76rem;color:rgba(242,249,255,.7);}
.hour-symbol {font-size:1.45rem;color:#c9fff9;margin:.55rem 0;}
.hour-temp {font-size:1.18rem;font-weight:600;letter-spacing:-.045em;}
.hour-rain {font-size:.68rem;color:rgba(213,248,255,.67);margin-top:4px;}
.forecast-grid {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:9px;}
.day-card {padding:15px 10px;text-align:center;min-height:150px;animation:rise-in .7s cubic-bezier(.16,1,.3,1) both;}
.day-name {font-size:.78rem;color:rgba(240,249,255,.72);font-weight:600;}
.day-symbol {font-size:1.65rem;color:#c5fff5;margin:13px 0;}
.day-desc {font-size:.67rem;color:rgba(240,249,255,.7);min-height:2em;}
.day-temp {font-size:.9rem;font-weight:600;margin-top:10px;}
.day-temp span {font-weight:400;color:rgba(240,249,255,.53);margin-left:5px;}
.globe-shell {padding:12px;border-radius:26px;background:linear-gradient(145deg,rgba(255,255,255,.13),rgba(255,255,255,.055));border:1px solid rgba(255,255,255,.16);backdrop-filter:blur(18px); }
.globe-caption {color:rgba(234,247,255,.72);font-size:.88rem;line-height:1.65;max-width:850px;}
.footer-note {font-size:.72rem;color:rgba(233,246,255,.57);line-height:1.6;margin-top:1.6rem;}
@keyframes rise-in {from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes slide-left {from{opacity:0;transform:translateX(-25px)}to{opacity:1;transform:translateX(0)}}
@keyframes slide-right {from{opacity:0;transform:translateX(24px) scale(.99)}to{opacity:1;transform:translateX(0) scale(1)}}
@keyframes pulse {0%,100%{opacity:1;transform:scale(1)}50%{opacity:.45;transform:scale(.76)}}
@keyframes sheen {from{transform:translateX(-130%) skewX(-18deg)}to{transform:translateX(470%) skewX(-18deg)}}
@media (max-width: 900px) { .metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.forecast-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.hourly-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.topbar{align-items:flex-start;flex-direction:column}.hero-card,.right-card{min-height:unset} }
@media (max-width: 520px) { .main .block-container{padding-left:1rem;padding-right:1rem}.forecast-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hourly-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.metric-grid{gap:8px}.metric-card{padding:14px}.hero-temp{font-size:5rem}.hero-card h1{font-size:3.2rem} }
@media (prefers-reduced-motion: reduce) { *,*:before,*:after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important} }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def place_label(place: dict[str, Any]) -> str:
    parts = [str(place.get("name", "Unknown location"))]
    admin = place.get("admin1")
    country = place.get("country")
    if admin and admin != parts[0]:
        parts.append(str(admin))
    if country:
        parts.append(str(country))
    return ", ".join(parts)


def location_from_search_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": result.get("name", "Selected location"),
        "country": result.get("country", ""),
        "admin1": result.get("admin1", ""),
        "lat": float(result["latitude"]),
        "lng": float(result["longitude"]),
        "timezone": result.get("timezone", ""),
    }


def metric_card(name: str, value: str, note: str, symbol: str, delay: int = 0) -> str:
    return f"""
    <div class="glass metric-card" style="animation-delay:{delay}ms">
      <div class="metric-name"><span style="font-size:1rem;color:#b5fff5">{symbol}</span>{html.escape(name)}</div>
      <div class="metric-value">{html.escape(value)}</div>
      <div class="metric-sub">{html.escape(note)}</div>
    </div>
    """


def render_forecast_chart(weather: dict[str, Any], unit: str) -> None:
    hourly = weather["hourly"]
    times = hourly.get("time", [])
    temperatures = hourly.get("temperature_2m", [])
    rain_chance = hourly.get("precipitation_probability", [])
    current_time = weather.get("current", {}).get("time", "")

    start = 0
    for index, timestamp in enumerate(times):
        if timestamp >= current_time:
            start = index
            break
    else:
        start = 0

    times_slice = times[start:start + 24]
    temp_slice = temperatures[start:start + 24]
    if not times_slice or not temp_slice:
        st.info("Hourly forecast data is not available for this location right now.")
        return

    displayed = [float(v) * 9 / 5 + 32 if unit == "°F" else float(v) for v in temp_slice]
    labels = [datetime.fromisoformat(t).strftime("%I %p").lstrip("0") for t in times_slice]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels,
        y=displayed,
        mode="lines+markers",
        name="Temperature",
        line={"color": "#a5fff2", "width": 3, "shape": "spline", "smoothing": 0.7},
        marker={"color": "#ffffff", "size": 6, "line": {"color": "#a5fff2", "width": 2}},
        fill="tozeroy",
        fillcolor="rgba(114,239,224,0.10)",
        hovertemplate="%{x}<br><b>%{y:.1f}°" + ("F" if unit == "°F" else "C") + "</b><extra></extra>",
    ))
    fig.update_layout(
        height=280,
        margin={"l": 5, "r": 9, "t": 15, "b": 3},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "rgba(240,249,255,.76)", "size": 11},
        showlegend=False,
        hovermode="x unified",
        xaxis={"showgrid": False, "zeroline": False, "fixedrange": True, "tickangle": 0, "nticks": 8},
        yaxis={"showgrid": True, "gridcolor": "rgba(255,255,255,.10)", "zeroline": False, "fixedrange": True, "ticksuffix": "°", "nticks": 5},
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})


def render_dashboard(place: dict[str, Any], unit: str) -> None:
    title = place_label(place)
    st.markdown(
        f"""<div class="topbar">
          <div><div class="welcome">Welcome back</div><div class="top-title">Your weather, at a glance</div></div>
          <div class="live-pill"><span class="live-dot"></span> Forecast connected <span style="opacity:.55">·</span> Open-Meteo</div>
        </div>
        <div class="eyebrow" style="margin:0 0 12px 2px">Weather forecast / {html.escape(title)}</div>""",
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Fetching the latest available forecast…"):
            weather = fetch_forecast(place["lat"], place["lng"])
    except (requests.RequestException, ValueError, KeyError) as error:
        st.error("The weather service could not be reached. Check your internet connection and try Refresh weather.")
        with st.expander("Technical detail"):
            st.code(str(error))
        return

    current = weather["current"]
    daily = weather["daily"]
    hourly = weather["hourly"]
    code = current.get("weather_code")
    description = weather_description(code)
    symbol = weather_symbol(code)
    temperature = display_temperature(current.get("temperature_2m"), unit)
    feels_like = display_temperature(current.get("apparent_temperature"), unit)
    update_time = str(current.get("time", ""))
    update_label = update_time.replace("T", " ") if update_time else "time unavailable"

    left, right = st.columns([1.42, 1], gap="medium")
    with left:
        st.markdown(
            f"""<div class="glass hero-card">
              <div class="hero-location"><span style="color:#b3fff4;font-size:1.1rem">⌖</span>{html.escape(title)}</div>
              <div class="eyebrow">Current conditions</div>
              <div class="hero-temp-row"><div class="hero-temp">{html.escape(temperature)}</div><div class="hero-unit">{html.escape(unit[1:])}</div><div class="hero-symbol" style="margin-left:auto">{html.escape(symbol)}</div></div>
              <div class="hero-condition">{html.escape(description)}</div>
              <div class="hero-note">Feels like {html.escape(feels_like)}. Use the hourly curve and the seven-day outlook below to plan ahead. Local model time: {html.escape(update_label)}.</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with right:
        wind_direction = current.get("wind_direction_10m")
        direction_text = f"{round(float(wind_direction))}°" if wind_direction is not None else "—"
        sunrise = daily.get("sunrise", [""])[0]
        sunset = daily.get("sunset", [""])[0]
        sunrise_text = sunrise.split("T")[-1] if "T" in sunrise else "—"
        sunset_text = sunset.split("T")[-1] if "T" in sunset else "—"
        uv = daily.get("uv_index_max", [None])[0]
        st.markdown(
            f"""<div class="glass right-card">
              <div class="eyebrow">Atmosphere</div><h2 style="font-size:1.75rem;margin:.55rem 0 1.25rem">Today's conditions</h2>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px 15px">
                <div><div class="metric-name">◌ Relative humidity</div><div style="font-size:1.7rem;font-weight:650;margin-top:8px">{safe_number(current.get('relative_humidity_2m'), '%')}</div><div class="metric-sub">Air moisture</div></div>
                <div><div class="metric-name">↗ Wind speed</div><div style="font-size:1.7rem;font-weight:650;margin-top:8px">{safe_number(current.get('wind_speed_10m'), ' km/h')}</div><div class="metric-sub">Direction {html.escape(direction_text)}</div></div>
                <div><div class="metric-name">☂ Rain chance</div><div style="font-size:1.7rem;font-weight:650;margin-top:8px">{safe_number(daily.get('precipitation_probability_max', [None])[0], '%')}</div><div class="metric-sub">Highest chance today</div></div>
                <div><div class="metric-name">ϟ UV index</div><div style="font-size:1.7rem;font-weight:650;margin-top:8px">{safe_number(uv)}</div><div class="metric-sub">Daily maximum</div></div>
              </div>
              <div style="border-top:1px solid rgba(255,255,255,.13);display:flex;justify-content:space-between;gap:12px;margin-top:25px;padding-top:17px;font-size:.82rem;color:rgba(240,249,255,.75)">
                <span>Sunrise <b style="color:white">{html.escape(sunrise_text)}</b></span><span>Sunset <b style="color:white">{html.escape(sunset_text)}</b></span>
              </div>
            </div>""",
            unsafe_allow_html=True,
        )

    metrics = st.columns(4, gap="small")
    metric_values = [
        ("Feels like", feels_like, "Perceived temperature", "≈"),
        ("Wind gusts", safe_number(current.get("wind_gusts_10m"), " km/h"), "Peak gust estimate", "↗"),
        ("Cloud cover", safe_number(current.get("cloud_cover"), "%"), "Sky covered by cloud", "☁"),
        ("Pressure", safe_number(current.get("pressure_msl"), " hPa"), "Mean sea-level pressure", "⌁"),
    ]
    for idx, (column, values) in enumerate(zip(metrics, metric_values)):
        with column:
            st.markdown(metric_card(*values, delay=idx * 70), unsafe_allow_html=True)

    st.markdown(
        "<div class='section-heading'><div><h2>Next 24 hours</h2><p>Temperature trend and upcoming changes</p></div><p>Local time</p></div>",
        unsafe_allow_html=True,
    )

    # Compact hour cards; the chart below shows the wider trend.
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    codes = hourly.get("weather_code", [])
    rains = hourly.get("precipitation_probability", [])
    current_time = str(current.get("time", ""))
    start = next((i for i, value in enumerate(times) if value >= current_time), 0)
    hour_cards: list[str] = []
    for i in range(start, min(start + 6, len(times))):
        time_label = readable_day(times[i], "%I %p").lstrip("0")
        rain_text = f"{rains[i]}% rain" if i < len(rains) and rains[i] is not None else "Forecast"
        hour_cards.append(
            f"<div class='hour-card' style='animation-delay:{i-start}00ms'>"
            f"<div class='hour-time'>{html.escape(time_label)}</div>"
            f"<div class='hour-symbol'>{html.escape(weather_symbol(codes[i] if i < len(codes) else None))}</div>"
            f"<div class='hour-temp'>{html.escape(display_temperature(temps[i], unit))}</div>"
            f"<div class='hour-rain'>{html.escape(rain_text)}</div></div>"
        )
    st.markdown(f"<div class='hourly-grid'>{''.join(hour_cards)}</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown(
            "<div class='glass' style='padding:18px 18px 5px'><div class='eyebrow' style='padding:3px 7px'>Temperature curve</div>",
            unsafe_allow_html=True,
        )
        render_forecast_chart(weather, unit)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='section-heading'><div><h2>Seven-day outlook</h2><p>Daily high and low temperatures</p></div></div>",
        unsafe_allow_html=True,
    )
    day_cards = []
    for i, date_value in enumerate(daily.get("time", [])[:7]):
        high_values = daily.get("temperature_2m_max", [])
        low_values = daily.get("temperature_2m_min", [])
        code_values = daily.get("weather_code", [])
        rain_values = daily.get("precipitation_probability_max", [])
        label = "Today" if i == 0 else readable_day(date_value, "%A")
        high = display_temperature(high_values[i] if i < len(high_values) else None, unit)
        low = display_temperature(low_values[i] if i < len(low_values) else None, unit)
        day_code = code_values[i] if i < len(code_values) else None
        rain = rain_values[i] if i < len(rain_values) else None
        day_cards.append(
            f"<div class='glass day-card' style='animation-delay:{i*55}ms'>"
            f"<div class='day-name'>{html.escape(label)}</div>"
            f"<div class='day-symbol'>{html.escape(weather_symbol(day_code))}</div>"
            f"<div class='day-desc'>{html.escape(weather_description(day_code))}</div>"
            f"<div class='day-temp'>{html.escape(high)} <span>{html.escape(low)}</span></div>"
            f"<div class='metric-sub' style='margin-top:7px'>{html.escape(safe_number(rain, '%'))} rain</div>"
            f"</div>"
        )
    st.markdown(f"<div class='forecast-grid'>{''.join(day_cards)}</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='footer-note'>Weather data: Open-Meteo forecast models. Values are forecasts/estimates, not guaranteed observations. The provider's model update time may differ by region. This starter is intended for learning and non-commercial use; review the API terms before commercial deployment.</div>",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Interactive 3D globe. This is intentionally a small browser widget; the app,
# API clients, state, charts and dashboard are Python/Streamlit.
# -----------------------------------------------------------------------------

GLOBE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  *{box-sizing:border-box} body{margin:0;background:transparent;color:#f4fbff;font-family:Inter,system-ui,sans-serif;overflow:hidden}
  .stage{position:relative;height:560px;width:100%;overflow:hidden;border-radius:22px;background:radial-gradient(ellipse at 48% 48%,rgba(22,87,106,.21),rgba(3,13,24,.08) 53%,rgba(2,9,17,.3));}
  #globe{position:absolute;inset:0;width:100%;height:100%;}
  .overlay{position:absolute;z-index:3;pointer-events:none;left:20px;top:18px;max-width:280px;text-shadow:0 2px 12px #001018}
  .tag{font-size:10px;font-weight:800;letter-spacing:.17em;text-transform:uppercase;color:#9ff8ed}
  .guide{font-size:12px;line-height:1.55;color:rgba(240,249,255,.68);margin-top:7px}
  .result{position:absolute;z-index:5;right:16px;bottom:16px;width:min(320px,calc(100% - 32px));padding:16px 17px;border:1px solid rgba(255,255,255,.19);border-radius:19px;background:rgba(5,20,31,.77);backdrop-filter:blur(18px);box-shadow:inset 0 1px rgba(255,255,255,.13);}
  .result-label{font-size:10px;color:#9ff8ed;text-transform:uppercase;letter-spacing:.16em;font-weight:800}
  .result-name{font-size:19px;font-weight:700;letter-spacing:-.04em;margin-top:7px}
  .result-cond{font-size:12px;color:rgba(240,249,255,.72);margin-top:3px}
  .result-row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-top:11px}
  .result-temp{font-size:35px;font-weight:600;letter-spacing:-.07em}
  .result-metrics{font-size:11px;color:rgba(240,249,255,.72);line-height:1.8;text-align:right}
  .controls{position:absolute;z-index:5;left:16px;bottom:16px;display:flex;gap:8px;pointer-events:auto}
  .controls button{border:1px solid rgba(255,255,255,.2);border-radius:999px;padding:9px 13px;color:#f5fbff;background:rgba(5,20,31,.75);backdrop-filter:blur(12px);font-size:11px;cursor:pointer}
  .controls button:hover{background:rgba(111,198,199,.28)}
  .legend{position:absolute;z-index:4;top:19px;right:18px;display:flex;gap:7px;align-items:center;color:rgba(239,249,255,.62);font-size:10px;background:rgba(3,18,29,.42);border:1px solid rgba(255,255,255,.1);padding:8px 10px;border-radius:999px;}
  .legend-dot{height:7px;width:7px;border-radius:50%;display:inline-block;margin-left:4px}
  @media(max-width:600px){.stage{height:490px}.overlay{max-width:180px;left:14px;top:14px}.guide{font-size:10px}.legend{top:auto;bottom:158px;right:12px}.result{bottom:12px;right:12px}.controls{bottom:148px;left:12px;flex-direction:column;align-items:flex-start}.result-temp{font-size:30px}}
</style>
</head>
<body>
<div class="stage">
  <div id="globe"></div>
  <div class="overlay"><div class="tag">Earth weather explorer</div><div class="guide">Drag to rotate · Scroll to zoom · Select a city or click a point on the planet to fetch its conditions.</div></div>
  <div class="legend"><span class="legend-dot" style="background:#80cfff"></span>Cool <span class="legend-dot" style="background:#68ead7"></span>Mild <span class="legend-dot" style="background:#ffbd82"></span>Warm</div>
  <div class="controls"><button id="rotateBtn">Ⅱ Pause rotation</button><button id="homeBtn">◎ Reset view</button></div>
  <div class="result" id="weatherResult"><div class="result-label">Selected point</div><div class="result-name">Loading weather…</div><div class="result-cond">Connecting to forecast service</div></div>
</div>
<script src="https://unpkg.com/globe.gl"></script>
<script>
const cityData = __CITY_DATA__;
const initialPlace = __INITIAL_PLACE__;
const weatherNames = {0:'Clear sky',1:'Mainly clear',2:'Partly cloudy',3:'Overcast',45:'Fog',48:'Rime fog',51:'Light drizzle',53:'Drizzle',55:'Dense drizzle',56:'Freezing drizzle',57:'Freezing drizzle',61:'Light rain',63:'Rain',65:'Heavy rain',66:'Freezing rain',67:'Freezing rain',71:'Light snow',73:'Snow',75:'Heavy snow',77:'Snow grains',80:'Rain showers',81:'Rain showers',82:'Heavy showers',85:'Snow showers',86:'Heavy snow showers',95:'Thunderstorm',96:'Thunderstorm with hail',99:'Thunderstorm with hail'};
const root = document.getElementById('globe');
let isRotating = true;
let world;

function markerColor(t){
  if (t === null || t === undefined || Number.isNaN(Number(t))) return '#9ff8ed';
  if (t < 5) return '#80cfff';
  if (t < 15) return '#83d7f5';
  if (t < 25) return '#68ead7';
  if (t < 32) return '#ffcf86';
  return '#ff957e';
}
function escapeHTML(value){return String(value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}
function showLoading(name){document.getElementById('weatherResult').innerHTML = `<div class="result-label">Fetching current model data</div><div class="result-name">${escapeHTML(name)}</div><div class="result-cond">Requesting Open-Meteo forecast…</div>`;}
async function fetchPointWeather(lat,lng,name){
  showLoading(name);
  const params = new URLSearchParams({latitude:String(lat),longitude:String(lng),current:'temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m',timezone:'auto'});
  try {
    const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`);
    if(!response.ok) throw new Error('Weather service returned '+response.status);
    const data = await response.json(); const c = data.current || {};
    const temp = c.temperature_2m == null ? '—' : Math.round(c.temperature_2m)+'°C';
    const feels = c.apparent_temperature == null ? '—' : Math.round(c.apparent_temperature)+'°C';
    const code = Number(c.weather_code); const condition = weatherNames[code] || 'Conditions unavailable';
    const updated = c.time ? c.time.replace('T',' ') : 'Update time unavailable';
    document.getElementById('weatherResult').innerHTML = `<div class="result-label">Weather at selected point</div><div class="result-name">${escapeHTML(name)}</div><div class="result-cond">${escapeHTML(condition)} · ${escapeHTML(updated)}</div><div class="result-row"><div class="result-temp">${escapeHTML(temp)}</div><div class="result-metrics">Feels like ${escapeHTML(feels)}<br>Humidity ${escapeHTML(c.relative_humidity_2m == null ? '—' : c.relative_humidity_2m+'%')}<br>Wind ${escapeHTML(c.wind_speed_10m == null ? '—' : c.wind_speed_10m+' km/h')}</div></div>`;
  } catch(error) {
    document.getElementById('weatherResult').innerHTML = `<div class="result-label">Could not load point</div><div class="result-name">${escapeHTML(name)}</div><div class="result-cond">Check your connection and select this point again.</div>`;
  }
}

world = Globe()(root)
  .globeImageUrl('https://unpkg.com/three-globe/example/img/earth-night.jpg')
  .backgroundImageUrl('https://unpkg.com/three-globe/example/img/night-sky.png')
  .backgroundColor('rgba(0,0,0,0)')
  .showAtmosphere(true)
  .atmosphereColor('#7be7ee')
  .atmosphereAltitude(0.17)
  .showGraticules(true)
  .pointsData(cityData)
  .pointLat('lat')
  .pointLng('lng')
  .pointColor(d => d.color || '#9ff8ed')
  .pointAltitude(0.018)
  .pointRadius(0.21)
  .pointLabel(d => `${escapeHTML(d.name)}, ${escapeHTML(d.country)}${d.temperature == null ? '' : ' · '+Math.round(d.temperature)+'°C'}`)
  .pointsTransitionDuration(450)
  .onPointClick((point) => {
    world.pointOfView({lat:point.lat,lng:point.lng,altitude:1.65},850);
    fetchPointWeather(point.lat,point.lng,`${point.name}, ${point.country}`);
  })
  .onGlobeClick(({lat,lng}) => {
    const name = `${lat.toFixed(2)}°, ${lng.toFixed(2)}°`;
    fetchPointWeather(lat,lng,name);
  });

world.width(root.clientWidth).height(root.clientHeight);
world.controls().autoRotate = isRotating;
world.controls().autoRotateSpeed = 0.28;
world.controls().enableDamping = true;
world.pointOfView({lat:initialPlace.lat,lng:initialPlace.lng,altitude:2.1},0);

// Fetch a multi-coordinate current forecast once, then tint the city markers by
// actual model temperature. If batch responses are unavailable, cyan markers remain.
async function colorCitiesByWeather(){
  try {
    const params = new URLSearchParams({
      latitude:cityData.map(c=>c.lat).join(','),
      longitude:cityData.map(c=>c.lng).join(','),
      current:'temperature_2m',timezone:'auto'
    });
    const response = await fetch(`https://api.open-meteo.com/v1/forecast?${params.toString()}`);
    if(!response.ok) return;
    const payload = await response.json();
    const records = Array.isArray(payload) ? payload : [payload];
    if(records.length !== cityData.length) return;
    const updated = cityData.map((city,i)=>{
      const temperature = records[i] && records[i].current ? records[i].current.temperature_2m : null;
      return {...city,temperature,color:markerColor(temperature)};
    });
    world.pointsData(updated);
  } catch(error) { /* Markers still work as location selectors if the color request fails. */ }
}

document.getElementById('rotateBtn').addEventListener('click',()=>{
  isRotating = !isRotating; world.controls().autoRotate = isRotating;
  document.getElementById('rotateBtn').textContent = isRotating ? 'Ⅱ Pause rotation' : '▶ Resume rotation';
});
document.getElementById('homeBtn').addEventListener('click',()=>world.pointOfView({lat:initialPlace.lat,lng:initialPlace.lng,altitude:2.1},950));
window.addEventListener('resize',()=>world.width(root.clientWidth).height(root.clientHeight));
fetchPointWeather(initialPlace.lat,initialPlace.lng,initialPlace.name + (initialPlace.country ? ', '+initialPlace.country : ''));
colorCitiesByWeather();
</script>
</body>
</html>"""


def build_globe_html(place: dict[str, Any]) -> str:
    """Prepare the interactive globe page with safe JSON data substitutions."""
    cities = list(GLOBE_CITIES)
    selected_key = (place.get("name", "").lower(), round(float(place["lat"]), 3), round(float(place["lng"]), 3))
    exists = any(
        (c["name"].lower(), round(float(c["lat"]), 3), round(float(c["lng"]), 3)) == selected_key
        for c in cities
    )
    if not exists:
        cities.insert(0, {
            "name": place.get("name", "Selected location"),
            "country": place.get("country", ""),
            "lat": float(place["lat"]),
            "lng": float(place["lng"]),
            "color": "#9ff8ed",
        })
    initial = {
        "name": str(place.get("name", "Selected location")),
        "country": str(place.get("country", "")),
        "lat": float(place["lat"]),
        "lng": float(place["lng"]),
    }
    cities_json = json.dumps(cities, ensure_ascii=False).replace("<", "\\u003c")
    initial_json = json.dumps(initial, ensure_ascii=False).replace("<", "\\u003c")
    return GLOBE_HTML.replace("__CITY_DATA__", cities_json).replace("__INITIAL_PLACE__", initial_json)


def render_earth_explorer(place: dict[str, Any]) -> None:
    st.markdown(
        """<div class="topbar"><div><div class="welcome">Look beyond your local forecast</div><div class="top-title">Earth weather explorer</div></div><div class="live-pill"><span class="live-dot"></span> Interactive 3D globe</div></div>
        <p class="globe-caption">Rotate the planet, zoom into a region, select a marker, or click anywhere on the globe to request its current weather-model conditions. City pins are tinted using the forecast temperature when the batch request succeeds.</p>""",
        unsafe_allow_html=True,
    )
    components.html(build_globe_html(place), height=580, scrolling=False)
    st.markdown(
        """<div class="footer-note">The globe is an interactive visualization, not a satellite camera or continuous radar feed. Clicking a location requests the latest model data available from Open-Meteo for that coordinate. Model update frequency and local accuracy vary by region. Globe texture assets and the Globe.gl library load from public CDNs, so the globe requires an internet connection.</div>""",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# App entry point
# -----------------------------------------------------------------------------

def init_session_state() -> None:
    if "selected_place" not in st.session_state:
        st.session_state.selected_place = {
            "name": "Bengaluru",
            "country": "India",
            "admin1": "Karnataka",
            "lat": 12.9716,
            "lng": 77.5946,
            "timezone": "Asia/Kolkata",
        }
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "last_search" not in st.session_state:
        st.session_state.last_search = ""


def main() -> None:
    inject_css()
    init_session_state()

    with st.sidebar:
        st.markdown(
            "<div class='brand-mark'><div class='brand-icon'>≈</div><div>AURORA<br><span style='font-size:.67rem;letter-spacing:.16em;color:rgba(240,249,255,.58);font-weight:600'>WEATHER LAB</span></div></div>",
            unsafe_allow_html=True,
        )
        page = st.radio("Workspace", ["Dashboard", "Explore Earth"], index=0, key="workspace", label_visibility="visible")
        st.markdown("---")
        st.markdown("<div class='eyebrow' style='margin-bottom:8px'>Find a location</div>", unsafe_allow_html=True)
        with st.form("city_search_form", clear_on_submit=False):
            query = st.text_input("City or place", placeholder="e.g. Bengaluru, Tokyo…", label_visibility="collapsed")
            search_clicked = st.form_submit_button("Search locations", use_container_width=True)
        if search_clicked:
            if query.strip():
                try:
                    with st.spinner("Searching places…"):
                        found = search_locations(query.strip())
                    st.session_state.search_results = found
                    st.session_state.last_search = query.strip()
                    st.session_state.place_choice = 0
                    if not found:
                        st.warning("No matching locations. Try adding a country name.")
                    else:
                        st.rerun()
                except requests.RequestException:
                    st.error("Location search failed. Check your internet connection.")
            else:
                st.warning("Type a city or place first.")

        results = st.session_state.search_results
        if results:
            st.caption(f"Matches for: {st.session_state.last_search}")
            choice = st.selectbox(
                "Search results",
                options=list(range(len(results))),
                format_func=lambda i: place_label(results[i]),
                key="place_choice",
                label_visibility="collapsed",
            )
            if st.button("Use selected location", use_container_width=True, type="primary"):
                st.session_state.selected_place = location_from_search_result(results[choice])
                st.session_state.search_results = []
                st.rerun()
        st.markdown("---")
        unit = st.radio("Temperature unit", ["°C", "°F"], horizontal=True, index=0, key="temperature_unit")
        st.caption("Forecasts update from the weather provider. Cached in this app for 15 minutes to reduce repeated requests.")
        if st.button("↻ Refresh weather", use_container_width=True):
            fetch_forecast.clear()
            search_locations.clear()
            st.rerun()
        st.markdown("---")
        st.markdown("<div class='footer-note'>Built with Python + Streamlit<br>Data by Open-Meteo</div>", unsafe_allow_html=True)

    selected_place = st.session_state.selected_place
    if page == "Dashboard":
        render_dashboard(selected_place, unit)
    else:
        render_earth_explorer(selected_place)


if __name__ == "__main__":
    main()
