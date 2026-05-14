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

from fetcher import fetch_all, STATIONS
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


def _do_fetch(display: AQIDisplay):
    print("[fetch] fetching all stations…")
    all_data = fetch_all()
    if not all_data:
        print("[fetch] failed — keeping last display")
        display.update(None)
        return

    current = all_data.get(STATION_KEYS[_station_idx])
    display.update(current)
    display.update_station_bar(all_data, STATION_KEYS)

    if current:
        print(f"[fetch] ok — {current['station']} {current['timestamp'].strftime('%H:%M')} "
              f"PM2.5={current['pollutants'].get('PM2.5', '?')} µg/m³")
    else:
        print("[fetch] current station failed — keeping last display")


def _fetch_loop(display: AQIDisplay):
    _do_fetch(display)  # fetch immediately at startup

    while True:
        t = time.localtime()

        if t.tm_min < 50:
            # Wait until :50 (or station change, capped at REFRESH_SECS)
            secs = min(REFRESH_SECS, (50 - t.tm_min) * 60 - t.tm_sec)
            triggered = _fetch_event.wait(timeout=secs)
            _fetch_event.clear()
            if triggered:
                _do_fetch(display)
                continue  # station change — restart countdown

        # Polling window :50→:00 — fetch every minute until data changes (max ~10×)
        last_ts = display.data["timestamp"] if display.data else None
        while time.localtime().tm_min >= 50:
            _fetch_event.wait(timeout=60)
            _fetch_event.clear()
            _do_fetch(display)
            new_ts = display.data["timestamp"] if display.data else None
            if new_ts != last_ts:
                # Got fresh data — sleep out the rest of the polling window then resume normal
                t2 = time.localtime()
                if t2.tm_min >= 50:
                    time.sleep((60 - t2.tm_min) * 60 - t2.tm_sec + 5)
                break


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
            display.current_station_idx = _station_idx
            display.loading = True
            display.data = None
            _fetch_event.set()

        display.render()
        clock.tick(30)

    display.quit()


if __name__ == "__main__":
    main()
