"""
FocusPilot — Rule Engine

Evaluează regulile de formatare condițională împotriva ferestrelor din sistem.

PRINCIPIU DE PROIECTARE
-----------------------
O regulă face EXACT ce spun setările ei. Nu există cazuri speciale pentru
anumite cuvinte, aplicații sau nume de reguli. Dacă o regulă nu se declanșează,
`explain()` spune de ce, în loc să eșueze în silence.

ORDINEA DE EVALUARE (toate filtrele configurate trebuie să treacă)
    1. Proces        — trigger.process_name
    2. Titlu         — trigger.window_title_pattern
    3. URL           — trigger.url_pattern
    4. Text          — trigger.search_text + additional_criteria, conform
                       trigger.text_condition și trigger.criteria_logic

UNDE SE DESENEAZĂ REPERUL (prima variantă disponibilă)
    1. Dreptunghiul elementului găsit prin UI Automation — se mișcă la scroll.
    2. Dreptunghiul șablonului imagine (snip) găsit pe ecran.
    3. Coordonatele salvate în regulă, conform region.mode.

Varianta 3 se folosește doar când potrivirea a venit din text sau titlu, nu
când a venit exclusiv din șablon: un șablon care nu mai e pe ecran înseamnă
că elementul s-a mutat, deci un chenar la coordonatele vechi ar fi greșit.
"""

import os
import re
import fnmatch
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Tuple, NamedTuple

from core import probe_engine

logger = logging.getLogger(__name__)

# Valorile citite la scanarea anterioară, pentru operatorul „s-a schimbat".
_previous_probe_values: Dict[str, Dict[str, str]] = {}

# ── Limite de siguranță pentru parcurgerea arborelui de accesibilitate ──
# Un arbore UIA de pagină web poate avea zeci de mii de noduri. Fără aceste
# limite o singură scanare poate dura secunde întregi și blochează aplicația.
UIA_MAX_NODES = 3000
UIA_MAX_DEPTH = 28
UIA_CACHE_TTL_SEC = 0.45

# Numărul de caractere păstrate dintr-un nume de element UIA.
UIA_MAX_TEXT_LEN = 400

TEXT_CONDITIONS = ("contains", "equals", "starts_with", "constellation", "regex")


class MatchResult(NamedTuple):
    """Rezultatul complet al evaluării unei reguli pe o fereastră."""

    matched: bool
    geometry: Optional[Tuple[int, int, int, int]]  # (x, y, w, h) pe ecranul virtual
    anchor: str          # "uia" | "template" | "configured" | "none"
    reason: str          # explicație lizibilă, pentru diagnostic și log
    # Marcaje rezolvate, pentru regulile cu câmpuri și condiții. Fiecare are
    # propria formă, culoare și dreptunghi, deci o regulă poate evidenția mai
    # multe câmpuri simultan, diferit.
    marks: Tuple[Dict[str, Any], ...] = ()

    @property
    def drawable(self) -> bool:
        return self.matched and (self.geometry is not None or bool(self.marks))


# ─────────────────────────────────────────────────────────────────────────────
# Disponibilitatea dependențelor opționale
# ─────────────────────────────────────────────────────────────────────────────

class _Capabilities:
    """
    Verifică o singură dată dacă bibliotecile de detecție sunt instalate și
    raportează lipsa lor VIZIBIL. Varianta anterioară prindea ImportError într-un
    `except Exception: pass`, deci detecția era moartă fără niciun indiciu.
    """

    def __init__(self) -> None:
        self._uia: Optional[bool] = None
        self._cv: Optional[bool] = None
        self._lock = threading.Lock()

    @property
    def uia(self) -> bool:
        """True dacă `uiautomation` poate fi folosit (detecție text în aplicații)."""
        if self._uia is None:
            with self._lock:
                if self._uia is None:
                    try:
                        import uiautomation  # noqa: F401
                        self._uia = True
                        logger.info("[CAPABILITĂȚI] UI Automation disponibil.")
                    except Exception as exc:
                        self._uia = False
                        logger.error(
                            "[CAPABILITĂȚI] UI Automation INDISPONIBIL (%s). "
                            "Detecția textului din pagini și aplicații nu va funcționa. "
                            "Instalați cu:  pip install uiautomation", exc
                        )
        return self._uia

    @property
    def opencv(self) -> bool:
        """True dacă OpenCV e disponibil (necesar pentru potrivirea de șabloane)."""
        if self._cv is None:
            with self._lock:
                if self._cv is None:
                    try:
                        import cv2  # noqa: F401
                        self._cv = True
                        logger.info("[CAPABILITĂȚI] OpenCV disponibil.")
                    except Exception as exc:
                        self._cv = False
                        logger.error(
                            "[CAPABILITĂȚI] OpenCV INDISPONIBIL (%s). Urmărirea prin "
                            "șablon imagine (snip) nu va funcționa. "
                            "Instalați cu:  pip install opencv-python", exc
                        )
        return self._cv

    def missing(self) -> List[str]:
        out = []
        if not self.uia:
            out.append("uiautomation")
        if not self.opencv:
            out.append("opencv-python")
        return out


