import os
import time
import logging
import datetime as dt
import requests
import streamlit as st
from dotenv import load_dotenv

# === SETUP ===
load_dotenv()
logging.basicConfig(
    filename="app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

OWM_API_KEY = os.getenv("OWM_API_KEY")
API_BASE = "https://api.openweathermap.org/data/2.5"
DEFAULT_UNITS = "metric"

st.set_page_config(page_title="Weather • Streamlit", page_icon="⛅", layout="wide")

# --- API helpers --------------------------------------------------------------


def get_current_weather(city, units=DEFAULT_UNITS, lang="en"):
    """Fetch current weather and log latency."""
    t0 = time.time()
    params = {"q": city, "appid": OWM_API_KEY, "units": units, "lang": lang}
    r = requests.get(f"{API_BASE}/weather", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    logging.info("current %s %.2fs", city, time.time() - t0)
    return data


def get_forecast(city, units=DEFAULT_UNITS, lang="en"):
    """Fetch 5-day forecast and log latency."""
    t0 = time.time()
    params = {"q": city, "appid": OWM_API_KEY, "units": units, "lang": lang}
    r = requests.get(f"{API_BASE}/forecast", params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    logging.info("forecast %s %.2fs", city, time.time() - t0)
    return data


def condition_key(weather_main: str) -> str:
    """Simplify weather type for background theme."""
    m = (weather_main or "").lower()
    if "thunder" in m:
        return "thunderstorm"
    if "drizzle" in m:
        return "drizzle"
    if "rain" in m:
        return "rain"
    if "snow" in m:
        return "snow"
    if "cloud" in m:
        return "clouds"
    if any(x in m for x in ["mist", "fog", "haze", "smoke"]):
        return "mist"
    if "clear" in m:
        return "clear"
    return "other"


def background_css(theme: str) -> str:
    """Return CSS with gradient and optional animation."""
    css_map = {
        "clear": {
            "gradient": "linear-gradient(135deg, #f7971e 0%, #ffd200 100%)",
        },
        "clouds": {
            "gradient": "linear-gradient(135deg, #606c88 0%, #3f4c6b 100%)",
        },
        "rain": {
            "gradient": "linear-gradient(135deg, #4b79a1 0%, #283e51 100%)",
            "animation": "rain",
        },
        "snow": {
            "gradient": "linear-gradient(135deg, #83a4d4 0%, #b6fbff 100%)",
            "animation": "snow",
        },
        "thunderstorm": {
            "gradient": "linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%)",
            "animation": "rain",
        },
        "mist": {
            "gradient": "linear-gradient(135deg, #bdc3c7 0%, #2c3e50 100%)",
        },
        "other": {
            "gradient": "linear-gradient(135deg, #D7D2CC 0%, #304352 100%)",
        },
    }

    data = css_map.get(theme, css_map["other"])
    gradient = data["gradient"]
    anim = data.get("animation")

    base_css = f"""
    <style>
    .stApp {{
        background: {gradient};
        background-attachment: fixed;
    }}
    .glass {{
        background: rgba(255,255,255,0.1);
        border-radius: 18px;
        padding: 18px;
        border: 1px solid rgba(192,192,192,0.4);
        box-shadow: 0 0 20px rgba(192,192,192,0.3);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
    }}
    .inline {{ display: flex; align-items: center; gap: .75rem; }}
    .muted {{ opacity: .9; }}
    .big-temp {{ font-size: 56px; font-weight: 700; line-height: 1; }}
    .day-card {{
        display:flex; flex-direction:column; align-items:center; gap:.35rem;
        background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius:16px; padding:14px; min-width:110px;
    }}
    .wicon {{ width: 64px; height: 64px; }}
    </style>
    """

    rain_css = """
    <style>
    .rain:before, .rain:after {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        background-image: radial-gradient(2px 12px at 20px 20px, rgba(255,255,255,.25) 50%, rgba(255,255,255,0) 51%);
        background-size: 10px 40px;
        animation: rain-fall 0.75s linear infinite;
        opacity: .35;
    }
    @keyframes rain-fall { 0% {{ transform: translateY(-40px); }} 100% {{ transform: translateY(40px); }} }
    </style>
    """

    snow_css = """
    <style>
    .snow:before, .snow:after {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        background-image:
          radial-gradient(3px 3px at 20px 20px, rgba(255,255,255,.9) 50%, rgba(255,255,255,0) 52%),
          radial-gradient(2px 2px at 60px 40px, rgba(255,255,255,.8) 50%, rgba(255,255,255,0) 52%),
          radial-gradient(2px 2px at 100px 80px, rgba(255,255,255,.85) 50%, rgba(255,255,255,0) 52%);
        background-size: 120px 120px;
        animation: snow-fall 6s linear infinite;
        opacity: .6;
    }
    @keyframes snow-fall { 0% {{ transform: translateY(-60px); }} 100% {{ transform: translateY(60px); }} }
    </style>
    """

    anim_css = ""
    if anim == "rain":
        anim_css = rain_css
    elif anim == "snow":
        anim_css = snow_css

    script = ""
    if anim in ("rain", "snow"):
        script = f"<script>const t=window.parent.document.querySelector('.stApp'); if(t) t.classList.add('{anim}');</script>"

    return base_css + anim_css + script


def group_forecast_daily(forecast_json):
    """Aggregate forecast data by day (average temperature & wind)."""
    items = forecast_json.get("list", [])
    tz = forecast_json.get("city", {}).get("timezone", 0)
    days = {}
    for it in items:
        ts = it["dt"]
        date = dt.datetime.utcfromtimestamp(ts + tz).date()
        e = days.setdefault(date, {"temps": [], "icons": [], "mains": [], "winds": []})
        e["temps"].append(it["main"]["temp"])
        e["icons"].append(it["weather"][0]["icon"])
        e["mains"].append(it["weather"][0]["main"])
        e["winds"].append(it["wind"]["speed"])
    out = []
    for d, v in sorted(days.items()):
        avg_t = sum(v["temps"]) / len(v["temps"])
        avg_w = sum(v["winds"]) / len(v["winds"])
        icon = v["icons"][len(v["icons"]) // 2]
        main = v["mains"][len(v["mains"]) // 2]
        out.append({"date": d, "temp": avg_t, "icon": icon, "main": main, "wind": avg_w})
    return out[:5]


# --- UI -----------------------------------------------------------------------

st.markdown(
    "<h1 style='margin-bottom:0'>Weather Forecast</h1>"
    "<p class='muted'>Type a city to get current conditions and a 5-day outlook.</p>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Settings")
    city = st.text_input("City", value="Warsaw")
    units = st.selectbox("Units", options=["metric", "imperial"], index=0)
    go = st.button("Show weather")

# --- Main Logic ---------------------------------------------------------------

if go and not OWM_API_KEY:
    st.error("Missing OWM_API_KEY. Set it as env var or .env file.")
    st.stop()

if go:
    ok = True
    try:
        current = get_current_weather(city, units=units)
        forecast = get_forecast(city, units=units)
    except Exception as e:
        ok = False
        st.error(f"Error fetching data: {e}")
        logging.error("%s: %s", city, e)
        st.stop()

    # Sidebar status
    st.sidebar.markdown(f"**API status:** {'✅ OK' if ok else '❌ DOWN'}")

    main = current["weather"][0]["main"]
    theme = condition_key(main)
    st.markdown(background_css(theme), unsafe_allow_html=True)

    # Current section
    col1, col2, col3 = st.columns([1.4, 1, 1])
    icon = current["weather"][0]["icon"]
    desc = current["weather"][0]["description"].title()
    temp = round(current["main"]["temp"])
    feels = round(current["main"]["feels_like"])
    humidity = current["main"]["humidity"]
    wind = current["wind"]["speed"]
    city_name = f"{current['name']}, {current['sys'].get('country','')}"
    unit_letter = "C" if units == "metric" else "F"
    wind_unit = "m/s" if units == "metric" else "mph"

    with col1:
        st.markdown(
            f"""
        <div class="glass">
            <div class="inline">
                <img class="wicon" src="https://openweathermap.org/img/wn/{icon}@2x.png"/>
                <div>
                    <div style="font-size:22px;font-weight:600">{city_name}</div>
                    <div class="muted">{desc}</div>
                </div>
            </div>
            <div style="margin-top:8px" class="inline">
                <div class="big-temp">{temp}°{unit_letter}</div>
                <div class="muted">feels like {feels}°</div>
            </div>
            <div class="inline muted" style="margin-top:6px">
                💧 {humidity}% &nbsp; · &nbsp; 🌬️ {wind} {wind_unit}
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        sunr = dt.datetime.utcfromtimestamp(
            current["sys"]["sunrise"] + current["timezone"]
        ).strftime("%H:%M")
        suns = dt.datetime.utcfromtimestamp(
            current["sys"]["sunset"] + current["timezone"]
        ).strftime("%H:%M")
        st.markdown(
            f"""
        <div class="glass">
            <div style="font-weight:600">Sunrise / Sunset</div>
            <div class="inline" style="margin-top:8px">🌅 {sunr} &nbsp; / &nbsp; 🌇 {suns}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col3:
        vis_km = (current.get("visibility", 0) or 0) / 1000
        st.markdown(
            f"""
        <div class="glass">
            <div style="font-weight:600">Coordinates</div>
            <div class="inline" style="margin-top:8px">📍 {current['coord']['lat']:.2f}, {current['coord']['lon']:.2f}</div>
            <div class="muted" style="margin-top:6px">Pressure: {current['main']['pressure']} hPa</div>
            <div class="muted">Visibility: {vis_km:.1f} km</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # Forecast
    st.markdown("### 5-Day Forecast")
    daily = group_forecast_daily(forecast)
    cols = st.columns(len(daily))
    for i, d in enumerate(daily):
        with cols[i]:
            day_name = d["date"].strftime("%a %d %b")
            t = round(d["temp"])
            wind = round(d["wind"], 1)
            st.markdown(
                f"""
            <div class="day-card">
                <div style="font-weight:600">{day_name}</div>
                <img class="wicon" src="https://openweathermap.org/img/wn/{d['icon']}@2x.png"/>
                <div>{t}°{unit_letter}</div>
                <div class="muted">{d['main']}</div>
                <div class="muted">💨 {wind} {wind_unit}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

else:
    st.info("Enter a city in the left sidebar and press **Show weather**.")
