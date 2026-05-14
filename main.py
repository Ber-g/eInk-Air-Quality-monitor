#!/usr/bin/env python3
"""
Air Quality Monitor — prototype + météo
Fetches RSQA data every 30 min + weather from Open-Meteo.
Press any key or click to toggle pollutant stats.
"""
import os
import threading
import time
import pygame

from fetcher import fetch, STATIONS
from weather import fetch_weather
from display import AQIDisplay

# ── Config — override via env vars on Pi ──────────────────────────────────────
REFRESH_SECS         = int(os.getenv("AQI_REFRESH", 30 * 60))
WEATHER_REFRESH_SECS = int(os.getenv("WEATHER_REFRESH", 30 * 60))
FULLSCREEN           = os.getenv("AQI_FULLSCREEN", "0") == "1"

# ── State ─────────────────────────────────────────────────────────────────────
STATION_KEYS = list(STATIONS.keys())
_station_idx = STATION_KEYS.index("ahuntsic")
_fetch_event = threading.Event()


def _do_fetch(display: AQIDisplay, key: str):
    print(f"[fetch] fetching {key}…")
    data = fetch(key)
    display.update(data)
    if data:
        print(f"[fetch] ok — {data['station']} {data['timestamp'].strftime('%H:%M')} "
              f"PM2.5={data['pollutants'].get('PM2.5','?')} µg/m³")
    else:
        print("[fetch] failed — keeping last display")


def _fetch_loop(display: AQIDisplay):
    while True:
        _do_fetch(display, STATION_KEYS[_station_idx])
        _fetch_event.wait(timeout=REFRESH_SECS)
        _fetch_event.clear()


def _weather_loop(display: AQIDisplay):
    while True:
        print("[weather] fetching…")
        w = fetch_weather()
        if w:
            display.update_weather(w)
            rain = f"pluie dans {w['rain_in_hours']:.1f}h" if w["rain_in_hours"] else "aucune pluie prévue"
            print(f"[weather] ok — {w['symbol']} {w['temperature']:.1f}°C  {rain}")
        else:
            print("[weather] failed — keeping last display")
        time.sleep(WEATHER_REFRESH_SECS)


def main():
    global _station_idx
    display = AQIDisplay(fullscreen=FULLSCREEN)

    t = threading.Thread(target=_fetch_loop, args=(display,), daemon=True)
    t.start()

    wt = threading.Thread(target=_weather_loop, args=(display,), daemon=True)
    wt.start()

    clock   = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            running = display.handle_event(event)

        if display.station_delta != 0:
            _station_idx = (_station_idx + display.station_delta) % len(STATION_KEYS)
            display.station_delta = 0
            display.loading = True
            display.data = None
            _fetch_event.set()

        display.render()
        clock.tick(30)

    display.quit()


if __name__ == "__main__":
    main()