CAPABILITIES = _Capabilities()


def _ensure_com_initialized() -> None:
    """
    Inițializează COM pe firul de execuție curent.

    UI Automation este o componentă COM. MonitorEngine rulează scanarea pe un
    fir de fundal, iar COM trebuie inițializat separat pe fiecare fir — altfel
    orice apel UIA eșuează. Aceasta era cauza pentru care detecția funcționa în
    dialogul de diagnostic (fir principal) dar nu în timpul monitorizării.
    """
    state = getattr(_com_state, "ready", False)
    if state:
        return
    try:
        import ctypes
        COINIT_APARTMENTTHREADED = 0x2
        RPC_E_CHANGED_MODE = -2147417850  # 0x80010106: deja init cu alt model
        hr = ctypes.windll.ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
        # S_OK (0), S_FALSE (1) și RPC_E_CHANGED_MODE sunt toate acceptabile.
        if hr not in (0, 1) and hr != RPC_E_CHANGED_MODE:
            logger.debug("CoInitializeEx a returnat 0x%08X", hr & 0xFFFFFFFF)
    except Exception as exc:
        logger.debug("CoInitializeEx indisponibil: %s", exc)
    _com_state.ready = True


_com_state = threading.local()


# ─────────────────────────────────────────────────────────────────────────────
# Instantaneu al textului accesibil dintr-o fereastră
# ─────────────────────────────────────────────────────────────────────────────

class UiaSnapshot(NamedTuple):
    """Textul vizibil dintr-o fereastră, cu coordonatele fiecărui element."""

    items: List[Tuple[str, Tuple[int, int, int, int]]]  # (text, (x, y, w, h))
    truncated: bool          # True dacă s-a atins limita de noduri
    captured_at: float

    def find(self, needle: str, case_sensitive: bool) -> Optional[Tuple[int, int, int, int]]:
        """Primul element al cărui text conține `needle`."""
        probe = needle if case_sensitive else needle.lower()
        for text, rect in self.items:
            hay = text if case_sensitive else text.lower()
            if probe in hay:
                return rect
        return None

    def joined_text(self) -> str:
        return "\n".join(t for t, _ in self.items)


_snapshot_cache: Dict[int, Tuple[Tuple[int, int, int, int], UiaSnapshot]] = {}
_snapshot_lock = threading.Lock()


def _window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    try:
        import win32gui
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return None
        rect = win32gui.GetWindowRect(hwnd)
        # O fereastră minimizată raportează coordonate puternic negative.
        if rect[0] < -30000 or rect[1] < -30000:
            return None
        if (rect[2] - rect[0]) < 80 or (rect[3] - rect[1]) < 80:
            return None
        return rect
    except Exception:
        return None


