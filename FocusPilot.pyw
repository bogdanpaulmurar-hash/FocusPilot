#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FocusPilot — Intelligent Screen & Browser Conditional Formatter
Entry-point executabil fără consolă CMD (.pyw).
"""

import sys
import os
import logging
import tkinter as tk
from typing import Dict, Any, List

# Asigurăm calea modulului la rădăcina proiectului
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Configurare logging în fișier TXT dedicat pentru depanare
LOG_FILE = os.path.join(BASE_DIR, "focuspilot_log.txt")
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
file_handler.setFormatter(file_formatter)

# Setăm root logger la DEBUG pentru a cuprinde toate modulele (MonitorEngine, Overlay, Picker, etc.)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(file_handler)

# Reducem zgomotul de debug din librăriile de nivel scăzut
logging.getLogger("comtypes").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.INFO)

logger = logging.getLogger("FocusPilot")
logger.setLevel(logging.DEBUG)

def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    """Prinde și salvează orice eroare neprevăzută în focuspilot_log.txt."""
    import traceback
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"EROARE FATALA NECAPTATA:\n{err_msg}")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now()}] CRASH FATAL:\n{err_msg}\n")
    except Exception:
        pass
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

import datetime
sys.excepthook = handle_uncaught_exception

from core.config_manager import ConfigManager
from core.monitor_engine import MonitorEngine
from core.keep_awake import enable_keep_awake, disable_keep_awake
from ui.overlay_cue import MultiScreenOverlay
from ui.main_window import MainWindow
from ui.tray_manager import TrayManager, create_tray_image
from ui.rule_editor_dialog import RuleEditorDialog
from ui.settings_dialog import SettingsDialog
from integrations.userscript_generator import generate_userscript


class FocusPilotApp:
    """Clasa principală de coordonare a ciclului de viață FocusPilot."""

    def __init__(self):
        logger.info("Pornire FocusPilot...")
        self.config_manager = ConfigManager(BASE_DIR)

        # Salvează imaginea ICO în assets dacă lipsește
        self._ensure_assets()

        # Inițializăm Tkinter Root (fereastră invizibilă la pornire)
        self.root = tk.Tk()
        self.root.title("FocusPilot Engine")
        self.root.withdraw()

        # 1. Overlay-ul HUD Multi-Monitor transparent și click-through
        self.overlay = MultiScreenOverlay()
        self.overlay.init_overlay(self.root)

        # 2. Motorul de scanare pe fundal
        self.monitor = MonitorEngine(
            self.config_manager,
            on_cues_changed=self._on_cues_detected
        )

        # 3. Fereastra Principală (Dashboard)
        self.dashboard = MainWindow(
            root=self.root,
            config_manager=self.config_manager,
            on_rules_changed=self._on_rules_updated,
            on_test_cue=self._test_single_cue,
            on_toggle_pause=self._toggle_pause,
            on_quit=self.quit_app
        )

        # 4. System Tray Manager
        self.tray = TrayManager(
            config_manager=self.config_manager,
            on_show_dashboard=self._show_dashboard_from_tray,
            on_new_rule=self._new_rule_from_tray,
            on_toggle_rule=self._toggle_rule_from_tray,
            on_edit_rule=self._edit_rule_from_tray,
            on_toggle_pause=self._toggle_pause,
            on_test_cue=self._test_demo_cues_from_tray,
            on_open_settings=self._open_settings_from_tray,
            on_quit=self.quit_app
        )

        # 5. Keep Awake (Always Awake dacă este activat)
        if self.config_manager.get_setting("keep_awake", True):
            enable_keep_awake()

        # Generăm scriptul de browser la pornire
        try:
            generate_userscript(self.config_manager)
        except Exception as e:
            logger.debug(f"Userscript generator skip: {e}")

    def _ensure_assets(self) -> None:
        """Generează icoana .ico și .png dacă lipsesc."""
        assets_dir = os.path.join(BASE_DIR, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        ico_path = os.path.join(assets_dir, "tray_icon.ico")
        png_path = os.path.join(assets_dir, "icon.png")

        if not os.path.exists(ico_path) or not os.path.exists(png_path):
            img = create_tray_image(is_active=True, size=128)
            img.save(png_path, format="PNG")
            img.save(ico_path, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])

    def start(self) -> None:
        """Pornește serviciile și intră în bucla de evenimente Tkinter."""
        self.tray.start()
        self.monitor.start()

        hide_on_start = self.config_manager.get_setting("hide_on_start", True)
        if not hide_on_start:
            self.root.after(200, self.dashboard.show)

        logger.info("FocusPilot inițializat complet. Intră în mainloop.")
        self.root.mainloop()

    # ── Callbacks Evenimente ──

    def _on_cues_detected(self, cues: List[Dict[str, Any]]) -> None:
        """Recepționează alertele detectate de MonitorEngine și le transmite Overlay-ului."""
        self.overlay.update_cues(cues)

    def _on_rules_updated(self) -> None:
        """Apelat când s-au modificat regulile."""
        self.tray.refresh()
        try:
            generate_userscript(self.config_manager)
        except Exception:
            pass

    def _show_dashboard_from_tray(self) -> None:
        self.root.after(0, self.dashboard.show)

    def _new_rule_from_tray(self) -> None:
        def _open():
            self.dashboard.show()
            self.dashboard._add_rule()
        self.root.after(0, _open)

    def _toggle_rule_from_tray(self, rule_id: str) -> None:
        self.config_manager.toggle_rule(rule_id)
        self._on_rules_updated()
        self.root.after(0, self.dashboard.refresh_rules_list)

    def _edit_rule_from_tray(self, rule_id: str) -> None:
        rule = self.config_manager.get_rule_by_id(rule_id)
        if rule:
            def _open():
                self.dashboard.show()
                self.dashboard._edit_rule(rule)
            self.root.after(0, _open)

    def _open_settings_from_tray(self) -> None:
        def _open():
            self.dashboard.show()
            self.dashboard._open_settings()
        self.root.after(0, _open)

    def _toggle_pause(self) -> bool:
        current_state = self.config_manager.get_setting("global_enabled", True)
        new_state = not current_state
        self.config_manager.set_setting("global_enabled", new_state)

        if new_state:
            self.monitor.resume()
        else:
            self.monitor.pause()

        self.tray.refresh()
        return not new_state

    def _test_single_cue(self, rule: Dict[str, Any]) -> None:
        """Testează reperul vizual desenându-l pe ecran timp de 6 secunde exact unde a fost configurat."""
        rule_name = rule.get('name', 'Unknown')
        logger.info(f"[TEST] Pornire testare vizuală manuală pentru regula: '{rule_name}'")
        
        try:
            region = rule.get("region", {})
            abs_x = region.get("abs_x", 0)
            abs_y = region.get("abs_y", 0)
            w = int(region.get("width", 360))
            h = int(region.get("height", 60))

            target_geo = None

            # 1. Încercăm să găsim poziția reală a elementului dacă fereastra țintă este deschisă
            from core.monitor_engine import get_foreground_window_info, get_virtual_screen_bounds
            import win32gui
            virt_bounds = get_virtual_screen_bounds()
            win_info = get_foreground_window_info()

            if win_info and RuleEngine.evaluate_rule(rule, win_info):
                cue_geo = RuleEngine.calculate_cue_geometry(rule, win_info, virt_bounds)
                if cue_geo:
                    target_geo = cue_geo
                    logger.info(f"[TEST] Element detectat în timp real pe fereastra activă: {target_geo}")

            if not target_geo:
                # Căutăm printre ferestrele vizibile din sistem care corespund regulii
                title_pat = rule.get("trigger", {}).get("window_title_pattern", "*")
                def _scan_win(hnd, extra):
                    nonlocal target_geo
                    if target_geo:
                        return
                    if win32gui.IsWindowVisible(hnd):
                        t = win32gui.GetWindowText(hnd)
                        if t and RuleEngine.match_string(title_pat, t):
                            rect = win32gui.GetWindowRect(hnd)
                            w_info = {"hwnd": hnd, "title": t, "process_name": "browser", "rect": rect, "extra_text": ""}
                            geo = RuleEngine.calculate_cue_geometry(rule, w_info, virt_bounds)
                            if geo:
                                target_geo = geo
                                logger.info(f"[TEST] Element detectat în fereastră de fundal: {target_geo}")
                try:
                    win32gui.EnumWindows(_scan_win, None)
                except Exception:
                    pass

            if not target_geo:
                # Dacă elementul nu a fost găsit activ pe ecran, folosim coordonatele configurate sau centrul ecranului
                if abs_x > 0 and abs_y > 0:
                    target_geo = (abs_x, abs_y, w, h)
                    logger.info(f"[TEST] Elementul nu este vizibil pe ecran; afișare la coordonatele salvate: {target_geo}")
                else:
                    sw = self.root.winfo_screenwidth() or 1920
                    sh = self.root.winfo_screenheight() or 1080
                    cx = (sw // 2) - (w // 2)
                    cy = (sh // 2) - (h // 2)
                    target_geo = (cx, cy, w, h)
                    logger.info(f"[TEST] Afișare test centrat pe ecran: {target_geo}")

            logger.info(f"[TEST] Coordonate finale trimise la overlay: {target_geo}")

            demo_cue = {
                "rule_id": rule.get("id", "demo"),
                "rule_name": rule_name,
                "geometry": target_geo,
                "visual_cue": rule.get("visual_cue", {}),
                "window_title": "Fereastră de Test"
            }
            self.overlay.update_cues([demo_cue])
            logger.info(f"[TEST] Comandă de afișare transmisă cu succes către MultiScreenOverlay.")

            # Auto-ascundere după 6 secunde dacă nu există potrivire reală de fundal
            self.root.after(6000, lambda: self._on_test_auto_hide(rule_name))
        except Exception as exc:
            import traceback
            logger.error(f"[TEST EȘUAT] Eroare la pregătirea sau afișarea reperului de test pentru '{rule_name}': {exc}\n{traceback.format_exc()}")

    def _on_test_auto_hide(self, rule_name: str) -> None:
        logger.info(f"[TEST] Expirat intervalul de 6 secunde pentru testul regulii '{rule_name}'. Se curăță overlay-ul.")
        self.overlay.update_cues([])

    def _test_demo_cues_from_tray(self) -> None:
        rules = self.config_manager.get_rules()
        if rules:
            self.root.after(0, lambda: self._test_single_cue(rules[0]))

    def quit_app(self) -> None:
        """Închidere completă și curată a aplicației."""
        logger.info("Oprire FocusPilot...")
        disable_keep_awake()
        self.monitor.stop()
        self.tray.stop()
        self.root.after(50, self.root.destroy)
        sys.exit(0)


if __name__ == "__main__":
    try:
        logger.info("=== START SESIUNE FOCUSPILOT ===")
        app = FocusPilotApp()
        app.start()
    except Exception as exc:
        import traceback
        err_details = traceback.format_exc()
        logger.critical(f"Eroare la pornirea FocusPilot:\n{err_details}")
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now()}] EROARE PORNIRE:\n{err_details}\n")
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Eroare FocusPilot",
                f"A apărut o problemă la pornire. Detaliile au fost salvate în:\n{LOG_FILE}\n\nEroare: {exc}"
            )
        except Exception:
            pass
        sys.exit(1)
