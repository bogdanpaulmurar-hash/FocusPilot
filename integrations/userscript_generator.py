"""
FocusPilot — Userscript Generator for Browser Conditional Formatting
Generează un script Tampermonkey / Violentmonkey (.user.js) din regulile active.
Permite formatarea condițională nativă DIRECT în orice browser (Edge, Chrome, Firefox),
marcând cu roșu, adăugând săgeți animate și stilizând câmpurile identificate conform regulilor.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional

from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


def generate_userscript(config_manager: ConfigManager, output_path: Optional[str] = None) -> str:
    """Generează conținutul scriptului de browser și îl salvează pe disc."""
    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, "integrations", "focuspilot_browser_highlighter.user.js")

    rules = config_manager.get_rules()
    active_rules = [r for r in rules if r.get("enabled", True)]

    rules_json = json.dumps(active_rules, indent=2, ensure_ascii=False)

    userscript_content = f"""// ==UserScript==
// @name         FocusPilot Browser Highlighter & Visual Cues
// @namespace    https://github.com/bogdanpaulmurar-hash/FocusPilot
// @version      1.0
// @description  Formatare condițională automată (chenar roșu, săgeată animată, badge-uri) conform regulilor FocusPilot
// @author       Bogdan Murar
// @match        *://*/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {{
    'use strict';

    const RULES = {rules_json};

    function applyVisualCues() {{
        RULES.forEach(rule => {{
            if (!rule.enabled) return;

            const trigger = rule.trigger || {{}};
            const searchText = (trigger.search_text || '').trim();
            if (!searchText) return;

            const cue = rule.visual_cue || {{}};
            const borderColor = cue.border_color || '#FF0000';
            const borderWidth = cue.border_width || 3;
            const arrowEnabled = cue.arrow_enabled !== false;
            const badgeEnabled = cue.badge_enabled !== false;
            const badgeText = cue.badge_text || '⚠️ MODIFICĂ AICI!';

            // Căutare elemente care conțin textul (suport text adânc, noduri imbricate și atribute title)
            const xpath = `//*[contains(., '${{searchText}}')] | //*[contains(@title, '${{searchText}}')] | //input[contains(@value, '${{searchText}}')] | //textarea[contains(., '${{searchText}}')]`;
            const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);

            for (let i = 0; i < result.snapshotLength; i++) {{
                const el = result.snapshotItem(i);
                if (el.dataset.focuspilotApplied) continue;
                el.dataset.focuspilotApplied = 'true';

                // 1. Formatare chenar roșu & fundal
                el.style.setProperty('outline', `${{borderWidth}}px solid ${{borderColor}}`, 'important');
                el.style.setProperty('outline-offset', '2px', 'important');
                el.style.setProperty('background-color', 'rgba(255, 0, 0, 0.15)', 'important');
                el.style.setProperty('transition', 'all 0.3s ease', 'important');

                // 2. Săgeată roșie indicatoare
                if (arrowEnabled) {{
                    const arrow = document.createElement('span');
                    arrow.className = 'focuspilot-arrow';
                    arrow.innerText = '➔ ⚠️ ';
                    arrow.style.cssText = `
                        color: ${{borderColor}};
                        font-size: 18px;
                        font-weight: bold;
                        margin-right: 6px;
                        display: inline-block;
                        animation: focuspilot-pulse 0.8s infinite alternate ease-in-out;
                    `;
                    el.parentNode.insertBefore(arrow, el);
                }}

                // 3. Badge avertizare deasupra
                if (badgeEnabled) {{
                    const badge = document.createElement('div');
                    badge.className = 'focuspilot-badge';
                    badge.innerText = badgeText;
                    badge.style.cssText = `
                        background: #D90429;
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: bold;
                        font-family: 'Segoe UI', sans-serif;
                        padding: 2px 8px;
                        border-radius: 4px;
                        display: inline-block;
                        margin-bottom: 4px;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                    `;
                    el.parentNode.insertBefore(badge, el);
                }}
            }}
        }});
    }}

    // Injectăm animația CSS de pulsare
    const style = document.createElement('style');
    style.innerHTML = `
        @keyframes focuspilot-pulse {{
            0% {{ transform: translateX(0); opacity: 0.8; }}
            100% {{ transform: translateX(6px); opacity: 1; }}
        }}
    `;
    document.head.appendChild(style);

    // Rulăm la încărcare și la mutații DOM dinamice (SPA / React)
    applyVisualCues();
    const observer = new MutationObserver(() => applyVisualCues());
    observer.observe(document.body, {{ childList: true, subtree: true }});
}})();
"""

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(userscript_content)
        logger.info(f"Userscript generat cu succes la {output_path}")
    except Exception as exc:
        logger.error(f"Eroare scriere Userscript: {exc}")

    return userscript_content
