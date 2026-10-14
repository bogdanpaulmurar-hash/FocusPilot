"""
FocusPilot — Selector interactiv de pe ecran

Două moduri de lucru:

  ZONĂ (implicit)  Tragi un dreptunghi peste zona dorită. Se întorc
                   coordonatele absolute și relative la fereastră, plus o
                   captură a zonei pentru urmărirea prin șablon imagine.

  PUNCT            Un singur clic pe o valoare din ecran. Se întorc
                   coordonatele punctului și, dacă UI Automation e disponibil,
                   textul elementului de sub cursor — ca să vezi imediat ce
                   valoare va citi câmpul.

În ambele moduri se identifică fereastra reală de sub selecție parcurgând
ordinea Z a ferestrelor Windows, ignorând ferestrele proprii FocusPilot.
Coordonatele mouse-ului se afișează în timp real, pentru alinierea fină.
"""

import logging
import tkinter as tk
from typing import Dict, Any, Optional, Callable, Tuple

import win32gui
import win32api
import win32con

logger = logging.getLogger(__name__)

# Ferestrele proprii nu trebuie confundate cu ținta.
OWN_WINDOW_TITLES = (
    "FocusPilot_Picker", "FocusPilot_Shape", "FocusPilot_Bar",
    "FocusPilot_Badge", "FocusPilot_Arrow", "FocusPilot_Overlay_HUD",
)
SYSTEM_WINDOW_TITLES = ("Program Manager", "Windows Input Experience",
                        "Default IME", "MSCTFIME UI")

MIN_SELECTION = 6          # sub atât, o tragere e de fapt un clic


