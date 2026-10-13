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
    "id": "rule_sample_02",
    "name": "Exemplu: Atenționare Text Critic (Generic)",
    "enabled": true,
    "trigger": {
      "target_type": "any_window",
      "window_title_pattern": "*GSP*",
      "url_pattern": "*",
      "process_name": "browser",
      "text_condition": "contains",
      "search_text": "Changed from 'Merge' to 'Wait for Merge'",
      "case_sensitive": false,
      "is_regex": false,
      "additional_criteria": [],
      "criteria_logic": "OR"
    },
    "visual_cue": {
      "box_enabled": true,
      "border_color": "#EB780A",
      "border_width": 2,
      "fill_color": "#FFA500",
      "fill_opacity": 0.15,
      "arrow_enabled": true,
      "arrow_direction": "left",
      "arrow_color": "#00ff40",
      "arrow_style": "triangle",
      "arrow_width": 14,
      "arrow_size": 22,
      "badge_enabled": true,
      "badge_text": "TimeStamp",
      "badge_bg": "#EB780A",
      "badge_fg": "#FFFFFF",
      "pulse_animation": true,
      "duration_sec": 3,
      "box_scope": "custom_region"
    },
    "region": {
      "mode": "visual_track",
      "rel_x": 0.151,
      "rel_y": 0.786,
      "width": 763,
      "height": 35,
      "monitor_index": -1,
      "abs_x": 284,
      "abs_y": 816,
      "template_image": "assets/rules/snip_1791808212611.png"
    },
    "steps": []
  },
  {
    "id": "rule_6b16e036",
    "name": "ticket classification TIMA",
    "enabled": true,
    "trigger": {
      "target_type": "browser_or_window",
      "window_title_pattern": "*TIMA*",
      "url_pattern": "*https://tima.siemens.com/otwg20/#/main*",
      "process_name": "browser",
      "text_condition": "contains",
      "search_text": "Please change category",
      "case_sensitive": false,
      "is_regex": false
    },
    "visual_cue": {
      "box_enabled": true,
      "border_color": "#008080",
      "border_width": 2,
      "fill_color": "#FF3333",
      "fill_opacity": 0.2,
      "arrow_enabled": true,
      "arrow_direction": "left",
      "arrow_color": "#ff0000",
      "arrow_size": 36,
      "badge_enabled": true,
      "badge_text": "🚨 SCHIMBĂ CATEGORIA!",
      "badge_bg": "#D90429",
      "badge_fg": "#FFFFFF",
      "pulse_animation": true,
      "duration_sec": 0,
      "box_scope": "exact_text"
    },
    "region": {
      "mode": "visual_track",
      "template_image": "assets/rules/snip_tima.png",
      "rel_x": 0.284,
      "rel_y": 0.737,
      "width": 310,
      "height": 30,
      "monitor_index": -1,
      "abs_x": 554,
      "abs_y": 751
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

            // Căutare elemente care conțin textul (suport text adânc, noduri imbricate și atribute title)
            const xpath = `//*[contains(., '${searchText}')] | //*[contains(@title, '${searchText}')] | //input[contains(@value, '${searchText}')] | //textarea[contains(., '${searchText}')]`;
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
