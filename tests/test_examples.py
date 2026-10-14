"""
Verifică regulile-exemplu din documentație.

Rulare:   python tests/test_examples.py

Exemplele din GHID_REGULI.md sunt extrase în examples/reguli_exemplu.json.
Acest test le trece prin motorul real, pe ecrane simulate, ca o regulă din
documentație să nu poată fi una care nu funcționează.
"""

import os
import sys
import json
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


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

from core import rule_engine, probe_engine                      # noqa: E402
from core.rule_engine import RuleEngine, UiaSnapshot            # noqa: E402
from core.mark_geometry import expand_mark, marks_for_cue       # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples", "reguli_exemplu.json")
VIRT = (0, 0, 1920, 1080)
WINDOW_RECT = (0, 0, 1600, 1000)


def load_examples():
    with open(EXAMPLES, encoding="utf-8") as handle:
        return json.load(handle)["rules"]


def by_id(rule_id):
    for rule in load_examples():
        if rule["id"] == rule_id:
            return rule
    raise AssertionError(f"regula '{rule_id}' lipsește din exemple")


def snapshot(*items):
    return UiaSnapshot(items=list(items), truncated=False, captured_at=1e9)


def window(title="Portal", process="chrome.exe", url="", hwnd=1):
    return {"hwnd": hwnd, "title": title, "process_name": process,
            "rect": WINDOW_RECT, "url": url, "extra_text": ""}


class ExampleTestCase(unittest.TestCase):
    """Înlocuiește citirea de pe ecran cu un conținut controlat."""

    screen = None

    def setUp(self):
        self._orig = rule_engine.capture_window_text
        rule_engine.capture_window_text = lambda hwnd, force=False: self.screen
        rule_engine.CAPABILITIES._uia = True
        rule_engine.CAPABILITIES._cv = True
        rule_engine._previous_probe_values.clear()

    def tearDown(self):
        rule_engine.capture_window_text = self._orig
        self.screen = None


