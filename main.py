#!/usr/bin/env python3
"""
Air Quality Monitor — prototype + météo
Fetches RSQA data every 30 min + weather from Open-Meteo.
Press any key or click to toggle pollutant stats.
"""
import os
import sys

# ── Early splash — init pygame before heavy imports so the screen lights up fast
import pygame
pygame.init()
_FULLSCREEN_EARLY = os.getenv("AQI_FULLSCREEN", "0") == "1"
if _FULLSCREEN_EARLY:
    _ei = pygame.display.Info()
    _ew, _eh = _ei.current_w, _ei.current_h
    _early_screen = pygame.display.set_mode((_ew, _eh), pygame.FULLSCREEN)
else:
    _early_screen = pygame.display.set_mode((800, 480), pygame.RESIZABLE)
pygame.display.set_caption("Air Quality")
pygame.mouse.set_visible(False)
_early_screen.fill((0, 160, 0))
pygame.display.flip()
# ─────────────────────────────────────────────────────────────────────────────

import tty
import termios
import atexit
import threading
import time

from fetcher import fetch_all, STATIONS
from weather import fetch_weather
from display import AQIDisplay
import history
import map_tile

# ── Config — override via env vars on Pi ──────────────────────────────────────
REFRESH_SECS         = int(os.getenv("AQI_REFRESH", 30 * 60))
WEATHER_REFRESH_SECS = int(os.getenv("WEATHER_REFRESH", 5 * 60))
FULLSCREEN           = os.getenv("AQI_FULLSCREEN", "0") == "1"

# ── State ─────────────────────────────────────────────────────────────────────
STATION_KEYS  = list(STATIONS.keys())
_active_keys  = list(STATION_KEYS)          # stations with live data (updated after each fetch)
_station_idx  = STATION_KEYS.index("ahuntsic")
_fetch_event  = threading.Event()


def _do_fetch(display: AQIDisplay):
    global _station_idx, _active_keys
    print("[fetch] fetching all stations…")
    all_data = fetch_all()
    if not all_data:
        print("[fetch] failed — keeping last display")
        display.update(None)
        return

    # Keep only stations that returned real data
    new_active = [k for k in STATION_KEYS if all_data.get(k) is not None]
    if not new_active:
        new_active = STATION_KEYS  # total failure — keep full list as fallback

    # Preserve the currently selected station if it survived, else fall back to index 0
    current_key = _active_keys[_station_idx] if _active_keys else STATION_KEYS[0]
    _active_keys = new_active
    _station_idx = _active_keys.index(current_key) if current_key in _active_keys else 0
    display.current_station_idx = _station_idx

    current = all_data.get(_active_keys[_station_idx])
    display.update(current)
    display.update_station_bar(all_data, _active_keys)
    if current:
        history.save(display.score, display.bg_color)
        print(f"[fetch] ok — {current['station']} {current['timestamp'].strftime('%H:%M')} "
              f"PM2.5={current['pollutants'].get('PM2.5', '?')} µg/m³  "
              f"({len(_active_keys)}/{len(STATION_KEYS)} stations actives)")
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
            rain = f"pluie le {w['rain_at'].strftime('%H:%M')}" if w["rain_at"] else "aucune pluie prévue"
            print(f"[weather] ok — {w['symbol']} {w['temperature']:.1f}°C  {rain}")
        else:
            print("[weather] failed — keeping last display")
        time.sleep(WEATHER_REFRESH_SECS)


def main():
    global _station_idx
    if sys.stdin.isatty():
        old = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())
        atexit.register(termios.tcsetattr, sys.stdin, termios.TCSADRAIN, old)
    display = AQIDisplay(fullscreen=FULLSCREEN)
    display.load_history(history.load_last_24h())
    map_tile.start_fetch()

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
            _station_idx = (_station_idx + display.station_delta) % len(_active_keys)
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
