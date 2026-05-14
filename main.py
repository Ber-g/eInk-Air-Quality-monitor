#!/usr/bin/env python3
"""
Air Quality Monitor — prototype
Fetches RSQA data every 30 min, displays fullscreen color on any monitor.
Press any key or click to toggle pollutant stats.
"""
import os
import threading
import time
import pygame

from fetcher import fetch, STATIONS
from display import AQIDisplay

# ── Config — override via env vars on Pi ──────────────────────────────────────
REFRESH_SECS = int(os.getenv("AQI_REFRESH", 30 * 60))
FULLSCREEN   = os.getenv("AQI_FULLSCREEN", "0") == "1"

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
        # Wait for refresh interval OR an early wake triggered by station change
        _fetch_event.wait(timeout=REFRESH_SECS)
        _fetch_event.clear()


def main():
    global _station_idx
    display = AQIDisplay(fullscreen=FULLSCREEN)

    t = threading.Thread(target=_fetch_loop, args=(display,), daemon=True)
    t.start()

    clock   = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            running = display.handle_event(event)

        # Station change requested via arrow keys
        if display.station_delta != 0:
            _station_idx = (_station_idx + display.station_delta) % len(STATION_KEYS)
            display.station_delta = 0
            display.loading = True
            display.data = None
            _fetch_event.set()   # wake fetch thread immediately

        display.render()
        clock.tick(30)

    display.quit()


if __name__ == "__main__":
    main()
