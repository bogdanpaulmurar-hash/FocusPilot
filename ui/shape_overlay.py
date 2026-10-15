"""
FocusPilot — Desenarea formelor de marcaj pe ecran

Fiecare marcaj se descompune în una sau mai multe PRIMITIVE, iar fiecare
primitivă este o fereastră Tk fără decorații, click-through, incapabilă să
preia focusul. Forma dictează tehnica, pentru că Windows nu oferă o singură
metodă bună pentru toate:

  solid        Dreptunghi complet opac. Chenarul se compune din patru bare
               solide, nu dintr-un dreptunghi gol transparent: o suprafață
               opacă rămâne vizibilă peste conținutul accelerat GPU din Chrome
               și Edge, unde transparența DWM nu e redată corect. Aceasta era
               alegerea originală a proiectului și se păstrează.

  translucent  Fereastră layered cu alfa — highlight ca trecerea unui marker.
               `fill_color` și `fill_opacity` existau în configurație de la
               început, dar nu erau desenate niciodată.

  canvas       Fereastră cu CULOARE-CHEIE: fundalul într-o nuanță aproape
               neagră declarată transparentă, cu forma desenată deasupra. Așa
               se obțin contururi neregulate — cercuri și săgeți — fără un
               dreptunghi vizibil în jur.

  badge        Fereastră opacă cu etichetă de text.
"""

import ctypes
import logging
import tkinter as tk
from typing import Dict, Any, List, Optional, Tuple

import win32gui
import win32con

from core.mark_geometry import Rect, as_int, as_float, expand_mark  # noqa: F401

logger = logging.getLogger(__name__)

# Nuanța declarată transparentă în ferestrele cu culoare-cheie. Aproape neagră,
# ca să nu coincidă cu o culoare pe care ar alege-o utilizatorul.
CHROMA = "#000001"

LWA_ALPHA = 0x00000002
MIN_ALPHA = 0.05
FALLBACK_COLOR = "#FF0000"


def _hwnd_of(widget: tk.Misc) -> Optional[int]:
    try:
        return int(widget.frame(), 16)
    except Exception:
        try:
            return widget.winfo_id()
        except Exception:
            return None


