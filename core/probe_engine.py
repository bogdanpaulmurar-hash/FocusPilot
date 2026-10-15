"""
FocusPilot — Câmpuri, Condiții și Marcaje

Aduce modelul de formatare condițională din Excel peste suprafața ecranului:

    Excel                           FocusPilot
    ─────────────────────────────   ──────────────────────────────────────
    $B$4, $D$7                      câmp numit, localizat pe ecran
    =AND($B$4="Merge"; $D$7>0)      condiții pe câmpuri, legate prin AND/OR
    format: chenar, fundal, font    marcaje: chenar, cerc, highlight, săgeți

TREI NOȚIUNI SEPARATE
---------------------
1. CÂMP (probe)     — un loc de pe ecran, cu nume, de unde se citește o valoare.
2. CONDIȚIE         — `câmp operator valoare`; mai multe, legate prin AND / OR.
3. MARCAJ (mark)    — ce câmp se evidențiază și cu ce formă și culori.

Un câmp se poate localiza în două moduri, cu compromisuri diferite:

  text_near     Valoarea aflată lângă o etichetă ("valoarea din dreapta lui
                «Status»"). Se recalculează la fiecare scanare, deci urmărește
                elementul când pagina derulează. Varianta recomandată.

  screen_point  Un punct fix pe ecran, capturat cu mouse-ul. Potrivit pentru
                ce stă mereu în același loc: bare de status, panouri fixe,
                toolbar-uri. Dacă pagina derulează, punctul arată spre alt
                element — de aceea nu e varianta implicită.

Valorile se citesc prin UI Automation, deci sunt text exact, nu rezultat de
recunoaștere optică. Comparațiile numerice lucrează pe numere reale.
"""

import re
import logging
import unicodedata
from typing import Dict, Any, List, Optional, Tuple, NamedTuple

logger = logging.getLogger(__name__)

Rect = Tuple[int, int, int, int]        # (x, y, w, h) pe ecranul virtual


def fold_text(text: str, case_sensitive: bool = False) -> str:
    """
    Forma de comparație a unui text. Fără sensibilitate la majuscule se ignoră
    și diacriticele: „Aplicatia porneste" găsește „Aplicația pornește".
    """
    if case_sensitive:
        return text
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def best_text_match(items: List[Tuple[str, Rect]], needle: str,
                    case_sensitive: bool = False,
                    window_area: int = 0) -> Optional[Tuple[str, Rect]]:
    """
    Elementul cel mai specific care conține `needle`.

    Fereastra și documentul paginii poartă ca nume titlul, deci „conțin" orice
    text din titlu; primul găsit ar încadra tot ecranul. Elementele cât jumătate
    din fereastră sunt containere și se sar; dintre restul câștigă cel mai mic.
    """
    probe = fold_text(needle, case_sensitive)
    matches = [(t, r) for t, r in items if probe in fold_text(t, case_sensitive)]
    if window_area > 0:
        matches = [(t, r) for t, r in matches if r[2] * r[3] < window_area * 0.5]
    if not matches:
        return None
    return min(matches, key=lambda m: m[1][2] * m[1][3])


# ─────────────────────────────────────────────────────────────────────────────
# Operatori de condiție
# ─────────────────────────────────────────────────────────────────────────────

#  cheie             etichetă afișată                         are nevoie de valoare
OPERATORS: Dict[str, Tuple[str, bool]] = {
    "equals":        ("este exact",                           True),
    "not_equals":    ("este diferit de",                      True),
    "contains":      ("conține",                              True),
    "not_contains":  ("nu conține",                           True),
    "starts_with":   ("începe cu",                            True),
    "ends_with":     ("se termină cu",                        True),
    "regex":         ("se potrivește cu expresia",            True),
    "is_empty":      ("este gol",                             False),
    "is_not_empty":  ("nu este gol",                          False),
    "greater_than":  ("este mai mare decât",                  True),
    "less_than":     ("este mai mic decât",                   True),
    "greater_equal": ("este mai mare sau egal cu",            True),
    "less_equal":    ("este mai mic sau egal cu",             True),
    "between":       ("este între (două valori: min;max)",     True),
    "is_number":     ("este un număr",                        False),
    "changed":       ("s-a schimbat de la ultima verificare", False),
}

NUMERIC_OPERATORS = {"greater_than", "less_than", "greater_equal",
                     "less_equal", "between"}


