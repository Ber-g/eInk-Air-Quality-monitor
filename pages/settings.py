#!/usr/bin/env python3
from __future__ import annotations
import pygame
from pages.base import BasePage

_DIM = (160, 160, 160)


class SettingsPage(BasePage):

    def render(self, screen, w: int, h: int, bar_h: int, fonts: dict) -> None:
        font   = fonts["large"]
        font_s = fonts["small"]
        t = font.render("Paramètres — à venir", True, _DIM)
        screen.blit(t, ((w - t.get_width()) // 2,
                        bar_h + (h - bar_h - t.get_height()) // 2))
        hint = font_s.render("[Esc] Retour", True, _DIM)
        screen.blit(hint, ((w - hint.get_width()) // 2,
                            h - hint.get_height() - 12))
