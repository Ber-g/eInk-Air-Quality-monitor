#!/usr/bin/env python3
from __future__ import annotations
"""
Minimal vector map — OpenStreetMap data via Overpass API.
Roads + water baked into a single Surface once after fetch.
Per-frame render = one blit + 2 circle draws.
"""
import json
import math
import os
import threading
import requests

# Bounding box covering ALL RSQA stations + weather point (with margin).
BBOX = (45.43, -73.80, 45.65, -73.52)   # min_lat, min_lon, max_lat, max_lon

WEATHER_LAT = 45.5427
WEATHER_LON = -73.6356  # 8464 Henri-Julien, Montréal

_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "map_data.json")

# Reference surface dimensions — 1000 px/°lat, longitude corrected for cos(lat).
# At 45.54°N, cos ≈ 0.700, so 1°lon ≈ 0.700°lat in physical distance.
_REF_H = 220   # 0.22° lat × 1000 px/°lat
_LAT_C = (BBOX[0] + BBOX[2]) / 2
_REF_W = int((BBOX[3] - BBOX[1]) * math.cos(math.radians(_LAT_C)) / (BBOX[2] - BBOX[0]) * _REF_H)
# → ≈ 196 px for current BBOX

_roads:          list | None           = None
_water:          list | None           = None
_surface:        "pygame.Surface|None" = None  # pre-baked roads+water at _REF_W × _REF_H
_scaled_surface: "pygame.Surface|None" = None  # cached scaled-down copy
_last_scale:     float                 = 0.0
_fetching = False
_baked    = False


def _proj(lat: float, lon: float, ox: int = 0, oy: int = 0) -> tuple[int, int]:
    min_lat, min_lon, max_lat, max_lon = BBOX
    px = int((lon - min_lon) / (max_lon - min_lon) * _REF_W) + ox
    py = int((max_lat - lat) / (max_lat - min_lat) * _REF_H) + oy
    return px, py


def _bake() -> None:
    """Render roads + water into a cached SRCALPHA surface (main thread only)."""
    global _surface, _baked
    import pygame

    surf = pygame.Surface((_REF_W, _REF_H), pygame.SRCALPHA)
    # water first (behind roads), in light grey
    for way in (_water or []):
        pts = [_proj(lat, lon) for lat, lon in way]
        if len(pts) >= 2:
            pygame.draw.aalines(surf, (200, 200, 200, 255), False, pts)
    # roads in medium grey
    for way in (_roads or []):
        pts = [_proj(lat, lon) for lat, lon in way]
        if len(pts) >= 2:
            pygame.draw.aalines(surf, (160, 160, 160, 255), False, pts)

    _surface        = surf
    _scaled_surface = None  # invalidate zoom cache
    _baked          = True
    print("[map] surface baked")


def _fetch() -> None:
    global _roads, _water, _fetching
    try:
        if os.path.exists(_CACHE):
            try:
                with open(_CACHE) as f:
                    d = json.load(f)
                if isinstance(d, dict) and "roads" in d and "water" in d:
                    _roads = d["roads"]
                    _water = d["water"]
                    print(f"[map] {len(_roads)} roads + {len(_water)} water from cache")
                    return
            except Exception as e:
                print(f"[map] cache invalid ({e}), re-fetching")
                os.remove(_CACHE)

        b = f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}"
        query = (
            f"[out:json][timeout:25];"
            f"("
            f"  way[\"highway\"~\"motorway|trunk|primary|secondary\"]({b});"
            f"  way[\"natural\"=\"water\"]({b});"
            f"  way[\"waterway\"~\"river|canal\"]({b});"
            f");"
            f"out geom;"
        )
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent":   "AirQualityInk/1.0",
            },
            timeout=30,
        )
        r.raise_for_status()

        roads, water = [], []
        for el in r.json().get("elements", []):
            if el.get("type") != "way" or "geometry" not in el:
                continue
            pts = [(n["lat"], n["lon"]) for n in el["geometry"]]
            if len(pts) < 2:
                continue
            tags = el.get("tags", {})
            if "natural" in tags or "waterway" in tags:
                water.append(pts)
            else:
                roads.append(pts)

        _roads, _water = roads, water
        with open(_CACHE, "w") as f:
            json.dump({"roads": roads, "water": water}, f)
        print(f"[map] fetched {len(roads)} roads + {len(water)} water")
    except Exception as e:
        print(f"[map] fetch failed: {e}")
    finally:
        _fetching = False


