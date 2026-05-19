#!/usr/bin/env python3
from __future__ import annotations
import pygame
from datetime import datetime, timedelta
from pages.base import BasePage, NavAction
import log_buffer

_TEXT   = (255, 255, 255)
_DIM    = (160, 160, 160)
_ACCENT = (255, 255,   0)

_GAP = 12   # gap between cards


class DebugPage(BasePage):

    def handle_event(self, event) -> NavAction:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return NavAction.BACK
            if event.key == pygame.K_r:
                log_buffer.info("[debug] refetch demandé par l'utilisateur")
                return NavAction.REFETCH
            if event.key == pygame.K_q:
                log_buffer.info("[debug] redémarrage demandé par l'utilisateur")
                return NavAction.RESTART
        return NavAction.NONE

    def render(self, screen, w: int, h: int, bar_h: int, fonts: dict) -> None:
        font_s = fonts["small"]
        font_m = fonts["medium"]
        pad = 64
        y   = bar_h + 12

        # Title
        t = font_s.render("ÉTAT DU SYSTÈME", True, _ACCENT)
        screen.blit(t, (pad, y))
        y += t.get_height() + 6

        # Next-fetch estimate
        disp = self._context.get("display")
        if disp and getattr(disp, "_bg_fetch_active", False):
            fetch_val = "en cours…"
        else:
            now = datetime.now()
            if now.minute < 50:
                next_fetch = now.replace(minute=50, second=0, microsecond=0)
            else:
                next_fetch = (now + timedelta(hours=1)).replace(minute=50, second=0, microsecond=0)
            fetch_val = next_fetch.strftime("%H:%M")

        cards = [
            ("STATION",      disp.data["station"] if disp and disp.data else "—"),
            ("DERNIÈRE MAJ", disp._data_age()     if disp and disp.data else "—"),
            ("FETCH",        fetch_val),
            ("SCORE AQI",    f"{disp.score:.2f}"  if disp else "—"),
        ]
        n       = len(cards)
        card_w  = (w - 2 * pad - (n - 1) * _GAP) // n
        card_h  = font_s.get_height() * 2 + 12
        for i, (label, value) in enumerate(cards):
            cx = pad + i * (card_w + _GAP)
            pygame.draw.rect(screen, _DIM, (cx, y, card_w, card_h), 1)
            lbl_s = font_s.render(label,       True, _DIM)
            val_s = font_s.render(value[:18],  True, _TEXT)
            screen.blit(lbl_s, (cx + 6, y + 4))
            screen.blit(val_s, (cx + 6, y + 4 + lbl_s.get_height() + 2))
        y += card_h + 10

        # Separator + log label
        pygame.draw.line(screen, _DIM, (pad, y), (w - pad, y), 1)
        y += 8
        lbl = font_s.render("JOURNAL", True, _ACCENT)
        screen.blit(lbl, (pad, y))
        y += lbl.get_height() + 4

        # Restart button — bottom-right, bordered rect
        btn_label = font_s.render("REDÉMARRER  [Q]", True, _TEXT)
        btn_w = btn_label.get_width() + 24
        btn_h = btn_label.get_height() + 14
        btn_x = w - pad - btn_w
        btn_y = h - btn_h - pad
        pygame.draw.rect(screen, _TEXT, (btn_x, btn_y, btn_w, btn_h), 1)
        screen.blit(btn_label, (btn_x + 12, btn_y + (btn_h - btn_label.get_height()) // 2))

        # Other hints — bottom-left, same baseline as button
        hints = font_s.render("[R] Refetch   [Esc] Retour", True, _DIM)
        hint_y = btn_y + (btn_h - hints.get_height()) // 2
        screen.blit(hints, (pad, hint_y))

        # Log lines — clip before button / hints area
        log_max = btn_y - 8
        for line in log_buffer.tail(12):
            s = font_s.render(line[:80], True, _DIM)
            if y + s.get_height() > log_max:
                break
            screen.blit(s, (pad, y))
            y += s.get_height() + 2
