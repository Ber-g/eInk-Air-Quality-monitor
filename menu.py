#!/usr/bin/env python3
from __future__ import annotations
"""
Retro Amiga/Minitel navigation system.

Adding a new page:
  1. Create pages/mypage.py subclassing BasePage
  2. Add a MenuItem to MENU_ITEMS below
  That's it — nothing else changes.
"""
from dataclasses import dataclass
from enum import Enum, auto
import pygame

from pages.base import BasePage, NavAction
from pages.debug    import DebugPage
from pages.settings import SettingsPage
from pages.art import ArtPage

# ── Visual constants ─────────────────────────────────────────────────────────
MENU_BG        = (  0,   0,   0)
MENU_TEXT      = (255, 255, 255)
MENU_CURSOR_BG = (255, 255, 255)
MENU_CURSOR_FG = (  0,   0,   0)
PAGE_BG        = (  0,   0,   0)
_PAD           = 64   # margin from screen edges to menu bar and page content


# ── Menu registry ─────────────────────────────────────────────────────────────
@dataclass
class MenuItem:
    label:      str
    page_class: type | None  # None = retour à l'écran principal (AQI)
    shortcut:   str   # cosmetic key hint (not wired to a keypress)


MENU_ITEMS: list[MenuItem] = [
    MenuItem("Qualité de l'air", None,         "Q"),  # Quitte le menu vers l'écran principal
    MenuItem("Musée",            ArtPage,      "M"),
    MenuItem("Debug",            DebugPage,    "D"),
    MenuItem("Paramètres",       SettingsPage, "P"),
]


# ── UI mode state machine ─────────────────────────────────────────────────────
class UIMode(Enum):
    NORMAL   = auto()   # main AQI screen — existing behaviour unchanged
    MENU_BAR = auto()   # menu bar shown, no page open
    PAGE     = auto()   # inside a page


