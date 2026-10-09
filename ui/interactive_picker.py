"""
FocusPilot — Interactive On-Screen Area & Window Picker
Permite utilizatorului să selecteze interactiv o zonă de pe oricare dintre cele 3 monitoare
sau să facă clic pe o fereastră pentru a-i captura automat titlul, procesul și coordonatele.
"""

import logging
import tkinter as tk
from typing import Dict, Any, Optional, Callable, Tuple

import win32gui
import win32api
import win32con

logger = logging.getLogger(__name__)


class InteractivePicker:
    """Overlay de selecție ecran cu reticul (crosshair) și dreptunghi de selecție."""

    def __init__(self, master: tk.Tk, on_picked: Callable[[Dict[str, Any]], None], on_cancel: Optional[Callable[[], None]] = None):
        self.master = master
        self.on_picked = on_picked
        self.on_cancel = on_cancel

        self.overlay: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None

        self.start_x = 0
        self.start_y = 0
        self.current_rect = None

        self._virt_x = 0
        self._virt_y = 0
        self._virt_w = 1920
        self._virt_h = 1080

    def start(self) -> None:
        """Pornește sesiunea de selecție pe ecran."""
        try:
            self._virt_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            self._virt_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            self._virt_w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            self._virt_h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        except Exception:
            self._virt_x, self._virt_y = 0, 0
            self._virt_w, self._virt_h = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        self.overlay = tk.Toplevel(self.master)
        self.overlay.title("FocusPilot_Picker")
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.attributes("-alpha", 0.30)
        self.overlay.config(cursor="crosshair")

        geo = f"{self._virt_w}x{self._virt_h}+{self._virt_x}+{self._virt_y}"
        self.overlay.geometry(geo)

        self.canvas = tk.Canvas(
            self.overlay,
            width=self._virt_w,
            height=self._virt_h,
            bg="#001824",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Mesaj informativ centrat pe monitorul principal
        info_x = self._virt_w // 2
        info_y = 50
        self.canvas.create_rectangle(
            info_x - 320, info_y - 25, info_x + 320, info_y + 25,
            fill="#00646E", outline="#00A3A6", width=2
        )
        self.canvas.create_text(
            info_x, info_y,
            text="🎯 Trageți un dreptunghi cu mouse-ul peste câmpul dorit  |  [ESC] Anulare",
            fill="#FFFFFF",
            font=("Segoe UI", 11, "bold")
        )

        self.canvas.bind("<ButtonPress-1>", self._on_button_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_up)

        # Asigurăm prinderea tastelor Escape și tastelor generale
        self.overlay.bind_all("<Escape>", lambda e: self.cancel())
        self.overlay.bind("<Escape>", lambda e: self.cancel())
        self.canvas.bind("<Escape>", lambda e: self.cancel())

        self.overlay.focus_force()

    def _on_button_down(self, event) -> None:
        self.start_x = event.x
        self.start_y = event.y
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        self.current_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#EB780A", fill="#EB780A", width=3, stipple="gray25"
        )

    def _on_mouse_move(self, event) -> None:
        if self.current_rect:
            self.canvas.coords(self.current_rect, self.start_x, self.start_y, event.x, event.y)

    def _on_button_up(self, event) -> None:
        end_x = event.x
        end_y = event.y

        # Calculăm dreptunghiul în coordonate virtuale
        x1 = min(self.start_x, end_x) + self._virt_x
        y1 = min(self.start_y, end_y) + self._virt_y
        x2 = max(self.start_x, end_x) + self._virt_x
        y2 = max(self.start_y, end_y) + self._virt_y
        w = max(20, x2 - x1)
        h = max(20, y2 - y1)

        # Detectăm fereastra de sub punctul de clic folosind Win32
        click_screen_pt = (x1, y1)
        hwnd = win32gui.WindowFromPoint(click_screen_pt)
        # Obținem fereastra rădăcină (top-level)
        root_hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
        if not root_hwnd:
            root_hwnd = hwnd

        win_title = win32gui.GetWindowText(root_hwnd)
        win_rect = win32gui.GetWindowRect(root_hwnd) # (left, top, right, bottom)
        wl, wt, wr, wb = win_rect
        ww = max(100, wr - wl)
        wh = max(100, wb - wt)

        # Calculăm coordonate relative la fereastră
        rel_x = round(max(0.0, min(1.0, (x1 - wl) / ww)), 3)
        rel_y = round(max(0.0, min(1.0, (y1 - wt) / wh)), 3)

        result_data = {
            "window_title": win_title,
            "window_rect": win_rect,
            "abs_x": x1,
            "abs_y": y1,
            "width": w,
            "height": h,
            "rel_x": rel_x,
            "rel_y": rel_y
        }

        self._cleanup()
        self.on_picked(result_data)

    def cancel(self) -> None:
        self._cleanup()
        if self.on_cancel:
            self.on_cancel()

    def _cleanup(self) -> None:
        if self.overlay:
            try:
                self.overlay.unbind_all("<Escape>")
            except Exception:
                pass
            self.overlay.destroy()
            self.overlay = None
            self.canvas = None