def parse_number(text: str) -> Optional[float]:
    """
    Extrage un număr dintr-un text de interfață.

    Tolerează spații, simboluri de monedă, separatori de mii și ambele
    convenții pentru separatorul zecimal, pentru că o celulă dintr-un portal
    poate arăta ca „1.234,50 EUR" sau „1,234.50".
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None

    match = re.search(r"-?\d[\d\s.,]*", raw)
    if not match:
        return None
    body = match.group(0).replace(" ", "").replace(" ", "")

    has_dot, has_comma = "." in body, "," in body
    if has_dot and has_comma:
        # Separatorul zecimal e ultimul care apare; celălalt separă miile.
        if body.rfind(",") > body.rfind("."):
            body = body.replace(".", "").replace(",", ".")
        else:
            body = body.replace(",", "")
    elif has_comma:
        # O singură virgulă cu 1-2 zecimale e separator zecimal; altfel, mii.
        tail = body.split(",")[-1]
        body = body.replace(",", "." if len(tail) <= 2 and body.count(",") == 1 else "")
    elif body.count(".") > 1:
        body = body.replace(".", "")

    try:
        return float(body)
    except ValueError:
        return None


def compare(value: Optional[str], operator: str, expected: str,
            case_sensitive: bool = False,
            previous: Optional[str] = None) -> bool:
    """Aplică un operator pe valoarea citită din câmp."""
    text = "" if value is None else str(value).strip()
    wanted = "" if expected is None else str(expected).strip()

    if operator == "is_empty":
        return text == ""
    if operator == "is_not_empty":
        return text != ""
    if operator == "is_number":
        return parse_number(text) is not None
    if operator == "changed":
        return previous is not None and previous != text

    if operator in NUMERIC_OPERATORS:
        number = parse_number(text)
        if number is None:
            return False
        if operator == "between":
            parts = [p for p in re.split(r"[;,]", wanted) if p.strip()]
            if len(parts) != 2:
                logger.warning("Operatorul 'between' cere două valori "
                               "separate prin ';', primit: %r", wanted)
                return False
            low, high = parse_number(parts[0]), parse_number(parts[1])
            if low is None or high is None:
                return False
            if low > high:
                low, high = high, low
            return low <= number <= high
        limit = parse_number(wanted)
        if limit is None:
            return False
        return {
            "greater_than": number > limit,
            "less_than": number < limit,
            "greater_equal": number >= limit,
            "less_equal": number <= limit,
        }[operator]

    if operator == "regex":
        try:
            return bool(re.search(wanted, text, 0 if case_sensitive else re.IGNORECASE))
        except re.error as exc:
            logger.warning("Expresie regulată invalidă %r: %s", wanted, exc)
            return False

    probe = fold_text(text, case_sensitive)
    target = fold_text(wanted, case_sensitive)

    if operator == "equals":
        return probe == target
    if operator == "not_equals":
        return probe != target
    if operator == "contains":
        return target in probe
    if operator == "not_contains":
        return target not in probe
    if operator == "starts_with":
        return probe.startswith(target)
    if operator == "ends_with":
        return probe.endswith(target)

    logger.warning("Operator necunoscut %r, se tratează ca 'contains'.", operator)
    return target in probe


# ─────────────────────────────────────────────────────────────────────────────
# Citirea valorii unui câmp
# ─────────────────────────────────────────────────────────────────────────────

# Cât de departe de etichetă se caută valoarea, în pixeli.
LABEL_SEARCH_RADIUS_X = 900
LABEL_SEARCH_RADIUS_Y = 40


class ProbeReading(NamedTuple):
    """Ce s-a citit dintr-un câmp și de unde."""

    name: str
    value: Optional[str]     # None = câmpul nu a putut fi localizat
    rect: Optional[Rect]     # unde se află pe ecran, pentru marcaje
    note: str                # explicație pentru diagnostic

    @property
    def located(self) -> bool:
        return self.rect is not None


def read_probe(probe: Dict[str, Any], snapshot, window_rect: Rect) -> ProbeReading:
    """
    Citește valoarea unui câmp din instantaneul ferestrei.

    `snapshot` este un UiaSnapshot (vezi core.rule_engine): lista elementelor
    vizibile cu text și coordonate, citită O SINGURĂ DATĂ pe fereastră și
    refolosită pentru toate câmpurile și toate regulile.
    """
    name = str(probe.get("name", "") or "câmp")
    locator = probe.get("locator") or {}
    kind = str(locator.get("kind", "text_near") or "text_near")

    if snapshot is None:
        return ProbeReading(name, None, None,
                            "Textul ferestrei nu a putut fi citit "
                            "(lipsește 'uiautomation'?).")

    if kind == "text_near":
        return _read_near_label(name, locator, snapshot)
    if kind == "screen_point":
        return _read_at_point(name, locator, snapshot)
    if kind == "screen_region":
        return _read_in_region(name, locator, snapshot)
    if kind == "text_self":
        return _read_label_itself(name, locator, snapshot)

    return ProbeReading(name, None, None, f"Mod de localizare necunoscut: '{kind}'.")


def _read_near_label(name: str, locator: Dict[str, Any], snapshot) -> ProbeReading:
    """
    Valoarea aflată lângă o etichetă.

    Se caută eticheta, apoi primul element cu text pe aceeași linie, în
    direcția cerută. Robust la scroll: eticheta se recaută la fiecare scanare.
    """
    label = str(locator.get("text", "") or "").strip()
    if not label:
        return ProbeReading(name, None, None,
                            "Câmpul nu are eticheta completată.")

    direction = str(locator.get("offset", "right") or "right")
    case_sensitive = bool(locator.get("case_sensitive", False))
    skip = max(0, int(locator.get("skip", 0) or 0))

    probe_label = fold_text(label, case_sensitive)
    best = best_text_match(snapshot.items, label, case_sensitive,
                           getattr(snapshot, "window_area", 0))
    label_rect = best[1] if best else None

    if label_rect is None:
        return ProbeReading(name, None, None,
                            f"Eticheta '{label[:40]}' nu e vizibilă pe ecran.")

    lx, ly, lw, lh = label_rect
    label_mid_y = ly + lh / 2
    label_mid_x = lx + lw / 2

    # Toleranțele se leagă de dimensiunea etichetei, nu de valori fixe.
    # O toleranță fixă pe verticală prinde elemente din rândul de deasupra, iar
    # una fixă pe orizontală prinde coloane vecine — și atunci câmpul citește
    # valoarea greșită, care e cel mai rău fel de eroare aici.
    band_y = max(6.0, lh * 0.6)
    band_x = max(20.0, lw * 0.75)

    candidates: List[Tuple[float, float, str, Rect]] = []
    for text, rect in snapshot.items:
        if rect == label_rect or not str(text).strip():
            continue
        rx, ry, rw, rh = rect

        if direction in ("right", "left"):
            drift = abs((ry + rh / 2) - label_mid_y)
            if drift > band_y:                       # alt rând
                continue
            distance = (rx - (lx + lw)) if direction == "right" else (lx - (rx + rw))
            if distance < -4 or distance > LABEL_SEARCH_RADIUS_X:
                continue
        else:                                        # "below" / "above"
            drift = abs((rx + rw / 2) - label_mid_x)
            if drift > band_x:                       # altă coloană
                continue
            distance = (ry - (ly + lh)) if direction == "below" else (ly - (ry + rh))
            if distance < -4 or distance > LABEL_SEARCH_RADIUS_Y * 12:
                continue

        # Un element care conține eticheta e containerul, nu valoarea.
        inner = fold_text(text, case_sensitive)
        if probe_label in inner:
            continue
        # Cel mai apropiat câștigă; la distanță egală, cel mai bine aliniat.
        candidates.append((distance, drift, text, rect))

    if not candidates:
        return ProbeReading(name, None, label_rect,
                            f"Eticheta '{label[:30]}' găsită, dar nu există "
                            f"text la {_direction_word(direction)} ei.")

    candidates.sort(key=lambda item: (item[0], item[1]))
    if skip >= len(candidates):
        return ProbeReading(name, None, label_rect,
                            f"S-a cerut al {skip + 1}-lea element de la etichetă, "
                            f"dar există doar {len(candidates)}.")

    _, _, value, rect = candidates[skip]
    return ProbeReading(name, value.strip(), rect,
                        f"Citit {_direction_word(direction)} etichetei "
                        f"'{label[:30]}': '{value.strip()[:40]}'.")


def _direction_word(direction: str) -> str:
    return {"right": "dreapta", "left": "stânga",
            "below": "sub", "above": "deasupra"}.get(direction, direction)


def _read_label_itself(name: str, locator: Dict[str, Any], snapshot) -> ProbeReading:
    """Textul etichetei însăși — util ca să verifici doar că un text apare."""
    needle = str(locator.get("text", "") or "").strip()
    if not needle:
        return ProbeReading(name, None, None, "Câmpul nu are text completat.")
    case_sensitive = bool(locator.get("case_sensitive", False))
    rect = snapshot.find(needle, case_sensitive)
    if rect is None:
        return ProbeReading(name, "", None,
                            f"Textul '{needle[:40]}' nu e vizibil pe ecran.")
    for text, item_rect in snapshot.items:
        if item_rect == rect:
            return ProbeReading(name, text.strip(), rect,
                                f"Text găsit: '{text.strip()[:40]}'.")
    return ProbeReading(name, needle, rect, "Text găsit.")


def _read_at_point(name: str, locator: Dict[str, Any], snapshot) -> ProbeReading:
    """
    Valoarea elementului aflat sub un punct fix de ecran.

    Se alege cel mai MIC element care conține punctul: elementele mari sunt
    containere, iar textul căutat se află în cel mai adânc dintre ele.
    """
    try:
        px = int(float(locator.get("x")))
        py = int(float(locator.get("y")))
    except (TypeError, ValueError):
        return ProbeReading(name, None, None,
                            "Câmpul nu are coordonate valide. Folosiți "
                            "'Alege de pe Ecran'.")

    best: Optional[Tuple[int, str, Rect]] = None
    for text, rect in snapshot.items:
        rx, ry, rw, rh = rect
        if rx <= px <= rx + rw and ry <= py <= ry + rh:
            area = rw * rh
            if best is None or area < best[0]:
                best = (area, text, rect)

    if best is None:
        return ProbeReading(name, None, None,
                            f"Niciun element cu text la punctul ({px}, {py}). "
                            "Elementul s-a mutat sau pagina a derulat.")
    _, value, rect = best
    return ProbeReading(name, value.strip(), rect,
                        f"Citit la ({px}, {py}): '{value.strip()[:40]}'.")


def _read_in_region(name: str, locator: Dict[str, Any], snapshot) -> ProbeReading:
    """Tot textul din interiorul unei zone dreptunghiulare fixe."""
    try:
        rx = int(float(locator.get("x")))
        ry = int(float(locator.get("y")))
        rw = int(float(locator.get("w", 200)))
        rh = int(float(locator.get("h", 30)))
    except (TypeError, ValueError):
        return ProbeReading(name, None, None, "Zona câmpului nu are coordonate valide.")

    pieces: List[Tuple[int, int, str]] = []
    bounds: Optional[List[int]] = None
    for text, rect in snapshot.items:
        ex, ey, ew, eh = rect
        # Centrul elementului trebuie să cadă în zonă.
        cx, cy = ex + ew / 2, ey + eh / 2
        if not (rx <= cx <= rx + rw and ry <= cy <= ry + rh):
            continue
        pieces.append((ey, ex, text.strip()))
        if bounds is None:
            bounds = [ex, ey, ex + ew, ey + eh]
        else:
            bounds = [min(bounds[0], ex), min(bounds[1], ey),
                      max(bounds[2], ex + ew), max(bounds[3], ey + eh)]

    if not pieces:
        return ProbeReading(name, "", (rx, ry, rw, rh),
                            f"Zona ({rx}, {ry}) {rw}x{rh} nu conține text.")

    pieces.sort()
    value = " ".join(piece for _, _, piece in pieces if piece)
    rect = (bounds[0], bounds[1], bounds[2] - bounds[0], bounds[3] - bounds[1])
    return ProbeReading(name, value, rect, f"Citit din zonă: '{value[:40]}'.")


# ─────────────────────────────────────────────────────────────────────────────
# Evaluarea condițiilor
# ─────────────────────────────────────────────────────────────────────────────

class ConditionOutcome(NamedTuple):
    probe: str
    operator: str
    expected: str
    actual: Optional[str]
    passed: bool
    note: str

    def describe(self) -> str:
        label = OPERATORS.get(self.operator, (self.operator, True))[0]
        shown = "(negăsit)" if self.actual is None else f"'{self.actual[:38]}'"
        needs_value = OPERATORS.get(self.operator, ("", True))[1]
        wanted = f" '{self.expected[:30]}'" if needs_value else ""
        mark = "✅" if self.passed else "❌"
        return f"{mark} {self.probe} {label}{wanted} — valoare citită: {shown}"


class RuleOutcome(NamedTuple):
    matched: bool
    readings: Dict[str, ProbeReading]
    outcomes: List[ConditionOutcome]
    logic: str

    def report(self) -> str:
        lines = [o.describe() for o in self.outcomes]
        for reading in self.readings.values():
            if not reading.located:
                lines.append(f"   ⚠️ {reading.name}: {reading.note}")
        word = "toate condițiile" if self.logic == "AND" else "cel puțin o condiție"
        lines.append(f"Logică: {self.logic} ({word} trebuie să fie îndeplinită)")
        return "\n".join(lines)


def evaluate_conditions(rule: Dict[str, Any], snapshot, window_rect: Rect,
                        previous_values: Optional[Dict[str, str]] = None
                        ) -> RuleOutcome:
    """
    Citește toate câmpurile regulii o dată, apoi evaluează condițiile.

    Câmpurile se citesc o singură dată chiar dacă mai multe condiții se referă
    la același câmp.
    """
    probes = rule.get("probes") or []
    conditions = rule.get("conditions") or []
    logic = str(rule.get("conditions_logic", "AND") or "AND").upper()
    if logic not in ("AND", "OR"):
        logic = "AND"

    readings: Dict[str, ProbeReading] = {}
    for probe in probes:
        reading = read_probe(probe, snapshot, window_rect)
        readings[reading.name] = reading

    outcomes: List[ConditionOutcome] = []
    for condition in conditions:
        probe_name = str(condition.get("probe", "") or "")
        operator = str(condition.get("operator", "contains") or "contains")
        expected = str(condition.get("value", "") or "")
        case_sensitive = bool(condition.get("case_sensitive", False))

        reading = readings.get(probe_name)
        if reading is None:
            outcomes.append(ConditionOutcome(
                probe_name or "(niciun câmp)", operator, expected, None, False,
                f"Condiția se referă la câmpul '{probe_name}', care nu e definit."))
            continue

        previous = (previous_values or {}).get(probe_name)
        passed = compare(reading.value, operator, expected, case_sensitive, previous)
        outcomes.append(ConditionOutcome(probe_name, operator, expected,
                                         reading.value, passed, reading.note))

    if not conditions:
        matched = False
    elif logic == "AND":
        matched = all(o.passed for o in outcomes)
    else:
        matched = any(o.passed for o in outcomes)

    return RuleOutcome(matched, readings, outcomes, logic)


def uses_conditions(rule: Dict[str, Any]) -> bool:
    """True dacă regula folosește modelul de câmpuri și condiții."""
    return bool(rule.get("probes")) and bool(rule.get("conditions"))


def validate_rule_fields(fields: Dict[str, Any]) -> Optional[str]:
    """
    Verifică o configurație de câmpuri, condiții și marcaje.

    Întoarce un mesaj de eroare lizibil, sau None dacă totul e coerent. Se
    apelează ÎNAINTE de salvare: o regulă cu o referință greșită s-ar salva
    fără reclamații și apoi pur și simplu nu s-ar declanșa, iar utilizatorul nu
    ar avea de unde să afle de ce.
    """
    probes = fields.get("probes") or []
    conditions = fields.get("conditions") or []
    marks = fields.get("marks") or []

    if not probes and not conditions and not marks:
        return None          # modelul nu e folosit pentru această regulă

    names = [str(p.get("name", "") or "").strip() for p in probes]
    names = [n for n in names if n]
    if not names:
        return "Nu există niciun câmp valid. Fiecare câmp are nevoie de un nume."

    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        return (f"Două câmpuri au același nume: {', '.join(duplicates)}. "
                "Numele sunt folosite ca referință, deci trebuie unice.")

    for probe in probes:
        locator = probe.get("locator") or {}
        kind = str(locator.get("kind", "") or "")
        label = probe.get("name", "?")
        if kind in ("text_near", "text_self") and not str(locator.get("text", "")).strip():
            return (f"Câmpul «{label}» se localizează după o etichetă, dar "
                    "eticheta nu e completată.")
        if kind in ("screen_point", "screen_region"):
            if locator.get("x") in (None, "") or locator.get("y") in (None, ""):
                return (f"Câmpul «{label}» se localizează prin coordonate, dar "
                        "acestea lipsesc. Folosiți «Alege de pe Ecran».")

    if not conditions:
        return ("Nu există nicio condiție. Fără condiții regula nu se poate "
                "declanșa.")

    for condition in conditions:
        probe_name = str(condition.get("probe", "") or "")
        if probe_name not in names:
            return (f"Condiția se referă la câmpul «{probe_name}», care nu "
                    "există.")
        operator = str(condition.get("operator", "") or "")
        if operator not in OPERATORS:
            return f"Operator necunoscut: «{operator}»."
        if OPERATORS[operator][1] and not str(condition.get("value", "") or "").strip():
            return (f"Condiția «{probe_name} {OPERATORS[operator][0]}» are nevoie "
                    "de o valoare de comparat.")
        if operator == "between":
            parts = [p for p in re.split(r"[;,]", str(condition.get("value", "")))
                     if p.strip()]
            if len(parts) != 2:
                return (f"Condiția «{probe_name} este între» are nevoie de două "
                        "valori separate prin punct și virgulă, de exemplu 10;20.")

    if not marks:
        return ("Nu există niciun marcaj. Condițiile s-ar verifica, dar nimic nu "
                "s-ar desena pe ecran.")

    for mark in marks:
        target = str(mark.get("target", "") or "")
        if target and target not in names:
            return f"Marcajul indică câmpul «{target}», care nu există."
        shape = str(mark.get("shape", "box") or "box")
        if shape not in SHAPES:
            return f"Formă de marcaj necunoscută: «{shape}»."

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Marcaje
# ─────────────────────────────────────────────────────────────────────────────

#  formă          etichetă afișată
SHAPES: Dict[str, str] = {
    "box":           "Chenar dreptunghiular",
    "circle":        "Cerc / elipsă",
    "highlight":     "Highlight translucid (ca marker-ul)",
    "underline":     "Subliniere",
    "strikethrough": "Linie peste text",
    "arrow":         "Săgeată (una sau mai multe)",
    "badge":         "Etichetă cu text",
}

DEFAULT_MARK_STYLE: Dict[str, Any] = {
    "shape": "box",
    "color": "#E60000",
    "thickness": 3,
    "padding": 4,
    "opacity": 0.30,          # doar pentru "highlight"
    "pulse": True,
    "arrow_direction": "right",
    "arrow_count": 1,
    "arrow_gap": 6,
    "arrow_style": "slim",
    "arrow_length": 22,
    "arrow_width": 14,
    "text": "",               # doar pentru "badge"
    "text_color": "#FFFFFF",
}


def resolve_marks(rule: Dict[str, Any], readings: Dict[str, ProbeReading],
                  fallback_rect: Optional[Rect]) -> List[Dict[str, Any]]:
    """
    Transformă marcajele configurate în forme concrete de desenat.

    Fiecare marcaj indică un câmp țintă; dacă acel câmp nu a putut fi localizat
    pe ecran, marcajul se omite — un cerc desenat într-un loc greșit e mai rău
    decât niciun cerc.
    """
    marks = rule.get("marks") or []
    drawn: List[Dict[str, Any]] = []

    for index, mark in enumerate(marks):
        style = dict(DEFAULT_MARK_STYLE)
        style.update({k: v for k, v in mark.items() if k != "target"})

        target = str(mark.get("target", "") or "").strip()
        rect: Optional[Rect] = None

        if target:
            reading = readings.get(target)
            if reading is None:
                logger.warning("Marcajul %d indică câmpul '%s', care nu e definit.",
                               index + 1, target)
                continue
            rect = reading.rect
            if rect is None:
                logger.debug("Marcajul pentru '%s' se omite: câmpul nu e pe ecran.",
                             target)
                continue
        else:
            rect = fallback_rect

        if rect is None:
            continue

        shape = str(style.get("shape", "box") or "box")
        if shape not in SHAPES:
            logger.warning("Formă necunoscută '%s', se folosește 'box'.", shape)
            shape = "box"
        style["shape"] = shape
        style["rect"] = _grow(rect, int(_num(style.get("padding"), 4)))
        drawn.append(style)

    return drawn


def _grow(rect: Rect, padding: int) -> Rect:
    x, y, w, h = rect
    return (x - padding, y - padding, w + padding * 2, h + padding * 2)


def _num(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
