#!/usr/bin/env python3
from __future__ import annotations
"""
Fullscreen pygame display for the air quality monitor.

Two modes toggled by any key/click:
  COLOR — entire screen filled with the AQI color
  STATS — same background + pollutant details overlay
"""
import os
import math
import pygame
from datetime import datetime
from aqi import label_pollutant, who_ratio, worst_pollutant, score_pollutant
import map_tile

_FONT_DIR            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Monofett")
_MONOFETT            = os.path.join(_FONT_DIR, "Monofett-Regular.ttf")
_WEATHER_ICONS_TTF   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weather-icons.ttf")

POLLUTANT_ORDER = ["PM2.5", "PM10", "NO2", "O3", "SO2", "CO"]

# Weather icon codepoints shown on loading screen (day variants, diverse set)
_LOADING_ICONS = [chr(c) for c in (
    0xf00d, 0xf00c, 0xf002, 0xf013, 0xf003,
    0xf009, 0xf008, 0xf0b2, 0xf00a, 0xf015,
    0xf010, 0xf02e, 0xf081, 0xf028, 0xf038,
)]

_MOIS = ["jan", "fév", "mar", "avr", "mai", "juin",
         "jul", "aoû", "sep", "oct", "nov", "déc"]

def _fmt_date(dt) -> str:
    return f"{dt.day} {_MOIS[dt.month - 1]}  {dt.strftime('%H:%M')}"


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
        self._prev_score = None
        self._history = []
        self.bg_color = (0, 200, 0)
        self.last_updated = None
        self.loading = True
        self.station_delta = 0
        self._loading_frame = 0
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
        self.font_pol    = f(max(19, self.h // 21))
        self.font_medium = f(max(20, self.h // 20))
        self.font_small  = f(max(14, self.h // 30))
        self.font_stats  = f(max(17, self.h // 26))

        # Monofett — used only for the quality label (main screen)
        try:
            self.font_display = pygame.font.Font(_MONOFETT, max(48, self.h // 6))
        except (FileNotFoundError, pygame.error):
            self.font_display = self.font_huge

        sym_size = max(40, self.h // 10)
        sym_size_med = max(30, self.h // 14)
        try:
            self.font_weather_symbol     = pygame.font.Font(_WEATHER_ICONS_TTF, sym_size)
            self.font_weather_symbol_med = pygame.font.Font(_WEATHER_ICONS_TTF, sym_size_med)
            self._weather_icons_loaded   = True
        except (FileNotFoundError, pygame.error):
            _fb = pygame.font.SysFont(chosen, sym_size, bold=False) if chosen else pygame.font.Font(None, sym_size)
            self.font_weather_symbol     = _fb
            self.font_weather_symbol_med = pygame.font.SysFont(chosen, sym_size_med, bold=False) if chosen else pygame.font.Font(None, sym_size_med)
            self._weather_icons_loaded   = False

        if chosen:
            self.font_small_italic = pygame.font.SysFont(chosen, max(14, self.h // 30), bold=False, italic=True)
        else:
            self.font_small_italic = pygame.font.Font(None, max(14, self.h // 30))

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
        self._prev_score = self.score if self.score > 0.0 else None
        self.score = worst_score or 0.0
        _, color = label_pollutant(pol, val) if pol else (None, (0, 210, 0))
        self.bg_color = color
        self._history.append((self.score, self.bg_color))
        if len(self._history) > 48:
            self._history.pop(0)

    def load_history(self, entries: list):
        self._history = entries[-48:]

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
        s_pol = self.font_pol.render(pol, True, tc)
        s_val = self.font_large.render(disp_val, True, tc)
        gap = max(8, self.w // 80)
        total_w = s_pol.get_width() + gap + s_val.get_width()
        x0 = (self.w - total_w) // 2
        y_val = self.h // 2 + self.h // 16 - s_val.get_height() // 2
        self.screen.blit(s_pol, (x0, y_val + s_val.get_height() - s_pol.get_height()))
        self.screen.blit(s_val, (x0 + s_pol.get_width() + gap, y_val))

        if ratio:
            self._draw_centered(ratio, self.font_medium, tc, offset_y=self.h // 5)

        pad = max(64, int(self.w * 0.07))

        # Station color bar — top of screen, one rectangle per station
        self._draw_station_bar()

        # Weather — top-left below the station bar
        if self.weather_data:
            wd        = self.weather_data
            top_y     = self._bar_h + max(16, int(self.h * 0.03))
            sym_char  = wd["symbol"] if self._weather_icons_loaded else wd.get("fallback", "?")
            sym       = self.font_weather_symbol.render(sym_char, True, tc)
            temp   = self.font_medium.render(f"{wd['temperature']:.0f}°C", True, tc)
            tx     = pad + sym.get_width() + 8
            rain_h = _rain_hours(self.weather_data)
            rain   = None
            if rain_h is not None and rain_h < 2.0:
                rain = self.font_small.render(_format_rain(rain_h), True, tc)
            rain_gap     = max(8, int(self.h * 0.018))
            text_block_h = temp.get_height() + (rain_gap + rain.get_height() if rain else 0)
            block_h      = max(sym.get_height(), text_block_h)
            sym_y        = top_y + (block_h - sym.get_height()) // 2
            ty           = top_y + (block_h - text_block_h) // 2
            self.screen.blit(sym,  (pad, sym_y))
            self.screen.blit(temp, (tx, ty))
            if rain:
                self.screen.blit(rain, (tx, ty + temp.get_height() + rain_gap))

        # Analog clock — top-right, same height as weather block
        clock_r = max(20, self.h // 22)
        clock_top_y = self._bar_h + max(16, int(self.h * 0.03))
        self._draw_analog_clock(self.w - pad - clock_r, clock_top_y + clock_r, clock_r, tc)

        age  = self._data_age()
        info = f"{self.data['station']}  ·  {age}"
        surf = self.font_small.render(info, True, tc)
        self.screen.blit(surf, (self.w - surf.get_width() - pad, self.h - surf.get_height() - 48))

        if self._prev_score is not None:
            diff = self.score - self._prev_score
            arrow = "↗" if diff > 0.05 else "↘" if diff < -0.05 else "→"
            a_surf = self.font_large.render(arrow, True, tc)
            self.screen.blit(a_surf, (pad, self.h - a_surf.get_height() - 48))

    def _draw_analog_clock(self, cx, cy, r, color):
        import pygame.gfxdraw
        now = datetime.now()
        # Outer ring — two AA circles to simulate stroke width 2
        pygame.gfxdraw.aacircle(self.screen, cx, cy, r,     color)
        pygame.gfxdraw.aacircle(self.screen, cx, cy, r - 1, color)
        # Tick marks at 12 / 3 / 6 / 9
        for angle_deg in (0, 90, 180, 270):
            a = math.radians(angle_deg - 90)
            x0 = cx + int((r - 5) * math.cos(a))
            y0 = cy + int((r - 5) * math.sin(a))
            x1 = cx + int(r * math.cos(a))
            y1 = cy + int(r * math.sin(a))
            pygame.draw.aaline(self.screen, color, (x0, y0), (x1, y1))
        # Hour hand
        h_a = math.radians((now.hour % 12 + now.minute / 60) * 30 - 90)
        hx  = cx + int(r * 0.55 * math.cos(h_a))
        hy  = cy + int(r * 0.55 * math.sin(h_a))
        pygame.draw.aaline(self.screen, color, (cx, cy), (hx, hy))
        pygame.draw.aaline(self.screen, color, (cx, cy), (hx, hy))  # double pass = thicker
        # Minute hand
        m_a = math.radians(now.minute * 6 - 90)
        mx  = cx + int(r * 0.82 * math.cos(m_a))
        my  = cy + int(r * 0.82 * math.sin(m_a))
        pygame.draw.aaline(self.screen, color, (cx, cy), (mx, my))
        # Center dot
        pygame.gfxdraw.aacircle(self.screen, cx, cy, 3, color)
        pygame.gfxdraw.filled_circle(self.screen, cx, cy, 3, color)

    # ── Stats mode ────────────────────────────────────────────────────────────

    def _draw_stats(self):
        self.screen.blit(self._overlay, (0, 0))

        tc  = (0, 0, 0)
        pad = max(64, int(self.w * 0.07))
        right = self.w - pad
        y   = max(20, int(self.h * 0.04))

        # Row 1 — station name (left) + digital clock (right)
        station_surf = self.font_large.render(self.data["station"], True, tc)
        clock_surf   = self.font_large.render(datetime.now().strftime("%H:%M"), True, tc)
        row1_h = max(station_surf.get_height(), clock_surf.get_height())
        self.screen.blit(station_surf, (pad, y + (row1_h - station_surf.get_height()) // 2))
        self.screen.blit(clock_surf,   (right - clock_surf.get_width(),
                                        y + (row1_h - clock_surf.get_height()) // 2))
        y += row1_h + 2

        # Row 2 — big weather icon | temp + italic date | rain message
        if self.weather_data:
            wd       = self.weather_data
            sym_char = wd["symbol"] if self._weather_icons_loaded else wd.get("fallback", "?")
            w_sym    = self.font_weather_symbol_med.render(sym_char, True, tc)
            w_temp   = self.font_medium.render(f"{wd['temperature']:.0f}°C", True, tc)
            w_date   = self.font_small_italic.render(_fmt_date(self.data["timestamp"]), True, tc)

            rain_h = _rain_hours(self.weather_data)
            if rain_h is None:
                rain_lines = ["Pas de pluie prévue", "Belle Journée à Montréal"]
            else:
                rain_lines = [_format_rain(rain_h)]
            rain_surfs   = [self.font_small.render(l, True, tc) for l in rain_lines]
            rain_total_h = sum(s.get_height() for s in rain_surfs) + 2 * max(0, len(rain_surfs) - 1)

            text_block_h = w_temp.get_height() + 4 + w_date.get_height()
            row2_h = max(w_sym.get_height(), text_block_h, rain_total_h)

            # icon
            self.screen.blit(w_sym, (pad, y + (row2_h - w_sym.get_height()) // 2))
            # temp stacked above italic date
            tx = pad + w_sym.get_width() + 10
            ty = y + (row2_h - text_block_h) // 2
            self.screen.blit(w_temp, (tx, ty))
            self.screen.blit(w_date, (tx, ty + w_temp.get_height() + 4))
            # rain lines right-aligned
            ry = y + (row2_h - rain_total_h) // 2
            for rs in rain_surfs:
                self.screen.blit(rs, (right - rs.get_width(), ry))
                ry += rs.get_height() + 2

            y += row2_h + int(self.h * 0.015)
        else:
            # no weather — just show data timestamp
            w_date = self.font_small_italic.render(_fmt_date(self.data["timestamp"]), True, tc)
            self.screen.blit(w_date, (pad, y))
            y += w_date.get_height() + int(self.h * 0.015)

        # Separator
        pygame.draw.line(self.screen, tc, (pad, y), (self.w - pad, y), 1)
        y += int(self.h * 0.015)

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

        self._draw_history_chart(y)
        self._draw_map(y)

    def _draw_history_chart(self, content_bottom: int = 0):
        n = len(self._history)
        if n < 2:
            return
        pad      = max(64, int(self.w * 0.07))
        map_w    = min(150, int(self.w * 0.18))
        margin_b = max(36, int(self.h * 0.075))
        bottom   = self.h - margin_b
        gap      = max(8, int(self.h * 0.02))
        chart_h  = min(50, max(20, bottom - content_bottom - gap))
        # chart_w fills the space between left margin and the map, minus a gap
        chart_w  = self.w - 2 * pad - map_w - gap
        x0 = pad
        y0 = bottom - chart_h
        bar_w = max(1, chart_w // n)
        for i, (score, color) in enumerate(self._history):
            bh = max(2, int(score * chart_h))
            pygame.draw.rect(self.screen, color,
                             (x0 + i * bar_w, y0 + chart_h - bh, max(1, bar_w - 1), bh))

    def _draw_map(self, content_bottom: int = 0):
        pad      = max(64, int(self.w * 0.07))
        map_w    = min(150, int(self.w * 0.18))
        margin_b = max(36, int(self.h * 0.075))
        bottom   = self.h - margin_b
        gap      = max(8, int(self.h * 0.02))
        map_h    = min(80, max(30, bottom - content_bottom - gap))
        x0 = self.w - pad - map_w
        y0 = bottom - map_h
        s_lat = self.data["lat"] if self.data and "lat" in self.data else None
        s_lon = self.data["lon"] if self.data and "lon" in self.data else None
        map_tile.draw(self.screen, x0, y0, map_w, map_h, s_lat, s_lon, color=(0, 0, 0))

    def _draw_pollutant_row(self, pol, val, col_bar, bar_max, y, row_h, tc):
        score        = score_pollutant(pol, val)
        label, bar_color = label_pollutant(pol, val)
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
        self._loading_frame += 1

        if self._weather_icons_loaded:
            icon_h  = self.font_weather_symbol.get_height()
            gap     = max(24, self.w // 18)
            step    = icon_h + gap
            total_w = len(_LOADING_ICONS) * step
            offset  = (self._loading_frame * 2) % total_w
            iy      = self.h // 2 - icon_h // 2

            # Fill screen width with scrolling icons (wrap around)
            slots = self.w // step + 2
            for i in range(slots + 1):
                ch   = _LOADING_ICONS[(i + offset // step) % len(_LOADING_ICONS)]
                x    = i * step - (offset % step)
                surf = self.font_weather_symbol.render(ch, True, tc)
                self.screen.blit(surf, (int(x), iy))

            s = self.font_small.render("Chargement…", True, tc)
            self.screen.blit(s, (self.w // 2 - s.get_width() // 2,
                                 iy + icon_h + max(12, int(self.h * 0.025))))
        else:
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
