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

import queue
import threading
import time

import log_buffer
from fetcher import fetch_all, STATIONS
from aqi import worst_pollutant, label_pollutant, score_pollutant
from weather import fetch_weather
from display import AQIDisplay
import history
import map_tile
from remote_server import RemoteServer

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
    log_buffer.info("[fetch] fetching all stations…")
    all_data = fetch_all()
    if not all_data:
        log_buffer.warning("[fetch] failed — keeping last display")
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
    display.current_station_key = _active_keys[_station_idx]

    current = all_data.get(_active_keys[_station_idx])
    display.update(current)
    display.update_station_bar(all_data, _active_keys)

    # Save all active stations — not just the selected one
    for key in _active_keys:
        data = all_data.get(key)
        if not data:
            continue
        pol, val, _ = worst_pollutant(data["pollutants"])
        _, color = label_pollutant(pol, val) if pol else (None, (0, 210, 0))
        score = score_pollutant(pol, val) if pol else 0.0
        history.save(key, data["timestamp"], score, color)

    if current:
        log_buffer.info(f"[fetch] ok — {current['station']} {current['timestamp'].strftime('%H:%M')} "
                        f"PM2.5={current['pollutants'].get('PM2.5', '?')} µg/m³  "
                        f"({len(_active_keys)}/{len(STATION_KEYS)} stations actives)")
    else:
        log_buffer.warning("[fetch] current station failed — keeping last display")


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
        log_buffer.info("[weather] fetching…")
        w = fetch_weather()
        if w:
            display.update_weather(w)
            rain = f"pluie le {w['rain_at'].strftime('%H:%M')}" if w["rain_at"] else "aucune pluie prévue"
            log_buffer.info(f"[weather] ok — {w['temperature']:.1f}°C  {rain}")
        else:
            log_buffer.warning("[weather] failed — keeping last display")
        time.sleep(WEATHER_REFRESH_SECS)


def main():
    global _station_idx
    log_buffer.init_file_log()
    log_buffer.info("[main] démarrage")
    display = AQIDisplay(fullscreen=FULLSCREEN)
    initial_key = _active_keys[_station_idx]
    display.current_station_key = initial_key
    display.load_history(history.load_last_24h(initial_key))
    map_tile.start_fetch()

    action_queue = queue.Queue()
    remote_server = RemoteServer(display, action_queue)
    remote_server.start()

    t = threading.Thread(target=_fetch_loop, args=(display,), daemon=True)
    t.start()

    wt = threading.Thread(target=_weather_loop, args=(display,), daemon=True)
    wt.start()

    clock   = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            running = display.handle_event(event)

        # ── Traitement des commandes reçues depuis l'API locale / Telegram ────
        while not action_queue.empty():
            try:
                action_type, kwargs, res_q = action_queue.get_nowait()
            except queue.Empty:
                break

            result = {"success": True}
            try:
                if action_type == "screenshot":
                    result["png_bytes"] = display.capture_screenshot()

                elif action_type == "set_view":
                    view = kwargs.get("view", "aqi")
                    if view in ("art", "musee", "musée"):
                        display.show_art()
                    elif view in ("aqi", "airq", "normal"):
                        display.show_aqi()
                    elif view == "menu":
                        display._nav.open_menu()
                    result["view"] = display._nav.get_active_page_name()

                elif action_type == "art_next":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        result["art"] = art_page.next_image()

                elif action_type == "art_prev":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        result["art"] = art_page.prev_image()

                elif action_type == "art_select":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        if kwargs.get("index") is not None:
                            result["art"] = art_page.set_image_by_index(int(kwargs["index"]))
                        elif kwargs.get("filename"):
                            result["art"] = art_page.set_image_by_name(str(kwargs["filename"]))

                elif action_type == "art_cartel":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        show_val = art_page.toggle_cartel(kwargs.get("show"))
                        result["show_cartel"] = show_val
                        result["art"] = art_page.get_current_info()

                elif action_type == "art_cartel_page":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        page_val = art_page.change_cartel_page(kwargs.get("delta", 1))
                        result["cartel_page"] = page_val
                        result["art"] = art_page.get_current_info()

                elif action_type == "art_add_and_show":
                    art_page = display.get_art_page()
                    if art_page:
                        display.show_art()
                        file_path = kwargs.get("file_path")
                        result["art"] = art_page.add_and_display_image(file_path)

                elif action_type == "art_delete":
                    art_page = display.get_art_page()
                    if art_page:
                        result = art_page.delete_media(str(kwargs.get("filename", "")))
                    else:
                        result = {"success": False, "error": "Page Musée indisponible"}

                elif action_type == "nav":
                    result = display.remote_nav(str(kwargs.get("action", "")))

                elif action_type == "station":
                    delta = kwargs.get("delta")
                    key = kwargs.get("key")
                    if delta is not None:
                        display.station_delta = int(delta)
                    elif key and key in _active_keys:
                        _station_idx = _active_keys.index(key)
                        display.station_delta = 0
                        display.current_station_idx = _station_idx
                        new_key = _active_keys[_station_idx]
                        display.current_station_key = new_key
                        display.load_history(history.load_last_24h(new_key))
                        display.start_loading()
                        _fetch_event.set()
                    result["station"] = display.current_station_key

            except Exception as ex:
                result = {"success": False, "error": str(ex)}

            if res_q:
                res_q.put(result)

        if display._restart_requested:
            remote_server.stop()
            display.quit()
            os.execv(sys.executable, [sys.executable] + sys.argv)

        if display._refetch_requested:
            display._refetch_requested = False
            display.start_loading()
            _fetch_event.set()

        if display.station_delta != 0:
            _station_idx = (_station_idx + display.station_delta) % len(_active_keys)
            display.station_delta = 0
            display.current_station_idx = _station_idx
            new_key = _active_keys[_station_idx]
            display.current_station_key = new_key
            display.load_history(history.load_last_24h(new_key))
            display.start_loading()
            _fetch_event.set()

        display.render()
        clock.tick(30)

    remote_server.stop()
    display.quit()


if __name__ == "__main__":
    main()
