"""
Teste pentru injectarea regulilor în browser prin CDP.

Rulare:   python tests/test_browser_injection.py

Două niveluri:

* Unitare, fără browser: deciziile (ce cadru primește scriptul, când se
  reinjectează, ce stare vede utilizatorul) cu un Playwright fals.
* Integrare, pe un Chromium / Edge real pornit cu portul de depanare: scriptul
  generat marchează efectiv textul, nu se dublează la reinjectare și dispare
  la dezactivare. Se sar, cu motiv, dacă lipsește pachetul playwright sau
  browserul. Browserul se poate indica explicit cu FOCUSPILOT_TEST_CHROME.
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations import playwright_highlighter as ph                     # noqa: E402
from integrations.playwright_highlighter import (                         # noqa: E402
    CdpInjector, InjectorStatus, inject_into_frames, is_injectable, parse_port,
    cdp_endpoint, VERSION_PROBE_JS, TEARDOWN_JS,
)
from integrations.userscript_generator import build_userscript            # noqa: E402


def rule(rule_id="r1", text="Pending", enabled=True, badge="ATENȚIE"):
    return {
        "id": rule_id, "name": rule_id, "enabled": enabled,
        "trigger": {"search_text": text, "url_pattern": "*",
                    "window_title_pattern": "*", "text_condition": "contains"},
        "visual_cue": {"box_enabled": True, "border_color": "#FF0000",
                       "border_width": 3, "badge_enabled": True,
                       "badge_text": badge, "arrow_enabled": False},
    }


# ── Dubluri ──────────────────────────────────────────────────────────────────

class FakeFrame:
    def __init__(self, url, version=None, fail=False):
        self.url = url
        self.version = version
        self.fail = fail
        self.injected = []
        self.torn_down = 0

    def evaluate(self, expression, arg=None):
        if self.fail:
            raise RuntimeError("Execution context was destroyed")
        if expression == VERSION_PROBE_JS:
            return self.version
        if expression == TEARDOWN_JS:
            self.torn_down += 1
            return True
        self.injected.append(expression)
        marker = "const VERSION = '"
        start = expression.index(marker) + len(marker)
        self.version = expression[start:expression.index("'", start)]
        return self.version


class FakePage:
    def __init__(self, frames):
        self.frames = frames


class FakeContext:
    def __init__(self, pages):
        self.pages = pages


class FakeBrowser:
    def __init__(self, frames):
        self.contexts = [FakeContext([FakePage(frames)])]
        self.connected = True

    def is_connected(self):
        return self.connected


class FakeChromium:
    def __init__(self, owner):
        self.owner = owner

    def connect_over_cdp(self, endpoint, timeout=None):
        self.owner.endpoints.append(endpoint)
        if self.owner.refuse:
            raise ConnectionRefusedError("ECONNREFUSED")
        return self.owner.browser


class FakePlaywright:
    def __init__(self, browser, refuse=False):
        self.browser = browser
        self.refuse = refuse
        self.endpoints = []
        self.stopped = 0
        self.chromium = FakeChromium(self)

    def stop(self):
        self.stopped += 1


# ── Funcții pure ─────────────────────────────────────────────────────────────

class PureFunctionsTest(unittest.TestCase):

    def test_only_web_pages_are_injectable(self):
        self.assertTrue(is_injectable("https://intranet/app"))
        self.assertTrue(is_injectable("HTTP://host"))
        self.assertTrue(is_injectable("file:///C:/x.html"))
        for url in ("edge://newtab/", "chrome://settings", "about:blank",
                    "devtools://devtools/x", "chrome-extension://abc/p.html", ""):
            self.assertFalse(is_injectable(url), url)

    def test_port_validation(self):
        self.assertEqual(parse_port("9222"), 9222)
        self.assertEqual(parse_port(" 9333 "), 9333)
        for bad in ("", "abc", "0", "70000", None):
            with self.assertRaises(ValueError):
                parse_port(bad)

    def test_endpoint_uses_ipv4_loopback(self):
        # `localhost` aștepta timeout-ul pe ::1 înainte de IPv4.
        self.assertEqual(cdp_endpoint(9222), "http://127.0.0.1:9222")

    def test_version_follows_active_rules(self):
        script_a, version_a = build_userscript([rule()])
        _, version_again = build_userscript([rule()])
        _, version_b = build_userscript([rule(text="Merge")])
        _, version_disabled_extra = build_userscript(
            [rule(), rule("r2", "Merge", enabled=False)])
        self.assertEqual(version_a, version_again)
        self.assertNotEqual(version_a, version_b)
        # O regulă dezactivată nu ajunge în browser, deci nu schimbă versiunea.
        self.assertEqual(version_a, version_disabled_extra)
        self.assertIn(f"const VERSION = '{version_a}';", script_a)
        self.assertNotIn("__RULES_", script_a)


# ── O trecere peste cadre ────────────────────────────────────────────────────

class InjectIntoFramesTest(unittest.TestCase):

    def setUp(self):
        self.script, self.version = build_userscript([rule()])

    def test_injects_only_where_version_differs(self):
        fresh = FakeFrame("https://a/")
        stale = FakeFrame("https://b/", version="old")
        current = FakeFrame("https://c/", version=self.version)
        internal = FakeFrame("edge://newtab/")
        report = inject_into_frames([fresh, stale, current, internal],
                                    self.script, self.version)
        self.assertEqual((report.pages, report.injected, report.up_to_date, report.failed),
                         (3, 2, 1, 0))
        self.assertEqual(len(fresh.injected), 1)
        self.assertEqual(len(stale.injected), 1)
        self.assertEqual(current.injected, [])
        self.assertEqual(internal.injected, [])
        self.assertTrue(fresh.injected[0].startswith("() => {"))
        self.assertIn("injectedBy = 'cdp'", fresh.injected[0])

    def test_failures_are_counted_not_raised(self):
        report = inject_into_frames([FakeFrame("https://x/", fail=True),
                                     FakeFrame("https://y/")],
                                    self.script, self.version)
        self.assertEqual((report.injected, report.failed), (1, 1))
        self.assertIn("https://x/", report.errors[0])


# ── Firul de injectare, cu Playwright fals ───────────────────────────────────

class CdpInjectorTest(unittest.TestCase):

    def setUp(self):
        self.rules = [rule()]
        self.frames = [FakeFrame("https://intranet/app")]
        self.browser = FakeBrowser(self.frames)
        self.fake = FakePlaywright(self.browser)
        self.injector = CdpInjector(lambda: build_userscript(self.rules),
                                    playwright_factory=lambda: self.fake)

    def test_disabled_by_default_and_does_not_connect(self):
        self.assertEqual(self.injector.tick().state, ph.DISABLED)
        self.assertEqual(self.fake.endpoints, [])

    def test_missing_playwright_is_reported(self):
        def factory():
            raise ImportError("No module named 'playwright'")
        injector = CdpInjector(lambda: build_userscript(self.rules),
                               playwright_factory=factory)
        injector.configure(True, 9222)
        status = injector.tick()
        self.assertEqual(status.state, ph.MISSING_PLAYWRIGHT)
        self.assertFalse(status.ok)
        self.assertIn("pip install playwright", status.describe())

    def test_unreachable_browser_names_port_and_launch_flag(self):
        self.fake.refuse = True
        self.injector.configure(True, 9333)
        status = self.injector.tick()
        self.assertEqual(status.state, ph.UNREACHABLE)
        self.assertIn("9333", status.describe())
        self.assertIn("--remote-debugging-port=9333", status.describe())

    def test_injects_once_then_again_after_rules_change(self):
        self.injector.configure(True, 9222)
        status = self.injector.tick()
        self.assertEqual(status.state, ph.CONNECTED)
        self.assertEqual(self.fake.endpoints, ["http://127.0.0.1:9222"])
        self.assertEqual(len(self.frames[0].injected), 1)

        self.injector.tick()
        self.assertEqual(len(self.frames[0].injected), 1, "aceeași versiune: fără reinjectare")

        self.rules = [rule(text="Merge")]
        self.injector.tick()
        self.assertEqual(len(self.frames[0].injected), 2)

    def test_new_tab_is_picked_up(self):
        self.injector.configure(True, 9222)
        self.injector.tick()
        late = FakeFrame("https://intranet/other")
        self.browser.contexts[0].pages.append(FakePage([late]))
        self.injector.tick()
        self.assertEqual(len(late.injected), 1)

    def test_disable_removes_marks_and_disconnects(self):
        self.injector.configure(True, 9222)
        self.injector.tick()
        self.injector.configure(False)
        self.assertEqual(self.injector.tick().state, ph.DISABLED)
        self.assertEqual(self.frames[0].torn_down, 1)
        self.assertEqual(self.fake.stopped, 1)

    def test_port_change_reconnects(self):
        self.injector.configure(True, 9222)
        self.injector.tick()
        self.injector.configure(True, 9333)
        self.injector.tick()
        self.assertEqual(self.fake.endpoints,
                         ["http://127.0.0.1:9222", "http://127.0.0.1:9333"])

    def test_lost_connection_reconnects(self):
        self.injector.configure(True, 9222)
        self.injector.tick()
        self.browser.connected = False
        self.injector.tick()
        self.assertEqual(len(self.fake.endpoints), 2)

    def test_status_ok_flags(self):
        self.assertTrue(InjectorStatus(ph.DISABLED).ok)
        self.assertTrue(InjectorStatus(ph.CONNECTED, "x").ok)
        self.assertFalse(InjectorStatus(ph.UNREACHABLE, "x").ok)
        self.assertFalse(InjectorStatus(ph.ERROR, "x").ok)

    def test_background_thread_survives_errors(self):
        def broken():
            raise RuntimeError("regulile nu se pot citi")
        injector = CdpInjector(broken, interval_sec=0.5,
                               playwright_factory=lambda: self.fake)
        injector.configure(True, 9222)
        with self.assertLogs(ph.logger, level="ERROR") as logs:
            injector.start()
            try:
                self._wait_for_error(injector)
            finally:
                injector.stop()
        failures = [r for r in logs.records if r.exc_info]
        self.assertEqual(len(failures), 1, "aceeași eroare se jurnalizează o singură dată")

    def _wait_for_error(self, injector):
        deadline = time.time() + 3
        while time.time() < deadline and injector.status().state != ph.ERROR:
            time.sleep(0.05)
        self.assertEqual(injector.status().state, ph.ERROR)
        # Câteva tic-uri cu aceeași eroare, iar firul trebuie să rămână viu.
        time.sleep(1.2)
        self.assertTrue(injector._thread.is_alive(), "firul nu trebuie să moară")


# ── Integrare pe browser real ────────────────────────────────────────────────

def _find_browser():
    explicit = os.environ.get("FOCUSPILOT_TEST_CHROME", "").strip()
    if explicit:
        return explicit if os.path.exists(explicit) else None
    candidates = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            candidates.append(p.chromium.executable_path)
    except Exception:
        pass
    for name in ("msedge", "chrome", "chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        if base:
            candidates.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    return next((c for c in candidates if c and os.path.exists(c)), None)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


try:
    import playwright  # noqa: F401
    HAVE_PLAYWRIGHT = True
except ImportError:
    HAVE_PLAYWRIGHT = False

BROWSER = _find_browser() if HAVE_PLAYWRIGHT else None

PAGE_HTML = """<!doctype html><html><head><title>Coada</title></head><body>
<table><tr><td id="a">Status: Pending review</td><td id="b">Merged</td></tr></table>
</body></html>"""

MARKS_JS = """() => ({
    outlined: Array.from(document.querySelectorAll('[data-focuspilot-marked]')).map(e => e.id),
    badges: document.querySelectorAll('.focuspilot-tag').length,
    version: window.__focuspilot ? window.__focuspilot.version : null,
})"""


@unittest.skipUnless(HAVE_PLAYWRIGHT, "pachetul playwright nu e instalat")
@unittest.skipUnless(BROWSER, "nu s-a găsit Chrome / Edge / Chromium (FOCUSPILOT_TEST_CHROME)")
class RealBrowserTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="focuspilot_cdp_")
        cls.page_path = os.path.join(cls.tmp, "coada.html")
        with open(cls.page_path, "w", encoding="utf-8") as handle:
            handle.write(PAGE_HTML)
        cls.port = _free_port()
        cls.proc = subprocess.Popen(
            [BROWSER, "--headless=new", f"--remote-debugging-port={cls.port}",
             f"--user-data-dir={os.path.join(cls.tmp, 'profil')}",
             "--no-first-run", "--no-default-browser-check", "--disable-gpu",
             "--no-sandbox", "file:///" + cls.page_path.replace("\\", "/").lstrip("/")],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", cls.port), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        try:
            cls.proc.wait(10)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.rules = [rule()]
        self.injector = CdpInjector(lambda: build_userscript(self.rules))

    def tearDown(self):
        self.injector.configure(False)
        self.injector.tick()

    def _page(self):
        for context in self.injector._browser.contexts:
            for page in context.pages:
                if page.url.startswith("file:"):
                    return page
        self.fail("pagina de test nu e deschisă în browser")

    def _marks(self, page):
        # Userscript-ul aplică imediat, dar reaplicările trec prin debounce.
        page.wait_for_timeout(400)
        return page.evaluate(MARKS_JS)

    def test_marks_follow_rules_and_disappear_on_disable(self):
        self.injector.configure(True, self.port)
        status = self.injector.tick()
        self.assertEqual(status.state, ph.CONNECTED, status.describe())
        page = self._page()

        marks = self._marks(page)
        self.assertEqual(marks["outlined"], ["a"])
        self.assertEqual(marks["badges"], 1)

        # A doua trecere nu dublează badge-ul.
        self.injector.tick()
        self.assertEqual(self._marks(page)["badges"], 1)

        # Regula schimbată: marcajul vechi dispare, apare cel nou.
        self.rules = [rule(text="Merged")]
        self.injector.tick()
        marks = self._marks(page)
        self.assertEqual(marks["outlined"], ["b"])
        self.assertEqual(marks["badges"], 1)

        # Paginile noi și navigările sunt prinse de trecerea următoare.
        page.reload()
        self.injector.tick()
        self.assertEqual(self._marks(page)["outlined"], ["b"])

        self.injector.configure(False)
        self.injector.tick()
        # Conexiunea injectorului s-a închis; verificăm cu una nouă.
        checker = CdpInjector(lambda: build_userscript([]))
        checker.configure(True, self.port)
        self.assertTrue(checker._ensure_connected(self.port))
        try:
            page = next(p for c in checker._browser.contexts for p in c.pages
                        if p.url.startswith("file:"))
            marks = page.evaluate(MARKS_JS)
            self.assertEqual((marks["outlined"], marks["badges"], marks["version"]),
                             ([], 0, None))
        finally:
            checker._disconnect()

    def test_disable_keeps_userscript_instance_it_did_not_inject(self):
        """Scriptul din Tampermonkey rămâne când se oprește injectarea CDP."""
        script, version = build_userscript(self.rules)
        self.injector.configure(True, self.port)
        self.injector.tick()
        page = self._page()
        # Simulează Tampermonkey: o instanță neinjectată de noi, aceeași versiune.
        page.evaluate("() => { const c = window.__focuspilot; if (c) { c.teardown(); } "
                      "delete window.__focuspilot; }")
        page.evaluate("() => {\n" + script + "\n}")
        self.assertEqual(self._marks(page)["version"], version)

        self.injector.tick()   # aceeași versiune: nu o înlocuiește
        self.assertNotEqual(page.evaluate("() => window.__focuspilot.injectedBy"), "cdp")

        removed = ph.teardown_frames(ph.iter_frames(self.injector._browser))
        self.assertEqual(removed, 0)
        self.assertEqual(self._marks(page)["outlined"], ["a"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
