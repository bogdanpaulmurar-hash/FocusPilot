"""
Teste pentru motorul de reguli FocusPilot.

Rulare:   python tests/test_rule_engine.py

Testele nu au nevoie de Windows: modulele win32* și uiautomation sunt
înlocuite cu dubluri, iar textul "citit de pe ecran" este furnizat direct.
Scopul este să verifice că o regulă face exact ce spun setările ei.
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Dubluri pentru modulele disponibile doar pe Windows ──────────────────────

def _install_windows_stubs():
    def mk(name, **attrs):
        if name in sys.modules:
            return sys.modules[name]
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
        return mod

    mk("win32gui",
       IsWindow=lambda h: True, IsWindowVisible=lambda h: True,
       IsIconic=lambda h: False, GetWindowText=lambda h: "Stub",
       GetWindowRect=lambda h: (0, 0, 1920, 1080),
       GetForegroundWindow=lambda: 1, EnumWindows=lambda cb, extra: None,
       GetWindowLong=lambda h, i: 0, SetWindowLong=lambda h, i, v: 0,
       GetTopWindow=lambda h: 0, GetWindow=lambda h, c: 0)
    mk("win32process", GetWindowThreadProcessId=lambda h: (0, 1))
    mk("win32api", GetSystemMetrics=lambda i: 1920)
    mk("win32con", SM_XVIRTUALSCREEN=76, SM_YVIRTUALSCREEN=77,
       SM_CXVIRTUALSCREEN=78, SM_CYVIRTUALSCREEN=79, GWL_EXSTYLE=-20,
       WS_EX_TRANSPARENT=0x20, WS_EX_TOOLWINDOW=0x80, WS_EX_LAYERED=0x80000,
       WS_EX_NOACTIVATE=0x8000000, GW_HWNDNEXT=2)
    mk("pyautogui", locateOnScreen=lambda *a, **k: None)


_install_windows_stubs()

from core import rule_engine                                      # noqa: E402
from core.rule_engine import RuleEngine, UiaSnapshot              # noqa: E402

VIRT = (0, 0, 1920, 1080)


def window(title="TIMA Web Gateway", process="chrome.exe",
           rect=(100, 100, 1700, 1000), url="", hwnd=1, extra_text=""):
    return {"hwnd": hwnd, "title": title, "process_name": process,
            "rect": rect, "url": url, "extra_text": extra_text}


def snapshot(*items):
    """items: (text, (x, y, w, h))"""
    return UiaSnapshot(items=list(items), truncated=False, captured_at=1e9)


class EngineTestCase(unittest.TestCase):
    """Înlocuiește citirea de pe ecran cu un conținut controlat."""

    screen = None          # UiaSnapshot sau None
    template_rect = None   # (x, y, w, h) sau None

    def setUp(self):
        self._orig_capture = rule_engine.capture_window_text
        self._orig_locate = rule_engine.locate_template

        rule_engine.capture_window_text = lambda hwnd, force=False: self.screen
        rule_engine.locate_template = lambda path, base, confidence=0.78: self.template_rect

        # Capabilitățile sunt irelevante aici: textul vine din dublură.
        rule_engine.CAPABILITIES._uia = True
        rule_engine.CAPABILITIES._cv = True

    def tearDown(self):
        rule_engine.capture_window_text = self._orig_capture
        rule_engine.locate_template = self._orig_locate
        self.screen = None
        self.template_rect = None


# ─────────────────────────────────────────────────────────────────────────────
# Condiția de text — era citită din config dar niciodată aplicată
# ─────────────────────────────────────────────────────────────────────────────

class TestTextConditions(unittest.TestCase):

    def test_contains(self):
        self.assertTrue(RuleEngine.text_matches("categorie", "Please change categorie now", "contains"))
        self.assertFalse(RuleEngine.text_matches("categorie", "nothing here", "contains"))

    def test_equals_is_not_contains(self):
        """'Este exact' trebuie să respingă o potrivire parțială."""
        self.assertTrue(RuleEngine.text_matches("Status", "Status", "equals"))
        self.assertFalse(RuleEngine.text_matches("Status", "Status changed today", "equals"))

    def test_equals_matches_one_line_of_many(self):
        page = "Header\nStatus\nFooter"
        self.assertTrue(RuleEngine.text_matches("Status", page, "equals"))

    def test_starts_with(self):
        self.assertTrue(RuleEngine.text_matches("Please", "Please change category", "starts_with"))
        self.assertFalse(RuleEngine.text_matches("change", "Please change category", "starts_with"))

    def test_constellation_requires_every_word(self):
        page = "ticket merged and waiting for approval"
        self.assertTrue(RuleEngine.text_matches("merged;waiting", page, "constellation"))
        self.assertFalse(RuleEngine.text_matches("merged;rejected", page, "constellation"))

    def test_regex(self):
        self.assertTrue(RuleEngine.text_matches(r"ID-\d{4}", "ticket ID-2048 open", "regex"))
        self.assertFalse(RuleEngine.text_matches(r"ID-\d{4}", "ticket ID-20 open", "regex"))

    def test_invalid_regex_does_not_raise(self):
        self.assertFalse(RuleEngine.text_matches("[unclosed", "anything", "regex"))

    def test_case_sensitivity_is_honoured(self):
        self.assertTrue(RuleEngine.text_matches("STATUS", "status", "contains", case_sensitive=False))
        self.assertFalse(RuleEngine.text_matches("STATUS", "status", "contains", case_sensitive=True))

    def test_literal_text_with_semicolon_is_not_split(self):
        """
        Un text căutat care conține ';' trebuie căutat întreg. Varianta
        anterioară îl despica în cuvinte-cheie separate, deci regula se
        declanșa pe fragmente pe care utilizatorul nu le ceruse.
        """
        needle = "Priority: high; escalate"
        self.assertTrue(RuleEngine.text_matches(needle, f"row says {needle} today", "contains"))
        self.assertFalse(RuleEngine.text_matches(needle, "escalate", "contains"))

    def test_apostrophes_are_literal(self):
        needle = "Changed from 'Merge' to 'Wait for Merge'"
        self.assertTrue(RuleEngine.text_matches(needle, f"log: {needle}", "contains"))


# ─────────────────────────────────────────────────────────────────────────────
# Criterii multiple
# ─────────────────────────────────────────────────────────────────────────────

class TestCriteriaExtraction(unittest.TestCase):

    def test_primary_text_stays_one_criterion(self):
        crits, logic = RuleEngine.extract_criteria_list(
            {"search_text": "Changed from 'Merge' to 'Wait for Merge'"})
        self.assertEqual(crits, ["Changed from 'Merge' to 'Wait for Merge'"])
        self.assertEqual(logic, "OR")

    def test_additional_criteria_from_list(self):
        crits, logic = RuleEngine.extract_criteria_list(
            {"search_text": "alpha", "additional_criteria": ["beta", "gamma"],
             "criteria_logic": "AND"})
        self.assertEqual(crits, ["alpha", "beta", "gamma"])
        self.assertEqual(logic, "AND")

    def test_duplicates_removed(self):
        crits, _ = RuleEngine.extract_criteria_list(
            {"search_text": "alpha", "additional_criteria": ["alpha", "beta"]})
        self.assertEqual(crits, ["alpha", "beta"])

    def test_logic_defaults_to_or_not_guessed_from_punctuation(self):
        """Logica vine din setare, nu din caracterele textului."""
        _, logic = RuleEngine.extract_criteria_list({"search_text": "a;b"})
        self.assertEqual(logic, "OR")
        _, logic = RuleEngine.extract_criteria_list({"search_text": "a|b"})
        self.assertEqual(logic, "OR")


class TestCriteriaLogic(EngineTestCase):

    def _rule(self, logic):
        return {
            "id": "r", "enabled": True,
            "trigger": {"search_text": "alpha", "additional_criteria": ["beta"],
                        "criteria_logic": logic, "text_condition": "contains"},
            "visual_cue": {}, "region": {"mode": "entire_window"},
        }

    def test_or_fires_on_one(self):
        self.screen = snapshot(("alpha only", (10, 10, 100, 20)))
        self.assertTrue(RuleEngine.evaluate(self._rule("OR"), window(), VIRT).matched)

    def test_and_needs_both(self):
        self.screen = snapshot(("alpha only", (10, 10, 100, 20)))
        self.assertFalse(RuleEngine.evaluate(self._rule("AND"), window(), VIRT).matched)
        self.screen = snapshot(("alpha", (10, 10, 100, 20)), ("beta", (10, 40, 100, 20)))
        self.assertTrue(RuleEngine.evaluate(self._rule("AND"), window(), VIRT).matched)

    def test_generic_word_has_no_special_treatment(self):
        """
        Motorul conținea o excepție scrisă în cod pentru cuvântul 'Status',
        care îl elimina din evaluare. O regulă trebuie să trateze orice cuvânt
        la fel, altfel comportamentul nu mai decurge din setări.
        """
        rule = {
            "id": "r", "enabled": True,
            "trigger": {"search_text": "Status", "criteria_logic": "OR",
                        "text_condition": "contains"},
            "visual_cue": {}, "region": {"mode": "entire_window"},
        }
        self.screen = snapshot(("Status", (10, 10, 60, 18)))
        self.assertTrue(RuleEngine.evaluate(rule, window(), VIRT).matched,
                        "cuvântul 'Status' trebuie tratat ca orice alt criteriu")


# ─────────────────────────────────────────────────────────────────────────────
# Filtre de fereastră
# ─────────────────────────────────────────────────────────────────────────────

class TestWindowFilters(EngineTestCase):

    def _rule(self, **trigger):
        base = {"search_text": "", "text_condition": "contains"}
        base.update(trigger)
        return {"id": "r", "enabled": True, "trigger": base,
                "visual_cue": {}, "region": {"mode": "entire_window"}}

    def test_process_browser_covers_edge_and_chrome(self):
        rule = self._rule(process_name="browser")
        self.assertTrue(RuleEngine.evaluate(rule, window(process="chrome.exe"), VIRT).matched)
        self.assertTrue(RuleEngine.evaluate(rule, window(process="msedge.exe"), VIRT).matched)
        self.assertFalse(RuleEngine.evaluate(rule, window(process="excel.exe"), VIRT).matched)

    def test_specific_process(self):
        rule = self._rule(process_name="excel.exe")
        self.assertTrue(RuleEngine.evaluate(rule, window(process="excel.exe"), VIRT).matched)
        self.assertFalse(RuleEngine.evaluate(rule, window(process="chrome.exe"), VIRT).matched)

    def test_title_keyword_gets_implicit_wildcards(self):
        rule = self._rule(window_title_pattern="TIMA")
        self.assertTrue(RuleEngine.evaluate(rule, window(title="My TIMA Portal"), VIRT).matched)
        self.assertFalse(RuleEngine.evaluate(rule, window(title="Other app"), VIRT).matched)

    def test_title_alternatives_with_pipe(self):
        rule = self._rule(window_title_pattern="*Service Platform*|*GSP*")
        self.assertTrue(RuleEngine.evaluate(rule, window(title="GSP Console"), VIRT).matched)
        self.assertTrue(RuleEngine.evaluate(rule, window(title="Service Platform X"), VIRT).matched)
        self.assertFalse(RuleEngine.evaluate(rule, window(title="Notepad"), VIRT).matched)

    def test_url_filter_is_applied(self):
        """
        `url_pattern` exista în editor și în config.json, dar motorul nu îl
        evalua niciodată: o regulă legată de un URL se declanșa pe orice pagină.
        """
        rule = self._rule(url_pattern="*tima.siemens.com/otwg20*")
        matching = window(url="https://tima.siemens.com/otwg20/#/main")
        other = window(url="https://intranet.example.com/home")
        self.assertTrue(RuleEngine.evaluate(rule, matching, VIRT).matched)
        self.assertFalse(RuleEngine.evaluate(rule, other, VIRT).matched)

    def test_url_filter_tolerates_unknown_url(self):
        """Dacă URL-ul nu poate fi citit, regula nu e respinsă pe nedrept."""
        rule = self._rule(url_pattern="*tima.siemens.com*")
        self.assertTrue(RuleEngine.evaluate(rule, window(url=""), VIRT).matched)

    def test_disabled_rule_never_matches(self):
        rule = self._rule()
        rule["enabled"] = False
        self.assertFalse(RuleEngine.evaluate(rule, window(), VIRT).matched)

    def test_failure_reason_is_explained(self):
        rule = self._rule(window_title_pattern="SAP")
        result = RuleEngine.evaluate(rule, window(title="Chrome"), VIRT)
        self.assertFalse(result.matched)
        self.assertIn("Titlu nepotrivit", result.reason)


# ─────────────────────────────────────────────────────────────────────────────
# Geometria chenarului
# ─────────────────────────────────────────────────────────────────────────────

class TestGeometry(EngineTestCase):

    def _rule(self, mode="visual_track", scope="custom_region", **region):
        reg = {"mode": mode, "width": 800, "height": 36,
               "rel_x": 0.15, "rel_y": 0.80, "abs_x": 286, "abs_y": 865}
        reg.update(region)
        return {
            "id": "r", "enabled": True,
            "trigger": {"search_text": "Wait for Merge", "text_condition": "contains"},
            "visual_cue": {"box_scope": scope, "padding": 4},
            "region": reg,
        }

    def test_anchors_on_found_element(self):
        self.screen = snapshot(("Changed to Wait for Merge", (400, 700, 260, 24)))
        result = RuleEngine.evaluate(self._rule(scope="exact_text"), window(), VIRT)
        self.assertTrue(result.drawable)
        self.assertEqual(result.anchor, "uia")
        x, y, w, h = result.geometry
        self.assertEqual((x, y), (396, 696))          # 4px padding
        self.assertEqual((w, h), (268, 32))

    def test_full_row_spans_the_window(self):
        self.screen = snapshot(("Wait for Merge", (400, 700, 260, 24)))
        result = RuleEngine.evaluate(self._rule(scope="full_row"), window(), VIRT)
        x, y, w, h = result.geometry
        self.assertEqual(x, 108)                      # marginea ferestrei + 8
        self.assertEqual(w, 1600 - 16)                # lățimea ferestrei - 16

    def test_custom_region_keeps_configured_width(self):
        self.screen = snapshot(("Wait for Merge", (400, 700, 120, 24)))
        result = RuleEngine.evaluate(self._rule(scope="custom_region"), window(), VIRT)
        _, _, w, _ = result.geometry
        self.assertGreaterEqual(w, 800, "lățimea configurată de utilizator trebuie respectată")

    def test_visual_track_falls_back_to_captured_coordinates(self):
        """
        Reparația centrală: când textul e găsit dar elementul nu are coordonate
        (titlu de fereastră, arbore truncat), modul 'visual_track' întorcea None
        și nu se desena NIMIC. Acum se folosesc coordonatele salvate la selecția
        interactivă, adică exact setările utilizatorului.
        """
        self.screen = None                    # fără coordonate pe ecran
        self.template_rect = None
        win = window(title="GSP — Changed to Wait for Merge")   # text în titlu
        result = RuleEngine.evaluate(self._rule(mode="visual_track"), win, VIRT)
        self.assertTrue(result.matched)
        self.assertTrue(result.drawable, "trebuie desenat la coordonatele salvate")
        self.assertEqual(result.anchor, "configured")
        x, y, _, _ = result.geometry
        self.assertEqual((x, y), (282, 861))           # abs_x/abs_y - padding

    def test_template_match_without_text_does_not_use_stale_coordinates(self):
        """
        Dacă potrivirea a venit DOAR din șablonul imagine și acesta nu mai e pe
        ecran, nu desenăm la coordonatele vechi: elementul s-a mutat.
        """
        self.screen = snapshot(("unrelated content", (10, 10, 50, 10)))
        self.template_rect = None
        result = RuleEngine.evaluate(self._rule(mode="visual_track"), window(), VIRT)
        self.assertFalse(result.matched)

    def test_template_match_anchors_on_template(self):
        self.screen = snapshot(("unrelated", (10, 10, 50, 10)))
        self.template_rect = (500, 820, 780, 34)
        rule = self._rule(mode="visual_track", scope="exact_text")
        rule["region"]["template_image"] = "assets/rules/snip.png"
        result = RuleEngine.evaluate(rule, window(), VIRT)
        self.assertTrue(result.drawable)
        self.assertEqual(result.anchor, "template")

    def test_entire_window(self):
        self.screen = snapshot(("Wait for Merge", (400, 700, 100, 20)))
        result = RuleEngine.evaluate(self._rule(mode="entire_window"), window(), VIRT)
        self.assertEqual(result.geometry, (108, 108, 1584, 884))

    def test_screen_absolute_uses_exact_coordinates(self):
        self.screen = None
        win = window(title="Wait for Merge here")
        rule = self._rule(mode="screen_absolute", abs_x=1000, abs_y=500,
                          width=300, height=40)
        result = RuleEngine.evaluate(rule, win, VIRT)
        self.assertEqual(result.geometry, (996, 496, 308, 48))

    def test_malformed_region_values_do_not_crash(self):
        rule = self._rule(mode="screen_absolute", abs_x="not-a-number",
                          width=None, height="40")
        self.screen = None
        result = RuleEngine.evaluate(rule, window(title="Wait for Merge"), VIRT)
        self.assertIsNotNone(result.geometry)


# ─────────────────────────────────────────────────────────────────────────────
# Pași secvențiali
# ─────────────────────────────────────────────────────────────────────────────

class TestSequentialSteps(unittest.TestCase):

    RULE = {"steps": [
        {"name": "unu", "delay_sec": 0, "duration_sec": 3},
        {"name": "doi", "delay_sec": 3, "duration_sec": 4},
    ]}

    def test_first_step(self):
        step = RuleEngine.get_active_step_for_rule(self.RULE, 1.0)
        self.assertEqual(step["name"], "unu")
        self.assertEqual(step["step_index"], 1)
        self.assertEqual(step["total_steps"], 2)

    def test_second_step(self):
        self.assertEqual(RuleEngine.get_active_step_for_rule(self.RULE, 4.0)["name"], "doi")

    def test_after_last_step(self):
        self.assertIsNone(RuleEngine.get_active_step_for_rule(self.RULE, 99.0))

    def test_no_steps(self):
        self.assertIsNone(RuleEngine.get_active_step_for_rule({"steps": []}, 1.0))

    def test_zero_duration_runs_indefinitely(self):
        rule = {"steps": [{"name": "x", "delay_sec": 0, "duration_sec": 0}]}
        self.assertIsNotNone(RuleEngine.get_active_step_for_rule(rule, 10_000.0))


# ─────────────────────────────────────────────────────────────────────────────
# Potrivirea de șabloane de fereastră
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchString(unittest.TestCase):

    def test_star_matches_everything(self):
        self.assertTrue(RuleEngine.match_string("*", "orice"))
        self.assertTrue(RuleEngine.match_string("", "orice"))

    def test_substring_without_wildcard(self):
        self.assertTrue(RuleEngine.match_string("TIMA", "My TIMA Portal"))

    def test_wildcards(self):
        self.assertTrue(RuleEngine.match_string("*TIMA*", "My TIMA Portal"))
        self.assertFalse(RuleEngine.match_string("TIMA*", "My TIMA Portal"))

    def test_alternatives(self):
        self.assertTrue(RuleEngine.match_string("*GSP*|*TIMA*", "TIMA Portal"))
        self.assertFalse(RuleEngine.match_string("*GSP*|*TIMA*", "Notepad"))

    def test_empty_text_never_matches_real_pattern(self):
        self.assertFalse(RuleEngine.match_string("TIMA", ""))




# ─────────────────────────────────────────────────────────────────────────────
# Configurație: izolarea regulilor implicite
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigDefaults(unittest.TestCase):

    def test_default_rules_are_deep_copied(self):
        """
        `list(DEFAULT_SAMPLE_RULES)` copia doar lista, iar dicționarele imbricate
        rămâneau partajate cu constanta de modul: modificarea unei reguli dintr-o
        configurație nouă altera șablonul pentru orice configurație ulterioară.
        """
        import tempfile
        from core import config_manager
        from core.config_manager import ConfigManager

        original = config_manager.DEFAULT_SAMPLE_RULES[0]["visual_cue"]["border_color"]

        with tempfile.TemporaryDirectory() as folder:
            cfg = ConfigManager(folder)
            rules = cfg.get_rules()
            self.assertTrue(rules, "configurația nouă trebuie să aibă reguli exemplu")
            rule_id = rules[0]["id"]
            cfg.update_rule(rule_id, {"visual_cue": {"border_color": "#123456"}})

        self.assertEqual(
            config_manager.DEFAULT_SAMPLE_RULES[0]["visual_cue"]["border_color"],
            original,
            "șablonul de reguli implicite nu trebuie modificat")

    def test_poll_interval_is_clamped(self):
        """Un interval prea mic ar face scanările să se suprapună."""
        import tempfile
        from core.config_manager import ConfigManager
        from core.monitor_engine import MonitorEngine

        with tempfile.TemporaryDirectory() as folder:
            cfg = ConfigManager(folder)
            engine = MonitorEngine(cfg)

            cfg.set_setting("poll_interval_sec", 0.01)
            self.assertGreaterEqual(engine._read_poll_interval(), 0.25)

            cfg.set_setting("poll_interval_sec", 999)
            self.assertLessEqual(engine._read_poll_interval(), 5.0)

            cfg.set_setting("poll_interval_sec", "nu-e-numar")
            self.assertGreater(engine._read_poll_interval(), 0)


class TestMissingTemplateWarning(unittest.TestCase):

    def test_missing_template_warns_only_once(self):
        """Un avertisment pe scanare ar umple jurnalul în câteva minute."""
        import logging
        rule_engine._missing_templates.clear()
        rule_engine.CAPABILITIES._cv = True

        with self.assertLogs(rule_engine.logger, level=logging.WARNING) as captured:
            for _ in range(20):
                rule_engine.locate_template("assets/rules/absent.png", "/nowhere")
        self.assertEqual(len(captured.records), 1,
                         "fișierul lipsă trebuie semnalat o singură dată")


if __name__ == "__main__":
    unittest.main(verbosity=2)