def capture_window_text(hwnd: int, force: bool = False) -> Optional[UiaSnapshot]:
    """
    Parcurge o singură dată arborele de accesibilitate al ferestrei și întoarce
    tot textul vizibil cu coordonatele lui.

    Un singur instantaneu deservește TOATE regulile și TOATE criteriile dintr-un
    ciclu de scanare. Varianta anterioară pornea o căutare UIA completă pentru
    fiecare criteriu al fiecărei reguli, de două ori (o dată ca să decidă
    potrivirea, o dată ca să calculeze coordonatele) — de unde încetinirea.
    """
    if not CAPABILITIES.uia:
        return None

    rect = _window_rect(hwnd)
    if rect is None:
        return None

    now = time.time()
    if not force:
        with _snapshot_lock:
            cached = _snapshot_cache.get(hwnd)
        if cached is not None:
            cached_rect, snap = cached
            if cached_rect == rect and (now - snap.captured_at) < UIA_CACHE_TTL_SEC:
                return snap

    _ensure_com_initialized()

    items: List[Tuple[str, Tuple[int, int, int, int]]] = []
    truncated = False

    try:
        import uiautomation as auto

        # Fără această setare fiecare căutare așteaptă implicit secunde întregi.
        try:
            auto.SetGlobalSearchTimeout(0)
        except Exception:
            pass

        root = auto.ControlFromHandle(hwnd)
        if root is None:
            return None

        win_l, win_t, win_r, win_b = rect
        budget = UIA_MAX_NODES
        queue: List[Tuple[Any, int]] = [(root, 0)]

        while queue:
            if budget <= 0:
                truncated = True
                break
            node, depth = queue.pop(0)
            budget -= 1

            try:
                # Un subarbore în afara ecranului nu poate conține text vizibil:
                # îl sărim complet. Aceasta este principala economie de timp.
                if getattr(node, "IsOffscreen", False):
                    continue

                box = node.BoundingRectangle
                if box is None:
                    continue
                w, h = box.width(), box.height()
                if w <= 0 or h <= 0:
                    continue

                # Păstrăm doar ce se află efectiv în interiorul ferestrei.
                inside = (box.left >= win_l - 6 and box.top >= win_t - 6
                          and box.right <= win_r + 6 and box.bottom <= win_b + 6)

                if inside:
                    name = node.Name or ""
                    if name:
                        items.append((name[:UIA_MAX_TEXT_LEN],
                                      (box.left, box.top, w, h)))

                if depth < UIA_MAX_DEPTH:
                    for child in node.GetChildren():
                        queue.append((child, depth + 1))
            except Exception:
                # Un nod poate dispărea în timpul parcurgerii (pagină dinamică).
                continue

    except Exception as exc:
        logger.debug("Parcurgere UIA eșuată pentru hwnd=%s: %s", hwnd, exc)
        return None

    snap = UiaSnapshot(items=items, truncated=truncated, captured_at=now)
    with _snapshot_lock:
        _snapshot_cache[hwnd] = (rect, snap)
        if len(_snapshot_cache) > 24:          # nu lăsăm cache-ul să crească
            oldest = min(_snapshot_cache.items(), key=lambda kv: kv[1][1].captured_at)
            _snapshot_cache.pop(oldest[0], None)
    if truncated:
        logger.debug("Instantaneu UIA truncat la %d noduri (hwnd=%s).",
                     UIA_MAX_NODES, hwnd)
    return snap


def invalidate_snapshot_cache(hwnd: Optional[int] = None) -> None:
    """Forțează recitirea arborelui la următoarea scanare."""
    with _snapshot_lock:
        if hwnd is None:
            _snapshot_cache.clear()
        else:
            _snapshot_cache.pop(hwnd, None)


# ─────────────────────────────────────────────────────────────────────────────
# Potrivirea de șabloane imagine (snip), cu limitare de ritm
# ─────────────────────────────────────────────────────────────────────────────

_template_cache: Dict[str, Tuple[float, Optional[Tuple[int, int, int, int]]]] = {}
_template_lock = threading.Lock()
_missing_templates: set = set()
TEMPLATE_CACHE_TTL_SEC = 1.2


def locate_template(template_path: str, base_dir: str,
                    confidence: float = 0.78) -> Optional[Tuple[int, int, int, int]]:
    """
    Caută un șablon imagine pe ecran și întoarce (x, y, w, h).

    O singură căutare implică o captură a întregului spațiu virtual (pe 3
    monitoare) plus o potrivire OpenCV — de ordinul sutelor de milisecunde.
    Rezultatul e păstrat scurt timp ca să nu se repete la fiecare scanare.
    """
    if not template_path or not CAPABILITIES.opencv:
        return None

    path = template_path if os.path.isabs(template_path) else os.path.join(base_dir, template_path)
    if not os.path.exists(path):
        # Avertizăm o singură dată pe cale: altfel mesajul s-ar repeta la
        # fiecare scanare și ar umple jurnalul.
        if path not in _missing_templates:
            _missing_templates.add(path)
            logger.warning("[ȘABLON] Fișierul lipsește, regula va folosi "
                           "coordonatele salvate: %s", path)
        return None

    now = time.time()
    with _template_lock:
        hit = _template_cache.get(path)
        if hit is not None and (now - hit[0]) < TEMPLATE_CACHE_TTL_SEC:
            return hit[1]

    found: Optional[Tuple[int, int, int, int]] = None
    try:
        import pyautogui
        box = pyautogui.locateOnScreen(path, confidence=confidence)
        if box is not None:
            found = (int(box.left), int(box.top), int(box.width), int(box.height))
    except Exception as exc:
        logger.debug("Potrivire șablon eșuată pentru %s: %s", path, exc)

    with _template_lock:
        _template_cache[path] = (now, found)
    return found


# ─────────────────────────────────────────────────────────────────────────────
# Motorul de reguli
# ─────────────────────────────────────────────────────────────────────────────

