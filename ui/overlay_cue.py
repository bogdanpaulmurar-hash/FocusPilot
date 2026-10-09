"""
FocusPilot — Multi-Monitor SilkTest-Style Frame Border & Indicator Overlay
Înlocuiește transparența defectuoasă DWM cu 4 ferestre TopMost opace de tip bară solidă (Chenar SilkTest)
și ferestre opace pentru săgeată și badge. 100% vizibil peste orice aplicație cu accelerare hardware GPU!
"""

import math
import logging
import tkinter as tk
from typing import Dict, Any, List, Optional, Tuple

import win32gui
import win32con
import win32api

logger = logging.getLogger(__name__)


class MultiScreenOverlay:
    """Sistem de evidențiere tip SilkTest format din ferestre opace TopMost click-through."""

    def __init__(self):
        self.master: Optional[tk.Tk] = None
        self.root: Optional[tk.Tk] = None
        self.active_cues: List[Dict[str, Any]] = []

        # 4 ferestre opace pentru chenar (Top, Bottom, Left, Right)
        self.bar_top: Optional[tk.Toplevel] = None
        self.bar_bottom: Optional[tk.Toplevel] = None
        self.bar_left: Optional[tk.Toplevel] = None
        self.bar_right: Optional[tk.Toplevel] = None
        self.bars: List[tk.Toplevel] = []

        # Fereastră opacă pentru Badge text
        self.badge_win: Optional[tk.Toplevel] = None
        self.badge_lbl: Optional[tk.Label] = None

        # Fereastră opacă pentru Săgeată
        self.arrow_win: Optional[tk.Toplevel] = None
        self.arrow_canvas: Optional[tk.Canvas] = None

        self._pulse_phase = 0
        self._pulse_timer = None
        self._is_visible = False

    def init_overlay(self, master: tk.Tk) -> None:
        """Inițializează componentele vizuale opace."""
        self.master = master
        self.root = master

        # 1. Creare 4 bare pentru chenar
        self.bars = []
        for name in ["top", "bottom", "left", "right"]:
            bar = tk.Toplevel(master)
            bar.title(f"FocusPilot_Bar_{name}")
            bar.overrideredirect(True)
            bar.attributes("-topmost", True)
            bar.configure(bg="#FF0000")
            bar.withdraw()
            self.bars.append(bar)

        self.bar_top, self.bar_bottom, self.bar_left, self.bar_right = self.bars

        # 2. Fereastră Badge
        self.badge_win = tk.Toplevel(master)
        self.badge_win.title("FocusPilot_Badge")
        self.badge_win.overrideredirect(True)
        self.badge_win.attributes("-topmost", True)
        self.badge_win.configure(bg="#D90429", padx=8, pady=4)
        self.badge_lbl = tk.Label(
            self.badge_win, text="", font=("Segoe UI", 10, "bold"),
            bg="#D90429", fg="#FFFFFF"
        )
        self.badge_lbl.pack()
        self.badge_win.withdraw()

        # 3. Fereastră Săgeată
        self.arrow_win = tk.Toplevel(master)
        self.arrow_win.title("FocusPilot_Arrow")
        self.arrow_win.overrideredirect(True)
        self.arrow_win.attributes("-topmost", True)
        self.arrow_win.configure(bg="#000001")
        try:
            self.arrow_win.attributes("-transparentcolor", "#000001")
        except Exception:
            pass
        self.arrow_canvas = tk.Canvas(self.arrow_win, bg="#000001", highlightthickness=0)
        self.arrow_canvas.pack(fill=tk.BOTH, expand=True)
        self.arrow_win.withdraw()

        # Aplicăm stil click-through pe toate elementele
        for w in self.bars + [self.badge_win, self.arrow_win]:
            self._apply_click_through(w)

        self._start_pulse_loop()

    def _apply_click_through(self, toplevel: tk.Toplevel) -> None:
        """Face fereastra transparentă la click-uri de mouse (click trece direct la aplicație)."""
        try:
            hwnd = int(toplevel.frame(), 16)
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW)
        except Exception as exc:
            logger.debug(f"Click-through note: {exc}")

    def update_cues(self, cues: List[Dict[str, Any]]) -> None:
        """Primește reperele de afișat și actualizează în firul principal."""
        if not self.master:
            return
        self.master.after(0, self._render_cues, cues)

    def _render_cues(self, cues: List[Dict[str, Any]]) -> None:
        self.active_cues = cues

        if not cues:
            if self._is_visible:
                for b in self.bars:
                    b.withdraw()
                if self.badge_win:
                    self.badge_win.withdraw()
                if self.arrow_win:
                    self.arrow_win.withdraw()
                self._is_visible = False
                logger.info("[OVERLAY] Repere ascunse.")
            return

        cue = cues[0]
        geo = cue.get("geometry", (300, 300, 350, 60))
        gx, gy, gw, gh = geo

        visual = cue.get("visual_cue", {})
        border_col = visual.get("border_color", "#FF0000")
        thickness = int(visual.get("border_width", 4))
        pulse_add = int(math.sin(self._pulse_phase) * 2) if visual.get("pulse_animation", True) else 0
        t = max(2, thickness + pulse_add)

        # 1. Poziționare cele 4 bare (Chenar Opaque Solid)
        if visual.get("box_enabled", True):
            for b in self.bars:
                b.configure(bg=border_col)

            # Top bar
            self.bar_top.geometry(f"{gw}x{t}+{gx}+{gy}")
            # Bottom bar
            self.bar_bottom.geometry(f"{gw}x{t}+{gx}+{gy + gh - t}")
            # Left bar
            self.bar_left.geometry(f"{t}x{gh}+{gx}+{gy}")
            # Right bar
            self.bar_right.geometry(f"{t}x{gh}+{gx + gw - t}+{gy}")

            for b in self.bars:
                b.deiconify()
                b.lift()
                b.attributes("-topmost", True)
                self._apply_click_through(b)
        else:
            for b in self.bars:
                b.withdraw()

        # 2. Poziționare Badge Text
        if visual.get("badge_enabled", True):
            badge_text = visual.get("badge_text", "⚠️ MODIFICĂ AICI!")
            badge_bg = visual.get("badge_bg", "#D90429")
            badge_fg = visual.get("badge_fg", "#FFFFFF")

            self.badge_win.configure(bg=badge_bg)
            self.badge_lbl.configure(text=badge_text, bg=badge_bg, fg=badge_fg)

            by = gy - 32
            if by < 10:
                by = gy + gh + 10
            self.badge_win.geometry(f"+{gx}+{by}")
            self.badge_win.deiconify()
            self.badge_win.lift()
            self.badge_win.attributes("-topmost", True)
            self._apply_click_through(self.badge_win)
        else:
            if self.badge_win:
                self.badge_win.withdraw()

        # 3. Poziționare Săgeată
        if visual.get("arrow_enabled", True):
            arr_dir = visual.get("arrow_direction", "up")
            arr_col = visual.get("arrow_color", "#FF0000")
            arr_sz = int(visual.get("arrow_size", 36))
            anim_offset = int(math.sin(self._pulse_phase * 2) * 5)

            if arr_dir == "up":
                aw = arr_sz + 8
                ah = arr_sz + 8
                ax = gx + (gw // 2) - (aw // 2)
                ay = gy + gh + 4 + anim_offset
                pts = [aw // 2, 4, 4, ah - 4, (aw // 2) - 4, ah - 12, (aw // 2) - 4, ah - 2, (aw // 2) + 4, ah - 2, (aw // 2) + 4, ah - 12, aw - 4, ah - 4]
            elif arr_dir == "down":
                aw = arr_sz + 8
                ah = arr_sz + 8
                ax = gx + (gw // 2) - (aw // 2)
                ay = gy - ah - 4 - anim_offset
                pts = [4, 4, (aw // 2) - 4, 12, (aw // 2) - 4, 2, (aw // 2) + 4, 2, (aw // 2) + 4, 12, aw - 4, 4, aw // 2, ah - 4]
            elif arr_dir == "right":
                aw = arr_sz + 8
                ah = arr_sz + 8
                ax = gx - aw - 4 - anim_offset
                ay = gy + (gh // 2) - (ah // 2)
                pts = [4, 4, ah // 2, 4, ah - 4, aw // 2, ah // 2, aw - 4, 4, aw - 4]
            else: # left
                aw = arr_sz + 8
                ah = arr_sz + 8
                ax = gx + gw + 4 + anim_offset
                ay = gy + (gh // 2) - (ah // 2)
                pts = [aw - 4, 4, aw - 4, ah - 4, 4, ah // 2]

            self.arrow_win.geometry(f"{aw}x{ah}+{ax}+{ay}")
            self.arrow_canvas.delete("all")
            # Desenăm conturul ascuțit al săgeții
            if arr_dir == "up":
                triangle = [aw // 2, 2, 4, ah - 4, aw - 4, ah - 4]
            elif arr_dir == "down":
                triangle = [4, 4, aw - 4, 4, aw // 2, ah - 2]
            elif arr_dir == "right":
                triangle = [4, 4, aw - 2, ah // 2, 4, ah - 4]
            else: # left
                triangle = [aw - 4, 4, aw - 4, ah - 4, 2, ah // 2]

            self.arrow_canvas.create_polygon(triangle, fill=arr_col, outline="#8B0000", width=2)
            self.arrow_win.deiconify()
            self.arrow_win.lift()
            self.arrow_win.attributes("-topmost", True)
            self._apply_click_through(self.arrow_win)
        else:
            if self.arrow_win:
                self.arrow_win.withdraw()

        self._is_visible = True
        logger.info(f"[OVERLAY FRAME-BORDER] Bare opace afișate cu succes la coordonatele ({gx}, {gy}, {gw}, {gh}).")

    def _start_pulse_loop(self) -> None:
        self._pulse_phase += 0.35
        if self._is_visible and self.active_cues:
            self._render_cues(self.active_cues)
        if self.master:
            self._pulse_timer = self.master.after(90, self._start_pulse_loop)
