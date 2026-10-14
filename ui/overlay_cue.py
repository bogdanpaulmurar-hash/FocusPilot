"""
FocusPilot — Solid Frame Border Overlay

Desenează reperele vizuale ca ferestre opace TopMost: patru bare pentru chenar,
o fereastră pentru săgeată și una pentru badge. Ferestrele opace rămân vizibile
peste suprafețele accelerate GPU din Chrome și Edge, unde transparența DWM nu
este redată corect.

Două proprietăți sunt esențiale și erau incomplete:

1. CLICK-THROUGH. `WS_EX_TRANSPARENT` singur nu e suficient pe Windows: pentru
   ca testarea la click să fie ignorată, fereastra trebuie să fie și
   `WS_EX_LAYERED`. Fără el barele interceptau click-urile utilizatorului.

2. FĂRĂ FURT DE FOCUS. Se adaugă `WS_EX_NOACTIVATE`, iar bucla de animație nu
   mai apelează `deiconify()` / `lift()` / `focus`. Varianta anterioară
   reaplica aceste operații la fiecare 90 ms pe șase ferestre, ceea ce muta
   focusul de la câmpul în care scria utilizatorul și producea pâlpâire.
"""

import math
import ctypes
import logging
import tkinter as tk
from typing import Dict, Any, List, Optional, Tuple

import win32gui
import win32con

logger = logging.getLogger(__name__)

# Cadența animației de pulsare. Mai rar decât cele 90 ms anterioare: la fiecare
# tic se repoziționau șase ferestre, ceea ce încărca inutil firul de interfață.
PULSE_INTERVAL_MS = 140

# Culoarea folosită ca „transparent” în fereastra săgeții. Aproape negru, ca să
# nu coincidă cu o culoare pe care utilizatorul ar alege-o pentru săgeată.
ARROW_CHROMA = "#000001"

LWA_ALPHA = 0x00000002
MAX_CUES = 6          # câte repere pot fi afișate simultan


def _hwnd_of(widget: tk.Misc) -> Optional[int]:
    """HWND-ul real al unei ferestre Tk."""
    try:
        return int(widget.frame(), 16)
    except Exception:
        try:
            return widget.winfo_id()
        except Exception:
            return None


def _make_click_through(widget: tk.Misc, already_layered: bool = False) -> None:
    """
    Face fereastra invizibilă la mouse și incapabilă să preia focusul.

    `already_layered` e True pentru ferestrele cărora Tk le-a aplicat deja
    `-transparentcolor`: acolo nu rescriem atributele de strat, ca să nu
    pierdem culoarea-cheie.
    """
    hwnd = _hwnd_of(widget)
    if not hwnd:
        return
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        style |= (win32con.WS_EX_LAYERED      # necesar ca WS_EX_TRANSPARENT să aibă efect
                  | win32con.WS_EX_TRANSPARENT
                  | win32con.WS_EX_TOOLWINDOW  # fără buton în bara de activități
                  | win32con.WS_EX_NOACTIVATE)  # nu fură focusul niciodată
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style)

        if not already_layered:
            # O fereastră layered nu se redă până nu i se setează atributele.
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    except Exception as exc:
        logger.debug("Aplicarea stilului click-through a eșuat: %s", exc)


