"""
Teste pentru câmpuri, condiții și marcaje.

Rulare:   python tests/test_probe_engine.py

Verifică modelul „dacă câmpul X are valoarea Z și câmpul Y are valoarea C,
atunci marchează". Nu are nevoie de Windows: textul „citit de pe ecran" este
furnizat direct ca instantaneu.
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _install_windows_stubs():
    def mk(name, **attrs):
        if name in sys.modules:
            return sys.modules[name]
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
        return mod

    mk("win32gui", IsWindow=lambda h: True, IsWindowVisible=lambda h: True,
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

from core import probe_engine, rule_engine                                # noqa: E402
from core.probe_engine import (compare, parse_number, read_probe,          # noqa: E402
                               evaluate_conditions, resolve_marks,
                               OPERATORS, SHAPES)
from core.rule_engine import RuleEngine, UiaSnapshot                       # noqa: E402
from core.mark_geometry import (expand_mark, visual_cue_to_marks,          # noqa: E402
                                marks_for_cue)

VIRT = (0, 0, 1920, 1080)
WINDOW_RECT = (0, 0, 1600, 1000)


def snapshot(*items):
    """items: (text, (x, y, w, h))"""
    return UiaSnapshot(items=list(items), truncated=False, captured_at=1e9)


def window(title="Portal", process="chrome.exe", url="", hwnd=1):
    return {"hwnd": hwnd, "title": title, "process_name": process,
            "rect": WINDOW_RECT, "url": url, "extra_text": ""}


# ─────────────────────────────────────────────────────────────────────────────
# Interpretarea numerelor din texte de interfață
# ─────────────────────────────────────────────────────────────────────────────

class TestParseNumber(unittest.TestCase):

    def test_plain(self):
        self.assertEqual(parse_number("42"), 42.0)
        self.assertEqual(parse_number("-7"), -7.0)
        self.assertEqual(parse_number("3.5"), 3.5)

    def test_european_format(self):
        """„1.234,50" este o mie două sute, nu 1.23."""
        self.assertEqual(parse_number("1.234,50"), 1234.50)

    def test_anglo_format(self):
        self.assertEqual(parse_number("1,234.50"), 1234.50)

    def test_thousands_only(self):
        self.assertEqual(parse_number("1.234.567"), 1234567.0)
        self.assertEqual(parse_number("12,345"), 12345.0)

    def test_decimal_comma(self):
        self.assertEqual(parse_number("12,5"), 12.5)

    def test_with_units_and_currency(self):
        self.assertEqual(parse_number("  1 250 EUR "), 1250.0)
        self.assertEqual(parse_number("qty: 18 buc"), 18.0)

    def test_not_a_number(self):
        self.assertIsNone(parse_number("Wait for Merge"))
        self.assertIsNone(parse_number(""))
        self.assertIsNone(parse_number(None))


# ─────────────────────────────────────────────────────────────────────────────
# Operatori
# ─────────────────────────────────────────────────────────────────────────────

