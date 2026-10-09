"""
FocusPilot — Theme & Styles
Paletă corporate Siemens modernă cu suport complet pentru Light Mode și Dark Mode.
"""

from typing import Dict, Any

# ── Paleta Oficială Siemens ──
SIEMENS_PETROL       = "#00646E"  # Brand primary
SIEMENS_TEAL         = "#00A3A6"  # Brand accent / teal
SIEMENS_ORANGE       = "#EB780A"  # Accent contrast
SIEMENS_RED_ALERT    = "#E60000"  # Critical red / conditional formatting
SIEMENS_GREEN        = "#009966"  # Success status
SIEMENS_YELLOW       = "#FFB900"  # Warning status

THEMES: Dict[str, Dict[str, str]] = {
    "dark": {
        "name": "dark",
        "bg_main": "#14191E",          # Fundal principal închis
        "bg_card": "#1E252D",          # Carduri / panouri
        "bg_input": "#28323D",         # Câmpuri de introducere
        "bg_hover": "#323E4C",         # Hover pe butoane/elemente
        "border": "#3A4756",           # Linii de delimitare
        "fg_primary": "#FFFFFF",       # Text alb pronunțat
        "fg_secondary": "#A6B4C2",     # Text secundar gri-albăstrui
        "fg_muted": "#6E7E8E",         # Text dezactivat
        "accent": SIEMENS_TEAL,        # Accent principal
        "accent_hover": "#00C2C5",     # Accent hover
        "accent_subtle": "#10383C",    # Fundal subtil accent
        "primary_btn": SIEMENS_PETROL, # Buton acțiune principală
        "primary_btn_hover": "#007D8A",
        "alert_red": SIEMENS_RED_ALERT,
        "alert_red_glow": "#FF4D4D",
        "orange": SIEMENS_ORANGE,
        "green": SIEMENS_GREEN,
    },
    "light": {
        "name": "light",
        "bg_main": "#F4F6F8",          # Fundal principal deschis
        "bg_card": "#FFFFFF",          # Carduri albe curate
        "bg_input": "#F8FAFC",         # Câmpuri de text
        "bg_hover": "#E2E8F0",         # Hover gri deschis
        "border": "#CBD5E1",           # Border subtil
        "fg_primary": "#0F172A",       # Text negru/indigo
        "fg_secondary": "#475569",     # Text secundar
        "fg_muted": "#94A3B8",         # Text discret
        "accent": SIEMENS_PETROL,      # Accent teal închis
        "accent_hover": "#004B52",
        "accent_subtle": "#E0F2F1",    # Fundal deschis teal
        "primary_btn": SIEMENS_PETROL,
        "primary_btn_hover": "#004B52",
        "alert_red": SIEMENS_RED_ALERT,
        "alert_red_glow": "#FF1A1A",
        "orange": SIEMENS_ORANGE,
        "green": SIEMENS_GREEN,
    }
}


def get_theme(theme_name: str = "dark") -> Dict[str, str]:
    """Returnează paleta de culori pentru tema cerută."""
    return THEMES.get(theme_name.lower(), THEMES["dark"])


FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_SUBTITLE = ("Segoe UI", 11, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_BODY_BOLD = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)
FONT_ICON = ("Segoe UI Emoji", 11)
