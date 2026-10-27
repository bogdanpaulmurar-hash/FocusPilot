#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FocusPilot — Intelligent Screen & Browser Conditional Formatter
Punct de intrare fără consolă CMD (.pyw).
"""

import os
import sys
import datetime
import logging
import logging.handlers
import tkinter as tk
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_FILE = os.path.join(BASE_DIR, "focuspilot_log.txt")


def configure_logging() -> None:
    """
    Jurnal rotativ, pe nivel INFO.

    Varianta anterioară punea logger-ul rădăcină pe DEBUG cu un handler care
    adăuga la nesfârșit în același fișier, iar overlay-ul scria o linie la
    fiecare redare — adică de peste zece ori pe secundă, cât timp un reper era
    afișat. Fișierul creștea nelimitat și scrierea pe disc concura cu bucla de
    interfață.
    """
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, mode="a", maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Nivelul se poate ridica la DEBUG fără modificări de cod:
    #   set FOCUSPILOT_DEBUG=1
    if os.environ.get("FOCUSPILOT_DEBUG", "").strip() in ("1", "true", "yes"):
        root.setLevel(logging.DEBUG)
        root.info("Jurnalizare DEBUG activată prin FOCUSPILOT_DEBUG.")

    for noisy in ("comtypes", "PIL", "uiautomation"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


configure_logging()
logger = logging.getLogger("FocusPilot")


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    """Salvează orice eroare neprevăzută în jurnal."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("EROARE NECAPTATĂ:", exc_info=(exc_type, exc_value, exc_traceback))
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = handle_uncaught_exception

from core.config_manager import ConfigManager                       # noqa: E402
from core.rule_engine import RuleEngine, CAPABILITIES               # noqa: E402
from core.monitor_engine import (                                   # noqa: E402
    MonitorEngine, get_foreground_window_info, get_virtual_screen_bounds,
    enumerate_content_windows, visible_part,
)
from core.keep_awake import enable_keep_awake, disable_keep_awake   # noqa: E402
from ui.overlay_cue import MultiScreenOverlay                       # noqa: E402
from ui.main_window import MainWindow                               # noqa: E402
from ui.tray_manager import TrayManager, create_tray_image          # noqa: E402
from integrations.userscript_generator import (                     # noqa: E402
    generate_userscript, build_userscript,
)
from integrations.playwright_highlighter import CdpInjector          # noqa: E402

TEST_CUE_SECONDS = 6