class TestOperators(unittest.TestCase):

    def test_text_operators(self):
        self.assertTrue(compare("Wait for Merge", "equals", "wait for merge"))
        self.assertFalse(compare("Wait for Merge", "equals", "Merge"))
        self.assertTrue(compare("Wait for Merge", "contains", "merge"))
        self.assertTrue(compare("Wait for Merge", "not_contains", "reject"))
        self.assertTrue(compare("Wait for Merge", "starts_with", "wait"))
        self.assertTrue(compare("Wait for Merge", "ends_with", "merge"))
        self.assertTrue(compare("Wait for Merge", "not_equals", "Merge"))

    def test_case_sensitive(self):
        self.assertFalse(compare("Merge", "equals", "merge", case_sensitive=True))
        self.assertTrue(compare("Merge", "equals", "Merge", case_sensitive=True))

    def test_emptiness(self):
        self.assertTrue(compare("", "is_empty", ""))
        self.assertTrue(compare("   ", "is_empty", ""))
        self.assertTrue(compare(None, "is_empty", ""))
        self.assertTrue(compare("x", "is_not_empty", ""))

    def test_numeric(self):
        self.assertTrue(compare("18", "greater_than", "10"))
        self.assertFalse(compare("5", "greater_than", "10"))
        self.assertTrue(compare("10", "greater_equal", "10"))
        self.assertTrue(compare("5", "less_than", "10"))
        self.assertTrue(compare("10", "less_equal", "10"))

    def test_numeric_on_text_is_false_not_an_error(self):
        self.assertFalse(compare("Wait for Merge", "greater_than", "10"))

    def test_between(self):
        self.assertTrue(compare("15", "between", "10;20"))
        self.assertFalse(compare("25", "between", "10;20"))
        self.assertTrue(compare("15", "between", "20;10"), "ordinea nu trebuie să conteze")

    def test_between_needs_two_values(self):
        self.assertFalse(compare("15", "between", "10"))

    def test_is_number(self):
        self.assertTrue(compare("1.234,50", "is_number", ""))
        self.assertFalse(compare("n/a", "is_number", ""))

    def test_changed(self):
        self.assertTrue(compare("Merge", "changed", "", previous="Wait for Merge"))
        self.assertFalse(compare("Merge", "changed", "", previous="Merge"))
        self.assertFalse(compare("Merge", "changed", "", previous=None),
                         "fără o valoare anterioară nu se poate afirma o schimbare")

    def test_regex(self):
        self.assertTrue(compare("ID-2048", "regex", r"^ID-\d{4}$"))
        self.assertFalse(compare("ID-20", "regex", r"^ID-\d{4}$"))

    def test_invalid_regex_does_not_raise(self):
        self.assertFalse(compare("x", "regex", "[unclosed"))

    def test_unknown_operator_falls_back_to_contains(self):
        self.assertTrue(compare("Wait for Merge", "nonexistent_op", "merge"))

    def test_every_operator_is_labelled(self):
        """Interfața afișează eticheta fiecărui operator; niciuna nu lipsește."""
        for key, (label, _needs_value) in OPERATORS.items():
            self.assertTrue(label.strip(), f"operatorul '{key}' nu are etichetă")


# ─────────────────────────────────────────────────────────────────────────────
# Localizarea câmpurilor
# ─────────────────────────────────────────────────────────────────────────────