def start_fetch() -> None:
    global _fetching
    if _fetching or _roads is not None:
        return
    _fetching = True
    threading.Thread(target=_fetch, daemon=True).start()


def draw(screen, x0: int, y0: int, w: int, h: int,
         station_lat: float | None = None,
         station_lon: float | None = None,
         color: tuple = (0, 0, 0)) -> None:
    """
    Draw the vector map. No background, no border.
    Bakes roads on first call after data loads (main-thread safe).
    """
    import pygame
    import pygame.gfxdraw

    global _baked, _scaled_surface, _last_scale
    if _roads is not None and not _baked:
        _bake()

    if not _baked:
        font = pygame.font.Font(None, 18)
        s = font.render("carte…", True, color)
        screen.blit(s, (x0 + w // 2 - s.get_width() // 2,
                        y0 + h // 2 - s.get_height() // 2))
        return

    # Project both points in reference frame (no offset)
    wx_ref, wy_ref = _proj(WEATHER_LAT, WEATHER_LON)
    if station_lat is not None and station_lon is not None:
        sx_ref, sy_ref = _proj(station_lat, station_lon)
    else:
        sx_ref, sy_ref = wx_ref, wy_ref

    # Auto-zoom: scale down so both points fit with padding (12px = enough to clear the dot circles)
    pad_px  = 12
    span_x  = abs(sx_ref - wx_ref)
    span_y  = abs(sy_ref - wy_ref)
    avail_x = max(1, w - 2 * pad_px)
    avail_y = max(1, h - 2 * pad_px)
    scale   = min(1.0,
                  avail_x / max(span_x, 1) if span_x > avail_x else 1.0,
                  avail_y / max(span_y, 1) if span_y > avail_y else 1.0)

    # Center of the two points in reference frame
    cx_ref = (wx_ref + sx_ref) / 2
    cy_ref = (wy_ref + sy_ref) / 2

    prev_clip = screen.get_clip()
    screen.set_clip((x0, y0, w, h))

    if scale >= 1.0:
        ox = int(x0 + w / 2 - cx_ref)
        oy = int(y0 + h / 2 - cy_ref)
        screen.blit(_surface, (ox, oy))
    else:
        # Rebuild scaled surface only when scale changes (one per station switch)
        if _scaled_surface is None or abs(_last_scale - scale) > 0.01:
            sw = max(1, int(_REF_W * scale))
            sh = max(1, int(_REF_H * scale))
            _scaled_surface = pygame.transform.scale(_surface, (sw, sh))
            _last_scale     = scale
        ox = int(x0 + w / 2 - cx_ref * scale)
        oy = int(y0 + h / 2 - cy_ref * scale)
        screen.blit(_scaled_surface, (ox, oy))

    # Helper: reference-frame px → screen px
    def ts(px, py):
        return int(px * scale + ox if scale < 1.0 else px + ox), \
               int(py * scale + oy if scale < 1.0 else py + oy)

    # Weather point ⊙ — hollow ring + center dot
    wx, wy = ts(wx_ref, wy_ref)
    pygame.gfxdraw.aacircle(screen, wx, wy, 6, color)
    pygame.gfxdraw.filled_circle(screen, wx, wy, 2, color)
    pygame.gfxdraw.aacircle(screen, wx, wy, 2, color)

    # AQ station — filled circle + outer ring
    if station_lat is not None and station_lon is not None:
        sxs, sys_ = ts(sx_ref, sy_ref)
        pygame.gfxdraw.filled_circle(screen, sxs, sys_, 5, color)
        pygame.gfxdraw.aacircle(screen,      sxs, sys_, 5, color)
        pygame.gfxdraw.aacircle(screen,      sxs, sys_, 7, color)

    screen.set_clip(prev_clip)
