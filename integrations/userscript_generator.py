"""
FocusPilot — Generator de Userscript pentru formatare condițională în browser

Produce un script Tampermonkey / Violentmonkey care aplică regulile direct în
DOM. Chenarul se atașează de elementul HTML, deci rămâne lipit de text când
utilizatorul derulează pagina — lucru pe care un overlay desktop nu poate face.

Trei defecte ale variantei anterioare sunt remediate aici:

1. XPATH SPART DE APOSTROFURI. Textul căutat era interpolat într-un literal
   XPath delimitat cu apostrof. O regulă ca
       Changed from 'Merge' to 'Wait for Merge'
   producea un XPath invalid, `document.evaluate` arunca excepție și scriptul
   se oprea complet. Acum căutarea se face cu un TreeWalker peste nodurile de
   text, deci nu există niciun literal de escapat.

2. TOATĂ PAGINA ÎNCADRATĂ. `//*[contains(., 'text')]` se potrivește și pe
   `<html>` și `<body>`, pentru că funcția `contains(.)` ia în calcul tot
   textul descendent. Scriptul încadra întregul document. Acum se marchează
   doar elementul cel mai adânc care conține efectiv textul.

3. BUCLĂ INFINITĂ DE MUTAȚII. Observatorul reacționa la mutații, iar funcția
   apelată insera la rândul ei elemente în DOM, declanșând noi mutații la
   infinit și blocând pagina. Acum observatorul este deconectat în timpul
   modificărilor și reactivat după, cu o temporizare.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

USERSCRIPT_TEMPLATE = r"""// ==UserScript==
// @name         FocusPilot Browser Highlighter & Visual Cues
// @namespace    https://github.com/bogdanpaulmurar-hash/FocusPilot
// @version      2.0
// @description  Formatare condițională (chenar, săgeată, badge) conform regulilor FocusPilot
// @author       Bogdan Murar
// @match        *://*/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

/* Generat automat de FocusPilot. Modificările manuale se pierd la
   următoarea salvare a unei reguli din aplicație. */