# ── Controller ───────────────────────────────────────────────────────────────
class NavigationController:
    """
    Owns the menu bar + page lifecycle.
    Instantiated by AQIDisplay; lives for the lifetime of the app.
    """

    def __init__(self, fonts: dict, context: dict):
        self.fonts    = fonts
        self.context  = context
        self.mode     = UIMode.NORMAL
        self.selected = 0
        self._page_cache:  dict[str, BasePage] = {}
        self._active_page: BasePage | None     = None
        self._blink_frames = 0   # >0 = enter-animation running

    # ── Public ───────────────────────────────────────────────────────────────

    @property
    def bar_h(self) -> int:
        """Bottom edge of the menu bar — includes the 64px top margin."""
        return _PAD + self.fonts["medium"].get_height() + 8

    def open_menu(self) -> None:
        self.mode     = UIMode.MENU_BAR
        self.selected = 0

    def show_aqi(self) -> None:
        """Bascule directement vers l'écran principal Qualité de l'air."""
        if self._active_page:
            self._active_page.on_exit()
            self._active_page = None
        self.mode = UIMode.NORMAL

    def show_art(self) -> ArtPage:
        """Bascule directement vers le mode Musée (ArtPage)."""
        return self.show_page_by_label("Musée")

    def show_page_by_label(self, label: str) -> BasePage | None:
        """Bascule directement sur une page par son label."""
        for i, item in enumerate(MENU_ITEMS):
            if item.label.lower() == label.lower():
                self.selected = i
                if item.page_class is None:
                    self.show_aqi()
                    return None
                if self._active_page and self._active_page != self._get_page(item):
                    self._active_page.on_exit()
                page = self._get_page(item)
                page.on_enter(self.context)
                self._active_page = page
                self.mode = UIMode.PAGE
                return page
        return None

    def get_art_page(self) -> ArtPage | None:
        """Récupère l'instance de la page Musée (qu'elle soit active ou en cache)."""
        for item in MENU_ITEMS:
            if item.page_class == ArtPage:
                return self._get_page(item)
        return None

    @property
    def active_page(self) -> BasePage | None:
        """Page actuellement ouverte, ou None en mode NORMAL / MENU_BAR."""
        return self._active_page

    def get_active_page_name(self) -> str:
        if self.mode == UIMode.NORMAL:
            return "aqi"
        if self.mode == UIMode.MENU_BAR:
            return "menu_bar"
        if self._active_page:
            return self._active_page.__class__.__name__
        return "unknown"

    def tick(self) -> None:
        """Call every frame regardless of mode."""
        if self._blink_frames > 0:
            self._blink_frames -= 1
            if self._blink_frames == 0:
                self._enter_page()
        if self._active_page and self.mode == UIMode.PAGE:
            self._active_page.tick()

    def handle_event(self, event) -> NavAction:
        if event.type != pygame.KEYDOWN:
            return NavAction.NONE

        key = event.key

        if self.mode == UIMode.MENU_BAR:
            if key == pygame.K_ESCAPE:
                self.mode = UIMode.NORMAL
            elif key in (pygame.K_LEFT, pygame.K_UP):
                self.selected = (self.selected - 1) % len(MENU_ITEMS)
            elif key in (pygame.K_RIGHT, pygame.K_DOWN, pygame.K_TAB):
                self.selected = (self.selected + 1) % len(MENU_ITEMS)
            elif key == pygame.K_RETURN:
                self._blink_frames = 6   # ~200 ms double-blink at 30 fps
            return NavAction.NONE

        if self.mode == UIMode.PAGE and self._active_page:
            if key == pygame.K_TAB:
                self._active_page.on_exit()
                self._active_page = None
                self.selected = (self.selected + 1) % len(MENU_ITEMS)
                self._blink_frames = 6
                self.mode = UIMode.MENU_BAR
                return NavAction.NONE
            action = self._active_page.handle_event(event)
            if action == NavAction.BACK:
                self._active_page.on_exit()
                self._active_page = None
                self.mode = UIMode.MENU_BAR
                return NavAction.NONE
            return action

        return NavAction.NONE

    def render(self, screen, w: int, h: int) -> None:
        screen.fill(PAGE_BG)
        if self.mode == UIMode.PAGE and self._active_page:
            self._active_page.render(screen, w, h, self.bar_h, self.fonts)

        # La barre de menu est affichée en mode MENU_BAR ou sur les pages utilitaires (Debug, Paramètres).
        # Sur la page Musée (ArtPage), l'affichage est 100% plein écran sans barre parasite.
        show_menu = (self.mode == UIMode.MENU_BAR) or (
            self.mode == UIMode.PAGE and not isinstance(self._active_page, ArtPage)
        )

        if show_menu:
            self._draw_menu_bar(screen, w)

    # ── Private ──────────────────────────────────────────────────────────────

    def _get_page(self, item: MenuItem) -> BasePage:
        if item.page_class is None:
            raise ValueError("MenuItem without page_class cannot instantiate a page")
        if item.label not in self._page_cache:
            self._page_cache[item.label] = item.page_class()
        return self._page_cache[item.label]

    def _enter_page(self) -> None:
        item = MENU_ITEMS[self.selected]
        
        # Si aucun fichier/classe n'est associé, on sort du menu vers l'écran principal
        if item.page_class is None:
            if self._active_page:
                self._active_page.on_exit()
                self._active_page = None
            self.mode = UIMode.NORMAL
            return

        page = self._get_page(item)
        page.on_enter(self.context)
        self._active_page = page
        self.mode = UIMode.PAGE

    def _draw_menu_bar(self, screen, w: int) -> None:
        font     = self.fonts["medium"]
        bar_top  = _PAD
        bar_h    = self.fonts["medium"].get_height() + 8   # height of the bar strip only
        pygame.draw.rect(screen, MENU_BG, (0, bar_top, w, bar_h))

        x = _PAD
        for i, item in enumerate(MENU_ITEMS):
            is_sel   = (i == self.selected)
            inverted = is_sel and self._blink_frames > 0 and (self._blink_frames % 2 == 0)
            use_hl   = is_sel and not inverted

            label_surf = font.render(f" {item.label} ", True,
                                     MENU_CURSOR_FG if use_hl else MENU_TEXT)
            iw = label_surf.get_width()
            if use_hl:
                pygame.draw.rect(screen, MENU_CURSOR_BG, (x, bar_top + 2, iw, bar_h - 4))
            screen.blit(label_surf, (x, bar_top + (bar_h - label_surf.get_height()) // 2))
            x += iw + 4

        pygame.draw.line(screen, MENU_TEXT, (0, bar_top + bar_h), (w, bar_top + bar_h), 1)