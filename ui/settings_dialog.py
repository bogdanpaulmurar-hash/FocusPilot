"""
FocusPilot — Settings Dialog
Panou de configurare generală: Autostart cu Windows, Rulare silențioasă în Tray,
Keep Awake (Sistem treaz), Interval de scanare și Temă Siemens (Dark / Light).
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional, Callable

from core.config_manager import ConfigManager
from core.autostart import set_autostart, is_autostart_enabled
from core.keep_awake import enable_keep_awake, disable_keep_awake
from ui.theme import get_theme, FONT_TITLE, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL

logger = logging.getLogger(__name__)


class SettingsDialog:
    """Fereastră modală pentru setările generale ale aplicației FocusPilot."""

    def __init__(self, parent: tk.Toplevel, config_manager: ConfigManager, on_settings_changed: Callable[[], None]):
        self.parent = parent
        self.cfg = config_manager
        self.on_settings_changed = on_settings_changed

        self.theme_name = self.cfg.get_setting("theme", "dark")
        self.theme = get_theme(self.theme_name)

        self.dialog: Optional[tk.Toplevel] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("⚙️ Setări Generale FocusPilot")
        self.dialog.geometry("540x520")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg=self.theme["bg_main"])
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        content = tk.Frame(self.dialog, bg=self.theme["bg_main"], padx=20, pady=16)
        content.pack(fill="both", expand=True)

        # Header
        tk.Label(
            content, text="⚙️ Preferințe și Comportament Sistem",
            font=FONT_TITLE, bg=self.theme["bg_main"], fg=self.theme["accent"]
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            content, text="Configurați pornirea cu Windows, modul silențios în tray și rata de scanare.",
            font=FONT_SMALL, bg=self.theme["bg_main"], fg=self.theme["fg_secondary"]
        ).pack(anchor="w", pady=(0, 14))

        # ── Card: Lansare & Background ──
        card1 = self._create_card(content, "Pornire și Sistem de Operare")

        # 1. Start with Windows
        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())
        chk_autostart = tk.Checkbutton(
            card1, text="Pornește automat odată cu Windows (Start with Windows)",
            variable=self.var_autostart, font=FONT_BODY_BOLD,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            selectcolor=self.theme["bg_input"], activebackground=self.theme["bg_card"],
            command=self._toggle_autostart
        )
        chk_autostart.pack(anchor="w", pady=4)

        # 2. Hide in tray after start
        self.var_hide_tray = tk.BooleanVar(value=self.cfg.get_setting("hide_on_start", True))
        chk_hide = tk.Checkbutton(
            card1, text="Ascunde în System Tray la pornire (Hide in Tray after start)",
            variable=self.var_hide_tray, font=FONT_BODY,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            selectcolor=self.theme["bg_input"], activebackground=self.theme["bg_card"]
        )
        chk_hide.pack(anchor="w", pady=4)

        # 3. Keep Awake
        self.var_keep_awake = tk.BooleanVar(value=self.cfg.get_setting("keep_awake", True))
        chk_awake = tk.Checkbutton(
            card1, text="Menține sistemul treaz (Always Awake - previne Sleep/Suspendare)",
            variable=self.var_keep_awake, font=FONT_BODY,
            bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            selectcolor=self.theme["bg_input"], activebackground=self.theme["bg_card"]
        )
        chk_awake.pack(anchor="w", pady=4)

        # ── Card: Scanare & Temă ──
        card2 = self._create_card(content, "Scanare Monitoare și Aspect Vizual")

        # Rata de scanare
        row_poll = tk.Frame(card2, bg=self.theme["bg_card"])
        row_poll.pack(fill="x", pady=6)
        tk.Label(row_poll, text="Interval scanare ecrane (sec):", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")

        current_poll = self.cfg.get_setting("poll_interval_sec", 1.0)
        self.var_poll = tk.DoubleVar(value=current_poll)
        scale_poll = tk.Scale(
            row_poll, from_=0.2, to=3.0, resolution=0.1, orient="horizontal",
            variable=self.var_poll, bg=self.theme["bg_card"], fg=self.theme["fg_primary"],
            highlightthickness=0, length=180
        )
        scale_poll.pack(side="right")

        # Temă
        row_theme = tk.Frame(card2, bg=self.theme["bg_card"])
        row_theme.pack(fill="x", pady=6)
        tk.Label(row_theme, text="Temă Interfață (Siemens Style):", font=FONT_BODY, bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(side="left")

        self.var_theme = tk.StringVar(value=self.theme_name)
        cb_theme = ttk.Combobox(row_theme, textvariable=self.var_theme, values=["dark", "light"], state="readonly", width=12)
        cb_theme.pack(side="right")

        # Buton Salvează
        btn_row = tk.Frame(content, bg=self.theme["bg_main"])
        btn_row.pack(fill="x", pady=(16, 0))

        btn_save = tk.Button(
            btn_row, text="💾 Salvează și Închide", font=FONT_BODY_BOLD,
            bg=self.theme["primary_btn"], fg="#FFFFFF", relief="flat",
            padx=20, pady=6, command=self._save_settings
        )
        btn_save.pack(side="right")

    def _create_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        card = tk.Frame(parent, bg=self.theme["bg_card"], bd=1, relief="solid")
        card.pack(fill="x", pady=8)
        lbl = tk.Label(card, text=title, font=FONT_SUBTITLE, bg=self.theme["bg_card"], fg=self.theme["accent"])
        lbl.pack(anchor="w", padx=12, pady=(10, 4))
        inner = tk.Frame(card, bg=self.theme["bg_card"])
        inner.pack(fill="x", padx=12, pady=(0, 10))
        return inner

    def _toggle_autostart(self) -> None:
        target_state = self.var_autostart.get()
        success = set_autostart(target_state)
        if not success:
            messagebox.showwarning("Atenție", "Nu s-a putut actualiza cheia de registru Windows Run.", parent=self.dialog)
            self.var_autostart.set(not target_state)

    def _save_settings(self) -> None:
        self.cfg.set_setting("hide_on_start", self.var_hide_tray.get(), auto_save=False)
        self.cfg.set_setting("keep_awake", self.var_keep_awake.get(), auto_save=False)
        self.cfg.set_setting("poll_interval_sec", round(self.var_poll.get(), 2), auto_save=False)
        self.cfg.set_setting("start_with_windows", self.var_autostart.get(), auto_save=False)

        new_theme = self.var_theme.get()
        self.cfg.set_setting("theme", new_theme, auto_save=True)

        if self.var_keep_awake.get():
            enable_keep_awake()
        else:
            disable_keep_awake()

        self.on_settings_changed()
        self.dialog.destroy()
