"""
FocusPilot — Monitor Engine
Scanner de fundal care monitorizează ferestrele și ecranele active (suport multi-monitor 3 ecrane),
identifică aplicațiile țintă și declanșează reperele vizuale conform regulilor active.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple

import win32gui
import win32process
import win32api
import win32con

from core.config_manager import ConfigManager
from core.rule_engine import RuleEngine

logger = logging.getLogger(__name__)


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """Returnează coordonatele întregului spațiu virtual pe toate cele 3 monitoare (X, Y, W, H)."""
    try:
        x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return (x, y, w, h)
    except Exception:
        # Fallback monitor primar
        return (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))


def get_process_name_native(pid: int) -> str:
    """Obține numele procesului direct prin Windows API (fără a depinde de psutil)."""
    import ctypes
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if h:
            buf = ctypes.create_unicode_buffer(1024)
            size = ctypes.c_ulong(1024)
            res = ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
            ctypes.windll.kernel32.CloseHandle(h)
            if res:
                import os
                return os.path.basename(buf.value).lower()
    except Exception:
        pass
    return ""


def get_foreground_window_info() -> Optional[Dict[str, Any]]:
    """Extrage informații complete despre fereastra aflată în prim-plan."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None

        title = win32gui.GetWindowText(hwnd)
        if not title:
            return None

        # Coordonate fereastră
        rect = win32gui.GetWindowRect(hwnd) # (left, top, right, bottom)

        # Extrage procesul
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc_name = get_process_name_native(pid)

        return {
            "hwnd": hwnd,
            "title": title,
            "process_name": proc_name,
            "rect": rect,
            "extra_text": ""
        }
    except Exception as exc:
        logger.debug(f"Eroare GetForegroundWindow: {exc}")
        return None


class MonitorEngine:
    """Motorul de fundal care rulează scanarea continuă a ecranelor și declanșează alertele."""

    def __init__(self, config_manager: ConfigManager, on_cues_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None):
        self.config_manager = config_manager
        self.on_cues_changed = on_cues_changed

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()

        # Cache pentru a nu redesena inutil când nu s-a schimbat starea
        self._last_active_rules_ids: List[str] = []
        self._rule_start_times: Dict[str, float] = {}

    def start(self) -> None:
        """Pornește firul de execuție al scannerului."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = not self.config_manager.get_setting("global_enabled", True)
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="FocusPilotMonitor")
            self._thread.start()
            logger.info("MonitorEngine pornit.")

    def stop(self) -> None:
        """Oprește scannerul."""
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("MonitorEngine oprit.")

    def pause(self) -> None:
        """Pauzează monitorizarea."""
        with self._lock:
            self._paused = True
        self._clear_cues()
        logger.info("MonitorEngine pauzat.")

    def resume(self) -> None:
        """Reia monitorizarea."""
        with self._lock:
            self._paused = False
        logger.info("MonitorEngine reluat.")

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def _clear_cues(self) -> None:
        self._last_active_rules_ids = []
        if self.on_cues_changed:
            self.on_cues_changed([])

    def _monitor_loop(self) -> None:
        """Bucla principală de scanare periodică."""
        while self._running:
            try:
                poll_interval = float(self.config_manager.get_setting("poll_interval_sec", 1.0))
                if poll_interval < 0.2:
                    poll_interval = 0.2

                if self._paused or not self.config_manager.get_setting("global_enabled", True):
                    time.sleep(poll_interval)
                    continue

                # 1. Extrage fereastra activă curentă
                win_info = get_foreground_window_info()
                if not win_info:
                    if self._last_active_rules_ids:
                        self._clear_cues()
                    self._rule_start_times.clear()
                    time.sleep(poll_interval)
                    continue

                now = time.time()
                # 2. Evaluează toate regulile active
                rules = self.config_manager.get_rules()
                matched_cues: List[Dict[str, Any]] = []
                matched_ids: List[str] = []

                virt_bounds = get_virtual_screen_bounds()

                for rule in rules:
                    if not rule.get("enabled", True):
                        continue

                    rule_id = rule["id"]
                    is_match = RuleEngine.evaluate_rule(rule, win_info)
                    if is_match:
                        # Gestionare durată afișare (duration_sec)
                        dur = float(rule.get("visual_cue", {}).get("duration_sec", 0))
                        if rule_id not in self._rule_start_times:
                            self._rule_start_times[rule_id] = now
                            logger.info(f"[MONITOR] Regula '{rule.get('name')}' declanșată. Durată afișare configurată: {dur}s.")

                        if dur > 0 and (now - self._rule_start_times[rule_id]) > dur:
                            # Durata a expirat pentru această sesiune
                            continue

                        matched_ids.append(rule_id)
                        cue_geo = RuleEngine.calculate_cue_geometry(rule, win_info, virt_bounds)

                        cue_data = {
                            "rule_id": rule_id,
                            "rule_name": rule["name"],
                            "geometry": cue_geo,  # (x, y, w, h)
                            "visual_cue": rule.get("visual_cue", {}),
                            "window_title": win_info["title"]
                        }
                        matched_cues.append(cue_data)
                    else:
                        # Resetează timerul când fereastra nu se mai potrivește
                        if rule_id in self._rule_start_times:
                            del self._rule_start_times[rule_id]

                # 3. Notifică doar dacă s-a schimbat lista de reguli potrivite
                if matched_ids != self._last_active_rules_ids:
                    if matched_ids:
                        logger.info(f"[MONITOR] Reguli declanșate ({len(matched_ids)}): {matched_ids} pe fereastra '{win_info.get('title')}' [{win_info.get('process_name')}]")
                    else:
                        active_rule_names = [r.get('name') for r in rules if r.get('enabled', True)]
                        logger.info(f"[MONITOR] Nicio regulă activă pe fereastra în prim-plan '{win_info.get('title')}' [{win_info.get('process_name')}]. Reguli evaluate: {active_rule_names}. Ascund repere.")
                    self._last_active_rules_ids = matched_ids
                    if self.on_cues_changed:
                        self.on_cues_changed(matched_cues)

            except Exception as exc:
                logger.error(f"Eroare în bucla MonitorEngine: {exc}")

            time.sleep(poll_interval)