class _CueWindows:
    """Setul de ferestre care desenează UN reper: chenar, badge, săgeată."""

    def __init__(self, master: tk.Misc):
        self.bars: List[tk.Toplevel] = []
        for side in ("top", "bottom", "left", "right"):
            bar = tk.Toplevel(master)
            bar.title(f"FocusPilot_Bar_{side}")
            bar.overrideredirect(True)
            bar.attributes("-topmost", True)
            bar.configure(bg="#FF0000")
            bar.withdraw()
            _make_click_through(bar)
            self.bars.append(bar)

        self.badge = tk.Toplevel(master)
        self.badge.title("FocusPilot_Badge")
        self.badge.overrideredirect(True)
        self.badge.attributes("-topmost", True)
        self.badge.configure(bg="#D90429", padx=8, pady=4)
        self.badge_label = tk.Label(self.badge, text="", font=("Segoe UI", 10, "bold"),
                                    bg="#D90429", fg="#FFFFFF")
        self.badge_label.pack()
        self.badge.withdraw()
        _make_click_through(self.badge)

        self.arrow = tk.Toplevel(master)
        self.arrow.title("FocusPilot_Arrow")
        self.arrow.overrideredirect(True)
        self.arrow.attributes("-topmost", True)
        self.arrow.configure(bg=ARROW_CHROMA)
        arrow_is_layered = False
        try:
            self.arrow.attributes("-transparentcolor", ARROW_CHROMA)
            arrow_is_layered = True
        except Exception:
            pass
        self.arrow_canvas = tk.Canvas(self.arrow, bg=ARROW_CHROMA, highlightthickness=0)
        self.arrow_canvas.pack(fill=tk.BOTH, expand=True)
        self.arrow.withdraw()
        _make_click_through(self.arrow, already_layered=arrow_is_layered)

        self._visible = False
        self._last_border_color: Optional[str] = None

    # ── Afișare ──────────────────────────────────────────────────────────────

    def show(self, geometry: Tuple[int, int, int, int], visual: Dict[str, Any],
             pulse_phase: float) -> None:
        gx, gy, gw, gh = (int(v) for v in geometry)
        gw = max(8, gw)
        gh = max(8, gh)

        pulsing = bool(visual.get("pulse_animation", True))
        base_thickness = _as_int(visual.get("border_width", 3), 3)
        wobble = int(math.sin(pulse_phase) * 2) if pulsing else 0
        thickness = max(1, min(base_thickness + wobble, max(1, min(gw, gh) // 2)))

        # ── Chenar ──
        if visual.get("box_enabled", True):
            color = visual.get("border_color", "#FF0000")
            if color != self._last_border_color:
                for bar in self.bars:
                    try:
                        bar.configure(bg=color)
                    except tk.TclError:
                        logger.debug("Culoare de chenar invalidă: %r", color)
                        break
                else:
                    self._last_border_color = color

            top, bottom, left, right = self.bars
            top.geometry(f"{gw}x{thickness}+{gx}+{gy}")
            bottom.geometry(f"{gw}x{thickness}+{gx}+{gy + gh - thickness}")
            left.geometry(f"{thickness}x{gh}+{gx}+{gy}")
            right.geometry(f"{thickness}x{gh}+{gx + gw - thickness}+{gy}")
            for bar in self.bars:
                if not self._visible:
                    bar.deiconify()
        else:
            for bar in self.bars:
                bar.withdraw()

        # ── Badge ──
        if visual.get("badge_enabled", True) and str(visual.get("badge_text", "")).strip():
            text = str(visual.get("badge_text"))
            bg = visual.get("badge_bg", "#D90429")
            fg = visual.get("badge_fg", "#FFFFFF")
            try:
                self.badge.configure(bg=bg)
                self.badge_label.configure(text=text, bg=bg, fg=fg)
            except tk.TclError:
                self.badge_label.configure(text=text)

            badge_y = gy - 32
            if badge_y < 4:
                badge_y = gy + gh + 8
            self.badge.geometry(f"+{gx}+{badge_y}")
            if not self._visible:
                self.badge.deiconify()
        else:
            self.badge.withdraw()

        # ── Săgeată ──
        if visual.get("arrow_enabled", True):
            self._draw_arrow(gx, gy, gw, gh, visual, pulse_phase, pulsing)
            if not self._visible:
                self.arrow.deiconify()
        else:
            self.arrow.withdraw()

        self._visible = True

    def _draw_arrow(self, gx: int, gy: int, gw: int, gh: int,
                    visual: Dict[str, Any], pulse_phase: float, pulsing: bool) -> None:
        direction = str(visual.get("arrow_direction", "up") or "up")
        color = visual.get("arrow_color", "#FF0000")
        style = str(visual.get("arrow_style", "slim") or "slim")
        thickness = _as_int(visual.get("arrow_width", 14 if style != "classic" else 32), 14)
        length = _as_int(visual.get("arrow_size", 22 if style != "classic" else 36), 22)
        drift = int(math.sin(pulse_phase * 2) * 4) if pulsing else 0

        if direction in ("up", "down"):
            width = max(18, thickness + 6)
            height = max(18, length + 6)
            ax = gx + (gw // 2) - (width // 2)
            # Săgeata stă pe partea opusă sensului în care arată, ca să indice
            # spre chenar fără a-l acoperi.
            ay = (gy + gh + 4 + drift) if direction == "up" else (gy - height - 4 - drift)
        else:
            width = max(18, length + 6)
            height = max(18, thickness + 6)
            ax = (gx - width - 4 - drift) if direction == "right" else (gx + gw + 4 + drift)
            ay = gy + (gh // 2) - (height // 2)

        self.arrow.geometry(f"{width}x{height}+{ax}+{ay}")
        self.arrow_canvas.delete("all")
        points = self._arrow_polygon(direction, style, thickness, length, width, height)
        outline = "#660000" if str(color).upper() != "#EB780A" else "#8C4600"
        try:
            self.arrow_canvas.create_polygon(points, fill=color, outline=outline, width=1)
        except tk.TclError:
            self.arrow_canvas.create_polygon(points, fill="#FF0000", outline=outline, width=1)

    @staticmethod
    def _arrow_polygon(direction: str, style: str, thickness: int, length: int,
                       box_w: int, box_h: int) -> List[int]:
        """Punctele poligonului săgeții, în coordonate locale ferestrei."""
        cx, cy = box_w // 2, box_h // 2
        half = max(6, thickness) // 2
        stem = max(2, min(5, max(6, thickness) // 3)) // 2 or 1

        if style in ("triangle", "classic"):
            if direction == "down":
                return [cx - half, 4, cx + half, 4, cx, box_h - 3]
            if direction == "up":
                return [cx, 3, cx + half, box_h - 4, cx - half, box_h - 4]
            if direction == "right":
                return [4, cy - half, box_w - 3, cy, 4, cy + half]
            return [box_w - 4, cy - half, 3, cy, box_w - 4, cy + half]

        head = max(7, min(14, int(max(10, length) * 0.55)))
        if direction == "down":
            base = box_h - head
            return [cx - stem, 3, cx + stem, 3, cx + stem, base, cx + half, base,
                    cx, box_h - 3, cx - half, base, cx - stem, base]
        if direction == "up":
            base = 3 + head
            return [cx, 3, cx + half, base, cx + stem, base, cx + stem, box_h - 3,
                    cx - stem, box_h - 3, cx - stem, base, cx - half, base]
        if direction == "right":
            base = box_w - head
            return [3, cy - stem, base, cy - stem, base, cy - half, box_w - 3, cy,
                    base, cy + half, base, cy + stem, 3, cy + stem]
        base = 3 + head
        return [box_w - 3, cy - stem, base, cy - stem, base, cy - half, 3, cy,
                base, cy + half, base, cy + stem, box_w - 3, cy + stem]

    def hide(self) -> None:
        if not self._visible:
            return
        for widget in self.bars + [self.badge, self.arrow]:
            try:
                widget.withdraw()
            except Exception:
                pass
        self._visible = False

    def destroy(self) -> None:
        for widget in self.bars + [self.badge, self.arrow]:
            try:
                widget.destroy()
            except Exception:
                pass
        self.bars = []


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class MultiScreenOverlay:
    """Afișează reperele vizuale pe toate monitoarele, fără a bloca mouse-ul."""

    def __init__(self):
        self.master: Optional[tk.Misc] = None
        self.active_cues: List[Dict[str, Any]] = []
        self._pool: List[_CueWindows] = []
        self._pulse_phase = 0.0
        self._pulse_job = None

    def init_overlay(self, master: tk.Misc) -> None:
        self.master = master
        self._schedule_pulse()

    # ── Interfață publică ────────────────────────────────────────────────────

    def update_cues(self, cues: List[Dict[str, Any]]) -> None:
        """
        Primește reperele de afișat. Apelat din firul de monitorizare, deci
        redarea este programată pe firul de interfață Tkinter.
        """
        if not self.master:
            return
        try:
            self.master.after(0, self._render, list(cues or []))
        except RuntimeError:
            pass          # interfața se închide

    def shutdown(self) -> None:
        if self._pulse_job and self.master:
            try:
                self.master.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        for widgets in self._pool:
            widgets.destroy()
        self._pool = []

    # ── Redare ───────────────────────────────────────────────────────────────

    def _render(self, cues: List[Dict[str, Any]]) -> None:
        if not self.master:
            return

        drawable = [c for c in (cues or []) if c.get("geometry")][:MAX_CUES]
        changed = len(drawable) != len(self.active_cues)
        self.active_cues = drawable

        for index, cue in enumerate(drawable):
            widgets = self._widgets_at(index)
            if widgets is None:
                break
            try:
                widgets.show(cue["geometry"], cue.get("visual_cue") or {},
                             self._pulse_phase)
            except Exception as exc:
                logger.debug("Redarea reperului '%s' a eșuat: %s",
                             cue.get("rule_name"), exc)

        for widgets in self._pool[len(drawable):]:
            widgets.hide()

        if changed:
            if drawable:
                logger.info("[OVERLAY] %d reper(e) afișat(e): %s", len(drawable),
                            ", ".join(str(c.get("rule_name", "?"))[:40] for c in drawable))
            else:
                logger.info("[OVERLAY] Repere ascunse.")

    def _widgets_at(self, index: int) -> Optional[_CueWindows]:
        """Setul de ferestre pentru al n-lea reper, creat la nevoie."""
        while len(self._pool) <= index:
            if len(self._pool) >= MAX_CUES:
                return None
            try:
                self._pool.append(_CueWindows(self.master))
            except Exception as exc:
                logger.error("Nu s-au putut crea ferestrele de overlay: %s", exc)
                return None
        return self._pool[index]

    # ── Animația de pulsare ──────────────────────────────────────────────────

    def _schedule_pulse(self) -> None:
        if not self.master:
            return
        try:
            self._pulse_job = self.master.after(PULSE_INTERVAL_MS, self._on_pulse)
        except RuntimeError:
            self._pulse_job = None

    def _on_pulse(self) -> None:
        self._pulse_phase += 0.35
        if self.active_cues:
            # Repoziționăm reperele existente, fără deiconify / lift / focus:
            # acelea mutau focusul din câmpul în care scria utilizatorul.
            for index, cue in enumerate(self.active_cues):
                if index >= len(self._pool):
                    break
                try:
                    self._pool[index].show(cue["geometry"], cue.get("visual_cue") or {},
                                           self._pulse_phase)
                except Exception:
                    pass
        self._schedule_pulse()
