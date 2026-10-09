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

    async def _apply_rules_to_page(self, page, rules: List[Dict[str, Any]]) -> None:
        """Injectează scriptul de evidențiere într-o pagină web deschisă."""
        for rule in rules:
            if not rule.get("enabled", True):
                continue

            trigger = rule.get("trigger", {})
            search_text = trigger.get("search_text", "").strip()
            if not search_text:
                continue

            cue = rule.get("visual_cue", {})
            border_color = cue.get("border_color", "#FF0000")
            border_width = cue.get("border_width", 3)
            badge_text = cue.get("badge_text", "⚠️ MODIFICĂ AICI!")

            js_code = f"""
            (() => {{
                const xpath = "//*[contains(text(), '{search_text}')]";
                const res = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                for (let i = 0; i < res.snapshotLength; i++) {{
                    const el = res.snapshotItem(i);
                    el.style.border = "{border_width}px solid {border_color}";
                    el.style.backgroundColor = "rgba(255, 0, 0, 0.15)";
                }}
            }})();
            """
            try:
                await page.evaluate(js_code)
            except Exception as e:
                logger.debug(f"Eroare injectare JS în pagină: {e}")

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
