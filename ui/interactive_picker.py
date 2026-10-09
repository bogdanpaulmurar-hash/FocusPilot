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

        self.overlay.bind("<ButtonPress-1>", self._on_button_down)
        self.overlay.bind("<B1-Motion>", self._on_mouse_move)
        self.overlay.bind("<ButtonRelease-1>", self._on_button_up)

        # Asigurăm prinderea tastelor Escape și tastelor generale
        self.overlay.bind_all("<Escape>", lambda e: self.cancel())
        self.overlay.bind("<Escape>", lambda e: self.cancel())
        self.canvas.bind("<Escape>", lambda e: self.cancel())

        # Grab pe picker pentru a garanta că primește toate evenimentele de mouse
        self.overlay.update()
        try:
            self.overlay.grab_set()
        except Exception:
            pass
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

        # Găsim fereastra reală de sub punctul selectat parcurgând Z-Order-ul Windows,
        # excluzând fereastra noastră de selecție (FocusPilot_Picker) și Overlay-ul!
        my_overlay_hwnd = None
        if self.overlay:
            try:
                my_overlay_hwnd = int(self.overlay.frame(), 16)
            except Exception:
                my_overlay_hwnd = self.overlay.winfo_id()

        center_pt = (x1 + (w // 2), y1 + (h // 2))
        real_hwnd = self._find_real_window_under_point(center_pt, my_overlay_hwnd)

        win_title = ""
        proc_name = ""
        win_rect = (x1, y1, x1 + w, y1 + h)

        if real_hwnd and win32gui.IsWindow(real_hwnd):
            win_title = win32gui.GetWindowText(real_hwnd)
            win_rect = win32gui.GetWindowRect(real_hwnd)
            proc_name = self._get_process_name_for_hwnd(real_hwnd)

        wl, wt, wr, wb = win_rect
        ww = max(50, wr - wl)
        wh = max(50, wb - wt)

        # Calculăm coordonate relative la fereastra reală capturată
        rel_x = round(max(0.0, min(1.0, (x1 - wl) / ww)), 3)
        rel_y = round(max(0.0, min(1.0, (y1 - wt) / wh)), 3)
        rel_w = round(max(0.02, min(1.0, w / ww)), 3)
        rel_h = round(max(0.02, min(1.0, h / wh)), 3)

        self._cleanup()

        # Salvăm un crop (snip) curat al zonei selectate pentru urmărire la scroll
        snip_rel_path = ""
        try:
            import pyautogui, time, os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            snip_dir = os.path.join(base_dir, "assets", "rules")
            os.makedirs(snip_dir, exist_ok=True)
            snip_filename = f"snip_{int(time.time()*1000)}.png"
            snip_full_path = os.path.join(snip_dir, snip_filename)
            # Pauză esențială pentru ca Windows DWM compositor să șteargă orice urmă vizuală a picker-ului
            time.sleep(0.18)
            crop_img = pyautogui.screenshot(region=(x1, y1, w, h))
            crop_img.save(snip_full_path)
            snip_rel_path = os.path.join("assets", "rules", snip_filename).replace("\\", "/")
            logger.info(f"[PICKER] Snip salvat pentru urmărire vizuală: {snip_rel_path}")
        except Exception as e:
            logger.warning(f"[PICKER] Salvare snip eșuată: {e}")

        result_data = {
            "window_title": win_title,
            "process_name": proc_name,
            "window_rect": win_rect,
            "abs_x": x1,
            "abs_y": y1,
            "width": w,
            "height": h,
            "rel_x": rel_x,
            "rel_y": rel_y,
            "rel_w": rel_w,
            "rel_h": rel_h,
            "snip_path": snip_rel_path
        }

        self.on_picked(result_data)

    def _find_real_window_under_point(self, pt: Tuple[int, int], exclude_hwnd: Optional[int]) -> Optional[int]:
        """Găsește fereastra de aplicație reală aflată sub punctul de ecran, ignorând overlay-urile proprii."""
        cur = win32gui.GetTopWindow(None)
        exclude_titles = [
            "FocusPilot_Picker", "FocusPilot_Overlay_HUD", "Program Manager",
            "Windows Input Experience", "Default IME", "MSCTFIME UI"
        ]
        while cur:
            if cur != exclude_hwnd and win32gui.IsWindowVisible(cur):
                txt = win32gui.GetWindowText(cur)
                if txt and not any(ign in txt for ign in exclude_titles):
                    l, t, r, b = win32gui.GetWindowRect(cur)
                    if l <= pt[0] <= r and t <= pt[1] <= b:
                        return cur
            cur = win32gui.GetWindow(cur, win32con.GW_HWNDNEXT)
        return None

    def _get_process_name_for_hwnd(self, hwnd: int) -> str:
        """Obține numele executabilului asociat ferestrei date."""
        try:
            import win32process
            import ctypes
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                buf = ctypes.create_unicode_buffer(1024)
                sz = ctypes.c_ulong(1024)
                ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
                ctypes.windll.kernel32.CloseHandle(h)
                import os
                return os.path.basename(buf.value).lower()
        except Exception:
            pass
        return ""

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
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None
            self.canvas = None
            try:
                if self.parent:
                    self.parent.update_idletasks()
                    self.parent.update()
            except Exception:
                pass
