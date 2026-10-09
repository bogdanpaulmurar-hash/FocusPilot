"""
FocusPilot — Multi-Monitor Transparent Click-Through Overlay Engine
Afișează repere vizuale frapante (chenar roșu, săgeată indicatoare, badge de alertă)
pe oricare dintre cele 3 monitoare, fără a bloca mouse-ul sau tastatura (click-through).
"""

import sys
import math
import time
import logging
import tkinter as tk
from typing import Dict, Any, List, Optional, Tuple

import win32gui
import win32con
import win32api

logger = logging.getLogger(__name__)

# Culoare magică folosită drept cheie de transparență în Windows
TRANSPARENT_KEY_COLOR = "#000001"


class MultiScreenOverlay:
    """Fereastră transparentă click-through întinsă peste toate cele 3 monitoare."""

    def __init__(self):
        self.root: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.active_cues: List[Dict[str, Any]] = []

        self._pulse_phase = 0
        self._pulse_timer = None
        self._is_visible = False

        self._virt_x = 0
        self._virt_y = 0
        self._virt_w = 1920
        self._virt_h = 1080

    def init_overlay(self, master: tk.Tk) -> None:
        """Inițializează fereastra Toplevel pe master-ul Tkinter dat."""
        if self.root is not None:
            return

        self.root = tk.Toplevel(master)
        self.root.title("FocusPilot_Overlay_HUD")
        self.root.overrideredirect(True)

        # Măsurăm coordonatele tuturor celor 3 ecrane
        try:
            self._virt_x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            self._virt_y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            self._virt_w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            self._virt_h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        except Exception:
            self._virt_x, self._virt_y = 0, 0
            self._virt_w, self._virt_h = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        geo = f"{self._virt_w}x{self._virt_h}+{self._virt_x}+{self._virt_y}"
        self.root.geometry(geo)

        # Configurare transparență și TopMost
        self.root.configure(bg=TRANSPARENT_KEY_COLOR)
        try:
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY_COLOR)
        except Exception as exc:
            logger.warning(f"Transparentcolor neacceptat: {exc}")

        self.root.attributes("-topmost", True)

        # Canvas peste întreaga arie
        self.canvas = tk.Canvas(
            self.root,
            width=self._virt_w,
            height=self._virt_h,
            bg=TRANSPARENT_KEY_COLOR,
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Aplicăm stilurile Windows WS_EX_TRANSPARENT și WS_EX_LAYERED pentru click-through
        self._apply_click_through()

        # Pornim ciclul de pulsare animație
        self._start_pulse_loop()
        self.root.withdraw()

    def _apply_click_through(self) -> None:
        """Face fereastra invizibilă pentru mouse (toate click-urile trec prin ea direct la aplicație)."""
        if not self.root:
            return
        try:
            hwnd = int(self.root.frame(), 16)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            ex_style |= (win32con.WS_EX_TRANSPARENT | win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        except Exception as exc:
            logger.debug(f"Eroare setare click-through: {exc}")

    def update_cues(self, cues: List[Dict[str, Any]]) -> None:
        """Actualizează lista de repere vizuale de afișat (apelat din orice thread)."""
        if not self.root:
            return
        self.root.after(0, self._render_cues, cues)

    def _render_cues(self, cues: List[Dict[str, Any]]) -> None:
        """Desenează reperele vizuale pe canvas."""
        self.active_cues = cues
        if not self.canvas or not self.root:
            return

        self.canvas.delete("all")

        if not cues:
            if self._is_visible:
                self.root.withdraw()
                self._is_visible = False
            return

        if not self._is_visible:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self._apply_click_through()
            self._is_visible = True

        for cue in cues:
            self._draw_single_cue(cue)

    def _draw_single_cue(self, cue: Dict[str, Any]) -> None:
        """Desenează un reper vizual specific (chenar, săgeată, badge)."""
        geo = cue.get("geometry", (100, 100, 300, 60))
        gx, gy, gw, gh = geo

        # Conversie din coordonate ecran virtual în coordonate locale canvas
        cx = gx - self._virt_x
        cy = gy - self._virt_y

        visual = cue.get("visual_cue", {})
        pulse_active = visual.get("pulse_animation", True)
        pulse_offset = int(math.sin(self._pulse_phase) * 2) if pulse_active else 0

        # 1. Chenar Roșu / Evidențiere Câmp
        if visual.get("box_enabled", True):
            border_color = visual.get("border_color", "#FF0000")
            base_width = int(visual.get("border_width", 3))
            final_width = max(1, base_width + pulse_offset)

            # Desenăm dreptunghiul de evidențiere
            self.canvas.create_rectangle(
                cx, cy, cx + gw, cy + gh,
                outline=border_color,
                width=final_width
            )

            # Efect de dublu chenar (glow exterior)
            self.canvas.create_rectangle(
                cx - 3, cy - 3, cx + gw + 3, cy + gh + 3,
                outline=border_color,
                width=1
            )

        # 2. Săgeată Indicatoare (focalizare atenție)
        if visual.get("arrow_enabled", True):
            arrow_color = visual.get("arrow_color", "#FF0000")
            direction = visual.get("arrow_direction", "right")
            arrow_size = int(visual.get("arrow_size", 36))
            anim_shift = int(math.sin(self._pulse_phase * 2) * 6) if pulse_active else 0

            self._draw_arrow(cx, cy, gw, gh, direction, arrow_color, arrow_size, anim_shift)

        # 3. Badge Text / Avertizare (ex: "⚠️ MODIFICĂ ACUM!")
        if visual.get("badge_enabled", True):
            badge_text = visual.get("badge_text", "⚠️ ATENȚIE AICI!")
            badge_bg = visual.get("badge_bg", "#D90429")
            badge_fg = visual.get("badge_fg", "#FFFFFF")
            arrow_dir = visual.get("arrow_direction", "right") if visual.get("arrow_enabled", True) else "right"
            arrow_sz = int(visual.get("arrow_size", 36)) if visual.get("arrow_enabled", True) else 0

            self._draw_badge(cx, cy, gw, gh, badge_text, badge_bg, badge_fg, arrow_dir, arrow_sz)

    def _draw_arrow(self, x: int, y: int, w: int, h: int, direction: str, color: str, size: int, anim_shift: int) -> None:
        """Desenează o săgeată plină de atenționare cu vârf ascuțit."""
        if direction == "right":
            # Săgeata stă la stânga câmpului și indică spre dreapta (spre câmp)
            tip_x = x - 12 + anim_shift
            tip_y = y + (h // 2)
            tail_x = tip_x - size
            points = [
                tail_x, tip_y - (size // 4),
                tip_x - (size // 2), tip_y - (size // 4),
                tip_x - (size // 2), tip_y - (size // 2),
                tip_x, tip_y,
                tip_x - (size // 2), tip_y + (size // 2),
                tip_x - (size // 2), tip_y + (size // 4),
                tail_x, tip_y + (size // 4)
            ]
        elif direction == "down":
            # Săgeata stă deasupra și indică în jos spre câmp
            tip_x = x + (w // 2)
            tip_y = y - 12 + anim_shift
            tail_y = tip_y - size
            points = [
                tip_x - (size // 4), tail_y,
                tip_x - (size // 4), tip_y - (size // 2),
                tip_x - (size // 2), tip_y - (size // 2),
                tip_x, tip_y,
                tip_x + (size // 2), tip_y - (size // 2),
                tip_x + (size // 4), tip_y - (size // 2),
                tip_x + (size // 4), tail_y
            ]
        elif direction == "left":
            # Săgeata stă la dreapta câmpului și indică spre stânga (spre câmp)
            tip_x = x + w + 12 - anim_shift
            tip_y = y + (h // 2)
            tail_x = tip_x + size
            points = [
                tail_x, tip_y - (size // 4),
                tip_x + (size // 2), tip_y - (size // 4),
                tip_x + (size // 2), tip_y - (size // 2),
                tip_x, tip_y,
                tip_x + (size // 2), tip_y + (size // 2),
                tip_x + (size // 2), tip_y + (size // 4),
                tail_x, tip_y + (size // 4)
            ]
        else: # "up"
            # Săgeata stă sub câmp și indică în sus spre câmp
            tip_x = x + (w // 2)
            tip_y = y + h + 12 - anim_shift
            tail_y = tip_y + size
            points = [
                tip_x - (size // 4), tail_y,
                tip_x - (size // 4), tip_y + (size // 2),
                tip_x - (size // 2), tip_y + (size // 2),
                tip_x, tip_y,
                tip_x + (size // 2), tip_y + (size // 2),
                tip_x + (size // 4), tip_y + (size // 2),
                tip_x + (size // 4), tail_y
            ]

        self.canvas.create_polygon(points, fill=color, outline="#8B0000", width=1)

    def _draw_badge(self, x: int, y: int, w: int, h: int, text: str, bg_color: str, fg_color: str, arrow_dir: str = "right", arrow_sz: int = 0) -> None:
        """Desenează un badge etichetă elegant, evitând suprapunerea cu săgeata."""
        font = ("Segoe UI", 10, "bold")
        badge_h = 24
        pad_x = 10
        approx_w = max(100, len(text) * 8 + pad_x * 2)

        bx = x
        if arrow_dir == "down" and arrow_sz > 0:
            # Săgeata e deasupra câmpului -> punem badge-ul deasupra săgeții ca să nu se suprapună
            by = y - arrow_sz - badge_h - 18
        elif arrow_dir == "up" and arrow_sz > 0:
            # Săgeata e dedesubt -> punem badge-ul deasupra câmpului
            by = y - badge_h - 6
        else:
            by = y - badge_h - 6

        # Dacă depășește ecranul sus, îl coborâm dedesubt
        if by < 5:
            by = y + h + 8 + (arrow_sz if arrow_dir == "up" else 0)

        # Dreptunghi fundal cu colțuri
        self.canvas.create_rectangle(
            bx, by, bx + approx_w, by + badge_h,
            fill=bg_color, outline="#FFFFFF", width=1
        )
        self.canvas.create_text(
            bx + (approx_w // 2), by + (badge_h // 2),
            text=text, fill=fg_color, font=font
        )

    def _start_pulse_loop(self) -> None:
        """Ciclu de re-desenare pentru animația de pulsare continuă."""
        self._pulse_phase += 0.35
        if self._is_visible and self.active_cues:
            self._render_cues(self.active_cues)
        if self.root:
            self._pulse_timer = self.root.after(80, self._start_pulse_loop)