class TestReadProbe(unittest.TestCase):

    #            etichetă            valoarea din dreapta
    SCREEN = snapshot(
        ("Status",   (100, 300, 60, 20)),
        ("Merge",    (200, 300, 80, 20)),
        ("Quantity", (100, 340, 80, 20)),
        ("18",       (200, 340, 40, 20)),
        ("Total",    (100, 380, 50, 20)),
        ("1.234,50 EUR", (200, 380, 120, 20)),
    )

    def _read(self, locator, name="câmp"):
        return read_probe({"name": name, "locator": locator}, self.SCREEN, WINDOW_RECT)

    def test_value_right_of_label(self):
        reading = self._read({"kind": "text_near", "text": "Status", "offset": "right"})
        self.assertEqual(reading.value, "Merge")
        self.assertEqual(reading.rect, (200, 300, 80, 20))

    def test_value_left_of_label(self):
        reading = self._read({"kind": "text_near", "text": "Merge", "offset": "left"})
        self.assertEqual(reading.value, "Status")

    def test_value_below_label(self):
        reading = self._read({"kind": "text_near", "text": "Status", "offset": "below"})
        self.assertEqual(reading.value, "Quantity")

    def test_picks_nearest_not_any(self):
        """Pe linia lui Quantity există un singur candidat; nu se sare peste el."""
        reading = self._read({"kind": "text_near", "text": "Quantity"})
        self.assertEqual(reading.value, "18")

    def test_skip_selects_further_element(self):
        reading = self._read({"kind": "text_near", "text": "Status",
                              "offset": "below", "skip": 1})
        self.assertEqual(reading.value, "Total")

    def test_missing_label_is_reported(self):
        reading = self._read({"kind": "text_near", "text": "Priority"})
        self.assertIsNone(reading.value)
        self.assertIn("nu e vizibilă", reading.note)

    def test_label_without_value_keeps_label_position(self):
        screen = snapshot(("Status", (100, 300, 60, 20)))
        reading = read_probe({"name": "s", "locator": {"kind": "text_near",
                                                       "text": "Status"}},
                             screen, WINDOW_RECT)
        self.assertIsNone(reading.value)
        self.assertEqual(reading.rect, (100, 300, 60, 20),
                         "poziția etichetei rămâne utilă pentru diagnostic")

    def test_screen_point_picks_smallest_element(self):
        """Elementele mari sunt containere; valoarea e în cel mai adânc."""
        screen = snapshot(
            ("tot rândul   Merge", (100, 300, 400, 24)),   # container
            ("Merge",              (200, 302, 80, 20)),    # valoarea
        )
        reading = read_probe({"name": "s", "locator": {"kind": "screen_point",
                                                       "x": 240, "y": 310}},
                             screen, WINDOW_RECT)
        self.assertEqual(reading.value, "Merge")
        self.assertEqual(reading.rect, (200, 302, 80, 20))

    def test_screen_point_with_nothing_there(self):
        reading = read_probe({"name": "s", "locator": {"kind": "screen_point",
                                                       "x": 5, "y": 5}},
                             self.SCREEN, WINDOW_RECT)
        self.assertIsNone(reading.value)
        self.assertIn("s-a mutat", reading.note)

    def test_screen_point_without_coordinates(self):
        reading = read_probe({"name": "s", "locator": {"kind": "screen_point"}},
                             self.SCREEN, WINDOW_RECT)
        self.assertIsNone(reading.value)
        self.assertIn("coordonate", reading.note)

    def test_screen_region_joins_text_in_reading_order(self):
        reading = read_probe({"name": "s", "locator": {
            "kind": "screen_region", "x": 90, "y": 290, "w": 260, "h": 60}},
            self.SCREEN, WINDOW_RECT)
        self.assertEqual(reading.value, "Status Merge Quantity 18")

    def test_text_self_returns_the_text_itself(self):
        reading = read_probe({"name": "s", "locator": {"kind": "text_self",
                                                       "text": "Merge"}},
                             self.SCREEN, WINDOW_RECT)
        self.assertEqual(reading.value, "Merge")

    def test_no_snapshot_is_reported_clearly(self):
        reading = read_probe({"name": "s", "locator": {"kind": "text_near",
                                                       "text": "Status"}},
                             None, WINDOW_RECT)
        self.assertIsNone(reading.value)
        self.assertIn("uiautomation", reading.note)

    def test_unknown_locator_kind(self):
        reading = self._read({"kind": "telepathy", "text": "Status"})
        self.assertIn("necunoscut", reading.note)


# ─────────────────────────────────────────────────────────────────────────────
# Condiții pe mai multe câmpuri — cerința centrală
# ─────────────────────────────────────────────────────────────────────────────

