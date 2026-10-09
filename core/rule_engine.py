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

    _uia_cache: Dict[Tuple[int, str], Any] = {}

    @classmethod
    def find_uia_control_geometry(cls, hwnd: int, search_text: str) -> Optional[Tuple[int, int, int, int]]:
        """Caută un control cu textul specificat prin UI Automation în fereastra dată."""
        if not hwnd or not search_text:
            return None
        cache_key = (hwnd, search_text)
        if cache_key in cls._uia_cache:
            ctrl = cls._uia_cache[cache_key]
            try:
                r = ctrl.BoundingRectangle
                if r.width() > 0 and r.height() > 0:
                    pad_x = 6
                    pad_y = 4
                    return (r.left - pad_x, r.top - pad_y, r.width() + (pad_x * 2), r.height() + (pad_y * 2))
            except Exception:
                cls._uia_cache.pop(cache_key, None)

        try:
            import uiautomation as auto
            win = auto.ControlFromHandle(hwnd)
            if not win:
                return None
            target = win.TextControl(SubName=search_text)
            if not target.Exists(0.12):
                target = win.Control(SubName=search_text)
            if target.Exists(0.12):
                cls._uia_cache[cache_key] = target
                r = target.BoundingRectangle
                if r.width() > 0 and r.height() > 0:
                    pad_x = 6
                    pad_y = 4
                    return (r.left - pad_x, r.top - pad_y, r.width() + (pad_x * 2), r.height() + (pad_y * 2))
            cls._uia_cache.pop(cache_key, None)
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
        if title_pattern and title_pattern != "*":
            # Asigurăm wildcard implicit dacă utilizatorul a introdus doar un cuvânt cheie
            norm_pattern = title_pattern if ("*" in title_pattern or "?" in title_pattern) else f"*{title_pattern}*"
            if not cls.match_string(norm_pattern, win_title, case_sensitive=False):
                return False

        # 3. Filtru Declanșator Text / Condiție Stil Excel
        search_text = trigger.get("search_text", "").strip()
        if not search_text:
            return True

        # Dacă titlul ferestrei sau procesul se potrivește deja cu ținta (ex: TIMA în browser),
        # regula este considerată activă pentru respectiva aplicație/pagină
        has_win_match = bool(title_pattern and title_pattern != "*" and cls.match_string(norm_pattern, win_title, case_sensitive=False))

        text_condition = trigger.get("text_condition", "contains")
        case_sensitive = trigger.get("case_sensitive", False)
        is_regex = trigger.get("is_regex", False)

        # Căutăm atât în titlu, cât și în orice text extras disponibil
        combined_haystack = f"{win_title} {extra_text}"

        # Curățare caractere emoji speciale pentru comparație tolerantă dacă e cazul
        def clean_txt(s: str) -> str:
            return re.sub(r"[^\w\s]", " ", s)

        matched = False
        if text_condition == "equals":
            if case_sensitive:
                matched = (search_text == win_title or search_text == extra_text)
            else:
                matched = (search_text.lower() == win_title.lower() or search_text.lower() == extra_text.lower())

        elif text_condition == "starts_with":
            flags = 0 if case_sensitive else re.IGNORECASE
            matched = bool(re.match(r"^" + re.escape(search_text), combined_haystack, flags))

        elif text_condition == "constellation":
            keywords = [k.strip() for k in re.split(r"[;,]+", search_text) if k.strip()]
            all_found = True
            for kw in keywords:
                if not cls.match_string(kw, combined_haystack, case_sensitive=case_sensitive):
                    all_found = False
                    break
            matched = all_found

        else: # "contains" sau implicit
            # Verificare directă
            matched = cls.match_string(search_text, combined_haystack, is_regex=is_regex, case_sensitive=case_sensitive)
            # Dacă nu s-a potrivit exact (de exemplu din cauza caracterelor emoji / spații), verificăm textul curățat
            if not matched and not is_regex and len(search_text) > 3:
                c_search = clean_txt(search_text).lower().strip()
                c_haystack = clean_txt(combined_haystack).lower()
                words = [w for w in c_search.split() if len(w) > 2]
                if words and all(w in c_haystack for w in words):
                    matched = True

        # Dacă fereastra se potrivește (ex: Chrome/Edge cu TIMA):
        # A. Verificăm dacă textul specificat se află pe ecran via Windows UI Automation
        hwnd = window_info.get("hwnd")
        if not matched and has_win_match and hwnd and search_text:
            uia_geo = cls.find_uia_control_geometry(hwnd, search_text)
            if uia_geo:
                matched = True

        region = rule.get("region", {})
        # B. Pentru modul visual_track, dacă există template_image valid pe disc
        if not matched and region.get("mode") == "visual_track":
            tmpl = region.get("template_image", "").strip()
            if has_win_match and tmpl:
                import os
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                tmpl_p = os.path.join(base_dir, tmpl) if not os.path.isabs(tmpl) else tmpl
                if os.path.exists(tmpl_p):
                    matched = True

        return matched

    @classmethod
    def calculate_cue_geometry(cls, rule: Dict[str, Any], window_info: Dict[str, Any], virtual_screen: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
        """
        Calculează coordonatele dreptunghiului țintă pe ecranul virtual (X, Y, W, H).
        Suportă cele 3 monitoare în coordonate Windows absolute.
        """
        region = rule.get("region", {})
        mode = region.get("mode", "window_relative")

        win_rect = window_info.get("rect", (0, 0, 800, 600))
        left, top, right, bottom = win_rect
        win_w = max(100, right - left)
        win_h = max(100, bottom - top)

        hwnd = window_info.get("hwnd")
        search_text = rule.get("trigger", {}).get("search_text", "").strip()

        # 1. Prioritate Maximă: Identificare precisă a elementului din pagină/aplicație prin Windows UI Automation
        if search_text and hwnd:
            uia_geo = cls.find_uia_control_geometry(hwnd, search_text)
            if uia_geo:
                return uia_geo

        # 2. Prioritate 2: Urmărire vizuală prin potrivire de șablon (OpenCV Template Matching)
        if mode == "visual_track":
            template_rel = region.get("template_image", "").strip()
            if not template_rel:
                return None
            try:
                import os, pyautogui
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                tmpl_path = os.path.join(base_dir, template_rel) if not os.path.isabs(template_rel) else template_rel
                if not os.path.exists(tmpl_path):
                    return None

                # Suport multi-monitor (3 monitoare): intersectăm fereastra cu ecranul virtual complet
                vx, vy, vw, vh = virtual_screen
                sx = max(vx, left)
                sy = max(vy, top)
                sw = max(10, min(win_w, (vx + vw) - sx))
                sh = max(10, min(win_h, (vy + vh) - sy))
                search_region = (int(sx), int(sy), int(sw), int(sh))

                loc = pyautogui.locateOnScreen(tmpl_path, region=search_region, confidence=0.8, grayscale=True)
                if loc:
                    return (int(loc.left), int(loc.top), int(loc.width), int(loc.height))
                return None
            except pyautogui.ImageNotFoundException:
                # Elementul NU se află pe ecran -> strict invizibil!
                return None
            except Exception as e:
                # Orice eroare în căutare -> nu afișăm nimic
                return None

        elif mode == "entire_window":
            # Înfășoară întreaga fereastră cu o mică margine
            pad = 8
            return (left + pad, top + pad, win_w - (pad * 2), win_h - (pad * 2))

        elif mode == "screen_absolute":
            abs_x = region.get("abs_x", 100)
            abs_y = region.get("abs_y", 100)
            w = region.get("width", 300)
            h = region.get("height", 60)
            return (abs_x, abs_y, w, h)

        else: # "window_relative" (implicit)
            rel_x = float(region.get("rel_x", 0.15))
            rel_y = float(region.get("rel_y", 0.30))
            
            # Folosim lățimea și înălțimea capturate din selecția utilizatorului
            w = int(region.get("width", 320))
            h = int(region.get("height", 60))

            target_x = int(left + (rel_x * win_w))
            target_y = int(top + (rel_y * win_h))

            # Evită depășirea ferestrei
            w = min(w, win_w - 10)
            h = min(h, win_h - 10)

            return (target_x, target_y, w, h)