class FocusPilotApp:
    """Coordonează ciclul de viață al aplicației."""

    def __init__(self):
        logger.info("=== Pornire FocusPilot ===")
        self.config_manager = ConfigManager(BASE_DIR)
        self._ensure_assets()

        self.root = tk.Tk()
        self.root.title("FocusPilot Engine")
        self.root.withdraw()

        self.overlay = MultiScreenOverlay()
        self.overlay.init_overlay(self.root)

        self.monitor = MonitorEngine(self.config_manager,
                                     on_cues_changed=self._on_cues_detected)

        self.browser_injector = CdpInjector(
            lambda: build_userscript(self.config_manager.get_rules()))

        self.dashboard = MainWindow(
            root=self.root,
            config_manager=self.config_manager,
            on_rules_changed=self._on_rules_updated,
            on_test_cue=self._test_single_cue,
            on_toggle_pause=self._toggle_pause,
            on_quit=self.quit_app,
            on_settings_changed=self._apply_browser_injection_settings,
            browser_status=self.browser_injector.status,
        )

        self.tray = TrayManager(
            config_manager=self.config_manager,
            on_show_dashboard=self._show_dashboard_from_tray,
            on_new_rule=self._new_rule_from_tray,
            on_toggle_rule=self._toggle_rule_from_tray,
            on_edit_rule=self._edit_rule_from_tray,
            on_toggle_pause=self._toggle_pause,
            on_test_cue=self._test_demo_cues_from_tray,
            on_open_settings=self._open_settings_from_tray,
            on_quit=self.quit_app,
        )

        if self.config_manager.get_setting("keep_awake", True):
            enable_keep_awake()

        self._test_hide_job = None
        self._regenerate_userscript()

    # ── Pregătire ────────────────────────────────────────────────────────────

    def _ensure_assets(self) -> None:
        """Generează icoanele dacă lipsesc."""
        assets_dir = os.path.join(BASE_DIR, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        ico = os.path.join(assets_dir, "tray_icon.ico")
        png = os.path.join(assets_dir, "icon.png")
        if os.path.exists(ico) and os.path.exists(png):
            return
        try:
            image = create_tray_image(is_active=True, size=128)
            image.save(png, format="PNG")
            image.save(ico, format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
        except Exception as exc:
            logger.warning("Generarea icoanelor a eșuat: %s", exc)

    def _regenerate_userscript(self) -> None:
        try:
            generate_userscript(self.config_manager)
        except Exception as exc:
            logger.warning("Generarea userscript-ului a eșuat: %s", exc)

    def _apply_browser_injection_settings(self) -> None:
        try:
            self.browser_injector.configure(
                self.config_manager.get_setting("cdp_injection_enabled", False),
                self.config_manager.get_setting("cdp_port", 9222))
        except ValueError as exc:
            # Un port invalid scris de mână în config.json: injectarea rămâne
            # oprită, dar motivul ajunge în jurnal, nu se pierde.
            logger.error("Injectare CDP oprită, port invalid: %s", exc)
            self.browser_injector.configure(False)

    def start(self) -> None:
        self.tray.start()
        self.monitor.start()
        self._apply_browser_injection_settings()
        self.browser_injector.start()

        if not self.config_manager.get_setting("hide_on_start", True):
            self.root.after(200, self.dashboard.show)

        # Dependențele lipsă fac detecția imposibilă, deci utilizatorul trebuie
        # să afle asta la pornire, nu după ce regulile nu se declanșează.
        self.root.after(1200, self._warn_about_missing_dependencies)

        logger.info("FocusPilot inițializat. Intră în bucla de evenimente.")
        self.root.mainloop()

    def _warn_about_missing_dependencies(self) -> None:
        missing = CAPABILITIES.missing()
        if not missing:
            return
        message = (
            "FocusPilot rulează cu detecție redusă: lipsesc pachetele\n\n"
            f"    {', '.join(missing)}\n\n"
        )
        if "uiautomation" in missing:
            message += ("Fără 'uiautomation' regulile bazate pe text nu se pot "
                        "declanșa: aplicația nu poate citi conținutul paginilor.\n\n")
        if "opencv-python" in missing:
            message += ("Fără 'opencv-python' urmărirea prin șablon imagine "
                        "(snip) nu funcționează.\n\n")
        message += "Instalați cu:\n\n    pip install " + " ".join(missing)

        logger.error("Dependențe lipsă la pornire: %s", ", ".join(missing))
        try:
            from tkinter import messagebox
            messagebox.showwarning("FocusPilot — dependențe lipsă", message)
        except Exception:
            pass

    # ── Evenimente ───────────────────────────────────────────────────────────

    def _on_cues_detected(self, cues: List[Dict[str, Any]]) -> None:
        self.overlay.update_cues(cues)

    def _on_rules_updated(self) -> None:
        """
        Regulile s-au schimbat: scannerul reîncarcă totul curat.

        Fără acest apel instantaneele din cache și cronometrele de durată
        rămâneau de la regulile vechi, deci o regulă nou salvată se comporta
        imprevizibil până la repornirea aplicației.
        """
        self.monitor.notify_rules_changed()
        self.tray.refresh()
        self._regenerate_userscript()
        self.browser_injector.notify_rules_changed()

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
        if not rule:
            return

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
        """Comută monitorizarea. Întoarce True dacă a rămas pe pauză."""
        enabled_now = not self.config_manager.get_setting("global_enabled", True)
        self.config_manager.set_setting("global_enabled", enabled_now)

        if enabled_now:
            self.monitor.resume()
        else:
            self.monitor.pause()

        self.tray.refresh()
        return not enabled_now

    # ── Testarea unei reguli ─────────────────────────────────────────────────

    def _test_single_cue(self, rule: Dict[str, Any]) -> None:
        """
        Desenează reperul regulii pe ecran timp de câteva secunde.

        Caută ținta printre ferestrele reale deschise, folosind exact același
        motor ca monitorizarea, ca testul să reflecte comportamentul real.
        """
        name = rule.get("name", "Regulă")
        logger.info("[TEST] Testare vizuală pentru '%s'.", name)

        try:
            geometry, note, warning = self._locate_test_geometry(rule)
            logger.info("[TEST] '%s': %s -> %s", name, note, geometry)
            if warning:
                # Fără avertisment, un chenar desenat demonstrativ arată ca o
                # potrivire reală, plasată greșit.
                from tkinter import messagebox
                self.root.after(100, lambda: messagebox.showwarning(
                    "FocusPilot — Test", warning))

            self.overlay.update_cues([{
                "rule_id": rule.get("id", "test"),
                "rule_name": f"{name} (test)",
                "geometry": geometry,
                "visual_cue": rule.get("visual_cue", {}),
                "window_title": "Test",
                "anchor": "test",
            }])

            if self._test_hide_job:
                self.root.after_cancel(self._test_hide_job)
            self._test_hide_job = self.root.after(
                TEST_CUE_SECONDS * 1000, self._hide_test_cue)
        except Exception as exc:
            logger.exception("[TEST] Testarea regulii '%s' a eșuat: %s", name, exc)

    def _locate_test_geometry(self, rule: Dict[str, Any]):
        """(geometrie, explicație, avertisment sau "") pentru testul unei reguli."""
        virtual = get_virtual_screen_bounds()
        has_text = bool(str(rule.get("trigger", {}).get("search_text", "") or "").strip())

        # 1. Ținta reală, dacă e deschisă pe oricare monitor și nu e acoperită.
        hidden_on = ""
        for window in enumerate_content_windows():
            result = RuleEngine.evaluate(rule, window, virtual, base_dir=BASE_DIR)
            if result.drawable and visible_part(result, window["hwnd"]) is None:
                hidden_on = hidden_on or window["title"][:50]
                continue
            if result.drawable:
                note = f"găsit pe '{window['title'][:40]}'"
                warning = ""
                if has_text and result.anchor == "configured":
                    warning = (
                        f"Textul a fost găsit pe „{window['title'][:50]}”, dar poziția "
                        "lui pe ecran nu a putut fi determinată (apare doar în titlu "
                        "sau într-un element care nu expune text).\n\n"
                        "Chenarul e desenat la poziția configurată în secțiunea 4. "
                        "Folosiți „Alege Interactiv de pe Ecran” pentru o poziție exactă.")
                return result.geometry, note, warning

        if hidden_on:
            not_found = (f"Ținta a fost găsită pe „{hidden_on}”, dar zona ei este "
                         "acoperită de altă fereastră, deci nu se marchează.\n\n"
                         "Aduceți fereastra în față și testați din nou.\n\n"
                         "Chenarul este afișat doar demonstrativ ({}).")
        else:
            not_found = ("Ținta regulii NU a fost găsită pe nicio fereastră deschisă.\n\n"
                         "Chenarul este afișat doar demonstrativ ({}).\n\n"
                         "Folosiți „Diagnosticare Live” ca să vedeți ce filtru "
                         "sau criteriu nu se potrivește.")

        # 2. Coordonatele salvate la selecția interactivă.
        region = rule.get("region", {})
        abs_x = RuleEngine._as_int(region.get("abs_x", 0), 0)
        abs_y = RuleEngine._as_int(region.get("abs_y", 0), 0)
        width = RuleEngine._as_int(region.get("width", 360), 360)
        height = RuleEngine._as_int(region.get("height", 60), 60)
        if abs_x or abs_y:
            note = "la coordonatele salvate"
            return (abs_x, abs_y, width, height), note, not_found.format(note)

        # 3. Centrul ecranului principal.
        screen_w = self.root.winfo_screenwidth() or 1920
        screen_h = self.root.winfo_screenheight() or 1080
        note = "în centrul ecranului"
        return ((screen_w - width) // 2, (screen_h - height) // 2, width, height), \
               note, not_found.format(note)

    def _hide_test_cue(self) -> None:
        self._test_hide_job = None
        self.overlay.update_cues([])

    def _test_demo_cues_from_tray(self) -> None:
        rules = self.config_manager.get_rules()
        if rules:
            self.root.after(0, lambda: self._test_single_cue(rules[0]))

    # ── Închidere ────────────────────────────────────────────────────────────

    def quit_app(self) -> None:
        """Închidere curată: oprește firele, apoi iese din bucla de evenimente."""
        logger.info("Oprire FocusPilot...")
        try:
            disable_keep_awake()
            self.monitor.stop()
            self.browser_injector.stop()
            self.tray.stop()
            self.overlay.shutdown()
        except Exception as exc:
            logger.warning("Eroare la oprire: %s", exc)
        finally:
            # `destroy` termină mainloop; sys.exit din interiorul unui callback
            # Tk lăsa ferestrele overlay în urmă pe ecran.
            try:
                self.root.destroy()
            except Exception:
                pass


def main() -> int:
    try:
        FocusPilotApp().start()
        return 0
    except Exception as exc:
        details = ""
        try:
            import traceback
            details = traceback.format_exc()
        except Exception:
            pass
        logger.critical("Eroare la pornirea FocusPilot:\n%s", details)
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Eroare FocusPilot",
                f"A apărut o problemă la pornire.\n\n{exc}\n\n"
                f"Detalii complete în:\n{LOG_FILE}"
            )
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
