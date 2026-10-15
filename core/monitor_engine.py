"""
FocusPilot — Monitor Engine

Scanner de fundal care urmărește ferestrele de pe toate monitoarele, evaluează
regulile active și transmite reperele vizuale de desenat.

Un ciclu de scanare:
    1. Adună ferestrele candidate (fereastra activă + ferestrele vizibile mari).
    2. Evaluează fiecare regulă activă o singură dată pe fereastra potrivită.
    3. Trimite către overlay doar dacă s-a schimbat ceva față de ciclul anterior.

Pasul 2 face o singură trecere pe regulă. Varianta anterioară evalua regula o
dată pentru a decide potrivirea și încă o dată pentru a calcula coordonatele,
fiecare trecere pornind o căutare UIA completă și o potrivire de șablon pe tot
spațiul virtual — de unde consumul de procesor și întârzierile.
"""

import os
import time
import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Dict, Any, List, Optional, Callable, Tuple

import win32gui
import win32process
import win32api
import win32con

from core.config_manager import ConfigManager
from core.rule_engine import (
    RuleEngine,
    CAPABILITIES,
    capture_window_text,
    invalidate_snapshot_cache,
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OWN_PID = os.getpid()

BROWSER_PROCESSES = {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}

# Ferestre de sistem care nu pot conține conținut de interes.
IGNORED_TITLES = {
    "Program Manager", "Windows Input Experience", "Default IME",
    "MSCTFIME UI", "Setup", "",
}
IGNORED_PROCESSES = {"textinputhost.exe", "applicationframehost.exe",
                     "searchhost.exe", "shellexperiencehost.exe"}

# Dimensiunea minimă ca o fereastră să fie considerată conținut, nu decorație.
MIN_WINDOW_W = 320
MIN_WINDOW_H = 200


def get_virtual_screen_bounds() -> Tuple[int, int, int, int]:
    """Spațiul virtual care acoperă toate monitoarele: (X, Y, W, H)."""
    try:
        return (
            win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN),
            win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN),
        )
    except Exception:
        return (0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1))


def get_process_name_native(pid: int) -> str:
    """Numele executabilului pentru un PID, direct prin Windows API."""
    import ctypes
    handle = None
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ""
        buf = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(1024)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    except Exception:
        pass
    finally:
        if handle:
            try:
                import ctypes as _c
                _c.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Citirea URL-ului din browser
# ─────────────────────────────────────────────────────────────────────────────

_url_cache: Dict[int, Tuple[float, str]] = {}
_url_lock = threading.Lock()
URL_CACHE_TTL_SEC = 1.0


def get_browser_url(hwnd: int, process_name: str) -> str:
    """
    Citește adresa din bara de adrese a browserului prin UI Automation.

    Fără aceasta filtrul `url_pattern` din reguli nu putea fi evaluat niciodată,
    deși era prezent în editor și salvat în config.json.
    """
    if not hwnd or process_name not in BROWSER_PROCESSES or not CAPABILITIES.uia:
        return ""

    now = time.time()
    with _url_lock:
        hit = _url_cache.get(hwnd)
        if hit and (now - hit[0]) < URL_CACHE_TTL_SEC:
            return hit[1]

    url = ""
    try:
        from core.rule_engine import _ensure_com_initialized
        _ensure_com_initialized()
        import uiautomation as auto

        try:
            auto.SetGlobalSearchTimeout(0)
        except Exception:
            pass

        win = auto.ControlFromHandle(hwnd)
        if win is not None:
            # Bara de adrese este un control Edit aflat aproape de rădăcină.
            edit = win.EditControl(searchDepth=12)
            if edit.Exists(0, 0):
                try:
                    url = edit.GetValuePattern().Value or ""
                except Exception:
                    url = edit.Name or ""
    except Exception as exc:
        logger.debug("Citirea URL eșuată pentru hwnd=%s: %s", hwnd, exc)

    with _url_lock:
        _url_cache[hwnd] = (now, url)
        if len(_url_cache) > 32:
            _url_cache.pop(min(_url_cache, key=lambda k: _url_cache[k][0]), None)
    return url


# ─────────────────────────────────────────────────────────────────────────────
# Informații despre ferestre
# ─────────────────────────────────────────────────────────────────────────────