class TestMultiFieldConditions(unittest.TestCase):
    """„Dacă câmpul X are valoarea Z ȘI câmpul Y are valoarea C, marchează."""

    SCREEN = snapshot(
        ("Status",   (100, 300, 60, 20)),
        ("Merge",    (200, 300, 80, 20)),
        ("Quantity", (100, 340, 80, 20)),
        ("18",       (200, 340, 40, 20)),
    )

    RULE = {
        "id": "r1", "enabled": True,
        "trigger": {"process_name": "browser"},
        "probes": [
            {"name": "status", "locator": {"kind": "text_near", "text": "Status"}},
            {"name": "cantitate", "locator": {"kind": "text_near", "text": "Quantity"}},
        ],
        "conditions": [
            {"probe": "status", "operator": "equals", "value": "Merge"},
            {"probe": "cantitate", "operator": "greater_than", "value": "10"},
        ],
        "conditions_logic": "AND",
        "marks": [{"target": "cantitate", "shape": "circle", "color": "#E60000"}],
    }

    def test_both_conditions_true(self):
        outcome = evaluate_conditions(self.RULE, self.SCREEN, WINDOW_RECT)
        self.assertTrue(outcome.matched)
        self.assertEqual(len(outcome.outcomes), 2)
        self.assertTrue(all(o.passed for o in outcome.outcomes))

    def test_and_fails_when_one_is_false(self):
        screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Merge",    (200, 300, 80, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("3",        (200, 340, 40, 20)),        # sub 10
        )
        outcome = evaluate_conditions(self.RULE, screen, WINDOW_RECT)
        self.assertFalse(outcome.matched)

    def test_or_passes_when_one_is_true(self):
        rule = dict(self.RULE, conditions_logic="OR")
        screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Merge",    (200, 300, 80, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("3",        (200, 340, 40, 20)),
        )
        outcome = evaluate_conditions(rule, screen, WINDOW_RECT)
        self.assertTrue(outcome.matched)

    def test_each_probe_read_once_even_with_several_conditions(self):
        rule = dict(self.RULE, conditions=[
            {"probe": "status", "operator": "is_not_empty", "value": ""},
            {"probe": "status", "operator": "contains", "value": "Merge"},
            {"probe": "status", "operator": "not_contains", "value": "Reject"},
        ])
        outcome = evaluate_conditions(rule, self.SCREEN, WINDOW_RECT)
        self.assertTrue(outcome.matched)
        self.assertEqual(len(outcome.readings), 2, "câmpurile se citesc o dată")

    def test_condition_referring_to_undefined_probe_fails_loudly(self):
        rule = dict(self.RULE, conditions=[
            {"probe": "inexistent", "operator": "equals", "value": "x"}])
        outcome = evaluate_conditions(rule, self.SCREEN, WINDOW_RECT)
        self.assertFalse(outcome.matched)
        self.assertIn("nu e definit", outcome.outcomes[0].note)

    def test_no_conditions_never_matches(self):
        rule = dict(self.RULE, conditions=[])
        self.assertFalse(evaluate_conditions(rule, self.SCREEN, WINDOW_RECT).matched)

    def test_report_explains_each_condition(self):
        outcome = evaluate_conditions(self.RULE, self.SCREEN, WINDOW_RECT)
        report = outcome.report()
        self.assertIn("status", report)
        self.assertIn("cantitate", report)
        self.assertIn("AND", report)

    def test_changed_operator_uses_previous_values(self):
        rule = dict(self.RULE, conditions=[
            {"probe": "status", "operator": "changed", "value": ""}],
            conditions_logic="AND")
        unchanged = evaluate_conditions(rule, self.SCREEN, WINDOW_RECT,
                                        previous_values={"status": "Merge"})
        self.assertFalse(unchanged.matched)
        changed = evaluate_conditions(rule, self.SCREEN, WINDOW_RECT,
                                      previous_values={"status": "Wait for Merge"})
        self.assertTrue(changed.matched)


# ─────────────────────────────────────────────────────────────────────────────
# Marcaje
# ─────────────────────────────────────────────────────────────────────────────

