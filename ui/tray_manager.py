"""
FocusPilot — System Tray Manager (pystray)
Gestionează prezența permanentă în Windows System Tray, meniul bogat la clic dreapta,
submeniul dinamic cu regulile existente și comutarea rapidă.
"""

import os
import logging
import threading
from typing import Dict, Any, List, Optional, Callable

from PIL import Image, ImageDraw
import pystray

from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def create_tray_image(is_active: bool = True, size: int = 64) -> Image.Image:
    """Generează o icoană modernă și precisă în stil Siemens pentru System Tray."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Fundal circular Siemens Petrol (#00646E)
    bg_color = (0, 100, 110, 255) if is_active else (70, 80, 90, 255)
    border_color = (0, 163, 166, 255) if is_active else (110, 120, 130, 255)
    draw.ellipse((4, 4, size - 4, size - 4), fill=bg_color, outline=border_color, width=3)

    # Țintă / Reticul central
    cx, cy = size // 2, size // 2
    r_outer = 16
    draw.ellipse((cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer), outline=(255, 255, 255, 220), width=2)

    # Linii reticul
    draw.line((cx - r_outer - 5, cy, cx + r_outer + 5, cy), fill=(255, 255, 255, 220), width=2)
    draw.line((cx, cy - r_outer - 5, cx, cy + r_outer + 5), fill=(255, 255, 255, 220), width=2)

    # Punct roșu de alertă în colțul din dreapta sus (simbolizând atenția/formatarea condițională)
    dot_color = (230, 0, 0, 255) if is_active else (255, 185, 0, 255)
    draw.ellipse((size - 20, 4, size - 4, 20), fill=dot_color, outline=(255, 255, 255, 255), width=2)

    return image


class TrayManager:
    """Controler pentru icoana și meniul contextual de click-dreapta din Windows Tray."""

    def __init__(self, config_manager: ConfigManager,
                 on_show_dashboard: Callable[[], None],
                 on_new_rule: Callable[[], None],
                 on_toggle_rule: Callable[[str], None],
                 on_edit_rule: Callable[[str], None],
                 on_toggle_pause: Callable[[], bool],
                 on_test_cue: Callable[[], None],
                 on_open_settings: Callable[[], None],
                 on_quit: Callable[[], None]):
        self.cfg = config_manager
        self.on_show_dashboard = on_show_dashboard
        self.on_new_rule = on_new_rule
        self.on_toggle_rule = on_toggle_rule
        self.on_edit_rule = on_edit_rule
        self.on_toggle_pause = on_toggle_pause
        self.on_test_cue = on_test_cue
        self.on_open_settings = on_open_settings
        self.on_quit = on_quit

        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Pornește tray icon-ul într-un fir de execuție separat."""
        img = create_tray_image(is_active=True)
        menu = self._build_menu()

        self.icon = pystray.Icon(
            "FocusPilot",
            img,
            "FocusPilot — Monitorizare Ecrane & Formatare Condițională",
            menu
        )

        self._thread = threading.Thread(target=self.icon.run, daemon=True, name="FocusPilotTray")
        self._thread.start()
        logger.info("TrayManager pornit.")

    def stop(self) -> None:
        """Oprește icon-ul din tray."""
        if self.icon:
            self.icon.stop()
            self.icon = None
        logger.info("TrayManager oprit.")

    def refresh(self) -> None:
        """Actualizează meniul dinamic al icon-ului din tray."""
        if self.icon:
            self.icon.menu = self._build_menu()
            # Actualizează și starea imaginii dacă este pe pauză
            is_active = self.cfg.get_setting("global_enabled", True)
            self.icon.icon = create_tray_image(is_active=is_active)

    def _build_menu(self) -> pystray.Menu:
        """Construiește meniul la click-dreapta cu submeniul de reguli existente."""
        rules = self.cfg.get_rules()

        # Construim submeniul cu reguli existente
        rule_items = []
        if rules:
            for r in rules:
                rid = r.get("id")
                rname = r.get("name", "Regulă")
                is_on = r.get("enabled", True)
                status_icon = "✓ " if is_on else "○ "
                item_label = f"{status_icon}{rname}"
                rule_items.append(
                    pystray.MenuItem(
                        item_label,
                        self._create_rule_callback(rid)
                    )
                )
        else:
            rule_items.append(pystray.MenuItem("(Nicio regulă definită)", None, enabled=False))

        is_global_active = self.cfg.get_setting("global_enabled", True)
        pause_label = "⏸️ Pune pe pauză" if is_global_active else "▶️ Reia monitorizarea"

        menu_items = [
            pystray.MenuItem("🖥️ Deschide Dashboard", lambda icon, item: self.on_show_dashboard(), default=True),
            pystray.MenuItem("➕ Creează regulă nouă", lambda icon, item: self.on_new_rule()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("📋 Reguli Existente", pystray.Menu(*rule_items)),
            pystray.MenuItem(pause_label, lambda icon, item: self._handle_pause()),
            pystray.MenuItem("🎯 Testează repere vizuale", lambda icon, item: self.on_test_cue()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Setări", lambda icon, item: self.on_open_settings()),
            pystray.MenuItem("❌ Ieșire FocusPilot", lambda icon, item: self.on_quit())
        ]

        return pystray.Menu(*menu_items)

    def _create_rule_callback(self, rule_id: str):
        return lambda icon, item: self.on_toggle_rule(rule_id)

    def _handle_pause(self) -> None:
        self.on_toggle_pause()
        self.refresh()
