#!/usr/bin/env python3
from __future__ import annotations
"""
AQI scoring — WHO 2021 + EU thresholds (strictest of the two).

Design rule:
  label_pollutant()  → discrete level + color (source of truth for background color)
  score_pollutant()  → continuous 0.0–1.0 (used only for stats bar width)

These two are intentionally separate so the background color always matches
the displayed label, with no interpolation ambiguity.
"""

# One canonical color per level — shared by ALL pollutants.
LEVEL_COLORS = {
    "Excellent":    (  0, 210,   0),   # green
    "Bon":          (160, 230,   0),   # yellow-green
    "Modéré":       (255, 210,   0),   # yellow
    "Mauvais":      (255, 110,   0),   # orange
    "Très mauvais": (210,   0,   0),   # red
    "Dangereux":    ( 90,   0, 110),   # purple
}

# Breakpoints: list of (max_value µg/m³, level_label)
# WHO AQG 2021 + EU Directive 2008/50/EC — strictest value used.
THRESHOLDS = {
    "PM2.5": [
        (5,            "Excellent"),
        (10,           "Bon"),
        (15,           "Modéré"),
        (25,           "Mauvais"),
        (50,           "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
    "PM10": [
        (15,           "Excellent"),
        (30,           "Bon"),
        (45,           "Modéré"),
        (75,           "Mauvais"),
        (150,          "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
    "NO2": [
        (10,           "Excellent"),
        (25,           "Bon"),
        (50,           "Modéré"),
        (100,          "Mauvais"),
        (200,          "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
    "O3": [
        (50,           "Excellent"),
        (100,          "Bon"),
        (120,          "Modéré"),
        (160,          "Mauvais"),
        (240,          "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
    "SO2": [
        (20,           "Excellent"),
        (40,           "Bon"),
        (125,          "Modéré"),
        (200,          "Mauvais"),
        (350,          "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
    "CO": [
        (1000,         "Excellent"),
        (2000,         "Bon"),
        (4000,         "Modéré"),
        (10000,        "Mauvais"),
        (20000,        "Très mauvais"),
        (float("inf"), "Dangereux"),
    ],
}

# Health-impact weights (used only for worst-pollutant selection).
WEIGHTS = {
    "PM2.5": 0.35,
    "PM10":  0.20,
    "NO2":   0.20,
    "O3":    0.15,
    "SO2":   0.05,
    "CO":    0.05,
}

# WHO 2021 reference values (µg/m³) for the "Nx OMS" ratio display.
WHO_REFERENCE = {
    "PM2.5": 5,
    "PM10":  15,
    "NO2":   10,
    "O3":    60,
    "SO2":   40,
    "CO":    4000,
}


def label_pollutant(pollutant: str, value: float) -> tuple[str, tuple]:
    """
    Returns (label, rgb_color) for a value.
    Color comes from LEVEL_COLORS — always consistent with the label.
    """
    if value is None:
        return "N/A", (150, 150, 150)
    for max_val, level in THRESHOLDS.get(pollutant, []):
        if value <= max_val:
            return level, LEVEL_COLORS[level]
    return "Dangereux", LEVEL_COLORS["Dangereux"]


def score_pollutant(pollutant: str, value: float) -> float:
    """
    Returns 0.0 (clean) → 1.0 (hazardous).
    Used for bar width in stats — NOT for background color.
    """
    if value is None:
        return 0.0
    breakpoints = THRESHOLDS.get(pollutant, [])
    n = len(breakpoints)
    prev_max = 0.0
    for i, (max_val, _) in enumerate(breakpoints):
        if value <= max_val:
            band_w   = (max_val - prev_max) if max_val != float("inf") else prev_max
            position = min(1.0, (value - prev_max) / band_w) if band_w > 0 else 0
            return (i + position) / n
        prev_max = max_val
    return 1.0


def worst_pollutant(pollutants: dict) -> tuple[str, float, float] | tuple[None, None, None]:
    """Returns (name, value, score) of the worst pollutant."""
    best = (None, None, -1.0)
    for pol in WEIGHTS:
        val = pollutants.get(pol)
        if val is not None:
            s = score_pollutant(pol, val)
            if s > best[2]:
                best = (pol, val, s)
    return best if best[0] else (None, None, None)


def who_ratio(pollutant: str, value: float) -> str | None:
    """Returns e.g. '2.0x OMS'. None if reference unknown."""
    ref = WHO_REFERENCE.get(pollutant)
    if ref is None or value is None:
        return None
    return f"{value / ref:.1f}x OMS"


if __name__ == "__main__":
    print("PM2.5 scale:")
    for v in [3, 5, 8, 10, 12, 15, 20, 30, 60]:
        label, color = label_pollutant("PM2.5", v)
        score = score_pollutant("PM2.5", v)
        print(f"  {v:5} µg/m³  score={score:.2f}  {label:15}  color={color}")
