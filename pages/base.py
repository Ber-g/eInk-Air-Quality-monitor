#!/usr/bin/env python3
from __future__ import annotations
"""
Protocol contract for all menu pages.
Add a new page by subclassing BasePage and registering it in menu.py.
"""
from enum import Enum, auto
import pygame


class NavAction(Enum):
    NONE    = auto()   # no special action
    BACK    = auto()   # go back to menu bar
    QUIT    = auto()   # quit the application
    REFETCH = auto()   # trigger an immediate AQI data re-fetch
    RESTART = auto()   # restart the application process


class BasePage:
    """
    Base class for menu pages. Override only what you need.
    All methods have safe no-op defaults.
    """

    def on_enter(self, context: dict) -> None:
        """Called once when this page becomes active.
        context = {"display": AQIDisplay instance}
        """
        self._context = context

    def on_exit(self) -> None:
        """Called when leaving this page."""
        pass

    def tick(self) -> None:
        """Called every frame (30 fps). Use for animation or polling a queue.
        Never do blocking I/O here — use threading.Thread + queue.Queue."""
        pass

    def handle_event(self, event) -> NavAction:
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return NavAction.BACK
        return NavAction.NONE

    def render(self, screen, w: int, h: int, bar_h: int, fonts: dict) -> None:
        """Draw the page into the region (0, bar_h, w, h - bar_h)."""
        pass