def make_passthrough(widget: tk.Misc) -> None:
    """
    Face fereastra invizibilă la mouse și incapabilă să preia focusul.

    `WS_EX_TRANSPARENT` singur nu oprește testarea la click pe Windows: are
    nevoie și de `WS_EX_LAYERED`. `WS_EX_NOACTIVATE` împiedică fereastra să
    mute focusul din câmpul în care scrie utilizatorul.

    Atributele layered puse de Tk (culoarea-cheie pentru săgeți și cercuri,
    alfa pentru highlight) se păstrează: suprascrierea lor cu alfa simplu
    făcea fundalul săgeții vizibil, negru. Se aplică după afișare, pentru că Tk
    resetează stilurile ferestrei la afișare și la schimbarea transparenței.
    """
    hwnd = _hwnd_of(widget)
    if not hwnd:
        return
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        already_layered = bool(style & win32con.WS_EX_LAYERED)
        wanted = style | (win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                          | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_NOACTIVATE)
        if wanted != style:
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, wanted)
        if not already_layered:
            # O fereastră layered fără atribute nu se desenează deloc.
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)
    except Exception as exc:
        logger.debug("Stilul click-through nu s-a putut aplica: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Ferestrele de desen
# ─────────────────────────────────────────────────────────────────────────────

class ShapeWindow:
    """O fereastră reutilizabilă care poate desena oricare primitivă."""

    def __init__(self, master: tk.Misc):
        self.window = tk.Toplevel(master)
        self.window.title("FocusPilot_Shape")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=CHROMA)
        self.window.withdraw()

        self.canvas: Optional[tk.Canvas] = None
        self.label: Optional[tk.Label] = None

        self._layout: Optional[str] = None       # "plain" | "canvas" | "badge"
        self._chroma = False
        self._alpha: Optional[float] = None
        self._visible = False
        self._styled = False

    # ── Comutarea tehnicii ───────────────────────────────────────────────────

    def _layout_plain(self) -> None:
        if self._layout != "plain":
            if self.canvas is not None:
                self.canvas.pack_forget()
            if self.label is not None:
                self.label.pack_forget()
            self._layout = "plain"

    def _layout_canvas(self) -> None:
        if self.canvas is None:
            self.canvas = tk.Canvas(self.window, bg=CHROMA,
                                    highlightthickness=0, bd=0)
        if self._layout != "canvas":
            if self.label is not None:
                self.label.pack_forget()
            self.canvas.pack(fill=tk.BOTH, expand=True)
            self._layout = "canvas"

    def _layout_badge(self, bg: str, fg: str) -> None:
        if self.label is None:
            self.label = tk.Label(self.window, font=("Segoe UI", 10, "bold"),
                                  bg=bg, fg=fg, padx=8, pady=4)
        if self._layout != "badge":
            if self.canvas is not None:
                self.canvas.pack_forget()
            self.label.pack()
            self._layout = "badge"

    def _set_chroma(self, enabled: bool) -> None:
        if enabled == self._chroma:
            return
        try:
            self.window.attributes("-transparentcolor", CHROMA if enabled else "")
            self._chroma = enabled
            self._styled = False
        except Exception:
            pass

    def _set_alpha(self, alpha: Optional[float]) -> None:
        target = 1.0 if alpha is None else max(MIN_ALPHA, min(1.0, alpha))
        if target == self._alpha:
            return
        try:
            self.window.attributes("-alpha", target)
            self._alpha = target
            self._styled = False
        except Exception:
            pass

    def _set_bg(self, color: str) -> None:
        try:
            self.window.configure(bg=color)
        except tk.TclError:
            logger.debug("Culoare invalidă %r, se folosește roșu.", color)
            self.window.configure(bg=FALLBACK_COLOR)

    # ── Desen ────────────────────────────────────────────────────────────────

    def draw(self, primitive: Dict[str, Any]) -> None:
        kind = primitive["kind"]
        x, y, w, h = primitive["rect"]

        if kind == "solid":
            self._set_chroma(False)
            self._layout_plain()
            self._set_bg(primitive["color"])
            self._set_alpha(None)
            self.window.geometry(f"{max(1, int(w))}x{max(1, int(h))}+{int(x)}+{int(y)}")

        elif kind == "translucent":
            self._set_chroma(False)
            self._layout_plain()
            self._set_bg(primitive["color"])
            self.window.geometry(f"{max(1, int(w))}x{max(1, int(h))}+{int(x)}+{int(y)}")
            self._set_alpha(primitive.get("alpha", 0.3))

        elif kind == "oval":
            self._set_chroma(True)
            self._layout_canvas()
            self._set_bg(CHROMA)
            self._set_alpha(None)
            self.window.geometry(f"{max(4, int(w))}x{max(4, int(h))}+{int(x)}+{int(y)}")
            thickness = max(1, int(primitive.get("thickness", 3)))
            half = thickness / 2
            self.canvas.configure(bg=CHROMA)
            self.canvas.delete("all")
            self._safe_shape("oval", (half, half, int(w) - half, int(h) - half),
                             primitive["color"], thickness)

        elif kind == "polygons":
            self._set_chroma(True)
            self._layout_canvas()
            self._set_bg(CHROMA)
            self._set_alpha(None)
            self.window.geometry(f"{max(4, int(w))}x{max(4, int(h))}+{int(x)}+{int(y)}")
            self.canvas.configure(bg=CHROMA)
            self.canvas.delete("all")
            color = primitive["color"]
            outline = "#5A0000" if str(color).upper() != "#EB780A" else "#8C4600"
            for points in primitive["polygons"]:
                try:
                    self.canvas.create_polygon(points, fill=color,
                                               outline=outline, width=1)
                except tk.TclError:
                    self.canvas.create_polygon(points, fill=FALLBACK_COLOR,
                                               outline=outline, width=1)

        elif kind == "badge":
            self._set_chroma(False)
            bg = primitive["color"]
            self._layout_badge(bg, primitive.get("text_color", "#FFFFFF"))
            self._set_bg(bg)
            self._set_alpha(None)
            try:
                self.label.configure(text=primitive["text"], bg=bg,
                                     fg=primitive.get("text_color", "#FFFFFF"))
            except tk.TclError:
                self.label.configure(text=primitive["text"])
            self.window.geometry(f"+{int(x)}+{int(y)}")

        else:
            logger.debug("Primitivă necunoscută: %r", kind)
            return

        if not self._visible:
            self.window.deiconify()
            self._visible = True
            self._styled = False
        if not self._styled:
            self.window.update_idletasks()
            make_passthrough(self.window)
            self._styled = True

    def _safe_shape(self, shape: str, box, color: str, thickness: int) -> None:
        creator = getattr(self.canvas, f"create_{shape}")
        try:
            creator(*box, outline=color, width=thickness)
        except tk.TclError:
            creator(*box, outline=FALLBACK_COLOR, width=thickness)

    def hide(self) -> None:
        if self._visible:
            try:
                self.window.withdraw()
            except Exception:
                pass
            self._visible = False

    def destroy(self) -> None:
        try:
            self.window.destroy()
        except Exception:
            pass


class ShapePool:
    """Grup de ferestre de desen, create la nevoie și reutilizate."""

    def __init__(self, master: tk.Misc, limit: int = 40):
        self.master = master
        self.limit = limit
        self._windows: List[ShapeWindow] = []
        self._warned_limit = False

    def draw_marks(self, marks: List[Dict[str, Any]], phase: float) -> int:
        """Desenează toate marcajele; ascunde ferestrele rămase nefolosite."""
        primitives: List[Dict[str, Any]] = []
        for mark in marks:
            try:
                primitives.extend(expand_mark(mark, phase))
            except Exception as exc:
                logger.debug("Marcajul '%s' nu a putut fi pregătit: %s",
                             mark.get("shape"), exc)

        used = 0
        for primitive in primitives:
            window = self._acquire(used)
            if window is None:
                if not self._warned_limit:
                    self._warned_limit = True
                    logger.warning("Limita de %d forme simultane a fost atinsă; "
                                   "restul marcajelor nu se desenează.", self.limit)
                break
            try:
                window.draw(primitive)
                used += 1
            except Exception as exc:
                logger.debug("Desenarea primitivei %s a eșuat: %s",
                             primitive.get("kind"), exc)

        for window in self._windows[used:]:
            window.hide()
        return used

    def _acquire(self, index: int) -> Optional[ShapeWindow]:
        while len(self._windows) <= index:
            if len(self._windows) >= self.limit:
                return None
            try:
                self._windows.append(ShapeWindow(self.master))
            except Exception as exc:
                logger.error("Nu s-a putut crea fereastra de formă: %s", exc)
                return None
        return self._windows[index]

    def hide_all(self) -> None:
        for window in self._windows:
            window.hide()

    def destroy(self) -> None:
        for window in self._windows:
            window.destroy()
        self._windows = []
