"""
FocusPilot — Excel-Style Conditional Formatting Rule Editor Dialog
Dialog complet de configurare cu Live Preview, selecție culori Siemens,
configurare declanșator text și săgeți/chenare vizuale.
"""

import copy
import logging
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from typing import Dict, Any, Optional, Callable

from ui.theme import get_theme, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL
from ui.interactive_picker import InteractivePicker

logger = logging.getLogger(__name__)


class RuleEditorDialog:
    """Dialog modal pentru creare sau editare de regulă de formatare condițională."""

    def __init__(self, parent: tk.Toplevel, theme_name: str, rule: Optional[Dict[str, Any]], on_save: Callable[[Dict[str, Any]], None]):
        self.parent = parent
        self.theme_name = theme_name
        self.theme = get_theme(theme_name)
        self.on_save = on_save

        self.is_new = (rule is None)
        self.rule: Dict[str, Any] = copy.deepcopy(rule) if rule else self._get_default_rule()

        self.dialog: Optional[tk.Toplevel] = None
        self.preview_canvas: Optional[tk.Canvas] = None

        self._build_ui()

    def _get_default_rule(self) -> Dict[str, Any]:
        return {
            "id": "",
            "name": "Regulă Nouă de Atenționare",
            "enabled": True,
            "trigger": {
                "target_type": "browser_or_window",
                "window_title_pattern": "*",
                "url_pattern": "*",
                "process_name": "msedge.exe",
                "text_condition": "contains",
                "search_text": "",
                "case_sensitive": False,
                "is_regex": False
            },
            "visual_cue": {
                "box_enabled": True,
                "border_color": "#FF0000",
                "border_width": 3,
                "fill_color": "#FF3333",
                "fill_opacity": 0.20,
                "arrow_enabled": True,
                "arrow_direction": "right",
                "arrow_color": "#FF0000",
                "arrow_size": 36,
                "badge_enabled": True,
                "badge_text": "⚠️ MODIFICĂ AICI!",
                "badge_bg": "#D90429",
                "badge_fg": "#FFFFFF",
                "pulse_animation": True
            },
            "region": {
                "mode": "window_relative",
                "rel_x": 0.20,
                "rel_y": 0.30,
                "width": 350,
                "height": 60,
                "monitor_index": -1
            }
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
        canvas.configure(yview_scroll=scrollbar.set)

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

        # Proces (ex: msedge.exe)
        r_proc = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_proc.pack(fill="x", pady=4)
        tk.Label(r_proc, text="Nume Proces (opțional):", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")
        self.ent_proc = tk.Entry(r_proc, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_proc.insert(0, self.rule.get("trigger", {}).get("process_name", ""))
        self.ent_proc.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Tip Condiție Text
        r_cond = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_cond.pack(fill="x", pady=4)
        tk.Label(r_cond, text="Condiție Text:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")

        self.cond_options = [
            ("Conține text (Contains)", "contains"),
            ("Este exact (Equals)", "equals"),
            ("Începe cu (Starts with)", "starts_with"),
            ("Constelație cuvinte cheie (Separate prin ;)", "constellation"),
            ("Expresie regulată (Regex)", "regex")
        ]
        self.var_cond = tk.StringVar(value=self.rule.get("trigger", {}).get("text_condition", "contains"))
        combo_cond = ttk.Combobox(r_cond, textvariable=self.var_cond, values=[opt[1] for opt in self.cond_options], state="readonly", width=16)
        combo_cond.pack(side="left", padx=(8, 0))

        # Text Căutat
        r_txt = tk.Frame(sec2, bg=self.theme["bg_card"])
        r_txt.pack(fill="x", pady=4)
        tk.Label(r_txt, text="Text Căutat / Pattern:", font=FONT_BODY_BOLD, bg=self.theme["bg_card"], fg=self.theme["fg_primary"], width=18, anchor="w").pack(side="left")
        self.ent_search_text = tk.Entry(r_txt, font=FONT_BODY, bg=self.theme["bg_input"], fg=self.theme["fg_primary"], insertbackground=self.theme["fg_primary"], relief="flat")
        self.ent_search_text.insert(0, self.rule.get("trigger", {}).get("search_text", ""))
        self.ent_search_text.pack(side="left", fill="x", expand=True, padx=(8, 0))

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

        # Săgeată Roșie
        r_arr = tk.Frame(sec3, bg=self.theme["bg_card"])
        r_arr.pack(fill="x", pady=4)
        self.var_arrow = tk.BooleanVar(value=self.rule.get("visual_cue", {}).get("arrow_enabled", True))
        tk.Checkbutton(r_arr, text="Săgeată Roșie de Atenționare", variable=self.var_arrow, font=FONT_BODY_BOLD,
                       bg=self.theme["bg_card"], fg=self.theme["fg_primary"], selectcolor=self.theme["bg_input"],
                       command=self._update_preview).pack(side="left")

        tk.Label(r_arr, text="Direcție:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left", padx=(12, 4))
        self.var_arrow_dir = tk.StringVar(value=self.rule.get("visual_cue", {}).get("arrow_direction", "right"))
        cb_dir = ttk.Combobox(r_arr, textvariable=self.var_arrow_dir, values=["right", "left", "down", "up"], state="readonly", width=8)
        cb_dir.bind("<<ComboboxSelected>>", lambda e: self._update_preview())
        cb_dir.pack(side="left")

        self.arrow_color = self.rule.get("visual_cue", {}).get("arrow_color", "#FF0000")
        self.btn_arr_col = tk.Button(r_arr, text="🎨 Culoare Săgeată", bg=self.arrow_color, fg="#FFFFFF",
                                     font=FONT_SMALL, relief="flat", command=self._pick_arrow_color)
        self.btn_arr_col.pack(side="left", padx=10)

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

        # ── Secțiunea 4: Poziționare & Selector Interactiv ──
        sec4 = self._create_card(scroll_frame, "4. Zonă & Poziționare pe Ecran")

        r_mode = tk.Frame(sec4, bg=self.theme["bg_card"])
        r_mode.pack(fill="x", pady=4)
        tk.Label(r_mode, text="Mod Poziționare:", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")
        self.var_mode = tk.StringVar(value=self.rule.get("region", {}).get("mode", "window_relative"))
        cb_mode = ttk.Combobox(r_mode, textvariable=self.var_mode, values=["window_relative", "entire_window", "screen_absolute"], state="readonly", width=18)
        cb_mode.pack(side="left", padx=8)

        btn_pick = tk.Button(
            r_mode, text="🎯 Alege Interactiv de pe Ecran",
            bg=self.theme["accent"], fg="#FFFFFF", font=FONT_BODY_BOLD,
            relief="flat", padx=10, pady=2, command=self._start_picker
        )
        btn_pick.pack(side="right")

        # ── Secțiunea 5: Live Preview ──
        sec5 = self._create_card(scroll_frame, "5. Previzualizare Reper Vizual (Live Preview)")
        self.preview_canvas = tk.Canvas(sec5, height=130, bg="#11161B", highlightthickness=1, highlightbackground=self.theme["border"])
        self.preview_canvas.pack(fill="x", padx=4, pady=4)

        # ── Butoane Acțiune (Salvează / Anulează) ──
        btn_row = tk.Frame(scroll_frame, bg=self.theme["bg_main"])
        btn_row.pack(fill="x", padx=content_pad, pady=(12, 16))

        btn_cancel = tk.Button(
            btn_row, text="Anulează", font=FONT_BODY,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            relief="flat", padx=18, pady=6, command=self.dialog.destroy
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_save = tk.Button(
            btn_row, text="💾 Salvează Regula", font=FONT_BODY_BOLD,
            bg=self.theme["primary_btn"], fg="#FFFFFF",
            relief="flat", padx=22, pady=6, command=self._save_and_close
        )
        btn_save.pack(side="right")

        self._update_preview()

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
        self.dialog.withdraw()
        picker = InteractivePicker(self.parent, self._on_picked)
        picker.start()

    def _on_picked(self, data: Dict[str, Any]) -> None:
        self.dialog.deiconify()
        # Populăm automat câmpurile pe baza selecției utilizatorului
        if data.get("window_title"):
            self.ent_win_title.delete(0, tk.END)
            self.ent_win_title.insert(0, f"*{data['window_title'][:25]}*")

        if "region" not in self.rule:
            self.rule["region"] = {}

        self.rule["region"]["rel_x"] = data.get("rel_x", 0.20)
        self.rule["region"]["rel_y"] = data.get("rel_y", 0.30)
        self.rule["region"]["width"] = data.get("width", 320)
        self.rule["region"]["height"] = data.get("height", 60)
        self.var_mode.set("window_relative")

        messagebox.showinfo("FocusPilot", "Zona a fost capturată cu succes de pe ecran!", parent=self.dialog)

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

        # 1. Chenar roșu / alertă
        if self.var_box.get():
            bw = self.var_border_w.get()
            self.preview_canvas.create_rectangle(
                box_x, box_y, box_x + box_w, box_y + box_h,
                outline=self.border_color, width=bw
            )

        # 2. Săgeată indicatoare
        if self.var_arrow.get():
            direction = self.var_arrow_dir.get()
            col = self.arrow_color
            sz = 26
            if direction == "right":
                tip_x = box_x - 10
                tip_y = box_y + (box_h // 2)
                pts = [tip_x - sz, tip_y - 6, tip_x - 12, tip_y - 6, tip_x - 12, tip_y - 12, tip_x, tip_y, tip_x - 12, tip_y + 12, tip_x - 12, tip_y + 6, tip_x - sz, tip_y + 6]
            elif direction == "down":
                tip_x = box_x + (box_w // 2)
                tip_y = box_y - 8
                pts = [tip_x - 6, tip_y - sz, tip_x - 6, tip_y - 12, tip_x - 12, tip_y - 12, tip_x, tip_y, tip_x + 12, tip_y - 12, tip_x + 6, tip_y - 12, tip_x + 6, tip_y - sz]
            else:
                tip_x = box_x - 10
                tip_y = box_y + (box_h // 2)
                pts = [tip_x - sz, tip_y - 6, tip_x, tip_y, tip_x - sz, tip_y + 6]

            self.preview_canvas.create_polygon(pts, fill=col, outline="#8B0000", width=1)

        # 3. Badge Text
        if self.var_badge.get():
            badge_text = self.ent_badge_text.get() or "⚠️ ATENȚIE!"
            bx = box_x
            by = box_y - 24
            approx_w = max(100, len(badge_text) * 8 + 16)
            self.preview_canvas.create_rectangle(bx, by, bx + approx_w, by + 20, fill="#D90429", outline="#FFFFFF", width=1)
            self.preview_canvas.create_text(bx + (approx_w // 2), by + 10, text=badge_text, fill="#FFFFFF", font=FONT_SMALL)

    def _save_and_close(self) -> None:
        name = self.ent_name.get().strip()
        if not name:
            messagebox.showwarning("Atenție", "Introduceți un nume pentru regulă.", parent=self.dialog)
            return

        self.rule["name"] = name
        self.rule["enabled"] = self.var_enabled.get()

        if "trigger" not in self.rule:
            self.rule["trigger"] = {}
        self.rule["trigger"]["window_title_pattern"] = self.ent_win_title.get().strip() or "*"
        self.rule["trigger"]["process_name"] = self.ent_proc.get().strip()
        self.rule["trigger"]["text_condition"] = self.var_cond.get()
        self.rule["trigger"]["search_text"] = self.ent_search_text.get().strip()

        if "visual_cue" not in self.rule:
            self.rule["visual_cue"] = {}
        self.rule["visual_cue"]["box_enabled"] = self.var_box.get()
        self.rule["visual_cue"]["border_color"] = self.border_color
        self.rule["visual_cue"]["border_width"] = self.var_border_w.get()
        self.rule["visual_cue"]["arrow_enabled"] = self.var_arrow.get()
        self.rule["visual_cue"]["arrow_direction"] = self.var_arrow_dir.get()
        self.rule["visual_cue"]["arrow_color"] = self.arrow_color
        self.rule["visual_cue"]["badge_enabled"] = self.var_badge.get()
        self.rule["visual_cue"]["badge_text"] = self.ent_badge_text.get().strip()
        self.rule["visual_cue"]["pulse_animation"] = self.var_pulse.get()

        if "region" not in self.rule:
            self.rule["region"] = {}
        self.rule["region"]["mode"] = self.var_mode.get()

        self.on_save(self.rule)
        self.dialog.destroy()
