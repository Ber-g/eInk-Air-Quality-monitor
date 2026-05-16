#!/usr/bin/env python3
from __future__ import annotations
"""
Weather forecast via Open-Meteo (free, no token).
Returns None on failure — never returns fake data.
"""
import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LAT, LON = 45.5427, -73.6356  # Montréal, 8464 Henri-Julien (Villeray)

# Weather Icons font codepoints (erikflowers/weather-icons)
# Written as chr() to avoid PUA encoding issues in source files.
_I = chr  # shorthand
_WMO_ICONS: dict[int, tuple[str, str]] = {
    #   day                      night
    0:  (_I(0xf00d), _I(0xf02e)),  # day-sunny / night-clear
    1:  (_I(0xf00c), _I(0xf081)),  # day-sunny-overcast / night-alt-partly-cloudy
    2:  (_I(0xf002), _I(0xf086)),  # day-cloudy / night-alt-cloudy
    3:  (_I(0xf013), _I(0xf013)),  # cloudy
    45: (_I(0xf003), _I(0xf04a)),  # day-fog / night-fog
    48: (_I(0xf003), _I(0xf04a)),  # fog + rime
    51: (_I(0xf009), _I(0xf029)),  # day-showers / night-alt-showers
    53: (_I(0xf009), _I(0xf029)),  # moderate drizzle
    55: (_I(0xf008), _I(0xf028)),  # heavy drizzle -> rain
    61: (_I(0xf008), _I(0xf028)),  # light rain
    63: (_I(0xf008), _I(0xf028)),  # moderate rain
    65: (_I(0xf008), _I(0xf028)),  # heavy rain
    66: (_I(0xf0b2), _I(0xf0b3)),  # freezing rain light (day-sleet / night-sleet)
    67: (_I(0xf0b2), _I(0xf0b3)),  # freezing rain heavy
    71: (_I(0xf00a), _I(0xf038)),  # light snow
    73: (_I(0xf00a), _I(0xf038)),  # moderate snow
    75: (_I(0xf00a), _I(0xf038)),  # heavy snow
    77: (_I(0xf015), _I(0xf015)),  # snow grains / hail
    80: (_I(0xf009), _I(0xf029)),  # light rain showers
    81: (_I(0xf008), _I(0xf028)),  # moderate rain showers
    82: (_I(0xf008), _I(0xf028)),  # heavy rain showers
    85: (_I(0xf00a), _I(0xf038)),  # light snow showers
    86: (_I(0xf00a), _I(0xf038)),  # heavy snow showers
    95: (_I(0xf010), _I(0xf02d)),  # thunderstorm
    96: (_I(0xf010), _I(0xf02d)),  # thunderstorm + light hail
    99: (_I(0xf010), _I(0xf02d)),  # thunderstorm + heavy hail
}

# Unicode fallback when Weather Icons TTF is not loaded
_WMO_FALLBACK: dict[int, str] = {
    0: "☀", 1: "☀", 2: "☁", 3: "☁",
    45: "☁", 48: "☁",
    51: "☔", 53: "☔", 55: "☔",
    61: "☔", 63: "☔", 65: "☔",
    66: "☔", 67: "☔",
    71: "❄", 73: "❄", 75: "❄", 77: "❄",
    80: "☔", 81: "☔", 82: "☔",
    85: "❄", 86: "❄",
    95: "☔", 96: "☔", 99: "☔",
}

RAIN_THRESHOLD_MM = 0.2  # mm/h minimum to count as rain


def fetch_weather() -> dict | None:
    """
    Returns:
        {
            "temperature":  float,
            "weather_code": int,
            "symbol":       str,   # Weather Icons codepoint (day/night aware)
            "fallback":     str,   # Unicode fallback if TTF absent
            "rain_at":      datetime | None,
        }
    or None on failure.
    """
    try:
        r = requests.get(OPEN_METEO_URL, params={
            "latitude":      LAT,
            "longitude":     LON,
            "current":       "temperature_2m,weather_code,is_day",
            "hourly":        "precipitation",
            "timezone":      "America/Toronto",
            "forecast_days": 2,
        }, timeout=10)
        r.raise_for_status()
        data = r.json()

        current = data["current"]
        temp    = current["temperature_2m"]
        code    = int(current["weather_code"])
        is_day  = int(current.get("is_day", 1))

        icons    = _WMO_ICONS.get(code, (_I(0xf013), _I(0xf013)))
        symbol   = icons[0] if is_day else icons[1]
        fallback = _WMO_FALLBACK.get(code, "?")

        times   = data["hourly"]["time"]
        precip  = data["hourly"]["precipitation"]
        now     = datetime.now()
        rain_at = None
        for t_str, mm in zip(times, precip):
            t = datetime.fromisoformat(t_str)
            if t <= now:
                continue
            if mm >= RAIN_THRESHOLD_MM:
                rain_at = t
                break

        return {
            "temperature":  temp,
            "weather_code": code,
            "symbol":       symbol,
            "fallback":     fallback,
            "rain_at":      rain_at,
        }

    except Exception as e:
        print(f"[weather] fetch failed: {e}")
        return None


if __name__ == "__main__":
    w = fetch_weather()
    if w:
        rain = w["rain_at"]
        rain_str = rain.strftime("%H:%M") if rain else "aucune"
        print(f"code={w['weather_code']}  sym={repr(w['symbol'])}  "
              f"{w['temperature']:.1f}°C  pluie={rain_str}")
    else:
        print("fetch failed")
