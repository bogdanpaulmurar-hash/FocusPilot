"""
FocusPilot — Excel-Style Conditional Formatting Rule Editor Dialog
Dialog complet de configurare cu Live Preview, selecție culori Siemens,
configurare declanșator text și săgeți/chenare vizuale.
"""

import copy
import logging
import re
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from typing import Dict, Any, List, Optional, Callable

from core import probe_engine
from core.rule_engine import RuleEngine

from ui.theme import get_theme, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL
from ui.interactive_picker import InteractivePicker
from ui.condition_builder import ConditionBuilderPanel

logger = logging.getLogger(__name__)


class RuleEditorDialog:
    """Dialog modal pentru creare sau editare de regulă de formatare condițională."""

    def __init__(self, parent: tk.Toplevel, theme_name: str, rule: Optional[Dict[str, Any]], on_save: Callable[[Dict[str, Any]], None], on_test_cue: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.parent = parent
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.on_save = on_save
        self.on_test_cue = on_test_cue

        self.is_new = (rule is None)
        self.rule: Dict[str, Any] = copy.deepcopy(rule) if rule else self._get_default_rule()
        self.steps: List[Dict[str, Any]] = copy.deepcopy(self.rule.get("steps", []))

        self.dialog: Optional[tk.Toplevel] = None
        self.preview_canvas: Optional[tk.Canvas] = None
        self.criteria_entries: List[tk.Entry] = []
        self.criteria_rows: List[tk.Frame] = []

        self._build_ui()

    @staticmethod
    def _as_int(value: Any, default: int) -> int:
        """Conversie tolerantă: o valoare lipsă sau invalidă nu blochează dialogul."""
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @classmethod
    def _spin_value(cls, var: tk.Variable, default: int) -> int:
        """Citește un Spinbox fără a arunca excepție la text invalid."""
        try:
            return cls._as_int(var.get(), default)
        except tk.TclError:
            return default

    def _get_default_rule(self) -> Dict[str, Any]:
        return {
            "id": "",
            "name": "Regulă Nouă de Atenționare",
            "enabled": True,
            "trigger": {
                "target_type": "browser_or_window",
                "window_title_pattern": "*",
                "url_pattern": "*",
                "process_name": "browser",
                "text_condition": "contains",
                "search_text": "",
                "additional_criteria": "",
                "criteria_logic": "OR",
                "case_sensitive": False,
                "is_regex": False
            },
            "visual_cue": {
                "box_enabled": True,
                "box_scope": "custom_region",
                "border_color": "#FF0000",
                "border_width": 3,
                "fill_color": "#FF3333",
                "fill_opacity": 0.20,
                "arrow_enabled": True,
                "arrow_direction": "right",
                "arrow_color": "#FF0000",
                "arrow_style": "slim",     # Subțire & elegantă
                "arrow_width": 14,          # Grosime/lățime subțire
                "arrow_size": 22,           # Lungime fină
                "badge_enabled": True,
                "badge_text": "⚠️ MODIFICĂ AICI!",
                "badge_bg": "#D90429",
                "badge_fg": "#FFFFFF",
                "pulse_animation": True,
                "duration_sec": 0
            },
            "region": {
                "mode": "window_relative",
                "rel_x": 0.20,
                "rel_y": 0.30,
                "width": 350,
                "height": 60,
                "monitor_index": -1
            },
            "steps": []
        }

    def _build_ui(self) -> None:
        self.dialog = tk.Toplevel(self.parent)
        title = "➕ Creează Regulă Nouă" if self.is_new else f"✏️ Editează: {self.rule.get('name', 'Regulă')}"
        self.dialog.title(title)
        self.dialog.geometry("720x760")
        self.dialog.minsize(680, 680)
        self.dialog.configure(bg=self.theme["bg_main"])
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Canvas derulabil pentru ecrane cu rezoluție mai mică
        canvas = tk.Canvas(self.dialog, bg=self.theme["bg_main"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.theme["bg_main"])

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Suport pentru scroll cu rotița mouse-ului oriunde în dialogul de editare
        def _on_dialog_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else 1
            canvas.yview_scroll(delta, "units")

        self.dialog.bind("<MouseWheel>", _on_dialog_mousewheel)
        canvas.bind("<MouseWheel>", _on_dialog_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content_pad = 16

        # ── Header ──
        header_frame = tk.Frame(scroll_frame, bg=self.theme["bg_main"])
        header_frame.pack(fill="x", padx=content_pad, pady=(12, 6))

        tk.Label(
            header_frame,
            text="🎯 Configurator Formatare Condițională & Reper Vizual",
            font=FONT_TITLE,
            bg=self.theme["bg_main"],
            fg=self.theme["accent"]
        ).pack(anchor="w")

        tk.Label(
            header_frame,
            text="Definește criteriul de detecție (fereastră, pagină browser, text) și stilul de alertă vizuală pe ecran.",
            font=FONT_SMALL,
            bg=self.theme["bg_main"],
            fg=self.theme["fg_secondary"]
        ).pack(anchor="w", pady=(2, 0))

        # ── Secțiunea 1: Nume & Activare ──
        sec1 = self._create_card(scroll_frame, "1. Informații Generale")
        
        row1 = tk.Frame(sec1, bg=self.theme["bg_card"])
        row1.pack(fill="x", pady=4)
        tk.Label(row1, text="Nume Regulă:", font=FONT_BODY_BOLD, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=14, anchor="w").pack(side="left")
        self.ent_name = tk.Entry(row1, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_name.insert(0, self.rule.get("name", ""))
        self.ent_name.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.var_enabled = tk.BooleanVar(value=self.rule.get("enabled", True))
        chk_enabled = tk.Checkbutton(
            row1, text="Regulă Activă", variable=self.var_enabled,
            font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            selectcolor=self.theme["bg_input"], activebackground=self.theme["bg_card"]
        )
        chk_enabled.pack(side="left", padx=12)

        # ── Secțiunea 2: Declanșator / Condiție (Excel Style) ──
        sec2 = self._create_card(scroll_frame, "2. Declanșator Condițional (Când se afișează alerta)")

        # Titlu Fereastră
        r_win = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_win.pack(fill="x", pady=4)
        tk.Label(r_win, text="Titlu Fereastră / Tab:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")
        self.ent_win_title = tk.Entry(r_win, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_win_title.insert(0, self.rule.get("trigger", {}).get("window_title_pattern", "*"))
        self.ent_win_title.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # URL Browser / Adresă Web
        r_url = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_url.pack(fill="x", pady=4)
        tk.Label(r_url, text="Link / URL Pagină Web:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")
        self.ent_url = tk.Entry(r_url, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_url.insert(0, self.rule.get("trigger", {}).get("url_pattern", ""))
        self.ent_url.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Proces (ex: browsere sau aplicații deschise)
        r_proc = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_proc.pack(fill="x", pady=4)
        tk.Label(r_proc, text="Aplicație / Browser:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")

        # Opțiuni prestabilite și detectare aplicații deschise pe mașină
        self.proc_options = [
            "browser (Edge + Chrome)",
            "msedge.exe (Microsoft Edge)",
            "chrome.exe (Google Chrome)",
            "Orice proces (*)",
        ]
        self._populate_running_apps()

        current_proc = self.rule.get("trigger", {}).get("process_name", "browser (Edge + Chrome)")
        if not current_proc:
            current_proc = "browser (Edge + Chrome)"
        self.var_proc = tk.StringVar(value=current_proc)
        self.cb_proc = ttk.Combobox(r_proc, textvariable=self.var_proc, values=self.proc_options, width=32)
        self.cb_proc.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Tip Condiție Text
        r_cond = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_cond.pack(fill="x", pady=4)
        tk.Label(r_cond, text="Condiție Text:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")

        # Etichetele definite erau construite dar nelegate de combobox: lista
        # afișa valorile interne ("contains", "equals"). Acum eticheta e ce vede
        # utilizatorul, iar valoarea salvată se obține prin maparea inversă.
        self.cond_options = [
            ("Conține text (Contains)", "contains"),
            ("Este exact (Equals)", "equals"),
            ("Începe cu (Starts with)", "starts_with"),
            ("Constelație cuvinte cheie (separate prin ;)", "constellation"),
            ("Expresie regulată (Regex)", "regex"),
        ]
        self._cond_label_to_value = {label: value for label, value in self.cond_options}
        self._cond_value_to_label = {value: label for label, value in self.cond_options}

        saved_cond = str(self.rule.get("trigger", {}).get("text_condition", "contains"))
        self.var_cond = tk.StringVar(
            value=self._cond_value_to_label.get(saved_cond, self.cond_options[0][0]))
        combo_cond = ttk.Combobox(r_cond, textvariable=self.var_cond,
                                  values=[label for label, _ in self.cond_options],
                                  state="readonly", width=34)
        combo_cond.pack(side="left", padx=(8, 0))

        # Text Căutat (Criteriul Principal #1)
        r_txt = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_txt.pack(fill="x", pady=4)
        tk.Label(r_txt, text="Criteriu Text #1:", font=FONT_BODY_BOLD, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")
        self.ent_search_text = tk.Entry(r_txt, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_search_text.insert(0, self.rule.get("trigger", {}).get("search_text", ""))
        self.ent_search_text.pack(side="left", fill="x", expand=True, padx=(8, 6))

        # Butonul [+] Adaugă Criteriu
        self.btn_add_criterion = tk.Button(
            r_txt, text="➕ Criteriu", font=FONT_BODY_BOLD,
            bg=self.theme["accent"], fg="#FFFFFF", relief="flat", padx=10, pady=2,
            cursor="hand2", command=self._add_criterion_row
        )
        self.btn_add_criterion.pack(side="right")

        # Container dinamic pentru criterii suplimentare (inițial ascuns dacă nu există criterii)
        self.multi_criteria_container = tk.Frame(sec2, bg=self.theme["bg_card"])
        self.multi_criteria_container.pack(fill="x", pady=(2, 0))

        # Bară de logică (OR / AND) pentru criterii multiple (afișată doar când există criterii suplimentare)
        self.logic_bar = tk.Frame(self.multi_criteria_container, bg=self.theme["bg_input"], padx=8, pady=4, bd=1, relief="solid")
        tk.Label(self.logic_bar, text="🔗 Relație între Criterii:", font=FONT_BODY_BOLD, bg=self.theme["bg_input"], fg=self.theme["fg_primary"]).pack(side="left", padx=(0, 8))
        self.var_criteria_logic = tk.StringVar(value=self.rule.get("trigger", {}).get("criteria_logic", "OR"))
        self.cb_criteria_logic = ttk.Combobox(self.logic_bar, textvariable=self.var_criteria_logic, values=["OR (Oricare)", "AND (Toate simultan)"], state="readonly", width=18)
        self.cb_criteria_logic.pack(side="left")
        tk.Label(
            self.logic_bar,
            text="• OR = declanșează dacă oricare criteriu e găsit | AND = declanșează doar dacă toate sunt prezente",
            font=FONT_SMALL, bg=self.logic_bar["bg"], fg=self.theme["fg_secondary"]
        ).pack(side="left", padx=(10, 0))

        # Sub-container unde vor sta rândurile efective de criterii
        self.criteria_list_frame = tk.Frame(self.multi_criteria_container, bg=self.theme["bg_card"])
        self.criteria_list_frame.pack(fill="x", pady=(4, 0))

        # Populăm criteriile suplimentare existente
        self._init_existing_additional_criteria()

        # ── Secțiunea 3: Formatare Vizuală & Alertă (Săgeată, Chenar, Badge) ──
        sec3 = self._create_card(scroll_frame, "3. Formatare Vizuală & Semnalizare (Visual Cue)")

        # Chenar
        r_box = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_box.pack(fill="x", pady=4)
        self.var_box = tk.BooleanVar(value=self.rule.get("visual_cue", {}).get("box_enabled", True))
        tk.Checkbutton(r_box, text="Activează Chenar / Cadru Roșu", variable=self.var_box, font=FONT_BODY_BOLD,
                       bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"],
                       command=self._update_preview).pack(side="left")

        self.border_color = self.rule.get("visual_cue", {}).get("border_color", "#FF0000")
        self.btn_border_col = tk.Button(r_box, text="🎨 Culoare Chenar", bg=self.border_color, fg="#FFFFFF",
                                        font=FONT_SMALL, relief="flat", command=self._pick_border_color)
        self.btn_border_col.pack(side="left", padx=12)

        tk.Label(r_box, text="Grosime:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")
        self.var_border_w = tk.IntVar(value=self.rule.get("visual_cue", {}).get("border_width", 3))
        sp_width = tk.Spinbox(r_box, from_=1, to=10, textvariable=self.var_border_w, width=4, command=self._update_preview)
        sp_width.pack(side="left", padx=6)

        # Acoperire Chenar (Zonă Extinsă vs Text Strâns vs Tot Rândul) + Dimensiuni W x H
        r_box_scope = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_box_scope.pack(fill="x", pady=4)
        tk.Label(r_box_scope, text="Acoperire Chenar:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")

        cur_scope = self.rule.get("visual_cue", {}).get("box_scope", "custom_region")
        scope_map = {
            "custom_region": "Zonă Extinsă (W x H din selecție)",
            "exact_text": "Fix pe Textul Detectat (Strâns)",
            "full_row": "Tot Rândul Orizontal (Full Row)"
        }
        self.var_box_scope = tk.StringVar(value=scope_map.get(cur_scope, "Zonă Extinsă (W x H din selecție)"))
        cb_scope = ttk.Combobox(r_box_scope, textvariable=self.var_box_scope, values=list(scope_map.values()), state="readonly", width=28)
        cb_scope.bind("<<ComboboxSelected>>", lambda e: self._update_preview())
        cb_scope.pack(side="left", padx=(8, 10))

        tk.Label(r_box_scope, text="Lățime:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")
        # Dimensiunile implicite nu depind de numele regulii. Varianta anterioară
        # alegea 816x39 dacă numele conținea "GSP" și 350x60 altfel, deci
        # redenumirea unei reguli îi schimba chenarul.
        init_w = self._as_int(self.rule.get("region", {}).get("width"), 350)
        self.var_region_w = tk.IntVar(value=init_w)
        sp_rw = tk.Spinbox(r_box_scope, from_=40, to=3800, textvariable=self.var_region_w, width=5, font=FONT_BODY, command=self._update_preview)
        sp_rw.bind("<KeyRelease>", lambda e: self._update_preview())
        sp_rw.pack(side="left", padx=(4, 8))

        tk.Label(r_box_scope, text="Înălțime:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")
        init_h = self._as_int(self.rule.get("region", {}).get("height"), 60)
        self.var_region_h = tk.IntVar(value=init_h)
        sp_rh = tk.Spinbox(r_box_scope, from_=15, to=2000, textvariable=self.var_region_h, width=4, font=FONT_BODY, command=self._update_preview)
        sp_rh.bind("<KeyRelease>", lambda e: self._update_preview())
        sp_rh.pack(side="left", padx=(4, 6))

        # Săgeată de Atenționare
        r_arr = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_arr.pack(fill="x", pady=4)
        self.var_arrow = tk.BooleanVar(value=self.rule.get("visual_cue", {}).get("arrow_enabled", True))
        tk.Checkbutton(r_arr, text="Săgeată de Atenționare", variable=self.var_arrow, font=FONT_BODY_BOLD,
                       bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"],
                       command=self._update_preview).pack(side="left")

        tk.Label(r_arr, text="Direcție:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left", padx=(10, 2))
        self.var_arrow_dir = tk.StringVar(value=self.rule.get("visual_cue", {}).get("arrow_direction", "down"))
        cb_dir = ttk.Combobox(r_arr, textvariable=self.var_arrow_dir, values=["down", "up", "right", "left"], state="readonly", width=7)
        cb_dir.bind("<<ComboboxSelected>>", lambda e: self._update_preview())
        cb_dir.pack(side="left")

        # Stil Săgeată (Subțire / Triunghi / Clasic)
        tk.Label(r_arr, text="Stil:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left", padx=(10, 2))
        raw_style = self.rule.get("visual_cue", {}).get("arrow_style", "slim")
        style_map = {"slim": "Subțire & Fină", "triangle": "Triunghi Zvelt", "classic": "Clasică (Standard)"}
        self.var_arrow_style = tk.StringVar(value=style_map.get(raw_style, "Subțire & Fină"))
        cb_style = ttk.Combobox(r_arr, textvariable=self.var_arrow_style, values=["Subțire & Fină", "Triunghi Zvelt", "Clasică (Standard)"], state="readonly", width=14)
        cb_style.bind("<<ComboboxSelected>>", lambda e: self._on_arrow_style_changed())
        cb_style.pack(side="left")

        # Lățime / Grosime Săgeată
        tk.Label(r_arr, text="Lățime:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left", padx=(10, 2))
        default_w = 14 if raw_style != "classic" else 32
        self.var_arrow_w = tk.IntVar(value=self.rule.get("visual_cue", {}).get("arrow_width", default_w))
        sp_arr_w = tk.Spinbox(r_arr, from_=6, to=44, textvariable=self.var_arrow_w, width=4, font=FONT_BODY, command=self._update_preview)
        sp_arr_w.bind("<KeyRelease>", lambda e: self._update_preview())
        sp_arr_w.pack(side="left")

        self.arrow_color = self.rule.get("visual_cue", {}).get("arrow_color", "#FF0000")
        self.btn_arr_col = tk.Button(r_arr, text="🎨 Culoare Săgeată", bg=self.arrow_color, fg="#FFFFFF",
                                     font=FONT_SMALL, relief="flat", command=self._pick_arrow_color)
        self.btn_arr_col.pack(side="left", padx=8)

        # Badge Text
        r_bdg = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_bdg.pack(fill="x", pady=4)
        self.var_badge = tk.BooleanVar(value=self.rule.get("visual_cue", {}).get("badge_enabled", True))
        tk.Checkbutton(r_bdg, text="Etichetă / Badge Avertizare:", variable=self.var_badge, font=FONT_BODY_BOLD,
                       bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"],
                       command=self._update_preview).pack(side="left")
        self.ent_badge_text = tk.Entry(r_bdg, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"],
                                       insertbackground=self.theme["fg_primary"], relief="flat", width=24)
        self.ent_badge_text.insert(0, self.rule.get("visual_cue", {}).get("badge_text", "⚠️ MODIFICĂ AICI!"))
        self.ent_badge_text.bind("<KeyRelease>", lambda e: self._update_preview())
        self.ent_badge_text.pack(side="left", padx=8)

        self.var_pulse = tk.BooleanVar(value=self.rule.get("visual_cue", {}).get("pulse_animation", True))
        tk.Checkbutton(r_bdg, text="Efect Pulsare Animat", variable=self.var_pulse, font=FONT_BODY,
                       bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"]).pack(side="left", padx=8)

        # Durată Afișare (secunde, opțional)
        r_dur = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_dur.pack(fill="x", pady=4)
        tk.Label(r_dur, text="⏱️ Durată Afișare Reper:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=20, anchor="w").pack(side="left")
        self.var_duration = tk.StringVar(value=str(self.rule.get("visual_cue", {}).get("duration_sec", 0)))
        self.sp_duration = tk.Spinbox(r_dur, from_=0, to=300, textvariable=self.var_duration, width=6, font=FONT_BODY)
        self.sp_duration.pack(side="left", padx=(8, 4))
        tk.Label(r_dur, text="secunde (0 sau gol = permanent cât timp este deschisă fereastra)", font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]).pack(side="left", padx=6)

        # ── Secțiunea 4: Poziționare & Selector Interactiv ──
        sec4 = self._create_card(scroll_frame, "4. Zonă & Poziționare pe Ecran")

        r_mode = tk.Frame(sec4, bg=self.theme["bg_card"])
        r_mode.pack(fill="x", pady=4)
        tk.Label(r_mode, text="Mod Poziționare:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")
        self.var_mode = tk.StringVar(value=self.rule.get("region", {}).get("mode", "visual_track"))
        cb_mode = ttk.Combobox(r_mode, textvariable=self.var_mode, values=["visual_track", "window_relative", "entire_window", "screen_absolute"], state="readonly", width=20)
        cb_mode.pack(side="left", padx=8)

        btn_pick = tk.Button(
            r_mode, text="🎯 Alege Interactiv de pe Ecran",
            bg=self.theme["accent"], fg="#FFFFFF", font=FONT_BODY_BOLD,
            relief="flat", padx=10, pady=2, command=self._start_picker
        )
        btn_pick.pack(side="right")

        # Rând status snip / șablon vizual
        r_snip = tk.Frame(sec4, bg=self.theme["bg_card"])
        r_snip.pack(fill="x", pady=(4, 2))
        tmpl_cur = self.rule.get("region", {}).get("template_image", "")
        snip_txt = f"📸 Șablon Urmărire Vizuală: {tmpl_cur}" if tmpl_cur else "📸 Niciun șablon vizual definit (folosiți 'Alege Interactiv' pentru a selecta elementul/biletul de pe ecran)"
        self.lbl_snip = tk.Label(r_snip, text=snip_txt, font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["accent"] if tmpl_cur else self.theme["fg_secondary"], anchor="w")
        self.lbl_snip.pack(side="left", fill="x", expand=True)

        # ── Secțiunea 4b: Câmpuri, Condiții & Marcaje (model Excel) ──
        sec_cond = self._create_card(
            scroll_frame,
            "4b. Condiții pe Câmpuri & Marcaje Multiple (opțional, stil Excel)")
        self.condition_panel = ConditionBuilderPanel(
            sec_cond, self.theme_name, self.rule,
            start_picker=self._start_picker_for,
            suggest_window=self._suggest_window_from_pick,
        )

        # ── Secțiunea 5: Pachet de Condiții & Etape Secvențiale ──
        sec5 = self._create_card(scroll_frame, "5. Pachet de Condiții & Succesiune în Timp (Workflow / Pași în Lanț)")
        
        r_step_header = tk.Frame(sec5, bg=self.theme["bg_card"])
        r_step_header.pack(fill="x", pady=4)
        
        self.var_has_steps = tk.BooleanVar(value=bool(self.steps))
        chk_steps = tk.Checkbutton(
            r_step_header, text="Activează succesiune de pași (condiții diferite la intervale de timp diferite)",
            variable=self.var_has_steps, font=FONT_BODY_BOLD,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"],
            command=self._toggle_steps_panel
        )
        chk_steps.pack(side="left")

        btn_add_step = tk.Button(
            r_step_header, text="➕ Adaugă Pas în Lanț", font=FONT_SMALL,
            bg=self.theme["accent"], fg="#FFFFFF", relief="flat", padx=8, pady=2,
            command=self._add_step_dialog
        )
        btn_add_step.pack(side="right")

        btn_del_step = tk.Button(
            r_step_header, text="🗑️ Șterge Pas", font=FONT_SMALL,
            bg=self.theme["bg_hover"], fg=self.theme["alert_red"], relief="flat", padx=8, pady=2,
            command=self._remove_last_step
        )
        btn_del_step.pack(side="right", padx=6)

        self.steps_container = tk.Frame(sec5, bg=self.theme["bg_card"])
        self.steps_container.pack(fill="x", pady=(4, 0))
        self._render_steps_list()

        # ── Secțiunea 6: Live Preview ──
        sec6 = self._create_card(scroll_frame, "6. Previzualizare Reper Vizual (Live Preview)")
        self.preview_canvas = tk.Canvas(sec6, height=130, bg="#11161B", highlightthickness=1, highlightbackground=self.theme["border"])
        self.preview_canvas.pack(fill="x", padx=4, pady=4)

        # ── Butoane Acțiune (Salvează / Anulează / Test Live / Diagnostic) ──
        btn_row = tk.Frame(scroll_frame, bg=self.theme["bg_main"])
        btn_row.pack(fill="x", padx=content_pad, pady=(12, 16))

        btn_cancel = tk.Button(
            btn_row, text="Anulează", font=FONT_BODY,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            relief="flat", padx=14, pady=6, command=self.dialog.destroy
        )
        btn_cancel.pack(side="right", padx=(6, 0))

        btn_save = tk.Button(
            btn_row, text="💾 Salvează Regula", font=FONT_BODY_BOLD,
            bg=self.theme["primary_btn"], fg="#FFFFFF",
            relief="flat", padx=18, pady=6, command=self._save_and_close
        )
        btn_save.pack(side="right", padx=(6, 0))

        btn_test_live = tk.Button(
            btn_row, text="🎯 Testează pe Ecran Acum (Live)", font=FONT_BODY_BOLD,
            bg=self.theme["accent"], fg="#FFFFFF",
            relief="flat", padx=16, pady=6, command=self._test_current_rule
        )
        btn_test_live.pack(side="right", padx=(6, 0))

        btn_diag = tk.Button(
            btn_row, text="🔍 Diagnosticare Live", font=FONT_BODY_BOLD,
            bg="#004B52", fg="#FFFFFF",
            relief="flat", padx=14, pady=6, command=self._run_live_diagnostic
        )
        btn_diag.pack(side="left")

        self._update_preview()

    def _populate_running_apps(self) -> None:
        """Adaugă în dropdown aplicațiile reale deschise pe desktop."""
        try:
            import win32gui, win32process, ctypes, os
            detected = set()
            def enum_cb(h, _):
                if win32gui.IsWindowVisible(h):
                    t = win32gui.GetWindowText(h)
                    if t and len(t.strip()) > 1 and t not in ["Program Manager", "Windows Input Experience"]:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(h)
                            hp = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                            if hp:
                                buf = ctypes.create_unicode_buffer(1024)
                                sz = ctypes.c_ulong(1024)
                                ctypes.windll.kernel32.QueryFullProcessImageNameW(hp, 0, buf, ctypes.byref(sz))
                                ctypes.windll.kernel32.CloseHandle(hp)
                                exe = os.path.basename(buf.value).lower()
                                if exe not in ["focuspilot.exe", "python.exe", "pythonw.exe", "textinputhost.exe"]:
                                    detected.add((exe, t[:30]))
                        except Exception:
                            pass
                return True
            win32gui.EnumWindows(enum_cb, None)
            for exe, title in sorted(detected):
                opt = f"{exe} ({title}...)"
                if opt not in self.proc_options:
                    self.proc_options.append(opt)
        except Exception:
            pass

    def _create_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=self.theme["bg_card"], bd=1, relief="solid")
        card.pack(fill="x", padx=16, pady=6)
        lbl = tk.Label(card, text=title, font=FONT_SUBTITLE, bg=self.theme["bg_card"], fg=self.theme["accent"])
        lbl.pack(anchor="w", padx=10, pady=(8, 4))
        inner = tk.Frame(card, bg=self.theme["bg_card"])
        inner.pack(fill="x", padx=10, pady=(0, 8))
        return inner

    def _pick_border_color(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.border_color, parent=self.dialog)[1]
        if color:
            self.border_color = color
            self.btn_border_col.configure(bg=color)
            self._update_preview()

    def _pick_arrow_color(self) -> None:
        color = colorchooser.askcolor(initialcolor=self.arrow_color, parent=self.dialog)[1]
        if color:
            self.arrow_color = color
            self.btn_arr_col.configure(bg=color)
            self._update_preview()

    def _start_picker(self) -> None:
        """Captură de zonă pentru chenarul regulii."""
        self._start_picker_for("region", self._on_picked)

    def _start_picker_for(self, mode: str,
                          on_picked: Callable[[Dict[str, Any]], None]) -> None:
        """
        Pornește selectorul de ecran și întoarce rezultatul la `on_picked`.

        Panoul de câmpuri folosește același selector, dar în modul "point", ca
        să captureze coordonatele unui singur câmp.
        """
        # Grab-ul modal trebuie eliberat ÎNAINTE de a ascunde ferestrele:
        # altfel Tkinter reține toate click-urile și tastele, iar fereastra de
        # selecție nu primește niciun eveniment.
        try:
            self.dialog.grab_release()
        except Exception:
            pass

        self.dialog.withdraw()
        try:
            self.parent.withdraw()
        except Exception:
            pass

        def _done(data: Dict[str, Any]) -> None:
            self._restore_after_picker()
            on_picked(data)

        InteractivePicker(self.parent, _done, on_cancel=self._on_picker_cancelled,
                          mode=mode).start()

    def _restore_after_picker(self) -> None:
        """Readuce dialogul în prim-plan după selecție."""
        try:
            self.parent.deiconify()
        except Exception:
            pass
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()
        try:
            self.dialog.grab_set()
        except Exception:
            pass

    def _on_picker_cancelled(self) -> None:
        self._restore_after_picker()

    def _suggest_window_from_pick(self, window_title: str, process_name: str) -> None:
        """
        Completează filtrele de fereastră din ce a fost selectat, dar numai dacă
        utilizatorul nu le-a pus deja: o selecție de câmp nu trebuie să
        suprascrie un titlu scris de el.
        """
        current = self.ent_win_title.get().strip()
        if window_title and current in ("", "*"):
            self.ent_win_title.delete(0, tk.END)
            self.ent_win_title.insert(0, f"*{window_title[:40]}*")

        if process_name:
            if process_name.lower() in ("chrome.exe", "msedge.exe", "firefox.exe"):
                self.var_proc.set("browser (Edge + Chrome)")
            else:
                self.var_proc.set(process_name.lower())

    def _on_picked(self, data: Dict[str, Any]) -> None:
        # Populăm câmpurile pe baza selecției utilizatorului
        if data.get("window_title"):
            self.ent_win_title.delete(0, tk.END)
            self.ent_win_title.insert(0, f"*{data['window_title'][:40]}*")

        if data.get("process_name"):
            detected_proc = data["process_name"].lower()
            if detected_proc in ["chrome.exe", "msedge.exe"]:
                self.var_proc.set("browser (Edge + Chrome)")
            else:
                self.var_proc.set(detected_proc)

        if "region" not in self.rule:
            self.rule["region"] = {}

        self.rule["region"]["rel_x"] = data.get("rel_x", 0.20)
        self.rule["region"]["rel_y"] = data.get("rel_y", 0.30)
        self.rule["region"]["width"] = data.get("width", 320)
        self.rule["region"]["height"] = data.get("height", 60)
        self.rule["region"]["abs_x"] = data.get("abs_x", 0)
        self.rule["region"]["abs_y"] = data.get("abs_y", 0)
        if data.get("snip_path"):
            self.rule["region"]["template_image"] = data["snip_path"]
            self.var_mode.set("visual_track")
            if hasattr(self, "lbl_snip"):
                self.lbl_snip.configure(text=f"📸 Șablon Urmărire Vizuală: {data['snip_path']}", fg=self.theme["accent"])
        else:
            self.var_mode.set("window_relative")
            if hasattr(self, "lbl_snip"):
                self.lbl_snip.configure(text="📸 Niciun șablon vizual (mod poziție relativă)", fg=self.theme["fg_secondary"])

        if hasattr(self, "var_region_w"):
            self.var_region_w.set(data.get("width", 320))
        if hasattr(self, "var_region_h"):
            self.var_region_h.set(data.get("height", 60))

        messagebox.showinfo(
            "FocusPilot",
            f"✅ Câmp capturat cu succes!\n\n"
            f"• Fereastră: {data.get('window_title')}\n"
            f"• Aplicație: {data.get('process_name')}\n"
            f"• Dimensiune chenar: {data.get('width')} x {data.get('height')} px\n"
            f"• Urmărire dinamică (Scroll Tracking): ACTIVĂ",
            parent=self.dialog
        )

    def _init_existing_additional_criteria(self) -> None:
        """Populează rândurile de criterii suplimentare existente la deschiderea dialogului."""
        raw_add = self.rule.get("trigger", {}).get("additional_criteria", "")
        items = []
        if isinstance(raw_add, list):
            items = [str(x).strip() for x in raw_add if str(x).strip()]
        elif isinstance(raw_add, str) and raw_add.strip():
            items = [p.strip() for p in re.split(r"[\n\r;|]+", raw_add) if p.strip()]

        for val in items:
            self._create_criterion_entry(val)
        self._refresh_criteria_ui_visibility()

    def _add_criterion_row(self) -> None:
        """Adaugă un nou câmp de criteriu la apăsarea butonului [+] (obligatoriu)."""
        self._create_criterion_entry(initial_value="")
        self._refresh_criteria_ui_visibility()

    def _create_criterion_entry(self, initial_value: str = "") -> None:
        """Creează un rând cu etichetă, Entry și buton de ștergere [-] pentru un criteriu."""
        idx = len(self.criteria_entries) + 2  # #1 este cel principal
        row = tk.Frame(self.criteria_list_frame, bg=self.theme["bg_card"])
        row.pack(fill="x", pady=2)

        lbl = tk.Label(row, text=f"Criteriu Text #{idx}:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w")
        lbl.pack(side="left")

        entry = tk.Entry(row, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        entry.insert(0, initial_value)
        entry.pack(side="left", fill="x", expand=True, padx=(8, 6))

        # Buton de eliminare criteriu
        btn_remove = tk.Button(
            row, text="✖", font=FONT_SMALL,
            bg=self.theme["bg_card"], fg=self.theme["alert_red"], relief="flat", bd=0, padx=8, cursor="hand2",
            command=lambda r=row, e=entry: self._remove_criterion_row(r, e)
        )
        btn_remove.pack(side="right")

        self.criteria_entries.append(entry)
        self.criteria_rows.append(row)

    def _remove_criterion_row(self, row: tk.Frame, entry: tk.Entry) -> None:
        """Șterge un rând de criteriu și recalculează indecșii rămași."""
        if entry in self.criteria_entries:
            idx = self.criteria_entries.index(entry)
            self.criteria_entries.remove(entry)
            if row in self.criteria_rows:
                self.criteria_rows.remove(row)
            row.destroy()

            # Renumerotează etichetele rămase
            for i, r in enumerate(self.criteria_rows):
                for child in r.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(text=f"Criteriu Text #{i + 2}:")
                        break

            self._refresh_criteria_ui_visibility()

    def _refresh_criteria_ui_visibility(self) -> None:
        """Afișează bara de logică și containerul de criterii doar dacă există criterii suplimentare adăugate prin [+]."""
        if self.criteria_entries:
            self.logic_bar.pack(fill="x", pady=(2, 4), before=self.criteria_list_frame)
            self.multi_criteria_container.pack(fill="x", pady=(2, 0))
        else:
            self.logic_bar.pack_forget()
            self.multi_criteria_container.pack_forget()

    def _get_all_criteria_values(self) -> List[str]:
        """Extrage valorile ne-vide din toate câmpurile de criterii suplimentare."""
        result = []
        for e in self.criteria_entries:
            val = e.get().strip()
            if val:
                result.append(val)
        return result

    def _on_arrow_style_changed(self) -> None:
        """Ajustează automat grosimea la selectarea stilului de săgeată."""
        style_name = self.var_arrow_style.get()
        if "Subțire" in style_name or "Zvelt" in style_name:
            self.var_arrow_w.set(14)
        else:
            self.var_arrow_w.set(32)
        self._update_preview()

    def _toggle_steps_panel(self) -> None:
        """Activează sau dezactivează panoul de pași secvențiali."""
        if self.var_has_steps.get() and not self.steps:
            # Inițializăm automat primul pas pe baza configurării curente
            self._add_step_dialog()
        self._render_steps_list()

    def _render_steps_list(self) -> None:
        """Afișează lista vizuală de pași secvențiali."""
        for child in self.steps_container.winfo_children():
            child.destroy()

        if not self.var_has_steps.get():
            lbl_info = tk.Label(
                self.steps_container,
                text="ℹ️ Mod Standard (un singur pas). Bifați căsuța pentru a adăuga mai mulți pași secvențiali la intervale diferite.",
                font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]
            )
            lbl_info.pack(anchor="w", pady=4)
            return

        if not self.steps:
            lbl_empty = tk.Label(
                self.steps_container,
                text="Nu există încă pași adăugați. Apăsați '➕ Adaugă Pas în Lanț'.",
                font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]
            )
            lbl_empty.pack(anchor="w", pady=4)
            return

        for idx, step in enumerate(self.steps):
            row = tk.Frame(self.steps_container, bg=self.theme["bg_input"], padx=8, pady=4, bd=1, relief="solid")
            row.pack(fill="x", pady=3)

            p_txt = f"📍 Pas #{idx+1}: {step.get('name', 'Etapă')} | Start: {step.get('delay_sec', 0)}s | Durată: {step.get('duration_sec', 3)}s | Badge: '{step.get('badge_text', '')}' | Săgeată: {step.get('arrow_direction', 'down')}"
            tk.Label(row, text=p_txt, font=FONT_SMALL, bg=self.theme["bg_input"], fg=self.theme["fg_primary"]).pack(side="left")

    def _add_step_dialog(self) -> None:
        """Adaugă o nouă etapă în pachetul secvențial."""
        step_idx = len(self.steps) + 1
        calc_delay = 0
        if self.steps:
            last = self.steps[-1]
            calc_delay = int(last.get("delay_sec", 0)) + int(last.get("duration_sec", 3))

        new_step = {
            "step_index": step_idx,
            "name": f"Etapa {step_idx}",
            "delay_sec": calc_delay,
            "duration_sec": 3,
            "search_text": self.ent_search_text.get().strip(),
            "badge_text": f"Pas #{step_idx}: " + (self.ent_badge_text.get().strip() or "Acțiune"),
            "arrow_direction": self.var_arrow_dir.get(),
            "arrow_color": self.arrow_color,
            "region": copy.deepcopy(self.rule.get("region", {}))
        }
        self.steps.append(new_step)
        self.var_has_steps.set(True)
        self._render_steps_list()

    def _remove_last_step(self) -> None:
        """Șterge ultimul pas din pachetul secvențial."""
        if self.steps:
            self.steps.pop()
            if not self.steps:
                self.var_has_steps.set(False)
            self._render_steps_list()

    def _update_preview(self) -> None:
        if not self.preview_canvas:
            return

        self.preview_canvas.delete("all")
        cw = self.preview_canvas.winfo_width() or 640
        ch = 130

        # Desenăm un câmp formular simulat
        box_x = 180
        box_y = 45
        box_w = 260
        box_h = 42

        # Câmp text simulat
        self.preview_canvas.create_rectangle(
            box_x, box_y, box_x + box_w, box_y + box_h,
            fill="#1E252D", outline="#3A4756", width=1
        )
        self.preview_canvas.create_text(
            box_x + 15, box_y + 21,
            text="[ Câmp Formular Web / Desktop ]", fill="#A6B4C2", font=FONT_BODY, anchor="w"
        )

        # 1. Chenar alertă
        if self.var_box.get():
            bw = self.var_border_w.get()
            scope_val = self.var_box_scope.get() if hasattr(self, "var_box_scope") else "Zonă Extinsă"
            if "Exact" in scope_val:
                bx_draw, by_draw, bw_draw, bh_draw = box_x, box_y, box_w, box_h
            elif "Rând" in scope_val:
                bx_draw, by_draw, bw_draw, bh_draw = 15, box_y, cw - 30, box_h
            else: # Zonă Extinsă
                rw = self.var_region_w.get() if hasattr(self, "var_region_w") else box_w
                rh = self.var_region_h.get() if hasattr(self, "var_region_h") else box_h
                scaled_w = min(cw - 30, max(box_w, rw // 2))
                bx_draw, by_draw, bw_draw, bh_draw = max(15, box_x - 100), box_y, scaled_w, max(box_h, rh)

            self.preview_canvas.create_rectangle(
                bx_draw, by_draw, bx_draw + bw_draw, by_draw + bh_draw,
                outline=self.border_color, width=bw
            )

        # 2. Săgeată indicatoare (Subțire sau clasică)
        if self.var_arrow.get():
            col = self.arrow_color
            arrow_dir = self.var_arrow_dir.get()
            arrow_w = self.var_arrow_w.get() if hasattr(self, "var_arrow_w") else 14
            style_name = self.var_arrow_style.get() if hasattr(self, "var_arrow_style") else "Subțire & Fină"
            is_slim = "Subțire" in style_name
            is_triangle = "Triunghi" in style_name
            
            hw = max(6, arrow_w)
            total_l = 22 if is_slim else 26
            stem_w = max(2, min(5, hw // 3))

            if arrow_dir == "down":
                tip_x = box_x + (box_w // 2)
                tip_y = box_y - 4
                if is_triangle:
                    pts = [tip_x - hw // 2, tip_y - total_l, tip_x + hw // 2, tip_y - total_l, tip_x, tip_y]
                elif is_slim:
                    head_h = 10
                    hb = tip_y - head_h
                    top_y = tip_y - total_l
                    pts = [tip_x - stem_w // 2, top_y, tip_x + stem_w // 2, top_y, tip_x + stem_w // 2, hb, tip_x + hw // 2, hb, tip_x, tip_y, tip_x - hw // 2, hb, tip_x - stem_w // 2, hb]
                else: # clasic
                    pts = [tip_x - hw // 2, tip_y - total_l, tip_x + hw // 2, tip_y - total_l, tip_x, tip_y]

            elif arrow_dir == "up":
                tip_x = box_x + (box_w // 2)
                tip_y = box_y + box_h + 4
                if is_triangle or not is_slim:
                    pts = [tip_x, tip_y, tip_x + hw // 2, tip_y + total_l, tip_x - hw // 2, tip_y + total_l]
                else:
                    head_h = 10
                    hb = tip_y + head_h
                    bot_y = tip_y + total_l
                    pts = [tip_x, tip_y, tip_x + hw // 2, hb, tip_x + stem_w // 2, hb, tip_x + stem_w // 2, bot_y, tip_x - stem_w // 2, bot_y, tip_x - stem_w // 2, hb, tip_x - hw // 2, hb]

            elif arrow_dir == "left":
                tip_x = box_x + box_w + 4
                tip_y = box_y + (box_h // 2)
                if is_triangle or not is_slim:
                    pts = [tip_x + total_l, tip_y - hw // 2, tip_x, tip_y, tip_x + total_l, tip_y + hw // 2]
                else:
                    head_w = 10
                    hb = tip_x + head_w
                    right_x = tip_x + total_l
                    pts = [right_x, tip_y - stem_w // 2, hb, tip_y - stem_w // 2, hb, tip_y - hw // 2, tip_x, tip_y, hb, tip_y + hw // 2, hb, tip_y + stem_w // 2, right_x, tip_y + stem_w // 2]

            else: # right
                tip_x = box_x - 4
                tip_y = box_y + (box_h // 2)
                if is_triangle or not is_slim:
                    pts = [tip_x - total_l, tip_y - hw // 2, tip_x, tip_y, tip_x - total_l, tip_y + hw // 2]
                else:
                    head_w = 10
                    hb = tip_x - head_w
                    left_x = tip_x - total_l
                    pts = [left_x, tip_y - stem_w // 2, hb, tip_y - stem_w // 2, hb, tip_y - hw // 2, tip_x, tip_y, hb, tip_y + hw // 2, hb, tip_y + stem_w // 2, left_x, tip_y + stem_w // 2]

            self.preview_canvas.create_polygon(pts, fill=col, outline="#660000" if col != "#EB780A" else "#8C4600", width=1)

        # 3. Badge Text
        if self.var_badge.get():
            badge_text = self.ent_badge_text.get() or "⚠️ ATENȚIE!"
            bx = box_x
            arrow_dir = self.var_arrow_dir.get()
            if arrow_dir == "down" and self.var_arrow.get():
                by = box_y - 28 - 24
            else:
                by = box_y - 26

            approx_w = max(100, len(badge_text) * 8 + 16)
            self.preview_canvas.create_rectangle(bx, by, bx + approx_w, by + 20, fill="#D90429", outline="#FFFFFF", width=1)
            self.preview_canvas.create_text(bx + (approx_w // 2), by + 10, text=badge_text, fill="#FFFFFF", font=FONT_SMALL)

    def _get_current_rule_snapshot(self) -> Dict[str, Any]:
        """Extrage o copie a stării curente din formular pentru testare sau salvare."""
        snap = copy.deepcopy(self.rule)
        snap["name"] = self.ent_name.get().strip() or "Regulă Nouă"
        snap["enabled"] = self.var_enabled.get()

        if "trigger" not in snap:
            snap["trigger"] = {}
        snap["trigger"]["window_title_pattern"] = self.ent_win_title.get().strip() or "*"
        snap["trigger"]["url_pattern"] = self.ent_url.get().strip()
        
        proc_val = self.var_proc.get().strip()
        if "browser" in proc_val.lower():
            snap["trigger"]["process_name"] = "browser"
        elif "chrome.exe" in proc_val.lower():
            snap["trigger"]["process_name"] = "chrome.exe"
        elif "msedge.exe" in proc_val.lower():
            snap["trigger"]["process_name"] = "msedge.exe"
        elif "orice proces" in proc_val.lower():
            snap["trigger"]["process_name"] = ""
        else:
            snap["trigger"]["process_name"] = proc_val.split()[0].lower()

        snap["trigger"]["text_condition"] = self._cond_label_to_value.get(
            self.var_cond.get(), "contains")
        snap["trigger"]["search_text"] = self.ent_search_text.get().strip()
        # "Expresie regulată" din lista de condiții activează și indicatorul
        # folosit de motor, ca cele două setări să nu se poată contrazice.
        snap["trigger"]["is_regex"] = (snap["trigger"]["text_condition"] == "regex")

        # Preluare criterii dinamice adăugate prin butonul [+]
        additional_list = self._get_all_criteria_values()
        snap["trigger"]["additional_criteria"] = additional_list
        raw_logic = self.var_criteria_logic.get() if hasattr(self, "var_criteria_logic") else "OR"
        snap["trigger"]["criteria_logic"] = "AND" if "AND" in raw_logic else "OR"

        if "visual_cue" not in snap:
            snap["visual_cue"] = {}
        snap["visual_cue"]["box_enabled"] = self.var_box.get()
        snap["visual_cue"]["border_color"] = self.border_color
        snap["visual_cue"]["border_width"] = self.var_border_w.get()

        scope_map_rev = {
            "Zonă Extinsă (W x H din selecție)": "custom_region",
            "Fix pe Textul Detectat (Strâns)": "exact_text",
            "Tot Rândul Orizontal (Full Row)": "full_row"
        }
        snap["visual_cue"]["box_scope"] = scope_map_rev.get(self.var_box_scope.get(), "custom_region") if hasattr(self, "var_box_scope") else "custom_region"

        snap["visual_cue"]["arrow_enabled"] = self.var_arrow.get()
        snap["visual_cue"]["arrow_direction"] = self.var_arrow_dir.get()
        snap["visual_cue"]["arrow_color"] = self.arrow_color

        st_map = {"Subțire & Fină": "slim", "Triunghi Zvelt": "triangle", "Clasică (Standard)": "classic"}
        snap["visual_cue"]["arrow_style"] = st_map.get(self.var_arrow_style.get(), "slim")
        snap["visual_cue"]["arrow_width"] = self.var_arrow_w.get()
        snap["visual_cue"]["arrow_size"] = 22 if snap["visual_cue"]["arrow_style"] != "classic" else 36

        snap["visual_cue"]["badge_enabled"] = self.var_badge.get()
        snap["visual_cue"]["badge_text"] = self.ent_badge_text.get().strip()
        snap["visual_cue"]["pulse_animation"] = self.var_pulse.get()

        try:
            dur = int(self.var_duration.get().strip() or 0)
        except ValueError:
            dur = 0
        snap["visual_cue"]["duration_sec"] = dur

        region = snap.setdefault("region", {})
        region["mode"] = self.var_mode.get()
        # Un Spinbox poate conține text tastat de utilizator, nu doar cifre, iar
        # `IntVar.get()` ar arunca excepție și ar anula salvarea regulii.
        region["width"] = self._spin_value(self.var_region_w, 350)
        region["height"] = self._spin_value(self.var_region_h, 60)

        # Coordonatele capturate cu selectorul interactiv se păstrează explicit:
        # pe ele se bazează desenarea când elementul nu poate fi localizat live.
        for key, default in (("abs_x", 0), ("abs_y", 0),
                             ("rel_x", 0.2), ("rel_y", 0.3),
                             ("monitor_index", -1)):
            region.setdefault(key, self.rule.get("region", {}).get(key, default))
        if self.rule.get("region", {}).get("template_image"):
            region["template_image"] = self.rule["region"]["template_image"]

        if self.var_has_steps.get() and self.steps:
            snap["steps"] = copy.deepcopy(self.steps)
        else:
            snap["steps"] = []

        # Câmpuri, condiții și marcaje. Dacă panoul nu e folosit, cheile se
        # golesc, iar motorul tratează regula pe calea clasică.
        if getattr(self, "condition_panel", None) is not None:
            snap.update(self.condition_panel.to_rule_fields())

        return snap

    def _test_current_rule(self) -> None:
        """Testează reperul direct pe ecran din fereastra de editare."""
        if not self.on_test_cue:
            messagebox.showinfo("FocusPilot", "Funcția de testare nu este disponibilă direct.", parent=self.dialog)
            return

        snapshot = self._get_current_rule_snapshot()
        self.on_test_cue(snapshot)

    def _run_live_diagnostic(self) -> None:
        """
        Explică de ce regula se declanșează sau nu, chiar acum, pe ecran.

        Foloseste ACELASI motor ca monitorizarea. Varianta anterioară avea
        propria copie a logicii de potrivire, care putea raporta
        "REGULA ESTE 100% VALIDĂ" pentru o regulă ce nu se declanșa niciodată
        în realitate — motorul real evalua alte condiții.
        """
        from core.monitor_engine import (enumerate_content_windows,
                                         get_virtual_screen_bounds)
        from core.rule_engine import RuleEngine, CAPABILITIES

        rule_data = self._get_current_rule_snapshot()
        virtual = get_virtual_screen_bounds()
        windows = enumerate_content_windows()

        report = ["🔍 DIAGNOSTICARE LIVE FOCUSPILOT", "=" * 48, ""]

        missing = CAPABILITIES.missing()
        if missing:
            report += [
                "⚠️ DEPENDENȚE LIPSĂ — detecția este incompletă:",
                f"     pip install {' '.join(missing)}",
            ]
            if "uiautomation" in missing:
                report.append("   Fără 'uiautomation' textul din pagini nu poate fi citit.")
            report.append("")

        if not windows:
            report.append("❌ Nu s-a găsit nicio fereastră de aplicație deschisă.")
            messagebox.showinfo("Diagnosticare Live", "\n".join(report), parent=self.dialog)
            return

        report.append(f"Ferestre verificate: {len(windows)} (pe toate monitoarele)")
        report.append("")

        uses_probes = probe_engine.uses_conditions(rule_data)

        match = None
        for window in windows:
            result = RuleEngine.evaluate(rule_data, window, virtual)
            mark = "✅" if result.matched else "❌"
            title = (window.get("title") or "")[:44]
            report.append(f"{mark} {title}")
            report.append(f"     proces: {window.get('process_name') or '?'}")
            if window.get("url"):
                report.append(f"     URL:    {window['url'][:60]}")

            if uses_probes:
                # Pentru regulile cu câmpuri arătăm fiecare condiție separat, cu
                # valoarea citită efectiv: altfel nu se vede CARE condiție a picat.
                report.extend(self._condition_lines(rule_data, window))
            else:
                report.append(f"     {result.reason}")
            report.append("")
            if result.matched and match is None:
                match = (window, result)

        report.append("-" * 48)
        if match is None:
            report.append("REZULTAT: regula NU se declanșează acum.")
            report.append("")
            report.append("Verificați, în ordine:")
            report.append("  • 'Aplicație / Browser' — comparați cu procesul listat mai sus.")
            report.append("  • 'Titlu Fereastră' — folosiți * în jurul cuvântului-cheie.")
            report.append("  • 'Link / URL' — lăsați * dacă nu contează adresa.")
            report.append("  • Textul căutat — trebuie să fie VIZIBIL în pagină acum.")
        else:
            window, result = match
            report.append(f"REZULTAT: regula SE DECLANȘEAZĂ pe '{(window.get('title') or '')[:36]}'.")
            if result.geometry:
                x, y, w, h = result.geometry
                anchor_text = {
                    "uia": "ancorat pe elementul din pagină (urmărește scroll-ul)",
                    "template": "ancorat pe șablonul imagine",
                    "configured": "la coordonatele salvate în regulă",
                }.get(result.anchor, result.anchor)
                report.append(f"Chenar: {w}x{h} px la ({x}, {y}) — {anchor_text}.")
            else:
                report.append("Dar nu s-au putut determina coordonatele chenarului.")
                report.append("Folosiți '🎯 Alege Interactiv de pe Ecran'.")

        messagebox.showinfo("Diagnosticare Live FocusPilot", "\n".join(report),
                            parent=self.dialog)

    def _condition_lines(self, rule: Dict[str, Any],
                         window: Dict[str, Any]) -> List[str]:
        """Starea fiecărei condiții pe o fereastră, cu valorile citite."""
        from core.rule_engine import capture_window_text

        try:
            snapshot = capture_window_text(window.get("hwnd"), force=True)
        except Exception as exc:
            return [f"     Textul ferestrei nu a putut fi citit: {exc}"]

        outcome = probe_engine.evaluate_conditions(
            rule, snapshot, window.get("rect") or (0, 0, 0, 0))

        lines = []
        for item in outcome.outcomes:
            lines.append("     " + item.describe())
        for reading in outcome.readings.values():
            if not reading.located:
                lines.append(f"       ⚠️ {reading.name}: {reading.note}")
        lines.append(f"     Logică: {outcome.logic}")
        return lines

    def _save_and_close(self) -> None:
        if not self.ent_name.get().strip():
            messagebox.showwarning("Atenție", "Introduceți un nume pentru regulă.",
                                   parent=self.dialog)
            return

        # Validarea câmpurilor și condițiilor se face înainte de salvare, ca
        # utilizatorul să afle acum, nu când regula nu se declanșează.
        if getattr(self, "condition_panel", None) is not None:
            problem = self.condition_panel.validate()
            if problem:
                messagebox.showwarning("Configurație incompletă", problem,
                                       parent=self.dialog)
                return

        final_rule = self._get_current_rule_snapshot()

        if not probe_engine.uses_conditions(final_rule):
            criteria, _logic = RuleEngine.extract_criteria_list(
                final_rule.get("trigger", {}))
            title = final_rule.get("trigger", {}).get("window_title_pattern", "")
            if not criteria and title in ("", "*"):
                if not messagebox.askyesno(
                        "Regulă foarte largă",
                        "Regula nu are nici text căutat, nici filtru de titlu, "
                        "nici condiții pe câmpuri.\n\n"
                        "Se va declanșa pe orice fereastră care trece filtrul de "
                        "aplicație. Continuați?",
                        parent=self.dialog):
                    return

        self.on_save(final_rule)
        self.dialog.destroy()