class RuleEngine:
    """Evaluator de condiții configurate de utilizator, în stil Microsoft Excel."""

    # ── Potrivire de text ────────────────────────────────────────────────────

    @classmethod
    def match_string(cls, pattern: str, text: str, is_regex: bool = False,
                     case_sensitive: bool = False) -> bool:
        """
        Potrivește un ȘABLON DE FEREASTRĂ (titlu, URL, proces) cu un text.

        Acceptă wildcard-uri `*` și `?`, alternative separate prin `|`, sau o
        expresie regulată dacă `is_regex`. Un șablon fără wildcard se potrivește
        ca subșir, pentru ca utilizatorul să poată scrie doar un cuvânt-cheie.

        Atenție: separarea pe `|` se aplică DOAR șabloanelor de fereastră, nu
        textului căutat în pagină — vezi `text_matches`.
        """
        if not pattern or pattern == "*":
            return True
        if not text:
            return False

        if is_regex:
            try:
                return bool(re.search(pattern, text, 0 if case_sensitive else re.IGNORECASE))
            except re.error as exc:
                logger.warning("Expresie regulată invalidă %r: %s", pattern, exc)
                return False

        if "|" in pattern:
            return any(
                cls.match_string(part.strip(), text, False, case_sensitive)
                for part in pattern.split("|") if part.strip()
            )

        pat = pattern if case_sensitive else pattern.lower()
        txt = text if case_sensitive else text.lower()

        if "*" in pat or "?" in pat:
            return fnmatch.fnmatch(txt, pat)
        return pat in txt

    @classmethod
    def text_matches(cls, needle: str, haystack: str, condition: str = "contains",
                     case_sensitive: bool = False, is_regex: bool = False) -> bool:
        """
        Aplică `trigger.text_condition` așa cum a fost configurată.

        Varianta anterioară citea `text_condition` într-o variabilă și nu o
        folosea niciodată: orice setare se comporta ca "contains", deci
        "Este exact" și "Începe cu" nu aveau niciun efect.

        Textul căutat este tratat LITERAL. Nu se despică pe `;` sau `|`, pentru
        ca o frază care conține aceste caractere să fie căutată întreagă. Pentru
        mai multe cuvinte-cheie se folosește condiția "constellation" sau
        criteriile suplimentare din editor.
        """
        if not needle:
            return True
        if not haystack:
            return False

        if is_regex or condition == "regex":
            try:
                return bool(re.search(needle, haystack, 0 if case_sensitive else re.IGNORECASE))
            except re.error as exc:
                logger.warning("Expresie regulată invalidă %r: %s", needle, exc)
                return False

        probe = needle if case_sensitive else needle.lower()
        hay = haystack if case_sensitive else haystack.lower()

        if condition == "equals":
            # Comparăm cu fiecare linie: textul extras din pagină e multi-linie.
            return any(line.strip() == probe.strip() for line in hay.splitlines())
        if condition == "starts_with":
            return any(line.strip().startswith(probe.strip()) for line in hay.splitlines())
        if condition == "constellation":
            words = [w.strip() for w in re.split(r"[;|]", probe) if w.strip()]
            return bool(words) and all(w in hay for w in words)
        # "contains" (implicit)
        return probe in hay

    @classmethod
    def extract_criteria_list(cls, trigger: Dict[str, Any]) -> Tuple[List[str], str]:
        """
        Întoarce (lista_de_criterii, logica) exact cum au fost configurate.

        `search_text` este criteriul principal și rămâne o singură frază
        literală. `additional_criteria` sunt criteriile adăugate explicit din
        editor cu butonul [+]. Logica vine din `criteria_logic` (OR / AND) și
        nu se mai ghicește din punctuația textului.
        """
        criteria: List[str] = []

        primary = str(trigger.get("search_text", "") or "").strip()
        if primary:
            criteria.append(primary)

        additional = trigger.get("additional_criteria", "")
        if isinstance(additional, (list, tuple)):
            extra = [str(x).strip() for x in additional if str(x).strip()]
        elif isinstance(additional, str) and additional.strip():
            # Un singur câmp text cu mai multe criterii: linii, ';' sau '|'.
            extra = [p.strip() for p in re.split(r"[\n\r;|]+", additional) if p.strip()]
        else:
            extra = []
        criteria.extend(extra)

        logic = str(trigger.get("criteria_logic", "") or "").strip().upper()
        if logic not in ("AND", "OR"):
            logic = "OR"

        seen = set()
        unique = [c for c in criteria if not (c in seen or seen.add(c))]
        return unique, logic

    # ── Evaluarea completă a unei reguli ─────────────────────────────────────

    @classmethod
    def evaluate(cls, rule: Dict[str, Any], window_info: Dict[str, Any],
                 virtual_screen: Optional[Tuple[int, int, int, int]] = None,
                 active_step: Optional[Dict[str, Any]] = None,
                 base_dir: Optional[str] = None) -> MatchResult:
        """
        Decide într-o singură trecere dacă regula se aplică și unde se desenează.

        Întoarce un MatchResult cu motivul deciziei, ca interfața de diagnostic
        să poată explica utilizatorului ce filtru a picat.
        """
        if not rule.get("enabled", True):
            return MatchResult(False, None, "none", "Regula este dezactivată.")

        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        trigger = (active_step.get("trigger") if active_step else None) or rule.get("trigger", {})
        win_title = str(window_info.get("title", "") or "")
        proc_name = str(window_info.get("process_name", "") or "")
        url = str(window_info.get("url", "") or "")
        hwnd = window_info.get("hwnd")

        case_sensitive = bool(trigger.get("case_sensitive", False))
        is_regex = bool(trigger.get("is_regex", False))
        condition = str(trigger.get("text_condition", "contains") or "contains")
        if condition not in TEXT_CONDITIONS:
            condition = "contains"

        # ── 1. Filtru proces ────────────────────────────────────────────────
        target_proc = str(trigger.get("process_name", "") or "").strip().lower()
        if target_proc and target_proc not in ("*", "orice proces", "any"):
            if not cls._process_matches(target_proc, proc_name):
                return MatchResult(False, None, "none",
                                   f"Proces nepotrivit: regula cere '{target_proc}', "
                                   f"fereastra rulează '{proc_name or 'necunoscut'}'.")

        # ── 2. Filtru titlu fereastră ───────────────────────────────────────
        title_pattern = str(trigger.get("window_title_pattern", "") or "").strip()
        if title_pattern and title_pattern != "*":
            if not cls.match_string(cls._normalize_pattern(title_pattern), win_title,
                                    case_sensitive=False):
                return MatchResult(False, None, "none",
                                   f"Titlu nepotrivit: regula cere '{title_pattern}', "
                                   f"fereastra are '{win_title[:60]}'.")

        # ── 3. Filtru URL ───────────────────────────────────────────────────
        # Acest filtru lipsea complet din motor: o regulă cu URL configurat se
        # declanșa pe orice pagină din fereastra respectivă.
        url_pattern = str(trigger.get("url_pattern", "") or "").strip()
        if url_pattern and url_pattern != "*":
            if not url:
                # URL-ul nu a putut fi citit. Titlul rămâne singurul filtru;
                # nu respingem regula, dar o consemnăm pentru diagnostic.
                logger.debug("Regula '%s' are filtru URL dar URL-ul ferestrei "
                             "nu e disponibil; se continuă fără el.",
                             rule.get("name"))
            elif not cls.match_string(cls._normalize_pattern(url_pattern), url,
                                      case_sensitive=False):
                return MatchResult(False, None, "none",
                                   f"URL nepotrivit: regula cere '{url_pattern}', "
                                   f"pagina este '{url[:70]}'.")

        # ── 4a. Câmpuri și condiții (modelul Excel) ─────────────────────────
        # Dacă regula definește câmpuri și condiții, acestea decid. Regulile
        # care folosesc doar `trigger.search_text` merg pe calea de mai jos,
        # deci configurațiile existente funcționează nemodificate.
        if probe_engine.uses_conditions(rule):
            return cls._evaluate_conditions(rule, window_info, virtual_screen,
                                            active_step, hwnd)

        # ── 4b. Filtru text ─────────────────────────────────────────────────
        criteria, logic = cls.extract_criteria_list(trigger)

        if not criteria:
            # Fără criterii de text regula se bazează doar pe fereastră.
            geo = cls.resolve_geometry(rule, window_info, virtual_screen,
                                       located=None, active_step=active_step)
            return MatchResult(True, geo, "configured" if geo else "none",
                               "Potrivire pe fereastră (fără criterii de text).")

        snapshot = capture_window_text(hwnd) if hwnd else None
        page_text = snapshot.joined_text() if snapshot else ""
        haystack = f"{win_title}\n{window_info.get('extra_text', '') or ''}\n{page_text}"

        hits: Dict[str, Optional[Tuple[int, int, int, int]]] = {}
        for crit in criteria:
            if cls.text_matches(crit, haystack, condition, case_sensitive, is_regex):
                # Coordonatele elementului, dacă textul a venit din pagină.
                hits[crit] = snapshot.find(crit, case_sensitive) if snapshot else None
            else:
                hits[crit] = None

        found = [c for c in criteria
                 if cls.text_matches(c, haystack, condition, case_sensitive, is_regex)]

        if logic == "AND":
            text_ok = len(found) == len(criteria)
        else:
            text_ok = len(found) > 0

        located: Optional[Tuple[int, int, int, int]] = None
        anchor = "none"

        if text_ok:
            # Ancorăm pe primul criteriu găsit care are coordonate pe ecran.
            for crit in found:
                if hits.get(crit):
                    located = hits[crit]
                    anchor = "uia"
                    break

        # ── 5. Șablon imagine, dacă textul nu a fost găsit ──────────────────
        region = (active_step.get("region") if active_step else None) or rule.get("region", {})
        template = str(region.get("template_image", "") or "").strip()
        matched_by_template = False

        if not text_ok and template:
            tpl_rect = locate_template(template, base_dir)
            if tpl_rect:
                located = tpl_rect
                anchor = "template"
                matched_by_template = True

        if not text_ok and not matched_by_template:
            detail = cls._explain_text_miss(criteria, logic, snapshot, template)
            return MatchResult(False, None, "none", detail)

        # ── 6. Geometrie ────────────────────────────────────────────────────
        geo = cls.resolve_geometry(rule, window_info, virtual_screen,
                                   located=located, active_step=active_step,
                                   allow_configured_fallback=not matched_by_template)

        if geo is None:
            return MatchResult(
                True, None, "none",
                "Criteriu găsit, dar nu s-au putut determina coordonatele "
                "chenarului. Folosiți 'Alege Interactiv de pe Ecran' în editor."
            )

        if anchor == "none":
            anchor = "configured"
        where = {"uia": "ancorat pe elementul din pagină",
                 "template": "ancorat pe șablonul imagine",
                 "configured": "la coordonatele configurate"}[anchor]
        return MatchResult(True, geo, anchor,
                           f"Potrivire: '{found[0] if found else template}' — {where}.")

    # ── Evaluarea pe câmpuri și condiții ─────────────────────────────────────

    @classmethod
    def _evaluate_conditions(cls, rule: Dict[str, Any], window_info: Dict[str, Any],
                             virtual_screen: Optional[Tuple[int, int, int, int]],
                             active_step: Optional[Dict[str, Any]],
                             hwnd: Optional[int]) -> MatchResult:
        """
        Evaluează o regulă de forma „dacă câmpul X are valoarea Z și câmpul Y
        are valoarea C, atunci marchează...".
        """
        snapshot = capture_window_text(hwnd) if hwnd else None
        window_rect = window_info.get("rect") or (0, 0, 0, 0)

        rule_id = str(rule.get("id", "") or "")
        previous = _previous_probe_values.get(rule_id, {})

        outcome = probe_engine.evaluate_conditions(rule, snapshot, window_rect,
                                                   previous_values=previous)

        # Reținem valorile pentru operatorul „s-a schimbat".
        _previous_probe_values[rule_id] = {
            name: (reading.value or "")
            for name, reading in outcome.readings.items()
            if reading.value is not None
        }

        if not outcome.matched:
            failing = [o for o in outcome.outcomes if not o.passed]
            if failing:
                detail = failing[0].describe().lstrip("❌ ").strip()
            else:
                detail = "Regula nu are nicio condiție definită."
            return MatchResult(False, None, "none", detail)

        fallback = cls.resolve_geometry(rule, window_info, virtual_screen,
                                        located=None, active_step=active_step)
        marks = probe_engine.resolve_marks(rule, outcome.readings, fallback)

        if not marks:
            return MatchResult(
                True, None, "none",
                "Condițiile sunt îndeplinite, dar niciun marcaj nu a putut fi "
                "plasat: câmpurile țintă nu sunt vizibile pe ecran."
            )

        # Geometria principală rămâne primul marcaj, pentru compatibilitate cu
        # codul care așteaptă un singur dreptunghi.
        passed = len(outcome.outcomes)
        return MatchResult(True, marks[0]["rect"], "probe",
                           f"{passed} condiție(i) îndeplinite ({outcome.logic}); "
                           f"{len(marks)} marcaj(e).",
                           marks=tuple(marks))

    # ── Ajutătoare pentru evaluare ───────────────────────────────────────────

    @staticmethod
    def _normalize_pattern(pattern: str) -> str:
        """
        Un șablon fără wildcard devine `*cuvânt*`, dar fiecare alternativă
        separată prin `|` este tratată individual.
        """
        parts = []
        for part in pattern.split("|"):
            p = part.strip()
            if not p:
                continue
            parts.append(p if ("*" in p or "?" in p) else f"*{p}*")
        return "|".join(parts) if parts else "*"

    @staticmethod
    def _process_matches(target: str, actual: str) -> bool:
        """
        Potrivește numele procesului. `browser` acoperă orice browser cunoscut,
        ca o regulă să funcționeze indiferent dacă pagina e în Edge sau Chrome.
        """
        browsers = {"msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe"}
        actual = (actual or "").lower()
        if target in ("browser", "browser (edge + chrome)"):
            return actual in browsers
        if target in browsers:
            # Numirea unui browser anume acceptă tot familia, așa cum se
            # comporta și varianta anterioară și cum arată dropdown-ul.
            return actual in browsers
        return RuleEngine.match_string(target, actual, case_sensitive=False)

    @staticmethod
    def _explain_text_miss(criteria: List[str], logic: str,
                           snapshot: Optional[UiaSnapshot], template: str) -> str:
        """Mesaj concret despre de ce criteriile nu s-au potrivit."""
        missing = ", ".join(f"'{c[:40]}'" for c in criteria[:3])
        if snapshot is None:
            extra = ("Textul paginii nu a putut fi citit. "
                     + ("Instalați 'uiautomation'." if not CAPABILITIES.uia
                        else "Fereastra nu expune text accesibil."))
        elif snapshot.truncated:
            extra = (f"S-au citit primele {UIA_MAX_NODES} elemente ale paginii; "
                     "textul poate fi mai jos în pagină.")
        else:
            extra = f"S-au verificat {len(snapshot.items)} elemente din fereastră."
        tpl = ""
        if template:
            tpl = (" Șablonul imagine nu a fost găsit pe ecran."
                   if CAPABILITIES.opencv
                   else " Șablonul imagine nu a putut fi căutat: lipsește 'opencv-python'.")
        word = "toate criteriile" if logic == "AND" else "niciun criteriu"
        return f"Nu s-a găsit {word} ({missing}). {extra}{tpl}"

    # ── Geometria reperului vizual ───────────────────────────────────────────

    @classmethod
    def resolve_geometry(cls, rule: Dict[str, Any], window_info: Dict[str, Any],
                         virtual_screen: Optional[Tuple[int, int, int, int]] = None,
                         located: Optional[Tuple[int, int, int, int]] = None,
                         active_step: Optional[Dict[str, Any]] = None,
                         allow_configured_fallback: bool = True
                         ) -> Optional[Tuple[int, int, int, int]]:
        """
        Calculează dreptunghiul (x, y, w, h) unde se desenează reperul.

        `located` este dreptunghiul elementului găsit pe ecran, dacă există.
        `allow_configured_fallback` este False când potrivirea a venit exclusiv
        din șablon imagine: în acest caz coordonatele salvate sunt depășite.
        """
        region = (active_step.get("region") if active_step and active_step.get("region")
                  else rule.get("region", {})) or {}
        visual = ((active_step.get("visual_cue") if active_step else None)
                  or rule.get("visual_cue", {})) or {}

        win_rect = window_info.get("rect") or (0, 0, 1920, 1080)
        left, top, right, bottom = win_rect
        win_w = max(80, right - left)
        win_h = max(80, bottom - top)

        box_scope = str(visual.get("box_scope", "custom_region") or "custom_region")
        pad = cls._as_int(visual.get("padding", 4), 4)
        conf_w = cls._as_int(region.get("width", 350), 350)
        conf_h = cls._as_int(region.get("height", 60), 60)
        mode = str(region.get("mode", "window_relative") or "window_relative")

        # "entire_window" este o alegere explicită despre ZONĂ și are prioritate
        # față de ancorarea pe element: utilizatorul a cerut toată fereastra.
        if mode == "entire_window":
            return (left + 8, top + 8, win_w - 16, win_h - 16)

        # ── Varianta 1: ancorare pe elementul găsit pe ecran ────────────────
        if located is not None:
            ux, uy, uw, uh = located

            if box_scope == "exact_text":
                return (ux - pad, uy - pad, uw + pad * 2, uh + pad * 2)

            if box_scope == "full_row":
                return (left + 8, uy - pad, win_w - 16, max(uh, conf_h) + pad * 2)

            # "custom_region": păstrăm lățimea configurată de utilizator,
            # aliniată la stânga elementului găsit.
            target_w = max(conf_w, uw)
            target_h = max(conf_h, uh)
            target_x = ux - pad
            target_y = uy - max(0, (target_h - uh) // 2) - pad
            # Nu depășim marginea ferestrei.
            target_w = min(target_w, win_w - 16)
            return (int(target_x), int(target_y), int(target_w + pad * 2), int(target_h + pad * 2))

        # ── Varianta 2: coordonatele configurate de utilizator ──────────────
        if not allow_configured_fallback:
            logger.debug("Regula '%s': șablon negăsit pe ecran, nu se desenează "
                         "la coordonate vechi.", rule.get("name"))
            return None

        abs_x = cls._as_int(region.get("abs_x", 0), 0)
        abs_y = cls._as_int(region.get("abs_y", 0), 0)

        if mode == "screen_absolute":
            return (abs_x - pad, abs_y - pad, conf_w + pad * 2, conf_h + pad * 2)

        if mode == "visual_track":
            # Modul "visual_track" întorcea None aici, deci regulile create cu
            # selectorul interactiv nu desenau NIMIC atunci când elementul nu
            # era localizat — chiar dacă textul fusese găsit. Acum se folosesc
            # coordonatele capturate la selecție.
            if abs_x or abs_y:
                return (abs_x - pad, abs_y - pad, conf_w + pad * 2, conf_h + pad * 2)
            # fără coordonate absolute: cădem pe poziția relativă

        rel_x = cls._as_float(region.get("rel_x", 0.2), 0.2)
        rel_y = cls._as_float(region.get("rel_y", 0.3), 0.3)
        target_x = int(left + rel_x * win_w)
        target_y = int(top + rel_y * win_h)

        if box_scope == "full_row":
            return (left + 8, target_y - pad, win_w - 16, conf_h + pad * 2)

        return (target_x - pad, target_y - pad,
                min(conf_w, win_w - 16) + pad * 2,
                min(conf_h, win_h - 16) + pad * 2)

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    # ── Pași secvențiali ─────────────────────────────────────────────────────

    @classmethod
    def get_active_step_for_rule(cls, rule: Dict[str, Any],
                                 elapsed_sec: float) -> Optional[Dict[str, Any]]:
        """Pasul activ din succesiunea configurată, după timpul scurs."""
        steps = rule.get("steps") or []
        if not steps:
            return None

        for idx, step in enumerate(steps):
            start = cls._as_float(step.get("delay_sec", 0), 0.0)
            dur = cls._as_float(step.get("duration_sec", 4), 4.0)
            end = start + dur if dur > 0 else float("inf")
            if start <= elapsed_sec < end:
                out = dict(step)
                out["step_index"] = idx + 1
                out["total_steps"] = len(steps)
                return out
        return None

    # ── Compatibilitate cu apelurile existente ───────────────────────────────

    @classmethod
    def evaluate_rule(cls, rule: Dict[str, Any], window_info: Dict[str, Any]) -> bool:
        """Varianta boolean, păstrată pentru codul care o folosea deja."""
        return cls.evaluate(rule, window_info).matched

    @classmethod
    def calculate_cue_geometry(cls, rule: Dict[str, Any], window_info: Dict[str, Any],
                               virtual_screen: Tuple[int, int, int, int],
                               active_step: Optional[Dict[str, Any]] = None
                               ) -> Optional[Tuple[int, int, int, int]]:
        """Varianta care întoarce doar coordonatele, pentru codul existent."""
        return cls.evaluate(rule, window_info, virtual_screen,
                            active_step=active_step).geometry

    @classmethod
    def find_uia_control_geometry(cls, hwnd: int, search_text: str
                                 ) -> Optional[Tuple[int, int, int, int]]:
        """Caută un singur text în fereastră și întoarce coordonatele lui."""
        if not hwnd or not search_text:
            return None
        snap = capture_window_text(hwnd)
        if snap is None:
            return None
        rect = snap.find(search_text, case_sensitive=False)
        if rect is None:
            return None
        x, y, w, h = rect
        return (x - 6, y - 4, w + 12, h + 8)

    @classmethod
    def find_uia_criteria_geometry(cls, hwnd: int, criteria: List[str],
                                   logic: str = "OR"
                                   ) -> Optional[Tuple[int, int, int, int]]:
        """Coordonatele criteriilor: primul găsit (OR) sau încadrarea tuturor (AND)."""
        if not hwnd or not criteria:
            return None
        snap = capture_window_text(hwnd)
        if snap is None:
            return None

        found = []
        for crit in criteria:
            rect = snap.find(crit, case_sensitive=False)
            if rect is None:
                if logic == "AND":
                    return None
                continue
            if logic == "OR":
                return rect
            found.append(rect)

        if not found:
            return None
        min_x = min(r[0] for r in found)
        min_y = min(r[1] for r in found)
        max_x = max(r[0] + r[2] for r in found)
        max_y = max(r[1] + r[3] for r in found)
        return (min_x, min_y, max_x - min_x, max_y - min_y)