class TestMarks(unittest.TestCase):

    SCREEN = snapshot(
        ("Status",   (100, 300, 60, 20)),
        ("Merge",    (200, 300, 80, 20)),
        ("Quantity", (100, 340, 80, 20)),
        ("18",       (200, 340, 40, 20)),
    )

    def _readings(self):
        rule = {"probes": [
            {"name": "status", "locator": {"kind": "text_near", "text": "Status"}},
            {"name": "cantitate", "locator": {"kind": "text_near", "text": "Quantity"}},
        ], "conditions": [{"probe": "status", "operator": "is_not_empty", "value": ""}]}
        return evaluate_conditions(rule, self.SCREEN, WINDOW_RECT).readings

    def test_mark_lands_on_its_target_field(self):
        rule = {"marks": [{"target": "cantitate", "shape": "circle"}]}
        marks = resolve_marks(rule, self._readings(), None)
        self.assertEqual(len(marks), 1)
        x, y, w, h = marks[0]["rect"]
        # Dreptunghiul valorii "18" este (200, 340, 40, 20), plus padding 4.
        self.assertEqual((x, y, w, h), (196, 336, 48, 28))

    def test_several_marks_on_different_fields(self):
        rule = {"marks": [
            {"target": "status", "shape": "highlight", "color": "#FFB900"},
            {"target": "cantitate", "shape": "circle", "color": "#E60000"},
            {"target": "cantitate", "shape": "arrow", "arrow_count": 3},
        ]}
        marks = resolve_marks(rule, self._readings(), None)
        self.assertEqual(len(marks), 3)
        self.assertEqual([m["shape"] for m in marks],
                         ["highlight", "circle", "arrow"])
        self.assertNotEqual(marks[0]["rect"], marks[1]["rect"],
                            "fiecare marcaj stă pe câmpul lui")

    def test_mark_on_unlocated_field_is_skipped(self):
        """Un cerc desenat în locul greșit e mai rău decât niciun cerc."""
        rule = {"probes": [{"name": "lipsa", "locator": {"kind": "text_near",
                                                          "text": "Priority"}}],
                "conditions": [{"probe": "lipsa", "operator": "is_empty", "value": ""}],
                "marks": [{"target": "lipsa", "shape": "box"}]}
        readings = evaluate_conditions(rule, self.SCREEN, WINDOW_RECT).readings
        self.assertEqual(resolve_marks(rule, readings, None), [])

    def test_mark_without_target_uses_fallback_rect(self):
        rule = {"marks": [{"shape": "box"}]}
        marks = resolve_marks(rule, self._readings(), (10, 20, 300, 40))
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0]["rect"], (6, 16, 308, 48))

    def test_unknown_shape_falls_back_to_box(self):
        rule = {"marks": [{"target": "status", "shape": "hexagon"}]}
        marks = resolve_marks(rule, self._readings(), None)
        self.assertEqual(marks[0]["shape"], "box")

    def test_defaults_are_filled_in(self):
        rule = {"marks": [{"target": "status"}]}
        mark = resolve_marks(rule, self._readings(), None)[0]
        for key in ("shape", "color", "thickness", "pulse"):
            self.assertIn(key, mark)

    def test_every_shape_is_labelled(self):
        for key, label in SHAPES.items():
            self.assertTrue(label.strip(), f"forma '{key}' nu are etichetă")


# ─────────────────────────────────────────────────────────────────────────────
# Integrarea cu motorul de reguli
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineIntegration(unittest.TestCase):

    SCREEN = snapshot(
        ("Status",   (100, 300, 60, 20)),
        ("Merge",    (200, 300, 80, 20)),
        ("Quantity", (100, 340, 80, 20)),
        ("18",       (200, 340, 40, 20)),
    )

    RULE = {
        "id": "rule_cond", "enabled": True,
        "trigger": {"process_name": "browser", "window_title_pattern": "*Portal*"},
        "probes": [
            {"name": "status", "locator": {"kind": "text_near", "text": "Status"}},
            {"name": "cantitate", "locator": {"kind": "text_near", "text": "Quantity"}},
        ],
        "conditions": [
            {"probe": "status", "operator": "equals", "value": "Merge"},
            {"probe": "cantitate", "operator": "greater_than", "value": "10"},
        ],
        "conditions_logic": "AND",
        "marks": [
            {"target": "cantitate", "shape": "circle", "color": "#E60000"},
            {"target": "status", "shape": "highlight", "color": "#FFB900"},
        ],
        "visual_cue": {}, "region": {"mode": "window_relative"},
    }

    def setUp(self):
        self._orig = rule_engine.capture_window_text
        rule_engine.capture_window_text = lambda hwnd, force=False: self.SCREEN
        rule_engine.CAPABILITIES._uia = True
        rule_engine.CAPABILITIES._cv = True
        rule_engine._previous_probe_values.clear()

    def tearDown(self):
        rule_engine.capture_window_text = self._orig

    def test_rule_matches_and_returns_marks(self):
        result = RuleEngine.evaluate(self.RULE, window(title="My Portal"), VIRT)
        self.assertTrue(result.matched)
        self.assertTrue(result.drawable)
        self.assertEqual(result.anchor, "probe")
        self.assertEqual(len(result.marks), 2)

    def test_window_filters_still_apply_first(self):
        result = RuleEngine.evaluate(self.RULE, window(title="Notepad"), VIRT)
        self.assertFalse(result.matched)
        self.assertIn("Titlu nepotrivit", result.reason)

    def test_failing_condition_is_named_in_the_reason(self):
        screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Reject",   (200, 300, 80, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("18",       (200, 340, 40, 20)),
        )
        rule_engine.capture_window_text = lambda hwnd, force=False: screen
        result = RuleEngine.evaluate(self.RULE, window(title="Portal"), VIRT)
        self.assertFalse(result.matched)
        self.assertIn("status", result.reason)

    def test_legacy_text_rules_are_unaffected(self):
        """O regulă fără câmpuri folosește calea clasică, nemodificată."""
        legacy = {
            "id": "old", "enabled": True,
            "trigger": {"search_text": "Merge", "text_condition": "contains"},
            "visual_cue": {"box_scope": "exact_text"},
            "region": {"mode": "window_relative", "width": 200, "height": 30},
        }
        result = RuleEngine.evaluate(legacy, window(), VIRT)
        self.assertTrue(result.matched)
        self.assertEqual(result.anchor, "uia")
        self.assertEqual(result.marks, ())

    def test_uses_conditions_detection(self):
        self.assertTrue(probe_engine.uses_conditions(self.RULE))
        self.assertFalse(probe_engine.uses_conditions({"trigger": {"search_text": "x"}}))
        self.assertFalse(probe_engine.uses_conditions({"probes": [{"name": "a"}]}),
                         "câmpuri fără condiții nu formează o regulă")


