"""
FocusPilot — Config Manager
Încarcă, validează și persistă setările globale și regulile de formatare condițională.
"""

import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "config.json"


DEFAULT_SETTINGS = {
    "theme": "dark",                     # "dark" sau "light" (stil Siemens)
    "start_with_windows": False,
    "hide_on_start": True,
    "keep_awake": True,
    "poll_interval_sec": 1.0,            # Rata de verificare a ecranelor
    "sound_alert": False,
    "global_enabled": True
}


DEFAULT_SAMPLE_RULES = [
    {
        "id": "rule_sample_01",
        "name": "Exemplu: Câmpuri Critice Portal Web",
        "enabled": True,
        "trigger": {
            "target_type": "browser_or_window",
            "window_title_pattern": "*Siemens*",
            "url_pattern": "*",
            "process_name": "msedge.exe",
            "text_condition": "contains",
            "search_text": "Obligatoriu",
            "case_sensitive": False,
            "is_regex": False
        },
        "visual_cue": {
            "box_enabled": True,
            "border_color": "#FF1A1A",
            "border_width": 3,
            "fill_color": "#FF3333",
            "fill_opacity": 0.20,
            "arrow_enabled": True,
            "arrow_direction": "right",  # "right", "left", "down", "up"
            "arrow_color": "#FF0000",
            "arrow_size": 36,
            "badge_enabled": True,
            "badge_text": "⚠️ MODIFICĂ / VERIFICĂ ACUM!",
            "badge_bg": "#D90429",
            "badge_fg": "#FFFFFF",
            "pulse_animation": True
        },
        "region": {
            "mode": "window_relative",    # "window_relative", "screen_absolute", "entire_window"
            "rel_x": 0.20,
            "rel_y": 0.30,
            "width": 350,
            "height": 60,
            "monitor_index": -1          # -1 = oricare din cele 3 monitoare
        }
    },
    {
        "id": "rule_sample_02",
        "name": "Exemplu: Atenționare Text Critic (Generic)",
        "enabled": True,
        "trigger": {
            "target_type": "any_window",
            "window_title_pattern": "*",
            "url_pattern": "",
            "process_name": "",
            "text_condition": "contains",
            "search_text": "CONFIDENTIAL",
            "case_sensitive": False,
            "is_regex": False
        },
        "visual_cue": {
            "box_enabled": True,
            "border_color": "#EB780A",
            "border_width": 4,
            "fill_color": "#FFA500",
            "fill_opacity": 0.15,
            "arrow_enabled": True,
            "arrow_direction": "down",
            "arrow_color": "#EB780A",
            "arrow_size": 32,
            "badge_enabled": True,
            "badge_text": "🔒 SECTIUNE CRITICA",
            "badge_bg": "#EB780A",
            "badge_fg": "#FFFFFF",
            "pulse_animation": True
        },
        "region": {
            "mode": "entire_window",
            "rel_x": 0.05,
            "rel_y": 0.05,
            "width": 400,
            "height": 70,
            "monitor_index": -1
        }
    }
]


class ConfigManager:
    """Manager thread-safe pentru salvarea și încărcarea configurației FocusPilot."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.base_dir = base_dir
        self.config_path = os.path.join(self.base_dir, CONFIG_FILENAME)
        self._lock = Lock()
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Încarcă configurația din disc sau creează configurația implicită dacă lipsește."""
        with self._lock:
            if not os.path.exists(self.config_path):
                self._data = {
                    "settings": dict(DEFAULT_SETTINGS),
                    "rules": list(DEFAULT_SAMPLE_RULES)
                }
                self._save_unlocked()
                return self._data

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as exc:
                logger.error(f"Eroare la citirea {self.config_path}: {exc}. Creez default.")
                self._data = {
                    "settings": dict(DEFAULT_SETTINGS),
                    "rules": list(DEFAULT_SAMPLE_RULES)
                }
                self._save_unlocked()
                return self._data

            # Asigurăm completitudinea setărilor
            if "settings" not in self._data:
                self._data["settings"] = dict(DEFAULT_SETTINGS)
            else:
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in self._data["settings"]:
                        self._data["settings"][k] = v

            if "rules" not in self._data:
                self._data["rules"] = list(DEFAULT_SAMPLE_RULES)

            return self._data

    def save(self) -> bool:
        """Salvează configurația pe disc în mod thread-safe."""
        with self._lock:
            return self._save_unlocked()

    def _save_unlocked(self) -> bool:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error(f"Eroare la salvarea configurației: {exc}")
            return False

    # ── Getters & Setters Setări Globale ──

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any, auto_save: bool = True) -> None:
        with self._lock:
            if "settings" not in self._data:
                self._data["settings"] = dict(DEFAULT_SETTINGS)
            self._data["settings"][key] = value
            if auto_save:
                self._save_unlocked()

    def get_all_settings(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data.get("settings", {}))

    # ── Reguli ──

    def get_rules(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._data.get("rules", [])]

    def get_rule_by_id(self, rule_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for r in self._data.get("rules", []):
                if r.get("id") == rule_id:
                    return dict(r)
            return None

    def add_rule(self, rule: Dict[str, Any], auto_save: bool = True) -> str:
        """Adaugă o regulă nouă (generează ID dacă nu există)."""
        with self._lock:
            if "id" not in rule or not rule["id"]:
                rule["id"] = f"rule_{uuid.uuid4().hex[:8]}"
            if "rules" not in self._data:
                self._data["rules"] = []
            self._data["rules"].append(rule)
            if auto_save:
                self._save_unlocked()
            return rule["id"]

    def update_rule(self, rule_id: str, updated_fields: Dict[str, Any], auto_save: bool = True) -> bool:
        """Actualizează o regulă existentă pe baza ID-ului."""
        with self._lock:
            for i, r in enumerate(self._data.get("rules", [])):
                if r.get("id") == rule_id:
                    self._data["rules"][i].update(updated_fields)
                    if auto_save:
                        self._save_unlocked()
                    return True
            return False

    def toggle_rule(self, rule_id: str) -> bool:
        """Comută starea enabled/disabled a unei reguli."""
        with self._lock:
            for r in self._data.get("rules", []):
                if r.get("id") == rule_id:
                    r["enabled"] = not r.get("enabled", True)
                    self._save_unlocked()
                    return r["enabled"]
            return False

    def delete_rule(self, rule_id: str, auto_save: bool = True) -> bool:
        """Șterge o regulă după ID."""
        with self._lock:
            rules = self._data.get("rules", [])
            initial_len = len(rules)
            self._data["rules"] = [r for r in rules if r.get("id") != rule_id]
            deleted = len(self._data["rules"]) < initial_len
            if deleted and auto_save:
                self._save_unlocked()
            return deleted

    def move_rule_up(self, rule_id: str, auto_save: bool = True) -> bool:
        """Mută o regulă cu o poziție mai sus în ordinea de execuție."""
        with self._lock:
            rules = self._data.get("rules", [])
            for i, r in enumerate(rules):
                if r.get("id") == rule_id and i > 0:
                    rules[i], rules[i - 1] = rules[i - 1], rules[i]
                    if auto_save:
                        self._save_unlocked()
                    return True
            return False

    def move_rule_down(self, rule_id: str, auto_save: bool = True) -> bool:
        """Mută o regulă cu o poziție mai jos în ordinea de execuție."""
        with self._lock:
            rules = self._data.get("rules", [])
            for i, r in enumerate(rules):
                if r.get("id") == rule_id and i < len(rules) - 1:
                    rules[i], rules[i + 1] = rules[i + 1], rules[i]
                    if auto_save:
                        self._save_unlocked()
                    return True
            return False
