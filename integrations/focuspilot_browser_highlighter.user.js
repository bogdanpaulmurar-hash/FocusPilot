// ==UserScript==
// @name         FocusPilot Browser Highlighter & Visual Cues
// @namespace    https://github.com/bogdanpaulmurar-hash/FocusPilot
// @version      1.0
// @description  Formatare condițională automată (chenar roșu, săgeată animată, badge-uri) conform regulilor FocusPilot
// @author       Bogdan Murar
// @match        *://*/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    const RULES = [
  {
    "id": "rule_6b16e036",
    "name": "ticket classification TIMA",
    "enabled": true,
    "trigger": {
      "target_type": "browser_or_window",
      "window_title_pattern": "*FocusPilot_Picker*",
      "url_pattern": "*https://tima.siemens.com/otwg20/#/main\"",
      "process_name": "chrome.exe",
      "text_condition": "contains",
      "search_text": "Please change category",
      "case_sensitive": false,
      "is_regex": false
    },
    "visual_cue": {
      "box_enabled": true,
      "border_color": "#FF0000",
      "border_width": 4,
      "fill_color": "#FF3333",
      "fill_opacity": 0.2,
      "arrow_enabled": true,
      "arrow_direction": "up",
      "arrow_color": "#FF0000",
      "arrow_size": 36,
      "badge_enabled": true,
      "badge_text": "🚨 SCHIMBĂ CATEGORIA TIMA!",
      "badge_bg": "#D90429",
      "badge_fg": "#FFFFFF",
      "pulse_animation": true
    },
    "region": {
      "mode": "window_relative",
      "rel_x": 0.286,
      "rel_y": 0.725,
      "width": 316,
      "height": 44,
      "monitor_index": -1
    }
  },
  {
    "id": "rule_059e8be7",
    "name": "Regulă Nouă de Atenționare",
    "enabled": true,
    "trigger": {
      "target_type": "browser_or_window",
      "window_title_pattern": "*FocusPilot_Picker*",
      "url_pattern": "*",
      "process_name": "msedge.exe",
      "text_condition": "contains",
      "search_text": "Please change category",
      "case_sensitive": false,
      "is_regex": false
    },
    "visual_cue": {
      "box_enabled": true,
      "border_color": "#FF0000",
      "border_width": 3,
      "fill_color": "#FF3333",
      "fill_opacity": 0.2,
      "arrow_enabled": true,
      "arrow_direction": "right",
      "arrow_color": "#FF0000",
      "arrow_size": 36,
      "badge_enabled": true,
      "badge_text": "⚠️ MODIFICĂ AICI!",
      "badge_bg": "#D90429",
      "badge_fg": "#FFFFFF",
      "pulse_animation": true
    },
    "region": {
      "mode": "window_relative",
      "rel_x": 0.281,
      "rel_y": 0.715,
      "width": 344,
      "height": 59,
      "monitor_index": -1
    }
  }
];

    function applyVisualCues() {
        RULES.forEach(rule => {
            if (!rule.enabled) return;

            const trigger = rule.trigger || {};
            const searchText = (trigger.search_text || '').trim();
            if (!searchText) return;

            const cue = rule.visual_cue || {};
            const borderColor = cue.border_color || '#FF0000';
            const borderWidth = cue.border_width || 3;
            const arrowEnabled = cue.arrow_enabled !== false;
            const badgeEnabled = cue.badge_enabled !== false;
            const badgeText = cue.badge_text || '⚠️ MODIFICĂ AICI!';

            // Căutare elemente care conțin textul
            const xpath = `//*[contains(text(), '${searchText}')] | //input[contains(@value, '${searchText}')] | //textarea[contains(text(), '${searchText}')]`;
            const result = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);

            for (let i = 0; i < result.snapshotLength; i++) {
                const el = result.snapshotItem(i);
                if (el.dataset.focuspilotApplied) continue;
                el.dataset.focuspilotApplied = 'true';

                // 1. Formatare chenar roșu & fundal
                el.style.setProperty('outline', `${borderWidth}px solid ${borderColor}`, 'important');
                el.style.setProperty('outline-offset', '2px', 'important');
                el.style.setProperty('background-color', 'rgba(255, 0, 0, 0.15)', 'important');
                el.style.setProperty('transition', 'all 0.3s ease', 'important');

                // 2. Săgeată roșie indicatoare
                if (arrowEnabled) {
                    const arrow = document.createElement('span');
                    arrow.className = 'focuspilot-arrow';
                    arrow.innerText = '➔ ⚠️ ';
                    arrow.style.cssText = `
                        color: ${borderColor};
                        font-size: 18px;
                        font-weight: bold;
                        margin-right: 6px;
                        display: inline-block;
                        animation: focuspilot-pulse 0.8s infinite alternate ease-in-out;
                    `;
                    el.parentNode.insertBefore(arrow, el);
                }

                // 3. Badge avertizare deasupra
                if (badgeEnabled) {
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
                }
            }
        });
    }

    // Injectăm animația CSS de pulsare
    const style = document.createElement('style');
    style.innerHTML = `
        @keyframes focuspilot-pulse {
            0% { transform: translateX(0); opacity: 0.8; }
            100% { transform: translateX(6px); opacity: 1; }
        }
    `;
    document.head.appendChild(style);

    // Rulăm la încărcare și la mutații DOM dinamice (SPA / React)
    applyVisualCues();
    const observer = new MutationObserver(() => applyVisualCues());
    observer.observe(document.body, { childList: true, subtree: true });
})();
