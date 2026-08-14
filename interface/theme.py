"""ATLAS UI Theme — warm ivory / bordeaux design tokens.

Faithful translation of the ``ATLAS_UI.html`` prototype palette:

    ivory / ivory-soft / ivory-deep  – warm light surfaces
    bordeaux / -hover / -dark / -soft – the ATLAS signature accent
    ink / ink-soft / muted           – text hierarchy
    border / border-strong           – hairline separators

All interface modules import from here so colors stay consistent and
no raw hex values leak into widget code.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────
# Core brand palette
# ──────────────────────────────────────────────────────────────────────
IVORY = "#FFFBF0"          # app background
IVORY_SOFT = "#F7F0E2"     # subtle hover surface
IVORY_DEEP = "#EDE2CF"     # deeper warm surface / switch off
IVORY_PANEL = "#FFFDF8"    # panels, cards, message bubble (offscreen)

BORDEAUX = "#53161D"       # primary accent
BORDEAUX_HOVER = "#6B1D27"
BORDEAUX_DARK = "#3D0F15"
BORDEAUX_SOFT = "#F1E3E3"  # active item / command icon background

INK = "#211B1C"            # primary text
INK_SOFT = "#625A57"       # secondary text
MUTED = "#958B86"          # muted text / hints

BORDER = "#E5DCCD"         # default hairline
BORDER_STRONG = "#D5C9B7"  # emphasized border

# ──────────────────────────────────────────────────────────────────────
# Semantic tokens (component-facing)
# ──────────────────────────────────────────────────────────────────────
BACKGROUND = IVORY
SURFACE = IVORY_PANEL                 # cards, composer, modals
SURFACE_HOVER = IVORY_SOFT
SURFACE_DEEP = IVORY_DEEP
PANEL_BG = IVORY_PANEL
SIDEBAR_BG = "#FFFDF7"
TOPBAR_BG = "#FFFBF0"

BORDER_COLOR = BORDER
BORDER_STRONG_COLOR = BORDER_STRONG

ACCENT = BORDEAUX
ACCENT_HOVER = BORDEAUX_HOVER
ACCENT_PRESSED = BORDEAUX_DARK
ACCENT_SOFT = BORDEAUX_SOFT
TEXT = INK
TEXT_SECONDARY = INK_SOFT
TEXT_MUTED = MUTED
TEXT_ON_ACCENT = "#FFFFFF"

SELECTION_BG = BORDEAUX_SOFT

MODAL_BACKDROP = "#2B211F"            # dim behind modals / sidebar
MODAL_BORDER = BORDER_STRONG

# Code / monospace surfaces (warm dark for contrast)
CODE_BG = "#2A2322"
CODE_TEXT = "#F1E9E2"

# Status colours
STATUS_READY = "#2E7D32"
STATUS_BUSY = "#C77700"
STATUS_ERROR = "#C62828"

# ──────────────────────────────────────────────────────────────────────
# Typography
# ──────────────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_FAMILY_BOLD = "Segoe UI"
FONT_MONO = "Consolas"
FONT_EMOJI = "Segoe UI Emoji"

# Sizes in points
FONT_SIZE_XS = 8      # footnotes, meta, labels
FONT_SIZE_SM = 9
FONT_SIZE_BASE = 10
FONT_SIZE_LG = 11
FONT_SIZE_XL = 12
FONT_SIZE_2XL = 14
FONT_SIZE_3XL = 22
FONT_SIZE_4XL = 30


def font(size: int = FONT_SIZE_BASE, weight: str = "normal",
         family: str = FONT_FAMILY) -> tuple[str, int, str]:
    """Build a tkinter font tuple for the ATLAS design language."""
    return (family, size, weight)


# ──────────────────────────────────────────────────────────────────────
# Layout constants
# ──────────────────────────────────────────────────────────────────────
SIDEBAR_WIDTH = 310
SIDEBAR_ANIM_MS = 220
TOPBAR_HEIGHT = 68
CHAT_MAX_WIDTH = 900
CONTENT_PADDING = 24
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 18

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def lerp_color(a: str, b: str, t: float) -> str:
    """Linear interpolation between two hex colors (0.0–1.0)."""
    ra, ga, ba = _hex_to_rgb(a)
    rb, gb, bb = _hex_to_rgb(b)
    r = int(ra + (rb - ra) * t)
    g = int(ga + (gb - ga) * t)
    b = int(ba + (bb - ba) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ──────────────────────────────────────────────────────────────────────
# Legacy aliases — kept so older imports do not crash
# ──────────────────────────────────────────────────────────────────────
COLORS = {
    "bg": BACKGROUND,
    "bg_secondary": SIDEBAR_BG,
    "bg_panel": PANEL_BG,
    "bg_input": PANEL_BG,
    "bg_hover": SURFACE_HOVER,
    "border": BORDER,
    "primary": ACCENT,
    "primary_hover": ACCENT_HOVER,
    "accent": ACCENT,
    "text": TEXT,
    "text_muted": TEXT_MUTED,
    "user_left": PANEL_BG,
    "assistant_left": BACKGROUND,
    "user_right": PANEL_BG,
    "assistant_right": SURFACE_HOVER,
    "success": STATUS_READY,
    "warning": STATUS_BUSY,
    "danger": STATUS_ERROR,
    "purple": "#6B4E8E",
    "cyan": "#2E7D8E",
}

STATUS_COLORS = {
    "ready": STATUS_READY,
    "busy": STATUS_BUSY,
    "error": STATUS_ERROR,
}
