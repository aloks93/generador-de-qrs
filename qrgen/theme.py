"""Tema visual «industrial»: esquinas rectas, paleta grafito/hormigón y acento naranja.

Cada color es una tupla ``(modo claro, modo oscuro)``; CustomTkinter elige el
valor según el modo de apariencia activo, así que cambiar de tema es instantáneo.
"""

from __future__ import annotations

import tkinter.font as tkfont
from functools import lru_cache

import customtkinter as ctk
from customtkinter import ThemeManager

BG = ("#E4E2DD", "#0E0F11")
SURFACE = ("#F2F1ED", "#16181B")
SURFACE_2 = ("#D9D6CF", "#1E2125")
BORDER = ("#A9A49A", "#2E3238")
BORDER_STRONG = ("#6E6A62", "#4A5058")
TEXT = ("#121212", "#E8E6E1")
MUTED = ("#5E5B55", "#8A9097")
ACCENT = ("#E05A00", "#FF7A1A")
ACCENT_HOVER = ("#B84A00", "#FF9440")
ON_ACCENT = ("#FFFFFF", "#0E0F11")
WARN_BG = ("#F6E7D2", "#2A1F12")
ERROR = ("#B3261E", "#FF6B5E")
OK = ("#2E6B2E", "#7BD88F")


def _pick(*families: str) -> str:
    available = set(tkfont.families())
    return next((f for f in families if f in available), "TkDefaultFont")


class Fonts:
    """Se resuelven tras crear la ventana raíz (tkinter necesita un intérprete)."""

    display: str = "TkDefaultFont"
    body: str = "TkDefaultFont"
    mono: str = "TkFixedFont"

    @classmethod
    def load(cls) -> None:
        cls.display = _pick("Bahnschrift", "DIN Alternate", "Barlow", "Segoe UI", "Helvetica")
        cls.body = _pick("Segoe UI", "Inter", "Helvetica Neue", "Helvetica", "Arial")
        cls.mono = _pick("Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo", "Courier New")


@lru_cache(maxsize=None)
def font(kind: str = "body", size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    family = {"display": Fonts.display, "mono": Fonts.mono}.get(kind, Fonts.body)
    return ctk.CTkFont(family=family, size=size, weight=weight)


def apply() -> None:
    """Sustituye el tema por defecto. Debe llamarse antes de crear widgets."""
    ctk.set_default_color_theme("blue")
    t = ThemeManager.theme

    for name, spec in t.items():
        if not isinstance(spec, dict):
            continue
        for key in ("corner_radius", "button_corner_radius"):
            if key in spec:
                spec[key] = 0

    t["CTk"]["fg_color"] = list(BG)
    t["CTkToplevel"]["fg_color"] = list(BG)
    t["CTkFrame"].update(fg_color=list(SURFACE), top_fg_color=list(SURFACE_2), border_color=list(BORDER))
    t["CTkButton"].update(
        fg_color=list(ACCENT), hover_color=list(ACCENT_HOVER), border_color=list(BORDER_STRONG),
        text_color=list(ON_ACCENT), text_color_disabled=list(MUTED),
    )
    t["CTkLabel"]["text_color"] = list(TEXT)
    t["CTkEntry"].update(
        fg_color=list(BG), border_color=list(BORDER), text_color=list(TEXT),
        placeholder_text_color=list(MUTED), border_width=1,
    )
    t["CTkTextbox"].update(
        fg_color=list(BG), border_color=list(BORDER), text_color=list(TEXT), border_width=1,
        scrollbar_button_color=list(BORDER), scrollbar_button_hover_color=list(BORDER_STRONG),
    )
    t["CTkCheckBox"].update(
        fg_color=list(ACCENT), hover_color=list(ACCENT_HOVER), border_color=list(BORDER_STRONG),
        checkmark_color=list(ON_ACCENT), text_color=list(TEXT), border_width=2,
    )
    t["CTkSwitch"].update(
        fg_color=list(SURFACE_2), progress_color=list(ACCENT), button_color=list(TEXT),
        button_hover_color=list(MUTED), text_color=list(TEXT),
    )
    t["CTkSlider"].update(
        fg_color=list(SURFACE_2), progress_color=list(ACCENT), button_color=list(TEXT),
        button_hover_color=list(ACCENT),
    )
    t["CTkOptionMenu"].update(
        fg_color=list(SURFACE_2), button_color=list(BORDER), button_hover_color=list(BORDER_STRONG),
        text_color=list(TEXT),
    )
    t["CTkSegmentedButton"].update(
        fg_color=list(BORDER), selected_color=list(ACCENT), selected_hover_color=list(ACCENT_HOVER),
        unselected_color=list(SURFACE_2), unselected_hover_color=list(BORDER),
        text_color=list(TEXT), border_width=1,
    )
    t["CTkScrollbar"].update(button_color=list(BORDER), button_hover_color=list(BORDER_STRONG))
    t["CTkScrollableFrame"]["label_fg_color"] = list(SURFACE_2)
    t["DropdownMenu"].update(fg_color=list(SURFACE), hover_color=list(SURFACE_2), text_color=list(TEXT))