# ─────────────────────────────────────────────────────────────────────────────
# Desenarea formelor
# ─────────────────────────────────────────────────────────────────────────────

class TestShapeExpansion(unittest.TestCase):
    """Fiecare formă se descompune în primitive desenabile."""

    # core.mark_geometry nu importă nicio bibliotecă de interfață, deci
    # geometria se testează fără tkinter și fără Windows.
    expand = staticmethod(expand_mark)

    def test_box_becomes_four_opaque_bars(self):
        """
        Chenarul se desenează din patru bare opace, nu ca dreptunghi
        transparent: o suprafață opacă rămâne vizibilă peste conținutul
        accelerat GPU din Chrome și Edge.
        """
        out = self.expand({"shape": "box", "rect": (100, 100, 200, 40),
                           "thickness": 3, "pulse": False, "color": "#F00"}, 0.0)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(p["kind"] == "solid" for p in out))

    def test_highlight_is_translucent(self):
        out = self.expand({"shape": "highlight", "rect": (10, 10, 100, 20),
                           "opacity": 0.4, "pulse": False}, 0.0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "translucent")
        self.assertAlmostEqual(out[0]["alpha"], 0.4)

    def test_circle_grows_beyond_the_text(self):
        """O elipsă înscrisă exact ar tăia colțurile textului."""
        out = self.expand({"shape": "circle", "rect": (100, 100, 200, 40),
                           "pulse": False}, 0.0)
        self.assertEqual(out[0]["kind"], "oval")
        x, y, w, h = out[0]["rect"]
        self.assertLess(x, 100)
        self.assertGreater(w, 200)

    def test_underline_sits_at_the_bottom(self):
        out = self.expand({"shape": "underline", "rect": (10, 100, 80, 20),
                           "thickness": 2, "pulse": False}, 0.0)
        x, y, w, h = out[0]["rect"]
        self.assertEqual(h, 2)
        self.assertEqual(y, 118)

    def test_strikethrough_sits_in_the_middle(self):
        out = self.expand({"shape": "strikethrough", "rect": (10, 100, 80, 20),
                           "thickness": 2, "pulse": False}, 0.0)
        _, y, _, _ = out[0]["rect"]
        self.assertEqual(y, 109)

    def test_multiple_arrows(self):
        out = self.expand({"shape": "arrow", "rect": (300, 100, 80, 20),
                           "arrow_count": 3, "pulse": False}, 0.0)
        self.assertEqual(out[0]["kind"], "polygons")
        self.assertEqual(len(out[0]["polygons"]), 3)

    def test_arrow_count_is_capped(self):
        out = self.expand({"shape": "arrow", "rect": (300, 100, 80, 20),
                           "arrow_count": 99, "pulse": False}, 0.0)
        self.assertLessEqual(len(out[0]["polygons"]), 5)

    def test_arrow_sits_opposite_its_direction(self):
        """O săgeată „spre dreapta" stă la stânga zonei, ca să arate spre ea."""
        out = self.expand({"shape": "arrow", "rect": (300, 100, 80, 20),
                           "arrow_direction": "right", "pulse": False}, 0.0)
        self.assertLess(out[0]["rect"][0], 300)

    def test_badge_moves_below_when_there_is_no_room_above(self):
        high = self.expand({"shape": "badge", "rect": (10, 200, 80, 20),
                            "text": "x", "pulse": False}, 0.0)
        self.assertEqual(high[0]["rect"][1], 170)
        at_top = self.expand({"shape": "badge", "rect": (10, 2, 80, 20),
                              "text": "x", "pulse": False}, 0.0)
        self.assertGreater(at_top[0]["rect"][1], 2)

    def test_pulse_changes_thickness_over_time(self):
        thin = self.expand({"shape": "box", "rect": (0, 0, 200, 40),
                            "thickness": 3, "pulse": True}, 0.0)
        thick = self.expand({"shape": "box", "rect": (0, 0, 200, 40),
                             "thickness": 3, "pulse": True}, 1.57)
        self.assertNotEqual(thin[0]["rect"][3], thick[0]["rect"][3])

    def test_thickness_never_exceeds_half_the_box(self):
        out = self.expand({"shape": "box", "rect": (0, 0, 10, 6),
                           "thickness": 40, "pulse": False}, 0.0)
        for primitive in out:
            self.assertLessEqual(primitive["rect"][3], 6)

    def test_mark_without_rect_draws_nothing(self):
        self.assertEqual(self.expand({"shape": "box"}, 0.0), [])