# ─────────────────────────────────────────────────────────────────────────────
# Sănătatea fișierului de exemple
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleFile(unittest.TestCase):

    def test_file_exists_and_parses(self):
        self.assertTrue(os.path.exists(EXAMPLES), "fișierul de exemple lipsește")
        self.assertTrue(load_examples(), "fișierul nu conține nicio regulă")

    def test_every_rule_has_unique_id_and_name(self):
        rules = load_examples()
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)), "există ID-uri duplicate")
        for rule in rules:
            self.assertTrue(str(rule.get("name", "")).strip(),
                            f"regula {rule['id']} nu are nume")

    def test_condition_rules_pass_validation(self):
        """
        Fiecare exemplu cu câmpuri trebuie să treacă exact validarea care
        rulează la salvare în editor.
        """
        for rule in load_examples():
            if not probe_engine.uses_conditions(rule):
                continue
            problem = probe_engine.validate_rule_fields(rule)
            self.assertIsNone(problem,
                              f"exemplul '{rule['name']}' e invalid: {problem}")

    def test_every_mark_targets_a_defined_probe(self):
        for rule in load_examples():
            names = {p["name"] for p in rule.get("probes", [])}
            for mark in rule.get("marks", []):
                target = mark.get("target")
                if target:
                    self.assertIn(target, names,
                                  f"'{rule['name']}': marcajul indică un câmp "
                                  f"nedefinit '{target}'")

    def test_every_mark_shape_is_drawable(self):
        """O formă din documentație trebuie să producă primitive de desen."""
        for rule in load_examples():
            for mark in rule.get("marks", []):
                probe = dict(mark, rect=(100, 100, 200, 30))
                primitives = expand_mark(probe, 0.0)
                self.assertTrue(primitives,
                                f"'{rule['name']}': forma "
                                f"'{mark.get('shape')}' nu desenează nimic")

    def test_classic_rules_produce_marks(self):
        for rule in load_examples():
            if probe_engine.uses_conditions(rule):
                continue
            marks = marks_for_cue({"visual_cue": rule.get("visual_cue", {}),
                                   "geometry": (100, 100, 300, 30)})
            self.assertTrue(marks, f"'{rule['name']}' nu desenează nimic")


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul A — text simplu
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleA(ExampleTestCase):

    RULE = staticmethod(lambda: by_id("exemplu_text_simplu"))

    def test_fires_when_the_text_is_on_screen(self):
        self.screen = snapshot(("Please change category", (400, 500, 220, 24)))
        result = RuleEngine.evaluate(self.RULE(), window(title="TIMA Gateway"), VIRT)
        self.assertTrue(result.drawable)

    def test_does_not_fire_on_another_window(self):
        self.screen = snapshot(("Please change category", (400, 500, 220, 24)))
        result = RuleEngine.evaluate(self.RULE(), window(title="Notepad"), VIRT)
        self.assertFalse(result.matched)

    def test_does_not_fire_without_the_text(self):
        self.screen = snapshot(("All good", (400, 500, 80, 24)))
        result = RuleEngine.evaluate(self.RULE(), window(title="TIMA"), VIRT)
        self.assertFalse(result.matched)

    def test_does_not_fire_outside_a_browser(self):
        self.screen = snapshot(("Please change category", (400, 500, 220, 24)))
        result = RuleEngine.evaluate(self.RULE(),
                                     window(title="TIMA", process="excel.exe"), VIRT)
        self.assertFalse(result.matched)

    def test_draws_two_arrows_as_configured(self):
        self.screen = snapshot(("Please change category", (400, 500, 220, 24)))
        result = RuleEngine.evaluate(self.RULE(), window(title="TIMA"), VIRT)
        marks = marks_for_cue({"visual_cue": self.RULE()["visual_cue"],
                               "geometry": result.geometry})
        arrows = [m for m in marks if m["shape"] == "arrow"]
        self.assertEqual(len(expand_mark(arrows[0], 0.0)[0]["polygons"]), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul B — două câmpuri cu AND
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleB(ExampleTestCase):
    """Cerința centrală: „dacă câmpul X are valoarea Z și câmpul Y are C"."""

    RULE = staticmethod(lambda: by_id("exemplu_doua_campuri"))

    FULL = snapshot(
        ("Status",   (100, 300, 60, 20)),
        ("Wait for Merge", (200, 300, 120, 20)),
        ("Quantity", (100, 340, 80, 20)),
        ("18",       (200, 340, 40, 20)),
    )

    def test_fires_when_both_hold(self):
        self.screen = self.FULL
        result = RuleEngine.evaluate(self.RULE(), window(title="GSP Console"), VIRT)
        self.assertTrue(result.drawable)
        self.assertEqual(result.anchor, "probe")

    def test_does_not_fire_when_status_differs(self):
        self.screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Merged",   (200, 300, 80, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("18",       (200, 340, 40, 20)),
        )
        result = RuleEngine.evaluate(self.RULE(), window(title="GSP"), VIRT)
        self.assertFalse(result.matched)
        self.assertIn("status", result.reason)

    def test_does_not_fire_when_quantity_is_zero(self):
        self.screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Wait for Merge", (200, 300, 120, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("0",        (200, 340, 40, 20)),
        )
        result = RuleEngine.evaluate(self.RULE(), window(title="GSP"), VIRT)
        self.assertFalse(result.matched)
        self.assertIn("cantitate", result.reason)

    def test_status_equals_is_strict(self):
        """`este exact` nu trebuie să accepte o potrivire parțială."""
        self.screen = snapshot(
            ("Status",   (100, 300, 60, 20)),
            ("Wait for Merge later", (200, 300, 160, 20)),
            ("Quantity", (100, 340, 80, 20)),
            ("18",       (200, 340, 40, 20)),
        )
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(title="GSP"),
                                             VIRT).matched)

    def test_three_marks_on_two_fields(self):
        self.screen = self.FULL
        result = RuleEngine.evaluate(self.RULE(), window(title="GSP"), VIRT)
        self.assertEqual(len(result.marks), 3)
        shapes = [m["shape"] for m in result.marks]
        self.assertEqual(shapes, ["highlight", "circle", "arrow"])

        # Highlight-ul stă pe status, cercul pe cantitate: dreptunghiuri diferite.
        self.assertNotEqual(result.marks[0]["rect"], result.marks[1]["rect"])
        # Cercul și săgețile stau pe același câmp.
        self.assertEqual(result.marks[1]["rect"], result.marks[2]["rect"])

    def test_title_alternatives_both_work(self):
        self.screen = self.FULL
        for title in ("GSP Console", "Service Platform Industry"):
            self.assertTrue(
                RuleEngine.evaluate(self.RULE(), window(title=title), VIRT).matched,
                f"titlul '{title}' trebuie acceptat")


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul C — interval numeric
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleC(ExampleTestCase):

    RULE = staticmethod(lambda: by_id("exemplu_interval"))

    def _screen_with(self, price):
        return snapshot(("Total", (100, 400, 50, 20)),
                        (price, (200, 400, 140, 20)))

    def test_inside_the_range(self):
        self.screen = self._screen_with("1.234,50 EUR")
        self.assertTrue(RuleEngine.evaluate(self.RULE(), window(title="Portal"),
                                            VIRT).matched)

    def test_below_the_range(self):
        self.screen = self._screen_with("42,00 EUR")
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(title="Portal"),
                                             VIRT).matched)

    def test_above_the_range(self):
        self.screen = self._screen_with("9.999,00 EUR")
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(title="Portal"),
                                             VIRT).matched)

    def test_text_instead_of_a_number(self):
        self.screen = self._screen_with("n/a")
        result = RuleEngine.evaluate(self.RULE(), window(title="Portal"), VIRT)
        self.assertFalse(result.matched)

    def test_anglo_number_format_also_works(self):
        self.screen = self._screen_with("1,234.50")
        self.assertTrue(RuleEngine.evaluate(self.RULE(), window(title="Portal"),
                                            VIRT).matched)


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul D — câmp obligatoriu gol
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleD(ExampleTestCase):

    RULE = staticmethod(lambda: by_id("exemplu_camp_gol"))

    def test_fires_when_the_field_is_empty(self):
        # Eticheta e pe ecran, dar nu există nimic la dreapta ei.
        self.screen = snapshot(("Cost Center", (100, 500, 90, 20)))
        result = RuleEngine.evaluate(self.RULE(), window(title="Formular Nou"), VIRT)
        self.assertTrue(result.matched)

    def test_does_not_fire_when_filled_in(self):
        self.screen = snapshot(("Cost Center", (100, 500, 90, 20)),
                               ("DE-4711", (210, 500, 80, 20)))
        self.assertFalse(RuleEngine.evaluate(self.RULE(),
                                             window(title="Formular"), VIRT).matched)

    def test_marks_are_skipped_when_the_label_is_absent(self):
        """
        Fără etichetă pe ecran nu există unde desena. Condiția `este gol` e
        adevărată, dar un marcaj la întâmplare ar fi mai rău decât niciunul.
        """
        self.screen = snapshot(("altceva", (10, 10, 50, 20)))
        result = RuleEngine.evaluate(self.RULE(), window(title="Formular"), VIRT)
        self.assertTrue(result.matched)
        self.assertEqual(result.marks, ())
        self.assertIn("nu sunt vizibile", result.reason)


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul E — coordonate fixe
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleE(ExampleTestCase):

    RULE = staticmethod(lambda: by_id("exemplu_coordonate_fixe"))

    def test_reads_the_region_and_fires(self):
        self.screen = snapshot(("Connection error: timeout", (20, 1045, 300, 18)))
        result = RuleEngine.evaluate(self.RULE(), window(title="Orice"), VIRT)
        self.assertTrue(result.drawable)

    def test_does_not_fire_without_the_keyword(self):
        self.screen = snapshot(("Ready", (20, 1045, 60, 18)))
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(), VIRT).matched)

    def test_ignores_text_outside_the_region(self):
        """Textul din afara zonei definite nu trebuie luat în calcul."""
        self.screen = snapshot(("error somewhere else", (800, 200, 200, 18)))
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(), VIRT).matched)