(function () {
    'use strict';

    const RULES = __RULES_JSON__;
    const MARK = 'focuspilotMarked';
    const DEBOUNCE_MS = 250;

    if (!RULES.length) { return; }

    // ── Potrivirea paginii curente ──────────────────────────────────────────

    function wildcardToRegExp(pattern) {
        // Escapăm tot ce e special în regex, apoi reactivăm * și ? ca wildcard.
        const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return new RegExp('^' + escaped.replace(/\\\*/g, '.*').replace(/\\\?/g, '.') + '$', 'i');
    }

    function patternMatches(pattern, value) {
        if (!pattern || pattern === '*') { return true; }
        if (!value) { return false; }
        // Alternative separate prin '|', ca în aplicația desktop.
        return pattern.split('|').some(function (raw) {
            const part = raw.trim();
            if (!part) { return false; }
            if (part.indexOf('*') === -1 && part.indexOf('?') === -1) {
                return value.toLowerCase().indexOf(part.toLowerCase()) !== -1;
            }
            return wildcardToRegExp(part).test(value);
        });
    }

    function ruleAppliesToThisPage(rule) {
        const trigger = rule.trigger || {};
        if (!patternMatches(trigger.url_pattern, location.href)) { return false; }
        if (!patternMatches(trigger.window_title_pattern, document.title)) { return false; }
        return true;
    }

    // ── Potrivirea textului, cu aceleași condiții ca în aplicație ───────────

    function textMatches(needle, haystack, condition, caseSensitive, isRegex) {
        if (!needle) { return false; }
        if (isRegex || condition === 'regex') {
            try {
                return new RegExp(needle, caseSensitive ? '' : 'i').test(haystack);
            } catch (e) { return false; }
        }
        const probe = caseSensitive ? needle : needle.toLowerCase();
        const hay = caseSensitive ? haystack : haystack.toLowerCase();
        if (condition === 'equals') { return hay.trim() === probe.trim(); }
        if (condition === 'starts_with') { return hay.trim().indexOf(probe.trim()) === 0; }
        if (condition === 'constellation') {
            const words = probe.split(/[;|]/).map(function (w) { return w.trim(); })
                               .filter(Boolean);
            return words.length > 0 && words.every(function (w) {
                return hay.indexOf(w) !== -1;
            });
        }
        return hay.indexOf(probe) !== -1;   // "contains"
    }

    function criteriaOf(trigger) {
        const out = [];
        if (trigger.search_text && String(trigger.search_text).trim()) {
            out.push(String(trigger.search_text).trim());
        }
        const extra = trigger.additional_criteria;
        if (Array.isArray(extra)) {
            extra.forEach(function (c) {
                if (c && String(c).trim()) { out.push(String(c).trim()); }
            });
        } else if (typeof extra === 'string' && extra.trim()) {
            extra.split(/[\n\r;|]+/).forEach(function (c) {
                if (c.trim()) { out.push(c.trim()); }
            });
        }
        return out;
    }

    // ── Găsirea celui mai adânc element care conține textul ─────────────────

    function findDeepestMatches(needle, condition, caseSensitive, isRegex) {
        // TreeWalker peste noduri de text: nu există literal de escapat, deci
        // apostrofurile și ghilimelele din text nu pot strica nimic.
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_TEXT, {
                acceptNode: function (node) {
                    if (!node.nodeValue || !node.nodeValue.trim()) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    const tag = node.parentElement && node.parentElement.tagName;
                    if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        const found = [];
        let node;
        while ((node = walker.nextNode())) {
            if (textMatches(needle, node.nodeValue, condition, caseSensitive, isRegex)) {
                // Părintele nodului de text este elementul cel mai apropiat
                // care conține efectiv textul — nu <body> sau <html>.
                const el = node.parentElement;
                if (el && found.indexOf(el) === -1) { found.push(el); }
            }
        }

        // Câmpurile de formular țin textul în value, nu în noduri de text.
        document.querySelectorAll('input, textarea').forEach(function (field) {
            if (textMatches(needle, field.value || '', condition, caseSensitive, isRegex)) {
                if (found.indexOf(field) === -1) { found.push(field); }
            }
        });
        return found;
    }

    // ── Aplicarea reperelor vizuale ─────────────────────────────────────────

    const ARROW_GLYPH = { right: '➔', left: '⬅', down: '⬇', up: '⬆' };

    function decorate(el, rule) {
        if (el.dataset && el.dataset[MARK] === rule.id) { return; }
        const cue = rule.visual_cue || {};

        if (cue.box_enabled !== false) {
            const width = cue.border_width || 3;
            const color = cue.border_color || '#FF0000';
            el.style.setProperty('outline', width + 'px solid ' + color, 'important');
            el.style.setProperty('outline-offset', '2px', 'important');
            if (cue.fill_color) {
                // Respectă culoarea și opacitatea configurate, în loc de un
                // roșu fix cum era înainte.
                el.style.setProperty('background-color',
                    hexToRgba(cue.fill_color, cue.fill_opacity), 'important');
            }
            if (cue.pulse_animation !== false) {
                el.style.setProperty('animation',
                    'focuspilot-glow 1.1s infinite alternate ease-in-out', 'important');
            }
        }

        const holder = el.parentNode;
        if (!holder || el === document.body || el === document.documentElement) {
            if (el.dataset) { el.dataset[MARK] = rule.id; }
            return;
        }

        if (cue.badge_enabled !== false && cue.badge_text) {
            const badge = document.createElement('span');
            badge.className = 'focuspilot-tag';
            badge.dataset.focuspilotRule = rule.id;
            badge.textContent = cue.badge_text;
            badge.style.cssText =
                'background:' + (cue.badge_bg || '#D90429') + ';' +
                'color:' + (cue.badge_fg || '#FFFFFF') + ';' +
                'font:bold 11px "Segoe UI",sans-serif;padding:2px 8px;border-radius:4px;' +
                'margin-right:6px;display:inline-block;vertical-align:middle;' +
                'box-shadow:0 2px 6px rgba(0,0,0,.3);';
            holder.insertBefore(badge, el);
        }

        if (cue.arrow_enabled !== false) {
            const arrow = document.createElement('span');
            arrow.className = 'focuspilot-tag';
            arrow.dataset.focuspilotRule = rule.id;
            // Glifa urmează direcția configurată, nu una fixă.
            arrow.textContent = ARROW_GLYPH[cue.arrow_direction] || ARROW_GLYPH.right;
            arrow.style.cssText =
                'color:' + (cue.arrow_color || '#FF0000') + ';' +
                'font-size:' + Math.max(14, cue.arrow_size || 20) + 'px;font-weight:bold;' +
                'margin-right:4px;display:inline-block;vertical-align:middle;' +
                'animation:focuspilot-nudge .9s infinite alternate ease-in-out;';
            holder.insertBefore(arrow, el);
        }

        if (el.dataset) { el.dataset[MARK] = rule.id; }
    }

    function hexToRgba(hex, opacity) {
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(String(hex).trim());
        const alpha = (opacity === undefined || opacity === null) ? 0.18 : Number(opacity);
        if (!m) { return 'rgba(255,0,0,' + alpha + ')'; }
        return 'rgba(' + parseInt(m[1], 16) + ',' + parseInt(m[2], 16) + ',' +
               parseInt(m[3], 16) + ',' + alpha + ')';
    }

    function clearRule(ruleId) {
        document.querySelectorAll('[data-focuspilot-rule="' + ruleId + '"]')
            .forEach(function (n) { n.remove(); });
        document.querySelectorAll('[data-' + 'focuspilot-marked' + ']')
            .forEach(function (el) {
                if (el.dataset[MARK] !== ruleId) { return; }
                el.style.removeProperty('outline');
                el.style.removeProperty('outline-offset');
                el.style.removeProperty('background-color');
                el.style.removeProperty('animation');
                delete el.dataset[MARK];
            });
    }

    // ── Ciclul principal ────────────────────────────────────────────────────

    let observer = null;
    let pending = null;

    function apply() {
        RULES.forEach(function (rule) {
            if (rule.enabled === false) { clearRule(rule.id); return; }
            if (!ruleAppliesToThisPage(rule)) { clearRule(rule.id); return; }

            const trigger = rule.trigger || {};
            const criteria = criteriaOf(trigger);
            if (!criteria.length) { return; }

            const condition = trigger.text_condition || 'contains';
            const caseSensitive = !!trigger.case_sensitive;
            const isRegex = !!trigger.is_regex;
            const logic = (trigger.criteria_logic || 'OR').toUpperCase();

            const perCriterion = criteria.map(function (c) {
                return findDeepestMatches(c, condition, caseSensitive, isRegex);
            });

            // Cu logica AND fiecare criteriu trebuie să existe în pagină.
            if (logic === 'AND' && perCriterion.some(function (list) {
                return list.length === 0;
            })) {
                clearRule(rule.id);
                return;
            }

            const targets = [];
            perCriterion.forEach(function (list) {
                list.forEach(function (el) {
                    if (targets.indexOf(el) === -1) { targets.push(el); }
                });
            });
            targets.forEach(function (el) { decorate(el, rule); });
        });
    }

    function run() {
        // Deconectăm observatorul cât timp modificăm DOM-ul, altfel propriile
        // noastre inserări declanșează o buclă infinită de mutații.
        if (observer) { observer.disconnect(); }
        try {
            apply();
        } catch (e) {
            console.warn('[FocusPilot] eroare la aplicarea regulilor:', e);
        } finally {
            if (observer) {
                observer.observe(document.body, { childList: true, subtree: true,
                                                  characterData: true });
            }
        }
    }

    function scheduleRun() {
        if (pending) { clearTimeout(pending); }
        pending = setTimeout(function () { pending = null; run(); }, DEBOUNCE_MS);
    }

    const style = document.createElement('style');
    style.textContent =
        '@keyframes focuspilot-nudge{0%{transform:translateX(0);opacity:.75}' +
        '100%{transform:translateX(5px);opacity:1}}' +
        '@keyframes focuspilot-glow{0%{outline-color:currentColor;opacity:.92}' +
        '100%{opacity:1}}';
    (document.head || document.documentElement).appendChild(style);

    observer = new MutationObserver(scheduleRun);
    run();

    // Aplicațiile de tip SPA schimbă adresa fără reîncărcare: reevaluăm.
    ['pushState', 'replaceState'].forEach(function (name) {
        const original = history[name];
        history[name] = function () {
            const out = original.apply(this, arguments);
            scheduleRun();
            return out;
        };
    });
    window.addEventListener('popstate', scheduleRun);
})();
"""


def generate_userscript(config_manager: ConfigManager,
                        output_path: Optional[str] = None) -> str:
    """Scrie scriptul de browser cu regulile active și întoarce conținutul."""
    if output_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(base_dir, "integrations",
                                   "focuspilot_browser_highlighter.user.js")

    active: List[Dict[str, Any]] = [
        _slim(rule) for rule in config_manager.get_rules()
        if rule.get("enabled", True)
    ]

    # json.dumps produce un literal JavaScript valid indiferent de ghilimelele,
    # apostrofurile sau diacriticele din textul regulilor.
    rules_json = json.dumps(active, indent=2, ensure_ascii=False)
    content = USERSCRIPT_TEMPLATE.replace("__RULES_JSON__", rules_json)

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        logger.info("Userscript generat (%d reguli active): %s", len(active), output_path)
    except Exception as exc:
        logger.error("Scrierea userscript-ului a eșuat: %s", exc)

    return content


def _slim(rule: Dict[str, Any]) -> Dict[str, Any]:
    """
    Păstrează doar câmpurile de care are nevoie browserul.

    Coordonatele de ecran și calea șablonului imagine nu au sens în DOM și nu
    trebuie să ajungă într-un fișier pe care utilizatorul îl instalează în
    browser.
    """
    return {
        "id": rule.get("id", ""),
        "name": rule.get("name", ""),
        "enabled": rule.get("enabled", True),
        "trigger": {
            key: rule.get("trigger", {}).get(key)
            for key in ("window_title_pattern", "url_pattern", "search_text",
                        "additional_criteria", "criteria_logic", "text_condition",
                        "case_sensitive", "is_regex")
        },
        "visual_cue": {
            key: rule.get("visual_cue", {}).get(key)
            for key in ("box_enabled", "border_color", "border_width",
                        "fill_color", "fill_opacity", "arrow_enabled",
                        "arrow_direction", "arrow_color", "arrow_size",
                        "badge_enabled", "badge_text", "badge_bg", "badge_fg",
                        "pulse_animation")
        },
    }
