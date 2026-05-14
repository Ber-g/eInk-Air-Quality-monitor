#!/usr/bin/env python3
from __future__ import annotations
"""
Weather forecast via Open-Meteo (free, no token).
Returns None on failure — never returns fake data.
"""
import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
LAT, LON = 45.5088, -73.5878  # Montréal, secteur Parc Jarry

# WMO weather interpretation code → Unicode symbol (monochrome-safe)
_WMO_SYMBOL: dict[int, str] = {
    0:  "☀",
    1:  "☀",  2: "⛅",  3: "☁",
    45: "☁",  48: "☁",
    51: "☔", 53: "☔", 55: "☔",
    61: "☔", 63: "☔", 65: "☔",
    71: "❄",  73: "❄",  75: "❄",  77: "❄",
    80: "☔", 81: "☔", 82: "☔",
    85: "❄",  86: "❄",
    95: "⛈", 96: "⛈", 99: "⛈",
}

RAIN_THRESHOLD_MM = 0.2  # mm/h minimum to count as rain


def fetch_weather() -> dict | None:
    """
    Returns:
        {
            "temperature":   float,        # °C
            "weather_code":  int,           # WMO code
            "symbol":        str,           # Unicode symbol
            "rain_in_hours": float | None,  # hours until next rain (None = no rain forecast)
        }
    or None on failure.
    """
    try:
        r = requests.get(OPEN_METEO_URL, params={
            "latitude":     LAT,
            "longitude":    LON,
            "current":      "temperature_2m,weather_code",
            "hourly":       "precipitation",
            "timezone":     "America/Toronto",
            "forecast_days": 2,
        }, timeout=10)
        r.raise_for_status()
        data = r.json()

        current = data["current"]
        temp    = current["temperature_2m"]
        code    = int(current["weather_code"])

        # Find first future hour with meaningful precipitation
        times  = data["hourly"]["time"]
        precip = data["hourly"]["precipitation"]
        now    = datetime.now()
        rain_in_hours = None
        for t_str, mm in zip(times, precip):
            t = datetime.fromisoformat(t_str)
            if t <= now:
                continue
            if mm >= RAIN_THRESHOLD_MM:
                rain_in_hours = (t - now).total_seconds() / 3600
                break

        return {
            "temperature":   temp,
            "weather_code":  code,
            "symbol":        _WMO_SYMBOL.get(code, "?"),
            "rain_in_hours": rain_in_hours,
        }

    except Exception as e:
        print(f"[weather] fetch failed: {e}")
        return None


if __name__ == "__main__":
    w = fetch_weather()
    if w:
        rain = w["rain_in_hours"]
        rain_str = f"{rain:.1f}h" if rain is not None else "aucune"
        print(f"{w['symbol']}  {w['temperature']:.1f}°C  —  prochaine pluie : {rain_str}")
    else:
        print("fetch failed")