def _describe_window(hwnd: int, with_url: bool = True) -> Optional[Dict[str, Any]]:
    """Adună titlul, procesul, coordonatele și (pentru browsere) URL-ul."""
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            return None
        title = win32gui.GetWindowText(hwnd)
        if not title or title in IGNORED_TITLES:
            return None

        rect = win32gui.GetWindowRect(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        # Propriile ferestre se recunosc după proces, nu după titlu: un titlu
        # ca „FocusPilot.pyw - Visual Studio Code" e o fereastră străină.
        if pid == OWN_PID:
            return None
        proc = get_process_name_native(pid)
        if proc in IGNORED_PROCESSES:
            return None

        return {
            "hwnd": hwnd,
            "title": title,
            "process_name": proc,
            "rect": rect,
            "url": get_browser_url(hwnd, proc) if with_url else "",
            "extra_text": "",
        }
    except Exception as exc:
        logger.debug("Descrierea ferestrei %s a eșuat: %s", hwnd, exc)
        return None


def get_foreground_window_info() -> Optional[Dict[str, Any]]:
    """Informații complete despre fereastra din prim-plan."""
    try:
        return _describe_window(win32gui.GetForegroundWindow())
    except Exception as exc:
        logger.debug("GetForegroundWindow a eșuat: %s", exc)
        return None


GW_HWNDPREV = 3
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14


def _dwm_attr(hwnd: int, attr: int, value) -> bool:
    try:
        return ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), attr, ctypes.byref(value), ctypes.sizeof(value)) == 0
    except Exception:
        return False


def _covers(hwnd: int, px: int, py: int) -> bool:
    """True dacă fereastra `hwnd` e afișată și conține punctul fizic (px, py)."""
    if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        return False
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    if pid == OWN_PID:                               # marcajele și editorul nostru
        return False
    if win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TRANSPARENT:
        return False
    cloaked = wintypes.DWORD(0)                      # ferestre UWP ascunse de DWM
    if _dwm_attr(hwnd, DWMWA_CLOAKED, cloaked) and cloaked.value:
        return False
    # Limitele DWM sunt în pixeli fizici, ca UIA, și exclud marginea invizibilă.
    box = wintypes.RECT()
    if not _dwm_attr(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, box):
        return False
    return box.left <= px < box.right and box.top <= py < box.bottom


