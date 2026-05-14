#!/usr/bin/env python3
from __future__ import annotations
"""
Fullscreen pygame display for the air quality monitor.

Two modes toggled by any key/click:
  COLOR — entire screen filled with the AQI color
  STATS — same background + pollutant details overlay
"""
import os
import pygame
from datetime import datetime
from aqi import label_pollutant, who_ratio, worst_pollutant, score_pollutant, LEVEL_COLORS

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Monofett")
_MONOFETT  = os.path.join(_FONT_DIR, "Monofett-Regular.ttf")

POLLUTANT_ORDER = ["PM2.5", "PM10", "NO2", "O3", "SO2", "CO"]


def _contrasting_text_color(bg: tuple) -> tuple:
    luminance = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def _format_rain(rain_h: float | None) -> str:
    if rain_h is None:
        return "Pas de pluie prévue"
    if rain_h <= 0:
        return "Pluie en cours"
    h, m = divmod(int(rain_h * 60), 60)
    if h == 0:
        return f"Pluie dans {m} min"
    return f"Pluie dans {h}h{m:02d}" if m else f"Pluie dans {h}h"


def _rain_hours(weather_data: dict | None) -> float | None:
    """Compute remaining hours to rain from stored absolute datetime."""
    if not weather_data:
        return None
    rain_at = weather_data.get("rain_at")
    if rain_at is None:
        return None
    return (rain_at - datetime.now()).total_seconds() / 3600