# ─────────────────────────────────────────────────────────────────────────────
# Exemplul F — valoare schimbată
# ─────────────────────────────────────────────────────────────────────────────

class TestExampleF(ExampleTestCase):

    RULE = staticmethod(lambda: by_id("exemplu_schimbare"))

    def _screen_with(self, status):
        return snapshot(("Status", (100, 300, 60, 20)),
                        (status, (200, 300, 120, 20)))

    def test_does_not_fire_on_the_first_look(self):
        """Fără o valoare anterioară nu se poate afirma o schimbare."""
        self.screen = self._screen_with("Merge")
        self.assertFalse(RuleEngine.evaluate(self.RULE(), window(title="Portal"),
                                             VIRT).matched)

    def test_fires_after_the_value_changes(self):
        rule = self.RULE()
        self.screen = self._screen_with("Merge")
        RuleEngine.evaluate(rule, window(title="Portal"), VIRT)       # memorează

        self.screen = self._screen_with("Wait for Merge")
        self.assertTrue(RuleEngine.evaluate(rule, window(title="Portal"),
                                            VIRT).matched)

    def test_does_not_fire_when_the_value_stays(self):
        rule = self.RULE()
        self.screen = self._screen_with("Merge")
        RuleEngine.evaluate(rule, window(title="Portal"), VIRT)
        self.assertFalse(RuleEngine.evaluate(rule, window(title="Portal"),
                                             VIRT).matched)


if __name__ == "__main__":
    unittest.main(verbosity=2)