def is_rect_on_top(hwnd: int, rect: Optional[Tuple[int, int, int, int]]) -> bool:
    """
    True dacă centrul lui `rect` nu e acoperit de o fereastră aflată deasupra
    lui `hwnd`. Textul unei ferestre din spate e citibil prin UI Automation,
    dar un marcaj desenat pentru el ar apărea peste fereastra din față.
    """
    if not hwnd or not rect:
        return True
    x, y, w, h = rect
    px, py = int(x + w // 2), int(y + h // 2)
    try:
        above = win32gui.GetWindow(hwnd, GW_HWNDPREV)
        while above:
            if _covers(above, px, py):
                logger.debug("Marcaj ascuns: '%s' acoperă ținta.",
                             win32gui.GetWindowText(above)[:50])
                return False
            above = win32gui.GetWindow(above, GW_HWNDPREV)
    except Exception as exc:
        logger.debug("Verificarea vizibilității a eșuat: %s", exc)
    return True


def visible_part(result: Any, hwnd: int) -> Optional[Tuple[Any, Tuple[Dict[str, Any], ...]]]:
    """
    (geometrie, marcaje) păstrând doar ce e vizibil pe ecran, sau None dacă
    nimic din potrivire nu se vede.
    """
    if result.marks:
        marks = tuple(m for m in result.marks if is_rect_on_top(hwnd, m.get("rect")))
        if not marks:
            return None
        return marks[0]["rect"], marks
    if result.geometry is not None and not is_rect_on_top(hwnd, result.geometry):
        return None
    return result.geometry, ()


def enumerate_content_windows(limit: int = 12) -> List[Dict[str, Any]]:
    """
    Ferestrele vizibile suficient de mari ca să conțină conținut de lucru,
    de pe toate monitoarele, cea activă prima.

    Pe un setup cu 3 ecrane utilizatorul se uită la un monitor în timp ce
    lucrează pe altul. Varianta anterioară analiza doar fereastra activă, deci o
    regulă pentru o pagină de pe al doilea monitor nu se declanșa niciodată.
    """
    found: List[Dict[str, Any]] = []
    seen = set()

    fg = get_foreground_window_info()
    if fg:
        found.append(fg)
        seen.add(fg["hwnd"])

    def _collect(hwnd, _):
        if len(found) >= limit:
            return True
        try:
            if hwnd in seen or not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.IsIconic(hwnd):          # minimizată: nimic vizibil
                return True
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            if (right - left) < MIN_WINDOW_W or (bottom - top) < MIN_WINDOW_H:
                return True
            # URL-ul se citește doar pentru fereastra activă: e un apel UIA
            # în plus pe fereastră și rar necesar pentru cele din fundal.
            info = _describe_window(hwnd, with_url=False)
            if info:
                found.append(info)
                seen.add(hwnd)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(_collect, None)
    except Exception as exc:
        logger.debug("EnumWindows a eșuat: %s", exc)

    return found


# ─────────────────────────────────────────────────────────────────────────────
# Motorul de monitorizare
# ─────────────────────────────────────────────────────────────────────────────

class MonitorEngine:
    """Firul de fundal care scanează ecranele și declanșează reperele vizuale."""

    def __init__(self, config_manager: ConfigManager,
                 on_cues_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None):
        self.config_manager = config_manager
        self.on_cues_changed = on_cues_changed

        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()

        self._last_cues_signature = ""
        self._rule_start_times: Dict[str, float] = {}
        self._last_reason: Dict[str, str] = {}
        self._warned_missing_deps = False

    # ── Ciclu de viață ───────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._paused = not self.config_manager.get_setting("global_enabled", True)
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True,
                                            name="FocusPilotMonitor")
            self._thread.start()
        logger.info("MonitorEngine pornit.")

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("MonitorEngine oprit.")

    def pause(self) -> None:
        with self._lock:
            self._paused = True
        self._clear_cues()
        logger.info("MonitorEngine pauzat.")

    def resume(self) -> None:
        with self._lock:
            self._paused = False
        # Regulile sau ferestrele se pot fi schimbat în pauză.
        invalidate_snapshot_cache()
        self._rule_start_times.clear()
        logger.info("MonitorEngine reluat.")

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def notify_rules_changed(self) -> None:
        """Apelat când utilizatorul salvează o regulă: repornește evaluarea curată."""
        invalidate_snapshot_cache()
        self._rule_start_times.clear()
        self._last_reason.clear()
        self._last_cues_signature = ""
        logger.info("MonitorEngine: reguli reîncărcate.")

    def last_reason_for(self, rule_id: str) -> str:
        """Ultima explicație de evaluare pentru o regulă, pentru diagnostic."""
        return self._last_reason.get(rule_id, "")

    # ── Bucla de scanare ─────────────────────────────────────────────────────

    def _clear_cues(self) -> None:
        self._last_cues_signature = ""
        if self.on_cues_changed:
            self.on_cues_changed([])

    def _read_poll_interval(self) -> float:
        """Intervalul de scanare, limitat ca să nu sature procesorul."""
        try:
            value = float(self.config_manager.get_setting("poll_interval_sec", 0.6))
        except (TypeError, ValueError):
            value = 0.6
        # Sub 0.25s o scanare nu are timp să se termine înainte de următoarea.
        return min(5.0, max(0.25, value))

    def _monitor_loop(self) -> None:
        # Inițializat ÎNAINTE de try: în varianta anterioară `poll_interval` era
        # definit în interiorul blocului try, iar `time.sleep(poll_interval)` de
        # la finalul buclei era în afara lui. O excepție la prima iterație lăsa
        # numele nelegat, iar UnboundLocalError — neprins — omora firul de
        # execuție în silence: monitorizarea se oprea fără niciun mesaj.
        poll_interval = self._read_poll_interval()

        while self._running:
            try:
                poll_interval = self._read_poll_interval()

                if self._paused or not self.config_manager.get_setting("global_enabled", True):
                    time.sleep(poll_interval)
                    continue

                self._warn_missing_dependencies_once()
                self._scan_once()

            except Exception as exc:
                logger.exception("Eroare în bucla MonitorEngine: %s", exc)

            time.sleep(poll_interval)

    def _warn_missing_dependencies_once(self) -> None:
        if self._warned_missing_deps:
            return
        self._warned_missing_deps = True
        missing = CAPABILITIES.missing()
        if missing:
            logger.error(
                "FocusPilot rulează cu detecție REDUSĂ: lipsesc pachetele %s. "
                "Rulați:  pip install %s",
                ", ".join(missing), " ".join(missing)
            )

    def _scan_once(self) -> None:
        """Un ciclu complet de evaluare a regulilor."""
        rules = [r for r in self.config_manager.get_rules() if r.get("enabled", True)]
        if not rules:
            if self._last_cues_signature:
                self._clear_cues()
            self._rule_start_times.clear()
            return

        windows = enumerate_content_windows()
        if not windows:
            if self._last_cues_signature:
                self._clear_cues()
            self._rule_start_times.clear()
            return

        virt_bounds = get_virtual_screen_bounds()
        now = time.time()
        cues: List[Dict[str, Any]] = []

        for rule in rules:
            rule_id = rule.get("id")
            if not rule_id:
                logger.warning("Regulă fără 'id', ignorată: %s", rule.get("name"))
                continue

            cue = self._evaluate_rule_against_windows(rule, rule_id, windows,
                                                      virt_bounds, now)
            if cue:
                cues.append(cue)

        # Trimitem doar la schimbare, dar semnătura include coordonatele, ca
        # reperul să urmărească elementul când utilizatorul derulează pagina.
        signature = repr([(c["rule_id"], c["geometry"],
                           tuple(m.get("rect") for m in c.get("marks", ())))
                          for c in cues])
        if signature != self._last_cues_signature:
            self._last_cues_signature = signature
            if self.on_cues_changed:
                self.on_cues_changed(cues)

    def _evaluate_rule_against_windows(self, rule: Dict[str, Any], rule_id: str,
                                       windows: List[Dict[str, Any]],
                                       virt_bounds: Tuple[int, int, int, int],
                                       now: float) -> Optional[Dict[str, Any]]:
        """Evaluează o regulă pe ferestrele candidate și întoarce reperul, dacă e cazul."""
        steps = rule.get("steps") or []
        started_at = self._rule_start_times.get(rule_id)
        elapsed = (now - started_at) if started_at is not None else 0.0

        active_step = RuleEngine.get_active_step_for_rule(rule, elapsed) if steps else None
        # Succesiunea s-a consumat, dar continuăm să verificăm potrivirea: altfel
        # cronometrul nu s-ar reseta niciodată și succesiunea nu ar mai putea
        # reporni când utilizatorul revine pe fereastră.
        sequence_done = bool(steps) and active_step is None and started_at is not None

        for win_info in windows:
            result = RuleEngine.evaluate(rule, win_info, virt_bounds,
                                         active_step=active_step, base_dir=BASE_DIR)

            if not result.matched:
                continue

            # Potrivirea dintr-o fereastră acoperită nu se marchează: s-ar
            # desena peste fereastra din față.
            shown = visible_part(result, win_info["hwnd"])
            if shown is None:
                continue
            geometry, marks = shown

            # Prima potrivire: pornim cronometrul duratei de afișare.
            if started_at is None:
                self._rule_start_times[rule_id] = now
                elapsed = 0.0
                logger.info("[REGULĂ] '%s' declanșată pe '%s' — %s",
                            rule.get("name"), win_info["title"][:50], result.reason)

            if result.reason != self._last_reason.get(rule_id):
                self._last_reason[rule_id] = result.reason

            if sequence_done:
                return None

            # Durata de afișare se aplică doar regulilor fără succesiune.
            if not steps:
                duration = RuleEngine._as_float(
                    (rule.get("visual_cue") or {}).get("duration_sec", 0), 0.0)
                if duration > 0 and elapsed > duration:
                    return None

            if geometry is None:
                return None

            visual = dict(rule.get("visual_cue") or {})
            display_name = rule.get("name", "Regulă")
            if active_step:
                visual.update({k: v for k, v in (active_step.get("visual_cue") or {}).items()})
                for key in ("badge_text", "arrow_direction", "arrow_color"):
                    if key in active_step:
                        visual[key] = active_step[key]
                display_name = (f"{display_name} (Pas {active_step['step_index']}"
                                f"/{active_step['total_steps']}: {active_step.get('name', '')})")

            return {
                "rule_id": rule_id,
                "rule_name": display_name,
                "geometry": geometry,
                "visual_cue": visual,
                "window_title": win_info["title"],
                "anchor": result.anchor,
                # Regulile cu câmpuri și condiții pot marca mai multe locuri
                # simultan, fiecare cu propria formă și culoare.
                "marks": list(marks),
            }

        # Nicio fereastră nu se potrivește: cronometrul repornește la revenire.
        if rule_id in self._rule_start_times:
            del self._rule_start_times[rule_id]
        return None
