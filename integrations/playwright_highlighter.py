"""
FocusPilot — Playwright Browser Highlighter & Automation
Permite injectarea directă a regulilor de formatare condițională (chenare roșii, săgeți animate,
badge-uri) în instanțe de browser conectate prin CDP (Chrome DevTools Protocol) sau Chromium.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PlaywrightBrowserHighlighter:
    """Interfață de automatizare pentru evidențiere vizuală în browser prin Playwright."""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self._browser = None
        self._playwright = None

    async def connect_and_highlight(self, rules: List[Dict[str, Any]]) -> bool:
        """Conectează Playwright la instanța existentă de browser (Edge / Chrome) și aplică regulile."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self.cdp_url)

            contexts = self._browser.contexts
            if not contexts:
                logger.warning("Niciun context de browser găsit prin CDP.")
                return False

            for ctx in contexts:
                for page in ctx.pages:
                    await self._apply_rules_to_page(page, rules)

            return True
        except Exception as exc:
            logger.info(f"CDP Browser nu este conectat pe {self.cdp_url} ({exc}). Se folosește Overlay HUD pe ecran.")
            return False

    # Primește (text_căutat, culoare, grosime) ca argumente, deci textul nu
    # este niciodată interpolat în cod. Varianta anterioară construia un literal
    # XPath cu apostrof, iar un text ca `Changed from 'Merge'` producea o
    # expresie invalidă și injectarea eșua.
    _HIGHLIGHT_JS = """
    ({ needle, color, width, fill }) => {
        // TreeWalker peste nodurile de text: fără literal XPath de escapat și
        // fără potrivire pe <html> / <body>, care ar încadra toată pagina.
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_TEXT, {
                acceptNode(node) {
                    const tag = node.parentElement && node.parentElement.tagName;
                    if (!node.nodeValue || !node.nodeValue.trim()) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );
        const probe = needle.toLowerCase();
        let node, count = 0;
        while ((node = walker.nextNode())) {
            if (node.nodeValue.toLowerCase().indexOf(probe) === -1) { continue; }
            const el = node.parentElement;
            if (!el) { continue; }
            el.style.setProperty('outline', width + 'px solid ' + color, 'important');
            el.style.setProperty('outline-offset', '2px', 'important');
            el.style.setProperty('background-color', fill, 'important');
            count++;
        }
        return count;
    }
    """

    async def _apply_rules_to_page(self, page, rules: List[Dict[str, Any]]) -> None:
        """Injectează evidențierea într-o pagină web deschisă."""
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            search_text = str(rule.get("trigger", {}).get("search_text", "") or "").strip()
            if not search_text:
                continue

            cue = rule.get("visual_cue", {})
            try:
                hit_count = await page.evaluate(self._HIGHLIGHT_JS, {
                    "needle": search_text,
                    "color": cue.get("border_color", "#FF0000"),
                    "width": cue.get("border_width", 3),
                    "fill": self._fill_css(cue),
                })
                if hit_count:
                    logger.info("Regula '%s': %d element(e) evidențiate în pagină.",
                                rule.get("name"), hit_count)
            except Exception as exc:
                logger.debug("Injectarea JS în pagină a eșuat: %s", exc)

    @staticmethod
    def _fill_css(cue: Dict[str, Any]) -> str:
        """Culoarea de fundal configurată, ca `rgba(...)`."""
        import re
        match = re.match(r"^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$",
                         str(cue.get("fill_color", "") or "").strip(), re.IGNORECASE)
        try:
            alpha = float(cue.get("fill_opacity", 0.18))
        except (TypeError, ValueError):
            alpha = 0.18
        if not match:
            return f"rgba(255,0,0,{alpha})"
        r, g, b = (int(part, 16) for part in match.groups())
        return f"rgba({r},{g},{b},{alpha})"

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
