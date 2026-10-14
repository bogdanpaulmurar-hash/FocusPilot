"""
FocusPilot — Geometria marcajelor

Transformă un marcaj configurat de utilizator în PRIMITIVE de desenat, și
convertește regulile clasice (`visual_cue`) în aceeași formă de marcaje.

Aici nu se desenează nimic și nu se importă nicio bibliotecă de interfață:
sunt doar calcule pe dreptunghiuri. Separarea ține geometria testabilă fără
Windows și fără tkinter, și face ca orice formă nouă să devină disponibilă
atât regulilor clasice cât și celor cu câmpuri și condiții.

PRIMITIVELE, și de ce sunt mai multe feluri:

  solid        Dreptunghi complet opac. Chenarul se compune din patru bare
               solide, nu dintr-un dreptunghi gol transparent: o suprafață
               opacă rămâne vizibilă peste conținutul accelerat GPU din Chrome
               și Edge, unde transparența DWM nu e redată corect. Aceasta era
               alegerea originală a proiectului și se păstrează.

  translucent  Fereastră cu alfa — highlight ca trecerea unui marker.

  oval         Contur de elipsă, desenat pe o fereastră cu culoare-cheie, ca
               să nu apară un dreptunghi în jurul cercului.

  polygons     Una sau mai multe săgeți, pe o singură fereastră cu
               culoare-cheie.

  badge        Etichetă de text.
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

Rect = Tuple[int, int, int, int]

MIN_ALPHA = 0.05


def as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Descompunerea unui marcaj în primitive
# ─────────────────────────────────────────────────────────────────────────────

def expand_mark(mark: Dict[str, Any], phase: float) -> List[Dict[str, Any]]:
    """
    Transformă un marcaj configurat în primitive de desenat.

    `phase` animă pulsarea: grosimea chenarului, opacitatea highlight-ului și
    deplasarea săgeților.
    """
    rect = mark.get("rect")
    if not rect:
        return []
    x, y, w, h = (int(v) for v in rect)
    w, h = max(2, w), max(2, h)

    shape = str(mark.get("shape", "box") or "box")
    color = mark.get("color", "#E60000")
    pulsing = bool(mark.get("pulse", True))
    thickness = max(1, as_int(mark.get("thickness", 3), 3))
    if pulsing:
        thickness = max(1, thickness + int(math.sin(phase) * 2))
    thickness = min(thickness, max(1, min(w, h) // 2))

    if shape == "highlight":
        opacity = as_float(mark.get("opacity", 0.30), 0.30)
        if pulsing:
            opacity = max(MIN_ALPHA, min(0.85, opacity + math.sin(phase) * 0.08))
        return [{"kind": "translucent", "rect": (x, y, w, h),
                 "color": color, "alpha": opacity}]

    if shape == "underline":
        return [{"kind": "solid", "rect": (x, y + h - thickness, w, thickness),
                 "color": color}]

    if shape == "strikethrough":
        return [{"kind": "solid",
                 "rect": (x, y + h // 2 - thickness // 2, w, thickness),
                 "color": color}]

    if shape == "circle":
        # O elipsă înscrisă exact în dreptunghi taie colțurile textului, deci
        # se lărgește puțin.
        gx = max(6, int(w * 0.10))
        gy = max(5, int(h * 0.30))
        return [{"kind": "oval", "rect": (x - gx, y - gy, w + gx * 2, h + gy * 2),
                 "color": color, "thickness": thickness}]

    if shape == "arrow":
        return [_arrow_primitive(x, y, w, h, color, mark, phase, pulsing)]

    if shape == "badge":
        place_y = y - 30 if y - 30 >= 4 else y + 8
        return [{"kind": "badge", "rect": (x, place_y, 0, 0),
                 "color": color, "text": str(mark.get("text", "") or "⚠️"),
                 "text_color": mark.get("text_color", "#FFFFFF")}]

    # "box": patru bare opace.
    return [
        {"kind": "solid", "rect": (x, y, w, thickness), "color": color},
        {"kind": "solid", "rect": (x, y + h - thickness, w, thickness), "color": color},
        {"kind": "solid", "rect": (x, y, thickness, h), "color": color},
        {"kind": "solid", "rect": (x + w - thickness, y, thickness, h), "color": color},
    ]


def _arrow_primitive(x: int, y: int, w: int, h: int, color: str,
                     mark: Dict[str, Any], phase: float,
                     pulsing: bool) -> Dict[str, Any]:
    """Una sau mai multe săgeți care indică spre zonă, pe o singură fereastră."""
    direction = str(mark.get("arrow_direction", "right") or "right")
    count = max(1, min(5, as_int(mark.get("arrow_count", 1), 1)))
    gap = max(0, as_int(mark.get("arrow_gap", 6), 6))
    length = max(10, as_int(mark.get("arrow_length", 22), 22))
    width = max(6, as_int(mark.get("arrow_width", 14), 14))
    arrow_style = str(mark.get("arrow_style", "slim") or "slim")
    drift = int(math.sin(phase * 2) * 4) if pulsing else 0

    span = count * length + (count - 1) * gap
    horizontal = direction in ("left", "right")

    if horizontal:
        box_w, box_h = span + 6, max(18, width + 6)
        # Săgeata stă pe latura opusă sensului în care arată, ca să indice
        # spre zonă fără a o acoperi.
        box_x = (x - box_w - 4 - drift) if direction == "right" else (x + w + 4 + drift)
        box_y = y + h // 2 - box_h // 2
    else:
        box_w, box_h = max(18, width + 6), span + 6
        box_x = x + w // 2 - box_w // 2
        box_y = (y + h + 4 + drift) if direction == "up" else (y - box_h - 4 - drift)

    polygons = []
    for index in range(count):
        shift = index * (length + gap)
        cell = (shift, 0, length, box_h) if horizontal else (0, shift, box_w, length)
        polygons.append(_arrow_points(direction, arrow_style, width, cell))

    return {"kind": "polygons", "rect": (box_x, box_y, box_w, box_h),
            "color": color, "polygons": polygons}


def _arrow_points(direction: str, arrow_style: str, thickness: int,
                  cell: Tuple[int, int, int, int]) -> List[int]:
    """Punctele unei singure săgeți, în interiorul celulei (ox, oy, cw, ch)."""
    ox, oy, cw, ch = cell
    cx, cy = ox + cw // 2, oy + ch // 2
    half = max(3, thickness // 2)
    stem = max(1, min(4, thickness // 4))

    if arrow_style in ("triangle", "classic"):
        if direction == "right":
            return [ox + 1, cy - half, ox + cw - 1, cy, ox + 1, cy + half]
        if direction == "left":
            return [ox + cw - 1, cy - half, ox + 1, cy, ox + cw - 1, cy + half]
        if direction == "down":
            return [cx - half, oy + 1, cx + half, oy + 1, cx, oy + ch - 1]
        return [cx, oy + 1, cx + half, oy + ch - 1, cx - half, oy + ch - 1]

    head = max(6, min(14, int((cw if direction in ("left", "right") else ch) * 0.5)))
    if direction == "right":
        base = ox + cw - head
        return [ox + 1, cy - stem, base, cy - stem, base, cy - half,
                ox + cw - 1, cy, base, cy + half, base, cy + stem, ox + 1, cy + stem]
    if direction == "left":
        base = ox + head
        return [ox + cw - 1, cy - stem, base, cy - stem, base, cy - half,
                ox + 1, cy, base, cy + half, base, cy + stem, ox + cw - 1, cy + stem]
    if direction == "down":
        base = oy + ch - head
        return [cx - stem, oy + 1, cx + stem, oy + 1, cx + stem, base,
                cx + half, base, cx, oy + ch - 1, cx - half, base, cx - stem, base]
    base = oy + head
    return [cx, oy + 1, cx + half, base, cx + stem, base, cx + stem, oy + ch - 1,
            cx - stem, oy + ch - 1, cx - stem, base, cx - half, base]


# ─────────────────────────────────────────────────────────────────────────────
# Regulile clasice, convertite la același model de marcaje
# ─────────────────────────────────────────────────────────────────────────────

def visual_cue_to_marks(visual: Dict[str, Any],
                        rect: Optional[tuple]) -> List[Dict[str, Any]]:
    """
    Convertește un `visual_cue` clasic în lista de marcaje echivalentă.

    Ordinea contează la suprapunere: highlight-ul se desenează primul, ca să
    stea sub chenar și sub săgeată.
    """
    if not rect:
        return []

    marks: List[Dict[str, Any]] = []
    pulse = bool(visual.get("pulse_animation", True))

    # `fill_color` și `fill_opacity` existau în configurație de la prima
    # versiune, dar nu erau desenate niciodată. Pentru ca regulile existente
    # să arate neschimbat, highlight-ul se desenează doar la cerere explicită.
    if visual.get("fill_enabled", False):
        marks.append({
            "shape": "highlight", "rect": rect,
            "color": visual.get("fill_color", "#FF3333"),
            "opacity": as_float(visual.get("fill_opacity", 0.20), 0.20),
            "pulse": pulse,
        })

    if visual.get("box_enabled", True):
        marks.append({
            "shape": str(visual.get("box_shape", "box") or "box"),
            "rect": rect,
            "color": visual.get("border_color", "#FF0000"),
            "thickness": as_int(visual.get("border_width", 3), 3),
            "pulse": pulse,
        })

    if visual.get("arrow_enabled", True):
        marks.append({
            "shape": "arrow", "rect": rect,
            "color": visual.get("arrow_color", "#FF0000"),
            "arrow_direction": visual.get("arrow_direction", "right"),
            "arrow_style": visual.get("arrow_style", "slim"),
            "arrow_length": as_int(visual.get("arrow_size", 22), 22),
            "arrow_width": as_int(visual.get("arrow_width", 14), 14),
            "arrow_count": as_int(visual.get("arrow_count", 1), 1),
            "arrow_gap": as_int(visual.get("arrow_gap", 6), 6),
            "pulse": pulse,
        })

    badge_text = str(visual.get("badge_text", "") or "").strip()
    if visual.get("badge_enabled", True) and badge_text:
        marks.append({
            "shape": "badge", "rect": rect,
            "color": visual.get("badge_bg", "#D90429"),
            "text": badge_text,
            "text_color": visual.get("badge_fg", "#FFFFFF"),
            "pulse": False,
        })

    return marks


def marks_for_cue(cue: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Marcajele de desenat pentru un reper, indiferent de tipul regulii."""
    marks = cue.get("marks")
    if marks:
        return list(marks)
    return visual_cue_to_marks(cue.get("visual_cue") or {}, cue.get("geometry"))