class InteractivePicker:
    """Overlay de selecție cu reticul, dreptunghi și coordonate live."""

    def __init__(self, master: tk.Misc, on_picked: Callable[[Dict[str, Any]], None],
                 on_cancel: Optional[Callable[[], None]] = None,
                 mode: str = "region"):
        """
        `mode`:
            "region" — tragere de dreptunghi (pentru chenare și șabloane)
            "point"  — un clic (pentru câmpuri localizate prin coordonate fixe)
        """
        self.master = master
        self.on_picked = on_picked
        self.on_cancel = on_cancel
        self.mode = mode if mode in ("region", "point") else "region"

        self.overlay: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None

        self.start_x = 0
        self.start_y = 0
        self._rect_id = None
        self._readout_id = None
        self._readout_bg = None
        self._finished = False

        self._virt_x = 0
        self._virt_y = 0
        self._virt_w = 1920
        self._virt_h = 1080

    # ── Pornire ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._read_virtual_bounds()

        self.overlay = tk.Toplevel(self.master)
        self.overlay.title("FocusPilot_Picker")
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.30)
        self.overlay.config(cursor="crosshair")
        self.overlay.geometry(f"{self._virt_w}x{self._virt_h}"
                              f"+{self._virt_x}+{self._virt_y}")

        self.canvas = tk.Canvas(self.overlay, width=self._virt_w,
                                height=self._virt_h, bg="#001824",
                                highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._draw_instructions()
        self._bind_events()

        self.overlay.update()
        try:
            self.overlay.grab_set()
        except Exception:
            pass
        self.overlay.focus_force()

    def _read_virtual_bounds(self) -> None:
        try:
            self._virt_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            self._virt_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            self._virt_w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            self._virt_h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        except Exception:
            self._virt_x, self._virt_y = 0, 0
            self._virt_w = win32api.GetSystemMetrics(0)
            self._virt_h = win32api.GetSystemMetrics(1)

    def _draw_instructions(self) -> None:
        text = ("🎯 Clic pe valoarea dorită   |   [ESC] Anulare"
                if self.mode == "point" else
                "🎯 Trageți un dreptunghi peste zona dorită   |   [ESC] Anulare")
        cx, cy = self._virt_w // 2, 50
        self.canvas.create_rectangle(cx - 340, cy - 25, cx + 340, cy + 25,
                                     fill="#00646E", outline="#00A3A6", width=2)
        self.canvas.create_text(cx, cy, text=text, fill="#FFFFFF",
                                font=("Segoe UI", 11, "bold"))

    def _bind_events(self) -> None:
        for widget in (self.canvas, self.overlay):
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Motion>", self._on_move)
            widget.bind("<Escape>", lambda _e: self.cancel())
        self.overlay.bind_all("<Escape>", lambda _e: self.cancel())

    # ── Coordonate live ──────────────────────────────────────────────────────

    def _on_move(self, event) -> None:
        """Afișează coordonatele absolute lângă cursor, pentru aliniere fină."""
        self._show_readout(event.x, event.y,
                           f"X: {event.x + self._virt_x}   Y: {event.y + self._virt_y}")

    def _show_readout(self, x: int, y: int, text: str) -> None:
        if not self.canvas:
            return
        if self._readout_id is not None:
            self.canvas.delete(self._readout_id)
        if self._readout_bg is not None:
            self.canvas.delete(self._readout_bg)

        # Eticheta stă lângă cursor, dar se mută ca să nu iasă din ecran.
        label_x = x + 18
        label_y = y + 18
        if label_x > self._virt_w - 190:
            label_x = x - 190
        if label_y > self._virt_h - 40:
            label_y = y - 40

        self._readout_bg = self.canvas.create_rectangle(
            label_x - 6, label_y - 12, label_x + 176, label_y + 12,
            fill="#0B2027", outline="#00A3A6", width=1)
        self._readout_id = self.canvas.create_text(
            label_x, label_y, text=text, anchor="w",
            fill="#8FE3E6", font=("Consolas", 10, "bold"))

    # ── Selecție ─────────────────────────────────────────────────────────────

    def _on_press(self, event) -> None:
        self.start_x, self.start_y = event.x, event.y
        if self._rect_id:
            self.canvas.delete(self._rect_id)
            self._rect_id = None
        if self.mode == "region":
            self._rect_id = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline="#EB780A", fill="#EB780A", width=3, stipple="gray25")

    def _on_drag(self, event) -> None:
        if self._rect_id:
            self.canvas.coords(self._rect_id, self.start_x, self.start_y,
                               event.x, event.y)
        width = abs(event.x - self.start_x)
        height = abs(event.y - self.start_y)
        self._show_readout(event.x, event.y, f"{width} x {height} px")

    def _on_release(self, event) -> None:
        if self._finished:
            return
        self._finished = True

        if self.mode == "point" or (abs(event.x - self.start_x) < MIN_SELECTION
                                    and abs(event.y - self.start_y) < MIN_SELECTION):
            self._finish_point(event.x, event.y)
        else:
            self._finish_region(event.x, event.y)

    # ── Rezultat: un punct ───────────────────────────────────────────────────

    def _finish_point(self, canvas_x: int, canvas_y: int) -> None:
        abs_x = canvas_x + self._virt_x
        abs_y = canvas_y + self._virt_y

        hwnd = self._window_under((abs_x, abs_y))
        title, process, rect = self._window_details(hwnd, (abs_x, abs_y, 1, 1))
        self._cleanup()

        # Textul de sub punct, ca utilizatorul să vadă imediat ce va citi
        # câmpul. Fără el ar trebui să salveze regula și să o testeze ca să afle.
        value, value_rect = self._read_text_at(hwnd, abs_x, abs_y)

        left, top, right, bottom = rect
        win_w = max(50, right - left)
        win_h = max(50, bottom - top)

        self.on_picked({
            "pick_mode": "point",
            "window_title": title,
            "process_name": process,
            "window_rect": rect,
            "abs_x": abs_x,
            "abs_y": abs_y,
            "rel_x": round(max(0.0, min(1.0, (abs_x - left) / win_w)), 4),
            "rel_y": round(max(0.0, min(1.0, (abs_y - top) / win_h)), 4),
            "width": value_rect[2] if value_rect else 200,
            "height": value_rect[3] if value_rect else 26,
            "value_preview": value,
            "value_rect": value_rect,
            "snip_path": "",
        })

    def _read_text_at(self, hwnd: Optional[int], x: int, y: int):
        """(text, dreptunghi) al elementului de sub punct, prin UI Automation."""
        if not hwnd:
            return "", None
        try:
            from core.rule_engine import capture_window_text
            from core.probe_engine import read_probe

            snapshot = capture_window_text(hwnd, force=True)
            if snapshot is None:
                return "", None
            reading = read_probe({"name": "previzualizare",
                                  "locator": {"kind": "screen_point", "x": x, "y": y}},
                                 snapshot, (0, 0, 0, 0))
            return (reading.value or ""), reading.rect
        except Exception as exc:
            logger.debug("Citirea textului de sub punct a eșuat: %s", exc)
            return "", None

    # ── Rezultat: o zonă ─────────────────────────────────────────────────────

    def _finish_region(self, end_x: int, end_y: int) -> None:
        x1 = min(self.start_x, end_x) + self._virt_x
        y1 = min(self.start_y, end_y) + self._virt_y
        x2 = max(self.start_x, end_x) + self._virt_x
        y2 = max(self.start_y, end_y) + self._virt_y
        width = max(20, x2 - x1)
        height = max(20, y2 - y1)

        center = (x1 + width // 2, y1 + height // 2)
        hwnd = self._window_under(center)
        title, process, rect = self._window_details(hwnd, (x1, y1, x1 + width,
                                                           y1 + height))
        self._cleanup()

        left, top, right, bottom = rect
        win_w = max(50, right - left)
        win_h = max(50, bottom - top)

        self.on_picked({
            "pick_mode": "region",
            "window_title": title,
            "process_name": process,
            "window_rect": rect,
            "abs_x": x1,
            "abs_y": y1,
            "width": width,
            "height": height,
            "rel_x": round(max(0.0, min(1.0, (x1 - left) / win_w)), 4),
            "rel_y": round(max(0.0, min(1.0, (y1 - top) / win_h)), 4),
            "rel_w": round(max(0.02, min(1.0, width / win_w)), 4),
            "rel_h": round(max(0.02, min(1.0, height / win_h)), 4),
            "snip_path": self._save_snip(x1, y1, width, height),
        })

    def _save_snip(self, x: int, y: int, width: int, height: int) -> str:
        """Captură a zonei, pentru urmărirea prin șablon imagine."""
        try:
            import os
            import time
            import pyautogui

            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            folder = os.path.join(base_dir, "assets", "rules")
            os.makedirs(folder, exist_ok=True)
            filename = f"snip_{int(time.time() * 1000)}.png"

            # Pauză necesară: compozitorul DWM trebuie să șteargă complet
            # overlay-ul de selecție, altfel tenta lui albastră intră în captură.
            time.sleep(0.22)
            pyautogui.screenshot(region=(x, y, width, height)).save(
                os.path.join(folder, filename))

            relative = os.path.join("assets", "rules", filename).replace("\\", "/")
            logger.info("[SELECTOR] Șablon salvat: %s", relative)
            return relative
        except Exception as exc:
            logger.warning("[SELECTOR] Salvarea șablonului a eșuat: %s", exc)
            return ""

    # ── Identificarea ferestrei ──────────────────────────────────────────────

    def _window_under(self, point: Tuple[int, int]) -> Optional[int]:
        """Fereastra reală de sub punct, ignorând ferestrele proprii FocusPilot."""
        own_hwnd = None
        if self.overlay is not None:
            try:
                own_hwnd = int(self.overlay.frame(), 16)
            except Exception:
                try:
                    own_hwnd = self.overlay.winfo_id()
                except Exception:
                    own_hwnd = None

        try:
            current = win32gui.GetTopWindow(None)
        except Exception:
            return None

        while current:
            try:
                if current != own_hwnd and win32gui.IsWindowVisible(current):
                    title = win32gui.GetWindowText(current)
                    if title and not self._is_own_or_system(title):
                        left, top, right, bottom = win32gui.GetWindowRect(current)
                        if left <= point[0] <= right and top <= point[1] <= bottom:
                            return current
                current = win32gui.GetWindow(current, win32con.GW_HWNDNEXT)
            except Exception:
                break
        return None

    @staticmethod
    def _is_own_or_system(title: str) -> bool:
        return (any(title.startswith(name) for name in OWN_WINDOW_TITLES)
                or title in SYSTEM_WINDOW_TITLES)

    def _window_details(self, hwnd: Optional[int], fallback_rect):
        """(titlu, proces, dreptunghi) pentru fereastra găsită."""
        if hwnd and win32gui.IsWindow(hwnd):
            try:
                return (win32gui.GetWindowText(hwnd),
                        self._process_name(hwnd),
                        win32gui.GetWindowRect(hwnd))
            except Exception:
                pass
        return ("", "", fallback_rect)

    @staticmethod
    def _process_name(hwnd: int) -> str:
        try:
            from core.monitor_engine import get_process_name_native
            import win32process
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return get_process_name_native(pid)
        except Exception:
            return ""

    # ── Închidere ────────────────────────────────────────────────────────────

    def cancel(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._cleanup()
        if self.on_cancel:
            self.on_cancel()

    def _cleanup(self) -> None:
        if not self.overlay:
            return
        try:
            self.overlay.unbind_all("<Escape>")
        except Exception:
            pass
        try:
            self.overlay.grab_release()
        except Exception:
            pass
        try:
            self.overlay.destroy()
        except Exception:
            pass
        self.overlay = None
        self.canvas = None
        try:
            if self.master:
                self.master.update_idletasks()
        except Exception:
            pass
