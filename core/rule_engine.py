"""
FocusPilot — Rule Engine
Evaluează regulile de formatare condițională împotriva stării curente a ferestrelor
și a ecranelor din sistem (suport complet pentru cele 3 monitoare).
"""

import re
import fnmatch
from typing import Dict, Any, List, Optional, Tuple


class RuleEngine:
    """Motor de evaluare a condițiilor definite de utilizator stil Microsoft Excel."""

    @classmethod
    def extract_criteria_list(cls, trigger: Dict[str, Any]) -> Tuple[List[str], str]:
        """
        Extrage lista de criterii de căutare și modul logic (AND / OR).
        Suportă:
          - search_text principal
          - additional_criteria (șir sau listă)
          - delimitatori '|' (OR) și ';' / '+' (AND)
        """
        primary = trigger.get("search_text", "").strip()
        additional = trigger.get("additional_criteria", "")
        logic = trigger.get("criteria_logic", "").strip().upper()

        raw_items = []
        if primary:
            raw_items.append(primary)

        if isinstance(additional, list):
            for item in additional:
                if str(item).strip():
                    raw_items.append(str(item).strip())
        elif isinstance(additional, str) and additional.strip():
            parts = [p.strip() for p in re.split(r"[\n\r;|]+", additional) if p.strip()]
            raw_items.extend(parts)

        if not logic:
            if primary and "|" in primary:
                logic = "OR"
            elif primary and (";" in primary or "+" in primary):
                logic = "AND"
            else:
                logic = "OR"

        expanded = []
        for c in raw_items:
            if logic == "OR" and "|" in c:
                expanded.extend([p.strip() for p in c.split("|") if p.strip()])
            elif logic == "AND" and (";" in c or "+" in c):
                expanded.extend([p.strip() for p in re.split(r"[;+]", c) if p.strip()])
            else:
                expanded.append(c)

        seen = set()
        final_list = []
        for item in expanded:
            if item and item not in seen:
                seen.add(item)
                final_list.append(item)

        return (final_list, logic)

    @classmethod
    def find_uia_criteria_geometry(cls, hwnd: int, criteria: List[str], logic: str = "OR") -> Optional[Tuple[int, int, int, int]]:
        """
        Caută controale UIA conform listei de criterii și logicii specificate (AND / OR).
        Dacă logica este AND și toate sunt găsite, returnează un bounding box unificat.
        Dacă logica este OR, returnează primul control găsit.
        """
        if not hwnd or not criteria:
            return None

        found_geos = []
        for crit in criteria:
            geo = cls.find_uia_control_geometry(hwnd, crit)
            if not geo and ("'" in crit or '"' in crit):
                clean_crit = crit.replace("'", "").replace('"', "").strip()
                geo = cls.find_uia_control_geometry(hwnd, clean_crit)
            if not geo and "$" in crit:
                clean_crit = crit.replace("$", "").strip()
                geo = cls.find_uia_control_geometry(hwnd, clean_crit)

            if geo:
                found_geos.append(geo)
                if logic == "OR":
                    return geo
            else:
                if logic == "AND":
                    return None

        if logic == "AND" and len(found_geos) == len(criteria) and found_geos:
            min_x = min(g[0] for g in found_geos)
            min_y = min(g[1] for g in found_geos)
            max_x = max(g[0] + g[2] for g in found_geos)
            max_y = max(g[1] + g[3] for g in found_geos)
            return (min_x, min_y, max_x - min_x, max_y - min_y)

        return found_geos[0] if found_geos else None

    @classmethod
    def find_uia_control_geometry(cls, hwnd: int, search_text: str) -> Optional[Tuple[int, int, int, int]]:
        """Caută un control cu textul specificat prin UI Automation în fereastra dată (doar dacă e vizibil pe ecran)."""
        if not hwnd or not search_text:
            return None

        # Verificare strictă că fereastra este validă, vizibilă și nu e minimizată
        win_rect = None
        try:
            import win32gui
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None
            win_rect = win32gui.GetWindowRect(hwnd)
            if win_rect[0] < -10000 or win_rect[1] < -10000:
                return None
            # Verificăm că fereastra are dimensiune reală
            if (win_rect[2] - win_rect[0]) < 100 or (win_rect[3] - win_rect[1]) < 100:
                return None
        except Exception:
            return None

        # Căutare UIA live fără cache persistent (elimină complet fantomele de pe alte tab-uri/pagini)
        try:
            import uiautomation as auto
            win = auto.ControlFromHandle(hwnd)
            if not win:
                return None

            target = win.TextControl(SubName=search_text)
            if not target.Exists(0.08):
                target = win.Control(SubName=search_text)

            if target.Exists(0.08):
                if not getattr(target, 'IsOffscreen', False):
                    r = target.BoundingRectangle
                    if r.width() > 0 and r.height() > 0:
                        # Verificare strictă: dreptunghiul trebuie să se afle în interiorul ferestrei active
                        if (win_rect[0] - 5 <= r.left and win_rect[1] - 5 <= r.top and r.right <= win_rect[2] + 5 and r.bottom <= win_rect[3] + 5):
                            pad_x = 6
                            pad_y = 4
                            return (r.left - pad_x, r.top - pad_y, r.width() + (pad_x * 2), r.height() + (pad_y * 2))
        except Exception:
            pass
        return None

    @classmethod
    def match_string(cls, pattern: str, text: str, is_regex: bool = False, case_sensitive: bool = False) -> bool:
        """Verifică dacă textul se potrivește cu un șablon (wildcard sau regex)."""
        if not pattern or pattern == "*":
            return True
        if not text:
            return False

        if not is_regex and ("|" in pattern or ";" in pattern):
            subpatterns = [p.strip() for p in re.split(r"[|;]", pattern) if p.strip()]
            for sp in subpatterns:
                if cls.match_string(sp, text, is_regex=False, case_sensitive=case_sensitive):
                    return True
            return False

        if not case_sensitive:
            pattern_proc = pattern.lower()
            text_proc = text.lower()
        else:
            pattern_proc = pattern
            text_proc = text

        if is_regex:
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                return bool(re.search(pattern, text, flags))
            except re.error:
                return False
        else:
            # Suport pentru wildcard standard (*, ?)
            if "*" in pattern_proc or "?" in pattern_proc:
                return fnmatch.fnmatch(text_proc, pattern_proc)
            return pattern_proc in text_proc

    @classmethod
    def evaluate_rule(cls, rule: Dict[str, Any], window_info: Dict[str, Any]) -> bool:
        """
        Evaluează dacă o regulă este declanșată pentru fereastra dată.
        window_info conține:
          - 'title': Titlul ferestrei active
          - 'process_name': Numele procesului (ex: msedge.exe)
          - 'rect': (left, top, right, bottom)
          - 'extra_text': text suplimentar extras sau disponibil
        """
        if not rule.get("enabled", True):
            return False

        trigger = rule.get("trigger", {})
        win_title = window_info.get("title", "")
        proc_name = window_info.get("process_name", "")
        extra_text = window_info.get("extra_text", "")

        # 1. Filtru Proces (ex: msedge.exe, chrome.exe)
        # Dacă este menționat browser (msedge.exe sau chrome.exe), acceptăm ambele browsere dacă procesul e browser
        target_proc = trigger.get("process_name", "").strip().lower()
        if target_proc and target_proc != "orice proces":
            if target_proc in ["msedge.exe", "chrome.exe", "firefox.exe", "browser"]:
                if proc_name not in ["msedge.exe", "chrome.exe", "firefox.exe"]:
                    return False
            else:
                if not cls.match_string(target_proc, proc_name, case_sensitive=False):
                    return False

        # 2. Filtru Titlu Fereastră
        title_pattern = trigger.get("window_title_pattern", "").strip()
        norm_pattern = "*"
        if title_pattern and title_pattern != "*":
            # Asigurăm wildcard implicit dacă utilizatorul a introdus doar un cuvânt cheie
            norm_pattern = title_pattern if ("*" in title_pattern or "?" in title_pattern) else f"*{title_pattern}*"
            if not cls.match_string(norm_pattern, win_title, case_sensitive=False):
                return False

        # 3. Filtru Declanșator Text / Criterii Multiple (Excel Style)
        criteria, logic = cls.extract_criteria_list(trigger)
        if not criteria:
            return True

        # Fereastra se potrivește cu ținta (inclusiv dacă utilizatorul a pus * pentru orice titlu de browser)
        win_title_matches = bool(not title_pattern or title_pattern == "*" or cls.match_string(norm_pattern, win_title, case_sensitive=False))
        has_win_match = win_title_matches

        text_condition = trigger.get("text_condition", "contains")
        case_sensitive = trigger.get("case_sensitive", False)
        is_regex = trigger.get("is_regex", False)

        combined_haystack = f"{win_title} {extra_text}"
        hwnd = window_info.get("hwnd")

        def check_single_text_match(crit: str) -> bool:
            """Verifică dacă un criteriu se potrivește în titlu, text sau prin UIA."""
            if not crit:
                return True

            # 1. Verificare în titlul ferestrei sau text extras
            if cls.match_string(crit, combined_haystack, is_regex=is_regex, case_sensitive=case_sensitive):
                return True

            # 2. Verificare UIA în elementele aplicației (doar dacă sunt pe ecran)
            if has_win_match and hwnd:
                geo = cls.find_uia_control_geometry(hwnd, crit)
                if geo:
                    return True
                if "'" in crit or '"' in crit:
                    clean_s = crit.replace("'", "").replace('"', "").strip()
                    if cls.find_uia_control_geometry(hwnd, clean_s):
                        return True
                # Dacă criteriul conține $, verificăm și fără caractere speciale
                if "$" in crit:
                    clean_s = crit.replace("$", "").strip()
                    if cls.find_uia_control_geometry(hwnd, clean_s):
                        return True
            return False

        if logic == "AND":
            matched = all(check_single_text_match(c) for c in criteria)
        else: # "OR"
            # Criteriul principal (search_text) este esențial dacă este definit:
            # dacă utilizatorul a setat o frază principală specifică, cerem ca măcar textul principal
            # sau o combinație relevantă să se potrivească
            primary = trigger.get("search_text", "").strip()
            if primary and len(criteria) > 1 and ("status" in [c.lower() for c in criteria]):
                # Protecție anti-fals-pozitiv pentru cuvinte generice precum 'Status'
                matched = any(check_single_text_match(c) for c in criteria if c.lower() != "status")
                if not matched:
                    matched = check_single_text_match(primary)
            else:
                matched = any(check_single_text_match(c) for c in criteria)

        # 4. Verificare prin șablon vizual snip (OpenCV / PyAutoGUI) ca recunoaștere vizuală
        region = rule.get("region", {})
        tmpl = region.get("template_image", "").strip()
        if not matched and has_win_match and tmpl:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tmpl_p = os.path.join(base_dir, tmpl) if not os.path.isabs(tmpl) else tmpl
            if os.path.exists(tmpl_p):
                try:
                    import pyautogui
                    loc = pyautogui.locateOnScreen(tmpl_p, confidence=0.70)
                    if loc:
                        matched = True
                except Exception:
                    pass

        return matched

    @classmethod
    def get_active_step_for_rule(cls, rule: Dict[str, Any], elapsed_sec: float) -> Optional[Dict[str, Any]]:
        """
        Determină pasul activ dintr-o secvență / pachet de pași (Condition Chaining / Sequences)
        în funcție de timpul scurs de la declanșarea regulii.
        """
        steps = rule.get("steps", [])
        if not steps:
            return None

        for idx, step in enumerate(steps):
            start = float(step.get("delay_sec", 0))
            dur = float(step.get("duration_sec", 4))
            end = start + dur if dur > 0 else 999999.0
            if start <= elapsed_sec < end:
                step_copy = dict(step)
                step_copy["step_index"] = idx + 1
                step_copy["total_steps"] = len(steps)
                return step_copy

        return None

    @classmethod
    def calculate_cue_geometry(cls, rule: Dict[str, Any], window_info: Dict[str, Any], virtual_screen: Tuple[int, int, int, int], active_step: Optional[Dict[str, Any]] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        Calculează coordonatele dreptunghiului țintă pe ecranul virtual (X, Y, W, H).
        Suportă:
          - box_scope = "exact_text": chenar strâns fix pe textul detectat
          - box_scope = "custom_region": zonă extinsă conform dimensiunilor configurate / capturate la selecție (W x H)
          - box_scope = "full_row": întregul rând orizontal din tabel / fereastră
        """
        region = active_step.get("region", {}) if (active_step and active_step.get("region")) else rule.get("region", {})
        visual = (active_step.get("visual_cue") if active_step else None) or rule.get("visual_cue", {})
        trigger = (active_step.get("trigger") if active_step else None) or rule.get("trigger", {})
        mode = region.get("mode", "window_relative")

        win_rect = window_info.get("rect", (0, 0, 800, 600))
        left, top, right, bottom = win_rect
        win_w = max(100, right - left)
        win_h = max(100, bottom - top)

        hwnd = window_info.get("hwnd")
        criteria, logic = cls.extract_criteria_list(trigger)

        # Setări chenar extins / padding
        box_scope = visual.get("box_scope", "custom_region")
        pad = int(visual.get("padding", 4))
        configured_w = int(region.get("width", 814))
        configured_h = int(region.get("height", 38))
        rel_x = float(region.get("rel_x", 0.15))
        rel_y = float(region.get("rel_y", 0.30))
        abs_x = int(region.get("abs_x", 0))

        # 1. Identificare prin Windows UI Automation (ancorare la rândul/textul din pagină)
        if criteria and hwnd:
            uia_geo = cls.find_uia_criteria_geometry(hwnd, criteria, logic=logic)
            if uia_geo:
                ux, uy, uw, uh = uia_geo

                if box_scope == "exact_text":
                    return (ux - pad, uy - pad, uw + pad * 2, uh + pad * 2)

                elif box_scope == "full_row":
                    return (left + 8, uy - pad, win_w - 16, max(uh, configured_h) + pad * 2)

                else: # "custom_region" (Zonă Extinsă - W x H din selecție)
                    # Poziționăm chenarul astfel încât să înceapă din stânga rândului (abs_x sau rel_x)
                    # și să aibă lățimea configurată (configured_w, ex: 814px)
                    if abs_x > 0 and abs_x < (ux + uw):
                        target_x = max(left + 8, abs_x - pad)
                    elif rel_x > 0 and int(left + (rel_x * win_w)) < (ux + uw):
                        target_x = max(left + 8, int(left + (rel_x * win_w)) - pad)
                    else:
                        target_x = max(left + 8, (ux + uw) - configured_w - pad)

                    target_w = max(configured_w, (ux + uw) - target_x)
                    target_y = uy - max(0, (configured_h - uh) // 2) - pad
                    target_h = max(configured_h, uh) + pad * 2
                    return (int(target_x), int(target_y), int(min(target_w, win_w - 10)), int(target_h))

        # 2. Prioritate 2: Urmărire vizuală prin potrivire de șablon (OpenCV / PyAutoGUI)
        if mode == "visual_track":
            template_rel = region.get("template_image", "").strip()
            if template_rel:
                try:
                    import os, pyautogui
                    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    tmpl_path = os.path.join(base_dir, template_rel) if not os.path.isabs(template_rel) else template_rel
                    if os.path.exists(tmpl_path):
                        loc = pyautogui.locateOnScreen(tmpl_path, confidence=0.70)
                        if loc:
                            if box_scope == "exact_text":
                                return (int(loc.left - pad), int(loc.top - pad), int(loc.width + pad * 2), int(loc.height + pad * 2))
                            elif box_scope == "full_row":
                                return (int(left + 8), int(loc.top - pad), int(win_w - 16), int(max(loc.height, configured_h) + pad * 2))
                            else: # custom_region
                                start_x = abs_x if (abs_x > 0 and abs_x <= loc.left) else loc.left
                                final_w = max(int(loc.width), configured_w)
                                final_h = max(int(loc.height), configured_h)
                                return (int(start_x - pad), int(loc.top - pad), int(final_w + pad * 2), int(final_h + pad * 2))
                except Exception:
                    pass

            # Dacă modul este visual_track și imaginea NU este pe ecran, NU desenăm nimic aiurea pe ecran!
            # Doar dacă utilizatorul a setat explicit window_relative folosim coordonatele relative.
            return None

        elif mode == "entire_window":
            pad_w = 8
            return (left + pad_w, top + pad_w, win_w - (pad_w * 2), win_h - (pad_w * 2))

        elif mode == "screen_absolute":
            abs_x_val = region.get("abs_x", 100)
            abs_y_val = region.get("abs_y", 100)
            return (abs_x_val - pad, abs_y_val - pad, configured_w + pad * 2, configured_h + pad * 2)

        else: # "window_relative" (implicit)
            target_x = int(left + (rel_x * win_w))
            target_y = int(top + (rel_y * win_h))
            if box_scope == "full_row":
                return (left + 8, target_y - pad, win_w - 16, configured_h + pad * 2)

            return (target_x - pad, target_y - pad, min(configured_w, win_w - 10) + pad * 2, min(configured_h, win_h - 10) + pad * 2)

