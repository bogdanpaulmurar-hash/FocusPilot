"""
FocusPilot — injectarea regulilor în browser prin CDP (Playwright)

Se conectează la Chrome / Edge pornit cu portul de depanare deschis și
injectează în fiecare tab ACELAȘI script pe care îl produce
`userscript_generator`. Rezultatul e identic cu userscript-ul din Tampermonkey
— chenarul urmează elementul la scroll — dar fără extensie de instalat.

Varianta anterioară a acestui modul avea propria copie a logicii din browser:
ignora filtrele de URL și titlu, condițiile de text, criteriile AND, săgețile
și badge-urile, aplica regulile o singură dată (un tab nou sau o navigare nu
mai primeau nimic) și nu era legată de interfață. Acum există o singură
implementare a logicii din pagină, iar acest modul doar o livrează.

Toate apelurile Playwright se fac pe firul `CdpInjector`: API-ul sincron al
Playwright e legat de firul pe care a fost pornit.

Modulul nu importă tkinter; interfața citește doar `CdpInjector.status()`.
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_PORT = 9222
DEFAULT_INTERVAL_SEC = 3.0
CONNECT_TIMEOUT_MS = 2000

# Doar paginile web obișnuite. Paginile interne ale browserului și extensiile
# refuză evaluarea sau n-au ce marca, iar o eroare pe fiecare tic pentru
# `edge://newtab` ar ascunde erorile care contează.
INJECTABLE_PREFIXES = ("http://", "https://", "file://")

LAUNCH_HINT = ("Browserul se pornește cu --remote-debugging-port={port} și "
               "--user-data-dir=<un folder separat>; pe profilul implicit "
               "Chrome și Edge recente ignoră portul. Detalii în GHID_REGULI.md.")


# ── Funcții pure, testabile fără browser ─────────────────────────────────────

def is_injectable(url: str) -> bool:
    return str(url or "").lower().startswith(INJECTABLE_PREFIXES)


def parse_port(value: Any) -> int:
    """Portul ca întreg valid, altfel ValueError cu un mesaj pentru utilizator."""
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"Portul trebuie să fie un număr, nu „{value}”.")
    if not 1 <= port <= 65535:
        raise ValueError(f"Portul {port} nu este între 1 și 65535.")
    return port


def cdp_endpoint(port: Any) -> str:
    # 127.0.0.1, nu `localhost`: pe Windows `localhost` se rezolvă întâi la
    # ::1, iar Chrome ascultă implicit doar pe IPv4, deci conectarea aștepta
    # până la timeout la fiecare încercare.
    return f"http://127.0.0.1:{parse_port(port)}"


VERSION_PROBE_JS = "() => (window.__focuspilot && window.__focuspilot.version) || null"

# Șterge doar instanța injectată de noi. Dacă pagina are scriptul din
# Tampermonkey, oprirea injectării CDP nu trebuie să-i ia marcajele.
TEARDOWN_JS = """() => {
    const current = window.__focuspilot;
    if (!current || current.injectedBy !== 'cdp') { return false; }
    if (typeof current.teardown === 'function') { current.teardown(); }
    delete window.__focuspilot;
    return true;
}"""


def wrap_for_evaluate(script: str) -> str:
    """
    Scriptul de browser ca funcție pentru `frame.evaluate`.

    `evaluate` rulează în lumea paginii și ocolește CSP-ul, spre deosebire de
    un `<script>` inserat, pe care multe aplicații interne îl blochează.
    Instanța creată aici e marcată `injectedBy = 'cdp'`, ca `TEARDOWN_JS` să
    știe ce îi aparține.
    """
    return ("() => {\n"
            "const __fpBefore = window.__focuspilot;\n"
            f"{script}\n"
            "const __fpNow = window.__focuspilot;\n"
            "if (__fpNow && __fpNow !== __fpBefore) { __fpNow.injectedBy = 'cdp'; }\n"
            "return __fpNow ? __fpNow.version : null;\n"
            "}")


@dataclass
class InjectionReport:
    """Ce s-a întâmplat la o trecere peste toate cadrele."""
    pages: int = 0
    injected: int = 0
    up_to_date: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


def inject_into_frames(frames: Iterable[Any], script: str, version: str) -> InjectionReport:
    """
    Injectează scriptul în cadrele care nu au deja versiunea curentă.

    Verificarea versiunii costă un apel scurt pe cadru, deci trecerea se poate
    repeta la câteva secunde: taburile noi, navigările și regulile schimbate
    sunt prinse fără evenimente de urmărit.
    """
    report = InjectionReport()
    wrapped = None
    for frame in frames:
        url = getattr(frame, "url", "")
        if not is_injectable(url):
            continue
        report.pages += 1
        try:
            if frame.evaluate(VERSION_PROBE_JS) == version:
                report.up_to_date += 1
                continue
            if wrapped is None:
                wrapped = wrap_for_evaluate(script)
            frame.evaluate(wrapped)
            report.injected += 1
        except Exception as exc:
            # Un cadru care navighează sau se închide între enumerare și
            # evaluare e normal; eșecurile se văd în stare, nu în jurnal la
            # fiecare tic.
            report.failed += 1
            report.errors.append(f"{url[:80]}: {exc}")
    return report


def teardown_frames(frames: Iterable[Any]) -> int:
    removed = 0
    for frame in frames:
        if not is_injectable(getattr(frame, "url", "")):
            continue
        try:
            if frame.evaluate(TEARDOWN_JS):
                removed += 1
        except Exception as exc:
            logger.debug("Curățarea cadrului %s a eșuat: %s", getattr(frame, "url", ""), exc)
    return removed


def iter_frames(browser: Any) -> List[Any]:
    """Toate cadrele din toate taburile; listă, ca să nu se schimbe sub noi."""
    frames: List[Any] = []
    for context in list(browser.contexts):
        for page in list(context.pages):
            frames.extend(list(page.frames))
    return frames


# ── Starea, așa cum o vede utilizatorul ──────────────────────────────────────

DISABLED = "disabled"
MISSING_PLAYWRIGHT = "missing_playwright"
UNREACHABLE = "unreachable"
CONNECTED = "connected"
ERROR = "error"


@dataclass(frozen=True)
class InjectorStatus:
    state: str
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state in (DISABLED, CONNECTED)

    def describe(self) -> str:
        if self.state == DISABLED:
            return "Dezactivată."
        if self.state == MISSING_PLAYWRIGHT:
            return ("Lipsește pachetul playwright. Instalați cu:  pip install playwright")
        if self.state == UNREACHABLE:
            return f"Browserul nu răspunde. {self.detail}"
        if self.state == CONNECTED:
            return f"Conectat. {self.detail}"
        return f"Eroare: {self.detail}"


def _default_playwright_factory():
    # Importat aici, nu sus: fără pachet, restul aplicației pornește normal,
    # iar lipsa lui apare în stare.
    from playwright.sync_api import sync_playwright
    return sync_playwright().start()


class CdpInjector:
    """
    Fir de fundal care ține scriptul de browser injectat în toate taburile.

    `script_provider()` întoarce (script, versiune) pentru regulile curente;
    se cheamă pe fiecare trecere, deci o regulă salvată ajunge în pagini la
    următorul tic, fără repornire.
    """

    def __init__(self, script_provider: Callable[[], Tuple[str, str]],
                 interval_sec: float = DEFAULT_INTERVAL_SEC,
                 playwright_factory: Optional[Callable[[], Any]] = None):
        self._script_provider = script_provider
        self._interval = max(0.5, float(interval_sec))
        self._factory = playwright_factory or _default_playwright_factory

        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stopping = False
        self._enabled = False
        self._port = DEFAULT_PORT
        self._status = InjectorStatus(DISABLED)
        self._thread: Optional[threading.Thread] = None

        # Folosite doar pe firul de lucru.
        self._playwright = None
        self._browser = None
        self._connected_port: Optional[int] = None
        self._last_error: Optional[str] = None

    # ── API pentru aplicație (orice fir) ─────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping = False
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="FocusPilotCdp")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stopping = True
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
            self._thread = None

    def configure(self, enabled: bool, port: Any = DEFAULT_PORT) -> None:
        with self._lock:
            self._enabled = bool(enabled)
            self._port = parse_port(port)
        self._wake.set()

    def notify_rules_changed(self) -> None:
        self._wake.set()

    def status(self) -> InjectorStatus:
        with self._lock:
            return self._status

    # ── Firul de lucru ───────────────────────────────────────────────────────

    def _run(self) -> None:
        try:
            while not self._stopping:
                try:
                    self.tick()
                except Exception as exc:
                    # Neprinsă, o excepție aici omora firul în tăcere și
                    # injectarea se oprea fără niciun semn în interfață.
                    # Urma completă intră în jurnal o dată per eroare, nu la
                    # fiecare tic cât timp eroarea persistă.
                    if str(exc) != self._last_error:
                        logger.exception("Injectarea CDP a eșuat: %s", exc)
                    self._last_error = str(exc)
                    self._set_status(InjectorStatus(ERROR, str(exc)))
                    self._disconnect()
                else:
                    self._last_error = None
                self._wake.wait(self._interval)
                self._wake.clear()
        finally:
            self._shutdown()

    def tick(self) -> InjectorStatus:
        """O trecere completă. Public pentru teste; în aplicație o cheamă firul."""
        with self._lock:
            enabled, port = self._enabled, self._port

        if not enabled:
            if self._browser is not None:
                self._remove_marks()
            self._disconnect()
            return self._set_status(InjectorStatus(DISABLED))

        if self._connected_port is not None and self._connected_port != port:
            self._remove_marks()
            self._disconnect()

        if not self._ensure_connected(port):
            return self.status()

        script, version = self._script_provider()
        report = inject_into_frames(iter_frames(self._browser), script, version)
        for error in report.errors:
            logger.debug("CDP: %s", error)
        if report.injected:
            logger.info("CDP: script injectat în %d cadre (versiunea %s).",
                        report.injected, version)

        detail = f"{report.pages} pagini web pe portul {port}."
        if report.failed:
            detail += f" {report.failed} nu au primit scriptul: {report.errors[0]}"
        return self._set_status(InjectorStatus(CONNECTED, detail))

    def _ensure_connected(self, port: int) -> bool:
        if self._browser is not None:
            try:
                if self._browser.is_connected():
                    return True
            except Exception:
                pass
            logger.info("CDP: conexiunea cu browserul s-a pierdut; se reconectează.")
            self._disconnect()

        if self._playwright is None:
            try:
                self._playwright = self._factory()
            except ImportError:
                self._set_status(InjectorStatus(MISSING_PLAYWRIGHT))
                return False

        try:
            self._browser = self._playwright.chromium.connect_over_cdp(
                cdp_endpoint(port), timeout=CONNECT_TIMEOUT_MS)
        except Exception as exc:
            self._browser = None
            self._set_status(InjectorStatus(
                UNREACHABLE, f"Nimic pe portul {port}: browserul trebuie pornit "
                             f"cu --remote-debugging-port={port}."))
            logger.debug("CDP: conectarea pe portul %d a eșuat: %s", port, exc)
            return False

        self._connected_port = port
        logger.info("CDP: conectat la browser pe portul %d.", port)
        return True

    def _remove_marks(self) -> None:
        if self._browser is None:
            return
        try:
            removed = teardown_frames(iter_frames(self._browser))
            if removed:
                logger.info("CDP: marcaje scoase din %d cadre.", removed)
        except Exception as exc:
            logger.warning("CDP: marcajele nu au putut fi scoase: %s", exc)

    def _disconnect(self) -> None:
        # Oprim doar driverul, fără `browser.close()`: browserul și taburile
        # sunt ale utilizatorului, noi închidem numai conexiunea noastră.
        self._browser = None
        self._connected_port = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception as exc:
                logger.debug("CDP: oprirea Playwright a eșuat: %s", exc)
            self._playwright = None

    def _shutdown(self) -> None:
        self._remove_marks()
        self._disconnect()

    def _set_status(self, status: InjectorStatus) -> InjectorStatus:
        with self._lock:
            previous, self._status = self._status, status
        # Jurnalul primește doar schimbările de stare, nu fiecare tic.
        if previous.state != status.state:
            level = logging.INFO if status.ok else logging.WARNING
            logger.log(level, "Injectare CDP: %s", status.describe())
        return status
