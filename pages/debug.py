#!/usr/bin/env python3
from __future__ import annotations
import pygame
from datetime import datetime, timedelta
from pages.base import BasePage, NavAction
import log_buffer
import history

_BG     = (  0,   0,   0)
_TEXT   = (255, 255, 255)
_DIM    = (160, 160, 160)
_ACCENT = (255, 255,   0)
_WARN   = (255,  80,  80)

_GAP = 12   # gap between cards


class DebugPage(BasePage):

    def on_enter(self, context: dict) -> None:
        super().on_enter(context)
        self._confirm_reset = False

    def handle_event(self, event) -> NavAction:
        if event.type != pygame.KEYDOWN:
            return NavAction.NONE
        key = event.key

        if self._confirm_reset:
            if key in (pygame.K_o, pygame.K_y):
                disp = self._context.get("display")
                history.clear()
                if disp:
                    disp._history        = []
                    disp._last_history_ts = None
                    if disp.data:
                        disp._history.append((disp.score, disp.bg_color))
                        disp._last_history_ts = disp.data["timestamp"]
                self._confirm_reset = False
            elif key in (pygame.K_ESCAPE, pygame.K_n):
                self._confirm_reset = False
            return NavAction.NONE

        if key == pygame.K_ESCAPE:
            return NavAction.BACK
        if key == pygame.K_r:
            log_buffer.info("[debug] refetch demandé par l'utilisateur")
            return NavAction.REFETCH
        if key == pygame.K_q:
            log_buffer.info("[debug] redémarrage demandé par l'utilisateur")
            return NavAction.RESTART
        if key == pygame.K_h:
            self._confirm_reset = True
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
        hints = font_s.render("[R] Refetch   [H] Reset historique   [Esc] Retour", True, _DIM)
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

        # Confirmation overlay
        if self._confirm_reset:
            self._draw_confirm(screen, w, h, fonts)

    def _draw_confirm(self, screen, w: int, h: int, fonts: dict) -> None:
        font_m = fonts["medium"]
        font_s = fonts["small"]

        lines = [
            ("Réinitialiser l'historique ?", font_m, _WARN),
            ("Les données seront perdues pour toujours.", font_s, _TEXT),
            ("", None, None),
            ("[O] Confirmer          [Esc / N] Annuler", font_s, _DIM),
        ]

        line_surfs = [(font.render(txt, True, col) if font else None)
                      for txt, font, col in lines]
        gap   = 10
        total_h = sum((s.get_height() if s else gap) for s in line_surfs) + gap * (len(lines) - 1)
        box_w   = max((s.get_width() for s in line_surfs if s), default=200) + 64
        box_h   = total_h + 48
        bx      = (w - box_w) // 2
        by      = (h - box_h) // 2

        pygame.draw.rect(screen, _BG,   (bx, by, box_w, box_h))
        pygame.draw.rect(screen, _WARN, (bx, by, box_w, box_h), 2)

        cy = by + 24
        for surf in line_surfs:
            if surf is None:
                cy += gap
                continue
            screen.blit(surf, ((w - surf.get_width()) // 2, cy))
            cy += surf.get_height() + gap