class TestLegacyConversion(unittest.TestCase):
    """Regulile clasice trec prin același traseu de desen ca cele noi."""

    convert = staticmethod(visual_cue_to_marks)
    for_cue = staticmethod(marks_for_cue)

    def test_classic_cue_becomes_box_arrow_and_badge(self):
        marks = self.convert({
            "box_enabled": True, "border_color": "#FF0000", "border_width": 3,
            "arrow_enabled": True, "arrow_direction": "left",
            "badge_enabled": True, "badge_text": "VERIFICĂ",
        }, (100, 200, 300, 30))
        self.assertEqual([m["shape"] for m in marks], ["box", "arrow", "badge"])

    def test_highlight_is_off_unless_asked_for(self):
        """
        `fill_color` și `fill_opacity` existau în config de la prima versiune,
        dar nu se desenau. Pornirea lor automat ar schimba aspectul regulilor
        existente fără ca utilizatorul să ceară asta.
        """
        marks = self.convert({"box_enabled": True, "fill_color": "#FF3333",
                              "fill_opacity": 0.2}, (0, 0, 100, 20))
        self.assertNotIn("highlight", [m["shape"] for m in marks])

        enabled = self.convert({"box_enabled": True, "fill_enabled": True,
                                "fill_color": "#FF3333", "fill_opacity": 0.2},
                               (0, 0, 100, 20))
        self.assertEqual(enabled[0]["shape"], "highlight",
                         "highlight-ul se desenează sub chenar")

    def test_empty_badge_text_draws_no_badge(self):
        marks = self.convert({"badge_enabled": True, "badge_text": "   "},
                             (0, 0, 100, 20))
        self.assertNotIn("badge", [m["shape"] for m in marks])

    def test_cue_with_marks_uses_them_directly(self):
        cue = {"marks": [{"shape": "circle", "rect": (1, 2, 3, 4)}],
               "visual_cue": {"box_enabled": True}, "geometry": (0, 0, 10, 10)}
        self.assertEqual(self.for_cue(cue)[0]["shape"], "circle")

    def test_cue_without_geometry_draws_nothing(self):
        self.assertEqual(self.for_cue({"visual_cue": {"box_enabled": True}}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