class AQIDisplay:
    def __init__(self, fullscreen: bool = True):
        pygame.init()
        pygame.display.set_caption("Air Quality")
        pygame.mouse.set_visible(False)

        if fullscreen:
            info = pygame.display.Info()
            self.w, self.h = info.current_w, info.current_h
            self.screen = pygame.display.set_mode((self.w, self.h), pygame.FULLSCREEN)
        else:
            self.w, self.h = 800, 480
            self.screen = pygame.display.set_mode((self.w, self.h), pygame.RESIZABLE)

        self._load_fonts()
        self.stats_visible = False
        self.data = None
        self.weather_data = None
        self._station_bar = []   # list of rgb tuples, one per station in STATION_KEYS order
        self.current_station_idx = 0
        self.score = 0.0
        self.bg_color = (0, 200, 0)
        self.last_updated = None
        self.loading = True
        self.station_delta = 0
        self._overlay = self._make_overlay()

    def _make_overlay(self):
        s = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        s.fill((255, 255, 255, 210))
        return s

    def _load_fonts(self):
        candidates = [
            "arialunicode",   # macOS — wide Unicode, renders weather symbols
            "dejavusans",     # Pi/Linux — wide Unicode, renders weather symbols
            "liberationsans", "freesans",
            "helvetica", "arial", "verdana", "ubuntu",
        ]
        chosen = None
        for name in candidates:
            if name in pygame.font.get_fonts():
                chosen = name
                break

        def f(size):
            if chosen:
                return pygame.font.SysFont(chosen, size, bold=False)
            return pygame.font.Font(None, size)

        self.font_huge   = f(max(48, self.h // 6))
        self.font_large  = f(max(28, self.h // 14))
        self.font_medium = f(max(20, self.h // 20))
        self.font_small  = f(max(14, self.h // 30))
        self.font_stats  = f(max(17, self.h // 26))  # slightly bigger than font_small, for stats rows

        # Monofett — used only for the quality label (main screen)
        try:
            self.font_display = pygame.font.Font(_MONOFETT, max(48, self.h // 6))
        except (FileNotFoundError, pygame.error):
            self.font_display = self.font_huge

        # Weather symbol — 2x font_medium, bold, same font family for Unicode coverage
        sym_size = max(40, self.h // 10)
        self.font_weather_symbol = pygame.font.SysFont(chosen, sym_size, bold=True) if chosen else pygame.font.Font(None, sym_size)

        # Station bar height = same as weather text block (symbol size excluded)
        self._bar_h = self.font_medium.get_height() + self.font_small.get_height() + 12

    def update(self, data: dict | None):
        """Receive new AQI data from fetch thread."""
        self.loading = False
        if data is None:
            return
        self.data = data
        self.last_updated = datetime.now()
        pol, val, worst_score = worst_pollutant(data["pollutants"])
        self.score = worst_score or 0.0
        _, color = label_pollutant(pol, val) if pol else (None, (0, 210, 0))
        self.bg_color = color

    def update_station_bar(self, all_data: dict, station_keys: list):
        """Compute station bar colors from all_data. Keeps last known color on failure."""
        if not self._station_bar:
            self._station_bar = [(80, 80, 80)] * len(station_keys)
        for i, key in enumerate(station_keys):
            data = all_data.get(key)
            if not data:
                continue
            pol, val, _ = worst_pollutant(data["pollutants"])
            _, color = label_pollutant(pol, val) if pol else (None, (80, 80, 80))
            self._station_bar[i] = color

    def update_weather(self, weather: dict | None):
        """Receive new weather data from weather thread."""
        if weather is not None:
            self.weather_data = weather

    def handle_event(self, event) -> bool:
        if event.type == pygame.QUIT:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False
            elif event.key == pygame.K_RIGHT:
                self.station_delta = 1
            elif event.key == pygame.K_LEFT:
                self.station_delta = -1
            else:
                self.stats_visible = not self.stats_visible
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.stats_visible = not self.stats_visible
        if event.type == pygame.VIDEORESIZE:
            self.w, self.h = event.w, event.h
            self.screen = pygame.display.set_mode((self.w, self.h), pygame.RESIZABLE)
            self._load_fonts()
            self._overlay = self._make_overlay()
        return True

    def render(self):
        self.screen.fill(self.bg_color)
        if self.loading:
            self._draw_loading()
        elif self.stats_visible and self.data:
            self._draw_stats()
        else:
            self._draw_color_mode()
        pygame.display.flip()

    # ── Color mode ────────────────────────────────────────────────────────────

    def _draw_color_mode(self):
        tc = _contrasting_text_color(self.bg_color)

        if self.data is None:
            self._draw_centered("Pas de données", self.font_large, tc)
            return

        pol, val, _ = worst_pollutant(self.data["pollutants"])
        label, _    = label_pollutant(pol, val)
        ratio       = who_ratio(pol, val)

        self._draw_centered(label, self.font_display, tc, offset_y=-self.h // 8)

        disp_val = f"{val/1000:.1f} mg/m³" if pol == "CO" else f"{val:.0f} µg/m³"
        self._draw_centered(f"{pol}  {disp_val}", self.font_large, tc, offset_y=self.h // 16)

        if ratio:
            self._draw_centered(ratio, self.font_medium, tc, offset_y=self.h // 5)

        dim = tuple(int(tc[i] * 0.6 + self.bg_color[i] * 0.4) for i in range(3))
        pad = max(64, int(self.w * 0.07))

        # Station color bar — top of screen, one rectangle per station
        self._draw_station_bar()

        # Weather — top-left below the station bar
        if self.weather_data:
            wd     = self.weather_data
            top_y  = self._bar_h + max(16, int(self.h * 0.03))
            sym    = self.font_weather_symbol.render(wd["symbol"], True, dim)
            self.screen.blit(sym, (pad, top_y))
            tx     = pad + sym.get_width() + 8
            ty     = top_y + (sym.get_height() - self.font_medium.get_height()) // 2
            temp   = self.font_medium.render(f"{wd['temperature']:.0f}°C", True, dim)
            self.screen.blit(temp, (tx, ty))
            rain_h = _rain_hours(self.weather_data)
            if rain_h is not None and rain_h < 2.0:
                rain = self.font_small.render(_format_rain(rain_h), True, dim)
                self.screen.blit(rain, (tx, ty + temp.get_height() + 4))

        # Bottom hints
        age  = self._data_age()
        info = f"{self.data['station']}  ·  {age}"
        surf = self.font_small.render(info, True, dim)
        self.screen.blit(surf, (self.w - surf.get_width() - pad, self.h - surf.get_height() - 48))

        s2 = self.font_small.render("appuyer pour les détails", True, dim)
        self.screen.blit(s2, (pad, self.h - s2.get_height() - 48))

    # ── Stats mode ────────────────────────────────────────────────────────────

    def _draw_stats(self):
        self.screen.blit(self._overlay, (0, 0))

        tc  = (0, 0, 0)
        pad = max(64, int(self.w * 0.07))
        right = self.w - pad
        y   = max(48, int(self.h * 0.07))

        # Row 1 — station name (left) + weather symbol + temp (right), all on same center line
        station_surf = self.font_large.render(self.data["station"], True, tc)
        w_sym = w_temp = None
        if self.weather_data:
            wd    = self.weather_data
            w_sym = self.font_weather_symbol.render(wd["symbol"], True, tc)
            w_temp = self.font_medium.render(f"  {wd['temperature']:.0f}°C", True, tc)
        row1_h = max(station_surf.get_height(),
                     w_sym.get_height() if w_sym else 0)
        self.screen.blit(station_surf,
                         (pad, y + (row1_h - station_surf.get_height()) // 2))
        if w_sym:
            total_w = w_sym.get_width() + w_temp.get_width()
            sx = right - total_w
            self.screen.blit(w_sym,  (sx, y + (row1_h - w_sym.get_height()) // 2))
            self.screen.blit(w_temp, (sx + w_sym.get_width(),
                                      y + (row1_h - w_temp.get_height()) // 2))
        y += row1_h + 4

        # Row 2 — timestamp (left) + rain forecast (right), both font_small same baseline
        ts  = self.data["timestamp"].strftime("%d %b  %H:%M")
        age = self._data_age()
        sub = self.font_small.render(f"{ts}  ({age})", True, tc)
        self.screen.blit(sub, (pad, y))
        if self.weather_data:
            rain_h = _rain_hours(self.weather_data)
            rs = self.font_small.render(_format_rain(rain_h), True, tc)
            self.screen.blit(rs, (right - rs.get_width(), y))
        y += sub.get_height() + int(self.h * 0.04)

        # Separator
        pygame.draw.line(self.screen, tc, (pad, y), (self.w - pad, y), 1)
        y += int(self.h * 0.03)

        # Bar spans full width between equal left/right margins
        col_bar = pad
        bar_max = right - pad
        row_h   = int(self.h * 0.085)

        for pol in POLLUTANT_ORDER:
            val = self.data["pollutants"].get(pol)
            if val is None:
                continue
            self._draw_pollutant_row(pol, val, col_bar, bar_max, y, row_h, tc)
            y += row_h + int(self.h * 0.012)
            if y > self.h * 0.92:
                break

        hint = self.font_small.render("appuyer pour fermer", True, tc)
        self.screen.blit(hint, (pad, self.h - hint.get_height() - 48))

    def _draw_pollutant_row(self, pol, val, col_bar, bar_max, y, row_h, tc):
        score        = score_pollutant(pol, val)
        label, _     = label_pollutant(pol, val)
        _, bar_color = label_pollutant(pol, val)
        bar_w        = int(bar_max * score)

        fh       = self.font_stats.get_height()
        gap_line = max(3, int(self.h * 0.007))
        bar_h    = max(10, row_h - fh - gap_line)
        bar_y    = y + fh + gap_line

        # Line 1 — name+value (left) and label (right), same baseline
        disp_val   = f"{val/1000:.1f} mg/m³" if pol == "CO" else f"{val:.0f} µg/m³"
        surf_left  = self.font_stats.render(f"{pol}  {disp_val}", True, tc)
        surf_right = self.font_stats.render(label, True, tc)
        self.screen.blit(surf_left,  (col_bar, y))
        self.screen.blit(surf_right, (col_bar + bar_max - surf_right.get_width(), y))

        # Line 2 — bar spanning full block width (equal margins on both sides)
        pygame.draw.rect(self.screen, (220, 220, 220), (col_bar, bar_y, bar_max, bar_h))
        if bar_w > 2:
            pygame.draw.rect(self.screen, bar_color,
                             (col_bar + 1, bar_y + 1, bar_w - 2, bar_h - 2))
        pygame.draw.rect(self.screen, tc, (col_bar, bar_y, bar_max, bar_h), 1)

    # ── Station bar ───────────────────────────────────────────────────────────

    def _draw_station_bar(self):
        if not self._station_bar:
            return
        n    = len(self._station_bar)
        rect_w = self.w // n
        rect_h = self._bar_h
        idx  = self.current_station_idx
        for i in range(n):
            color = self._station_bar[(idx + i) % n]
            x = i * rect_w
            w = (self.w - x) if i == n - 1 else rect_w
            pygame.draw.rect(self.screen, color, (x, 0, w, rect_h))

    # ── Loading screen ────────────────────────────────────────────────────────

    def _draw_loading(self):
        tc = _contrasting_text_color(self.bg_color)
        self._draw_centered("Chargement…", self.font_large, tc)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _draw_centered(self, text, font, color, offset_y=0):
        surf = font.render(text, True, color)
        x = (self.w - surf.get_width()) // 2
        y = (self.h - surf.get_height()) // 2 + offset_y
        self.screen.blit(surf, (x, y))

    def _data_age(self) -> str:
        if not self.data:
            return "?"
        delta = datetime.now() - self.data["timestamp"]
        mins = int(delta.total_seconds() / 60)
        if mins < 60:
            return f"il y a {mins} min"
        return f"il y a {mins // 60}h{mins % 60:02d}"

    def quit(self):
        pygame.quit()
