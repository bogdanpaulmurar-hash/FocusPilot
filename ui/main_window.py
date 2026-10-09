"""
FocusPilot — Main Dashboard Window
Interfață principală modernă în stil corporativ Siemens:
Listă reguli, configurare rapidă, previzualizare, comutare Dark/Light și minimizare în Tray.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional, Callable

from core.config_manager import ConfigManager
from ui.theme import get_theme, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL, FONT_ICON
from ui.rule_editor_dialog import RuleEditorDialog
from ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow:
    """Fereastra principală a aplicației FocusPilot."""

    def __init__(self, root: tk.Tk, config_manager: ConfigManager,
                 on_rules_changed: Callable[[], None],
                 on_test_cue: Callable[[Dict[str, Any]], None],
                 on_toggle_pause: Callable[[], bool],
                 on_quit: Callable[[], None]):
        self.root = root
        self.cfg = config_manager
        self.on_rules_changed = on_rules_changed
        self.on_test_cue = on_test_cue
        self.on_toggle_pause = on_toggle_pause
        self.on_quit = on_quit

        self.theme_name = self.cfg.get_setting("theme", "dark")
        self.theme = get_theme(self.theme_name)

        self._build_ui()
        self.refresh_rules_list()

    def _build_ui(self) -> None:
        self.root.title("FocusPilot — Smart Screen & Browser Conditional Formatter")
        self.root.geometry("880x620")
        self.root.minsize(760, 500)
        self.root.configure(bg=self.theme["bg_main"])

        # La închiderea ferestrei, doar o ascundem în Tray (nu oprim aplicația)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        # ── Bara de Navigare Superioară (Header) ──
        nav_bar = tk.Frame(self.root, bg=self.theme["primary_btn"], height=56, padx=16)
        nav_bar.pack(fill="x")
        nav_bar.pack_propagate(False)

        # Logo / Titlu
        title_box = tk.Frame(nav_bar, bg=self.theme["primary_btn"])
        title_box.pack(side="left", fill="y")

        tk.Label(
            title_box, text="🎯 FocusPilot", font=("Segoe UI", 14, "bold"),
            bg=self.theme["primary_btn"], fg="#FFFFFF"
        ).pack(side="left", pady=10)

        tk.Label(
            title_box, text=" | Smart Visual Cue & Conditional Formatter",
            font=("Segoe UI", 10), bg=self.theme["primary_btn"], fg="#B4D7DC"
        ).pack(side="left", pady=13, padx=(6, 0))

        # Butoane Header Dreapta
        btn_box = tk.Frame(nav_bar, bg=self.theme["primary_btn"])
        btn_box.pack(side="right", fill="y")

        self.btn_pause = tk.Button(
            btn_box, text="⏸️ Pauză", font=FONT_BODY_BOLD,
            bg=self.theme["accent"], fg="#FFFFFF", relief="flat",
            padx=12, pady=3, command=self._handle_toggle_pause
        )
        self.btn_pause.pack(side="left", padx=6, pady=12)

        btn_theme = tk.Button(
            btn_box, text="🌓 Temă", font=FONT_BODY,
            bg="#004B52", fg="#FFFFFF", relief="flat",
            padx=10, pady=3, command=self._toggle_theme
        )
        btn_theme.pack(side="left", padx=6, pady=12)

        btn_settings = tk.Button(
            btn_box, text="⚙️ Setări", font=FONT_BODY,
            bg="#004B52", fg="#FFFFFF", relief="flat",
            padx=10, pady=3, command=self._open_settings
        )
        btn_settings.pack(side="left", padx=6, pady=12)

        # ── Bara de Acțiuni Secundară (Sub-Header) ──
        sub_bar = tk.Frame(self.root, bg=self.theme["bg_main"], padx=16, pady=12)
        sub_bar.pack(fill="x")

        tk.Label(
            sub_bar, text="Reguli de Formatare Condițională Active pe Ecrane",
            font=FONT_SUBTITLE, bg=self.theme["bg_main"], fg=self.theme["fg_primary"]
        ).pack(side="left")

        btn_add = tk.Button(
            sub_bar, text="➕ Adaugă Regulă Nouă", font=FONT_BODY_BOLD,
            bg=self.theme["primary_btn"], fg="#FFFFFF", relief="flat",
            padx=14, pady=5, command=self._add_rule
        )
        btn_add.pack(side="right")

        btn_demo = tk.Button(
            sub_bar, text="👁️ Testează Repere Vizuale (Demo)", font=FONT_BODY,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"], relief="flat",
            padx=12, pady=5, command=self._test_demo_cues
        )
        btn_demo.pack(side="right", padx=(0, 10))

        # ── Zona Centrală: Listă Carduri Reguli (Derulabilă) ──
        container = tk.Frame(self.root, bg=self.theme["bg_main"], padx=16)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, bg=self.theme["bg_main"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.rules_frame = tk.Frame(self.canvas, bg=self.theme["bg_main"])

        self.rules_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rules_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Suport pentru scroll oriunde cu rotița mouse-ului (Mouse Wheel Scroll)
        def _on_mousewheel(event):
            delta = -1 * (event.delta // 120) if event.delta else 1
            self.canvas.yview_scroll(delta, "units")

        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # ── Bara de Stare Inferioară (Status Bar) ──
        self.status_bar = tk.Frame(self.root, bg=self.theme["bg_card"], height=32, padx=16)
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.pack_propagate(False)

        self.lbl_status = tk.Label(
            self.status_bar, text="● Monitorizare activă pe 3 ecrane",
            font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["green"]
        )
        self.lbl_status.pack(side="left", pady=6)

        self.lbl_count = tk.Label(
            self.status_bar, text="0 reguli configurate",
            font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]
        )
        self.lbl_count.pack(side="right", pady=6)

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def refresh_rules_list(self) -> None:
        """Reconstruiește lista de carduri pentru regulile din configurație."""
        for child in self.rules_frame.winfo_children():
            child.destroy()

        rules = self.cfg.get_rules()
        active_count = sum(1 for r in rules if r.get("enabled", True))
        self.lbl_count.configure(text=f"{active_count} active din {len(rules)} reguli")

        if not rules:
            empty_box = tk.Frame(self.rules_frame, bg=self.theme["bg_card"], bd=1, relief="solid", padx=20, pady=30)
            empty_box.pack(fill="x", pady=20)
            tk.Label(
                empty_box, text="Nu există nicio regulă definită.",
                font=FONT_SUBTITLE, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]
            ).pack()
            tk.Label(
                empty_box, text="Faceți clic pe '➕ Adaugă Regulă Nouă' pentru a crea prima formatare condițională.",
                font=FONT_SMALL, bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]
            ).pack(pady=(4, 0))
            return

        for rule in rules:
            self._render_rule_card(rule)

    def _render_rule_card(self, rule: Dict[str, Any]) -> None:
        """Afișează o regulă ca un card elegant cu detalii și acțiuni rapide."""
        rule_id = rule.get("id", "")
        is_enabled = rule.get("enabled", True)

        card = tk.Frame(self.rules_frame, bg=self.theme["bg_card"], bd=1, relief="solid", padx=12, pady=10)
        card.pack(fill="x", pady=6)

        # Dublu-clic pe card deschide direct dialogul de editare
        card.bind("<Double-Button-1>", lambda e, r=rule: self._edit_rule(r))

        # Rândul 1: Toggle activ + Nume + Butoane acțiune
        top_row = tk.Frame(card, bg=self.theme["bg_card"])
        top_row.pack(fill="x")
        top_row.bind("<Double-Button-1>", lambda e, r=rule: self._edit_rule(r))

        # Badge status vizual clar: [ACTIV] sau [INACTIV]
        status_bg = self.theme["green"] if is_enabled else self.theme["bg_hover"]
        status_fg = "#FFFFFF" if is_enabled else self.theme["fg_muted"]
        status_txt = "● ACTIV" if is_enabled else "○ OPRIT"
        lbl_badge_status = tk.Label(
            top_row, text=status_txt, font=FONT_SMALL, bg=status_bg, fg=status_fg,
            padx=8, pady=2, cursor="hand2"
        )
        lbl_badge_status.pack(side="left", padx=(0, 8))
        lbl_badge_status.bind("<Button-1>", lambda e, rid=rule_id: self._toggle_rule(rid))

        var_chk = tk.BooleanVar(value=is_enabled)
        chk = tk.Checkbutton(
            top_row, text=rule.get("name", "Fără nume"), variable=var_chk,
            font=FONT_BODY_BOLD, bg=self.theme["bg_card"],
            fg=self.theme["fg_primary"] if is_enabled else self.theme["fg_muted"],
            selectcolor=self.theme["bg_input"], activebackground=self.theme["bg_card"],
            cursor="hand2", command=lambda rid=rule_id: self._toggle_rule(rid)
        )
        chk.pack(side="left")
        chk.bind("<Double-Button-1>", lambda e, r=rule: self._edit_rule(r))

        # Butoane acțiune card
        btn_del = tk.Button(
            top_row, text="🗑️", font=FONT_ICON, bg=self.theme["bg_card"],
            fg=self.theme["alert_red"], relief="flat", bd=0, padx=6, cursor="hand2",
            command=lambda rid=rule_id: self._delete_rule(rid)
        )
        btn_del.pack(side="right")

        btn_edit = tk.Button(
            top_row, text="✏️ Editează", font=FONT_SMALL, bg=self.theme["bg_hover"],
            fg=self.theme["fg_primary"], relief="flat", padx=10, pady=2, cursor="hand2",
            command=lambda r=rule: self._edit_rule(r)
        )
        btn_edit.pack(side="right", padx=6)

        btn_test = tk.Button(
            top_row, text="🎯 Testează", font=FONT_SMALL, bg=self.theme["bg_hover"],
            fg=self.theme["accent"], relief="flat", padx=10, pady=2, cursor="hand2",
            command=lambda r=rule: self.on_test_cue(r)
        )
        btn_test.pack(side="right", padx=6)

        # Rândul 2: Informații Declanșator (Trigger info)
        trigger = rule.get("trigger", {})
        win_pat = trigger.get("window_title_pattern", "*")
        url_pat = trigger.get("url_pattern", "")
        proc = trigger.get("process_name", "") or "Orice proces"
        txt = trigger.get("search_text", "")
        cond = trigger.get("text_condition", "contains")

        info_row = tk.Frame(card, bg=self.theme["bg_card"])
        info_row.pack(fill="x", pady=(6, 0))
        info_row.bind("<Double-Button-1>", lambda e, r=rule: self._edit_rule(r))

        info_text = f"📍 Țintă: [{proc}] {win_pat}"
        if url_pat and url_pat != "*":
            info_text += f" | 🔗 URL: {url_pat}"
        if txt:
            info_text += f"  |  🔍 Condiție ({cond}): \"{txt[:35]}\""

        lbl_info = tk.Label(
            info_row, text=info_text, font=FONT_SMALL,
            bg=self.theme["bg_card"], fg=self.theme["fg_secondary"]
        )
        lbl_info.pack(side="left")
        lbl_info.bind("<Double-Button-1>", lambda e, r=rule: self._edit_rule(r))

        # Rândul 3: Rezumat Repere Vizuale (Badge-uri stilizate)
        cue = rule.get("visual_cue", {})
        cue_row = tk.Frame(card, bg=self.theme["bg_card"])
        cue_row.pack(fill="x", pady=(6, 0))

        if cue.get("box_enabled", True):
            self._render_badge(cue_row, f"Chenar {cue.get('border_color', '#FF0000')} ({cue.get('border_width', 3)}px)", self.theme["bg_input"], cue.get('border_color', '#FF0000'))

        if cue.get("arrow_enabled", True):
            dir_sym = {"right": "➔", "left": "⬅", "down": "⬇", "up": "⬆"}.get(cue.get("arrow_direction", "right"), "➔")
            self._render_badge(cue_row, f"Săgeată {dir_sym}", self.theme["bg_input"], cue.get("arrow_color", "#FF0000"))

        if cue.get("badge_enabled", True):
            self._render_badge(cue_row, cue.get("badge_text", "⚠️ ATENȚIE"), cue.get("badge_bg", "#D90429"), "#FFFFFF")

    def _render_badge(self, parent: tk.Widget, text: str, bg: str, fg: str) -> None:
        b = tk.Label(parent, text=text, font=FONT_SMALL, bg=bg, fg=fg, padx=6, pady=1)
        b.pack(side="left", padx=(0, 6))

    def _toggle_rule(self, rule_id: str) -> None:
        self.cfg.toggle_rule(rule_id)
        self.on_rules_changed()
        self.refresh_rules_list()

    def _add_rule(self) -> None:
        RuleEditorDialog(self.root, self.theme_name, None, self._on_rule_saved)

    def _edit_rule(self, rule: Dict[str, Any]) -> None:
        RuleEditorDialog(self.root, self.theme_name, rule, self._on_rule_saved)

    def _on_rule_saved(self, rule: Dict[str, Any]) -> None:
        rule_id = rule.get("id")
        if not rule_id or not self.cfg.get_rule_by_id(rule_id):
            self.cfg.add_rule(rule)
        else:
            self.cfg.update_rule(rule_id, rule)
        self.on_rules_changed()
        self.refresh_rules_list()

    def _delete_rule(self, rule_id: str) -> None:
        if messagebox.askyesno("Confirmare", "Sigur doriți să ștergeți această regulă?", parent=self.root):
            self.cfg.delete_rule(rule_id)
            self.on_rules_changed()
            self.refresh_rules_list()

    def _open_settings(self) -> None:
        SettingsDialog(self.root, self.cfg, self._on_settings_updated)

    def _on_settings_updated(self) -> None:
        new_theme = self.cfg.get_setting("theme", "dark")
        if new_theme != self.theme_name:
            self.theme_name = new_theme
            self.theme = get_theme(new_theme)
            # Reîmprospătează interfața cu noua temă
            self.root.configure(bg=self.theme["bg_main"])
            self.refresh_rules_list()

    def _toggle_theme(self) -> None:
        new_theme = "light" if self.theme_name == "dark" else "dark"
        self.cfg.set_setting("theme", new_theme, auto_save=True)
        self._on_settings_updated()

    def _handle_toggle_pause(self) -> None:
        is_paused = self.on_toggle_pause()
        if is_paused:
            self.btn_pause.configure(text="▶️ Reia", bg=self.theme["green"])
            self.lbl_status.configure(text="⏸️ Monitorizare pusă pe pauză", fg=self.theme["orange"])
        else:
            self.btn_pause.configure(text="⏸️ Pauză", bg=self.theme["accent"])
            self.lbl_status.configure(text="● Monitorizare activă pe 3 ecrane", fg=self.theme["green"])

    def _test_demo_cues(self) -> None:
        rules = self.cfg.get_rules()
        if rules:
            self.on_test_cue(rules[0])
        else:
            messagebox.showinfo("FocusPilot", "Nu există reguli de testat. Adăugați o regulă mai întâi.", parent=self.root)

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide(self) -> None:
        self.root.withdraw()
