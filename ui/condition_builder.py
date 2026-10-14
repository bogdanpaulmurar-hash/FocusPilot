"""
FocusPilot — Panoul de configurare pentru câmpuri, condiții și marcaje

Interfața pentru regulile de forma „dacă câmpul X are valoarea Z și câmpul Y
are valoarea C, atunci marchează...".

Trei liste, în ordinea în care se completează:

  1. CÂMPURI   De unde se citesc valorile. Fiecare câmp are un nume, pe care
               condițiile și marcajele îl folosesc ca referință — ca numele
               unei celule din Excel.
  2. CONDIȚII  `câmp operator valoare`, legate prin AND sau OR.
  3. MARCAJE   Ce câmp se evidențiază, cu ce formă și ce culoare.

Listele de condiții și marcaje se referă la câmpuri prin nume, deci
dropdown-urile lor se reîmprospătează de fiecare dată când un câmp e adăugat,
șters sau redenumit.
"""

import logging
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox
from typing import Dict, Any, List, Optional, Callable

from core.probe_engine import (OPERATORS, SHAPES, DEFAULT_MARK_STYLE,
                               validate_rule_fields)
from ui.theme import get_theme, FONT_SUBTITLE, FONT_BODY, FONT_BODY_BOLD, FONT_SMALL

logger = logging.getLogger(__name__)

LOCATOR_KINDS = [
    ("Lângă o etichetă (urmărește scroll-ul)", "text_near"),
    ("Punct fix pe ecran", "screen_point"),
    ("Zonă fixă pe ecran", "screen_region"),
    ("Textul în sine", "text_self"),
]

OFFSETS = [
    ("la dreapta etichetei", "right"),
    ("la stânga etichetei", "left"),
    ("sub etichetă", "below"),
    ("deasupra etichetei", "above"),
]

ARROW_DIRECTIONS = [("➔ dreapta", "right"), ("⬅ stânga", "left"),
                    ("⬇ jos", "down"), ("⬆ sus", "up")]


def _label_of(pairs, value, fallback_index=0):
    for label, key in pairs:
        if key == value:
            return label
    return pairs[fallback_index][0]


def _value_of(pairs, label, fallback_index=0):
    for text, key in pairs:
        if text == label:
            return key
    return pairs[fallback_index][1]


class ProbeRow:
    """Un rând de câmp: nume, mod de localizare, parametri, buton de captură."""

    def __init__(self, panel: "ConditionBuilderPanel", data: Dict[str, Any]):
        self.panel = panel
        theme = panel.theme
        locator = dict(data.get("locator") or {})

        self.frame = tk.Frame(panel.probes_host, bg=theme["bg_input"],
                              padx=6, pady=5, bd=1, relief="solid")
        self.frame.pack(fill="x", pady=3)

        top = tk.Frame(self.frame, bg=theme["bg_input"])
        top.pack(fill="x")

        tk.Label(top, text="Nume câmp:", font=FONT_BODY_BOLD, bg=theme["bg_input"],
                 fg=theme["fg_primary"], width=11, anchor="w").pack(side="left")
        self.name = tk.Entry(top, font=FONT_BODY, bg=theme["bg_card"],
                             fg=theme["fg_primary"], relief="flat", width=14,
                             insertbackground=theme["fg_primary"])
        self.name.insert(0, str(data.get("name", "") or ""))
        # Condițiile și marcajele referă câmpul prin nume, deci dropdown-urile
        # lor trebuie să afle imediat despre o redenumire.
        self.name.bind("<KeyRelease>", lambda _e: panel.refresh_references())
        self.name.pack(side="left", padx=(0, 10))

        tk.Label(top, text="Se găsește:", font=FONT_BODY, bg=theme["bg_input"],
                 fg=theme["fg_primary"]).pack(side="left")
        self.kind = tk.StringVar(
            value=_label_of(LOCATOR_KINDS, locator.get("kind", "text_near")))
        kind_box = ttk.Combobox(top, textvariable=self.kind, state="readonly",
                                values=[label for label, _ in LOCATOR_KINDS], width=32)
        kind_box.bind("<<ComboboxSelected>>", lambda _e: self._sync_fields())
        kind_box.pack(side="left", padx=(6, 8))

        tk.Button(top, text="✖", font=FONT_SMALL, bg=theme["bg_input"],
                  fg=theme["alert_red"], relief="flat", bd=0, padx=6,
                  cursor="hand2", command=self.remove).pack(side="right")

        tk.Button(top, text="🎯 Alege de pe Ecran", font=FONT_SMALL,
                  bg=theme["accent"], fg="#FFFFFF", relief="flat", padx=8,
                  cursor="hand2", command=self._pick).pack(side="right", padx=4)

        # ── Rândul pentru localizare după etichetă ──
        self.label_row = tk.Frame(self.frame, bg=theme["bg_input"])
        tk.Label(self.label_row, text="Eticheta:", font=FONT_BODY,
                 bg=theme["bg_input"], fg=theme["fg_primary"],
                 width=11, anchor="w").pack(side="left")
        self.label_text = tk.Entry(self.label_row, font=FONT_BODY, bg=theme["bg_card"],
                                   fg=theme["fg_primary"], relief="flat",
                                   insertbackground=theme["fg_primary"])
        self.label_text.insert(0, str(locator.get("text", "") or ""))
        self.label_text.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.offset = tk.StringVar(
            value=_label_of(OFFSETS, locator.get("offset", "right")))
        self.offset_box = ttk.Combobox(self.label_row, textvariable=self.offset,
                                       state="readonly", width=20,
                                       values=[label for label, _ in OFFSETS])
        self.offset_box.pack(side="left")

        tk.Label(self.label_row, text="sari peste:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left", padx=(8, 2))
        self.skip = tk.StringVar(value=str(locator.get("skip", 0) or 0))
        tk.Spinbox(self.label_row, from_=0, to=9, textvariable=self.skip,
                   width=3, font=FONT_SMALL).pack(side="left")

        # ── Rândul pentru coordonate ──
        self.coord_row = tk.Frame(self.frame, bg=theme["bg_input"])
        self.coords: Dict[str, tk.Entry] = {}
        for key, caption, default in (("x", "X:", 0), ("y", "Y:", 0),
                                      ("w", "Lățime:", 200), ("h", "Înălțime:", 26)):
            tk.Label(self.coord_row, text=caption, font=FONT_BODY,
                     bg=theme["bg_input"], fg=theme["fg_primary"]).pack(side="left",
                                                                        padx=(0, 2))
            entry = tk.Entry(self.coord_row, font=FONT_BODY, bg=theme["bg_card"],
                             fg=theme["fg_primary"], relief="flat", width=6,
                             insertbackground=theme["fg_primary"])
            entry.insert(0, str(locator.get(key, default)))
            entry.pack(side="left", padx=(0, 10))
            self.coords[key] = entry

        # ── Previzualizarea valorii citite ──
        self.preview = tk.Label(self.frame, text="", font=FONT_SMALL,
                                bg=theme["bg_input"], fg=theme["accent"], anchor="w")
        self.preview.pack(fill="x", pady=(3, 0))

        self._sync_fields()

    def _sync_fields(self) -> None:
        """Arată doar câmpurile relevante pentru modul de localizare ales."""
        kind = _value_of(LOCATOR_KINDS, self.kind.get())
        self.label_row.pack_forget()
        self.coord_row.pack_forget()

        if kind in ("text_near", "text_self"):
            self.label_row.pack(fill="x", pady=(4, 0))
            state = "readonly" if kind == "text_near" else "disabled"
            self.offset_box.configure(state=state)
        else:
            self.coord_row.pack(fill="x", pady=(4, 0))
            # O zonă are lățime și înălțime; un punct nu.
            for key in ("w", "h"):
                self.coords[key].configure(
                    state="normal" if kind == "screen_region" else "disabled")

    def _pick(self) -> None:
        kind = _value_of(LOCATOR_KINDS, self.kind.get())
        mode = "region" if kind == "screen_region" else "point"
        self.panel.start_picker(mode, self._apply_pick)

    def _apply_pick(self, data: Dict[str, Any]) -> None:
        """Completează câmpul din ce a fost selectat pe ecran."""
        kind = _value_of(LOCATOR_KINDS, self.kind.get())

        for key, value in (("x", data.get("abs_x", 0)), ("y", data.get("abs_y", 0)),
                           ("w", data.get("width", 200)), ("h", data.get("height", 26))):
            self.coords[key].configure(state="normal")
            self.coords[key].delete(0, tk.END)
            self.coords[key].insert(0, str(int(value)))
        self._sync_fields()

        preview = str(data.get("value_preview", "") or "")
        if preview:
            self.preview.configure(
                text=f"✅ Valoare citită acum: „{preview[:60]}”",
                fg=self.panel.theme["green"])
            # Pentru localizarea după etichetă, textul citit e un punct de
            # plecare bun pentru numele câmpului.
            if kind == "text_near" and not self.label_text.get().strip():
                self.label_text.insert(0, preview[:40])
        else:
            self.preview.configure(
                text="ℹ️ Nu s-a putut citi text la acel punct. Verificați că "
                     "fereastra țintă e vizibilă, sau folosiți o etichetă.",
                fg=self.panel.theme["fg_secondary"])

        if data.get("window_title"):
            self.panel.suggest_window(data["window_title"], data.get("process_name", ""))

    def remove(self) -> None:
        self.frame.destroy()
        if self in self.panel.probe_rows:
            self.panel.probe_rows.remove(self)
        self.panel.refresh_references()

    def to_dict(self) -> Optional[Dict[str, Any]]:
        name = self.name.get().strip()
        if not name:
            return None
        kind = _value_of(LOCATOR_KINDS, self.kind.get())
        locator: Dict[str, Any] = {"kind": kind}

        if kind in ("text_near", "text_self"):
            locator["text"] = self.label_text.get().strip()
            if kind == "text_near":
                locator["offset"] = _value_of(OFFSETS, self.offset.get())
                locator["skip"] = _as_int(self.skip.get(), 0)
        else:
            locator["x"] = _as_int(self.coords["x"].get(), 0)
            locator["y"] = _as_int(self.coords["y"].get(), 0)
            if kind == "screen_region":
                locator["w"] = _as_int(self.coords["w"].get(), 200)
                locator["h"] = _as_int(self.coords["h"].get(), 26)

        return {"name": name, "locator": locator}

    @property
    def probe_name(self) -> str:
        return self.name.get().strip()


class ConditionRow:
    """Un rând de condiție: câmp, operator, valoare."""

    def __init__(self, panel: "ConditionBuilderPanel", data: Dict[str, Any]):
        self.panel = panel
        theme = panel.theme

        self.frame = tk.Frame(panel.conditions_host, bg=theme["bg_input"],
                              padx=6, pady=4, bd=1, relief="solid")
        self.frame.pack(fill="x", pady=2)

        tk.Label(self.frame, text="Dacă", font=FONT_BODY_BOLD, bg=theme["bg_input"],
                 fg=theme["accent"]).pack(side="left", padx=(0, 6))

        self.probe = tk.StringVar(value=str(data.get("probe", "") or ""))
        self.probe_box = ttk.Combobox(self.frame, textvariable=self.probe,
                                      state="readonly", width=14, values=[])
        self.probe_box.pack(side="left")

        self.operator = tk.StringVar(
            value=OPERATORS.get(str(data.get("operator", "contains")),
                                ("conține", True))[0])
        operator_box = ttk.Combobox(
            self.frame, textvariable=self.operator, state="readonly", width=30,
            values=[label for label, _ in OPERATORS.values()])
        operator_box.bind("<<ComboboxSelected>>", lambda _e: self._sync_value_field())
        operator_box.pack(side="left", padx=6)

        self.value = tk.Entry(self.frame, font=FONT_BODY, bg=theme["bg_card"],
                              fg=theme["fg_primary"], relief="flat",
                              insertbackground=theme["fg_primary"])
        self.value.insert(0, str(data.get("value", "") or ""))
        self.value.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.case_sensitive = tk.BooleanVar(value=bool(data.get("case_sensitive", False)))
        tk.Checkbutton(self.frame, text="Aa", variable=self.case_sensitive,
                       font=FONT_SMALL, bg=theme["bg_input"], fg=theme["fg_secondary"],
                       selectcolor=theme["bg_card"],
                       activebackground=theme["bg_input"]).pack(side="left")

        tk.Button(self.frame, text="✖", font=FONT_SMALL, bg=theme["bg_input"],
                  fg=theme["alert_red"], relief="flat", bd=0, padx=6,
                  cursor="hand2", command=self.remove).pack(side="right")

        self._sync_value_field()

    def _sync_value_field(self) -> None:
        """Operatorii ca «este gol» nu au nevoie de o valoare de comparat."""
        key = self._operator_key()
        needs_value = OPERATORS.get(key, ("", True))[1]
        self.value.configure(state="normal" if needs_value else "disabled")

    def _operator_key(self) -> str:
        label = self.operator.get()
        for key, (text, _needs) in OPERATORS.items():
            if text == label:
                return key
        return "contains"

    def set_choices(self, names: List[str]) -> None:
        self.probe_box.configure(values=names)
        if self.probe.get() not in names:
            self.probe.set(names[0] if names else "")

    def remove(self) -> None:
        self.frame.destroy()
        if self in self.panel.condition_rows:
            self.panel.condition_rows.remove(self)

    def to_dict(self) -> Optional[Dict[str, Any]]:
        probe = self.probe.get().strip()
        if not probe:
            return None
        key = self._operator_key()
        return {
            "probe": probe,
            "operator": key,
            "value": self.value.get().strip() if OPERATORS.get(key, ("", True))[1] else "",
            "case_sensitive": self.case_sensitive.get(),
        }


class MarkRow:
    """Un rând de marcaj: câmp țintă, formă, culoare și parametri specifici."""

    def __init__(self, panel: "ConditionBuilderPanel", data: Dict[str, Any]):
        self.panel = panel
        theme = panel.theme
        self.color = str(data.get("color", DEFAULT_MARK_STYLE["color"]))

        self.frame = tk.Frame(panel.marks_host, bg=theme["bg_input"],
                              padx=6, pady=4, bd=1, relief="solid")
        self.frame.pack(fill="x", pady=2)

        row = tk.Frame(self.frame, bg=theme["bg_input"])
        row.pack(fill="x")

        tk.Label(row, text="Marchează", font=FONT_BODY_BOLD, bg=theme["bg_input"],
                 fg=theme["accent"]).pack(side="left", padx=(0, 6))

        self.target = tk.StringVar(value=str(data.get("target", "") or ""))
        self.target_box = ttk.Combobox(row, textvariable=self.target,
                                       state="readonly", width=14, values=[])
        self.target_box.pack(side="left")

        tk.Label(row, text="cu", font=FONT_BODY, bg=theme["bg_input"],
                 fg=theme["fg_primary"]).pack(side="left", padx=4)

        self.shape = tk.StringVar(
            value=SHAPES.get(str(data.get("shape", "box")), SHAPES["box"]))
        shape_box = ttk.Combobox(row, textvariable=self.shape, state="readonly",
                                 width=30, values=list(SHAPES.values()))
        shape_box.bind("<<ComboboxSelected>>", lambda _e: self._sync_options())
        shape_box.pack(side="left", padx=(0, 6))

        self.color_button = tk.Button(row, text="🎨", bg=self.color, fg="#FFFFFF",
                                      font=FONT_SMALL, relief="flat", padx=8,
                                      cursor="hand2", command=self._pick_color)
        self.color_button.pack(side="left")

        tk.Button(row, text="✖", font=FONT_SMALL, bg=theme["bg_input"],
                  fg=theme["alert_red"], relief="flat", bd=0, padx=6,
                  cursor="hand2", command=self.remove).pack(side="right")

        # ── Parametri care depind de formă ──
        self.options = tk.Frame(self.frame, bg=theme["bg_input"])
        self.options.pack(fill="x", pady=(3, 0))

        self.thickness = tk.StringVar(value=str(data.get("thickness", 3)))
        self.opacity = tk.StringVar(value=str(data.get("opacity", 0.30)))
        self.arrow_count = tk.StringVar(value=str(data.get("arrow_count", 1)))
        self.arrow_direction = tk.StringVar(
            value=_label_of(ARROW_DIRECTIONS, data.get("arrow_direction", "right")))
        self.text = tk.StringVar(value=str(data.get("text", "") or ""))
        self.pulse = tk.BooleanVar(value=bool(data.get("pulse", True)))

        self._build_options()
        self._sync_options()

    def _build_options(self) -> None:
        theme = self.panel.theme
        pack = {"side": "left", "padx": (0, 10)}

        self.thickness_box = tk.Frame(self.options, bg=theme["bg_input"])
        tk.Label(self.thickness_box, text="Grosime:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left")
        tk.Spinbox(self.thickness_box, from_=1, to=12, width=3, font=FONT_SMALL,
                   textvariable=self.thickness).pack(side="left", padx=2)

        self.opacity_box = tk.Frame(self.options, bg=theme["bg_input"])
        tk.Label(self.opacity_box, text="Opacitate:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left")
        tk.Spinbox(self.opacity_box, from_=0.05, to=0.90, increment=0.05, width=5,
                   font=FONT_SMALL, textvariable=self.opacity).pack(side="left", padx=2)

        self.arrow_box = tk.Frame(self.options, bg=theme["bg_input"])
        tk.Label(self.arrow_box, text="Direcție:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left")
        ttk.Combobox(self.arrow_box, textvariable=self.arrow_direction,
                     state="readonly", width=11,
                     values=[label for label, _ in ARROW_DIRECTIONS]).pack(side="left",
                                                                            padx=2)
        tk.Label(self.arrow_box, text="câte:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left",
                                                                      padx=(6, 0))
        tk.Spinbox(self.arrow_box, from_=1, to=5, width=3, font=FONT_SMALL,
                   textvariable=self.arrow_count).pack(side="left", padx=2)

        self.text_box = tk.Frame(self.options, bg=theme["bg_input"])
        tk.Label(self.text_box, text="Text:", font=FONT_SMALL,
                 bg=theme["bg_input"], fg=theme["fg_secondary"]).pack(side="left")
        tk.Entry(self.text_box, textvariable=self.text, font=FONT_SMALL, width=26,
                 bg=theme["bg_card"], fg=theme["fg_primary"],
                 relief="flat").pack(side="left", padx=2)

        self.pulse_box = tk.Frame(self.options, bg=theme["bg_input"])
        tk.Checkbutton(self.pulse_box, text="Pulsare", variable=self.pulse,
                       font=FONT_SMALL, bg=theme["bg_input"], fg=theme["fg_secondary"],
                       selectcolor=theme["bg_card"],
                       activebackground=theme["bg_input"]).pack(side="left")

        self._all_boxes = [self.thickness_box, self.opacity_box, self.arrow_box,
                           self.text_box, self.pulse_box]
        self._pack_options = pack

    def _sync_options(self) -> None:
        """Arată doar parametrii care au sens pentru forma aleasă."""
        shape = self._shape_key()
        for box in self._all_boxes:
            box.pack_forget()

        if shape in ("box", "circle", "underline", "strikethrough"):
            self.thickness_box.pack(**self._pack_options)
        if shape == "highlight":
            self.opacity_box.pack(**self._pack_options)
        if shape == "arrow":
            self.arrow_box.pack(**self._pack_options)
        if shape == "badge":
            self.text_box.pack(**self._pack_options)
        if shape != "badge":
            self.pulse_box.pack(**self._pack_options)

    def _shape_key(self) -> str:
        label = self.shape.get()
        for key, text in SHAPES.items():
            if text == label:
                return key
        return "box"

    def _pick_color(self) -> None:
        chosen = colorchooser.askcolor(initialcolor=self.color,
                                       parent=self.frame)[1]
        if chosen:
            self.color = chosen
            self.color_button.configure(bg=chosen)

    def set_choices(self, names: List[str]) -> None:
        self.target_box.configure(values=names)
        if self.target.get() not in names:
            self.target.set(names[0] if names else "")

    def remove(self) -> None:
        self.frame.destroy()
        if self in self.panel.mark_rows:
            self.panel.mark_rows.remove(self)

    def to_dict(self) -> Optional[Dict[str, Any]]:
        target = self.target.get().strip()
        if not target:
            return None
        shape = self._shape_key()
        mark: Dict[str, Any] = {"target": target, "shape": shape,
                                "color": self.color, "pulse": self.pulse.get()}

        if shape in ("box", "circle", "underline", "strikethrough"):
            mark["thickness"] = _as_int(self.thickness.get(), 3)
        if shape == "highlight":
            mark["opacity"] = _as_float(self.opacity.get(), 0.30)
        if shape == "arrow":
            mark["arrow_direction"] = _value_of(ARROW_DIRECTIONS,
                                                self.arrow_direction.get())
            mark["arrow_count"] = _as_int(self.arrow_count.get(), 1)
        if shape == "badge":
            mark["text"] = self.text.get().strip() or "⚠️"
            mark["pulse"] = False
        return mark


class ConditionBuilderPanel:
    """Panoul complet: câmpuri, condiții, marcaje."""

    def __init__(self, parent: tk.Widget, theme_name: str, rule: Dict[str, Any],
                 start_picker: Callable[[str, Callable], None],
                 suggest_window: Optional[Callable[[str, str], None]] = None):
        self.theme = get_theme(theme_name)
        self.start_picker = start_picker
        self.suggest_window = suggest_window or (lambda _t, _p: None)

        self.probe_rows: List[ProbeRow] = []
        self.condition_rows: List[ConditionRow] = []
        self.mark_rows: List[MarkRow] = []

        self._build(parent, rule)

    # ── Construcția interfeței ───────────────────────────────────────────────

    def _build(self, parent: tk.Widget, rule: Dict[str, Any]) -> None:
        theme = self.theme
        self.container = tk.Frame(parent, bg=theme["bg_card"])
        self.container.pack(fill="x")

        intro = tk.Label(
            self.container, anchor="w", justify="left", font=FONT_SMALL,
            bg=theme["bg_card"], fg=theme["fg_secondary"],
            text="Ca în Excel: definești câmpuri (ca niște celule), scrii condiții "
                 "pe ele, apoi alegi ce se marchează.\n"
                 "Exemplu: dacă «status» este exact «Wait for Merge» ȘI «cantitate» "
                 "este mai mare decât 0, încercuiește «cantitate»."
        )
        intro.pack(fill="x", pady=(0, 8))

        # ── 1. Câmpuri ──
        self.probes_host = self._section(
            "1. Câmpuri — de unde se citesc valorile",
            "Fiecare câmp primește un nume, folosit mai jos ca referință.",
            "➕ Adaugă Câmp", self.add_probe)
        for probe in (rule.get("probes") or []):
            self.probe_rows.append(ProbeRow(self, probe))

        # ── 2. Condiții ──
        self.conditions_host = self._section(
            "2. Condiții — când se declanșează regula",
            "Toate condițiile sunt verificate pe valorile citite din câmpuri.",
            "➕ Adaugă Condiție", self.add_condition)

        logic_row = tk.Frame(self.conditions_host.master, bg=theme["bg_card"])
        logic_row.pack(fill="x", pady=(2, 4), before=self.conditions_host)
        tk.Label(logic_row, text="Relația dintre condiții:", font=FONT_BODY,
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(side="left")
        self.logic = tk.StringVar(
            value="AND (toate simultan)"
            if str(rule.get("conditions_logic", "AND")).upper() == "AND"
            else "OR (oricare)")
        ttk.Combobox(logic_row, textvariable=self.logic, state="readonly", width=22,
                     values=["AND (toate simultan)", "OR (oricare)"]).pack(side="left",
                                                                            padx=8)
        for condition in (rule.get("conditions") or []):
            self.condition_rows.append(ConditionRow(self, condition))

        # ── 3. Marcaje ──
        self.marks_host = self._section(
            "3. Marcaje — ce se evidențiază și cum",
            "Mai multe marcaje pot sta pe câmpuri diferite, cu forme și culori diferite.",
            "➕ Adaugă Marcaj", self.add_mark)
        for mark in (rule.get("marks") or []):
            self.mark_rows.append(MarkRow(self, mark))

        self.refresh_references()

    def _section(self, title: str, hint: str, button_text: str,
                 command: Callable) -> tk.Frame:
        theme = self.theme
        header = tk.Frame(self.container, bg=theme["bg_card"])
        header.pack(fill="x", pady=(10, 2))

        tk.Label(header, text=title, font=FONT_SUBTITLE, bg=theme["bg_card"],
                 fg=theme["fg_primary"]).pack(side="left")
        tk.Button(header, text=button_text, font=FONT_SMALL, bg=theme["primary_btn"],
                  fg="#FFFFFF", relief="flat", padx=10, pady=2, cursor="hand2",
                  command=command).pack(side="right")

        tk.Label(self.container, text=hint, font=FONT_SMALL, bg=theme["bg_card"],
                 fg=theme["fg_muted"], anchor="w").pack(fill="x")

        host = tk.Frame(self.container, bg=theme["bg_card"])
        host.pack(fill="x", pady=(2, 0))
        return host

    # ── Adăugare de rânduri ──────────────────────────────────────────────────

    def add_probe(self) -> None:
        index = len(self.probe_rows) + 1
        self.probe_rows.append(ProbeRow(self, {"name": f"câmp{index}"}))
        self.refresh_references()

    def add_condition(self) -> None:
        if not self._probe_names():
            messagebox.showinfo(
                "FocusPilot",
                "Adăugați mai întâi un câmp: o condiție se referă la un câmp.",
                parent=self.container)
            return
        self.condition_rows.append(ConditionRow(self, {}))
        self.refresh_references()

    def add_mark(self) -> None:
        if not self._probe_names():
            messagebox.showinfo(
                "FocusPilot",
                "Adăugați mai întâi un câmp: un marcaj se plasează pe un câmp.",
                parent=self.container)
            return
        self.mark_rows.append(MarkRow(self, {}))
        self.refresh_references()

    # ── Sincronizarea referințelor la câmpuri ────────────────────────────────

    def _probe_names(self) -> List[str]:
        seen, names = set(), []
        for row in self.probe_rows:
            name = row.probe_name
            if name and name not in seen:
                seen.add(name)
                names.append(name)
        return names

    def refresh_references(self) -> None:
        """Reîmprospătează dropdown-urile care referă câmpuri prin nume."""
        names = self._probe_names()
        for row in self.condition_rows:
            row.set_choices(names)
        for row in self.mark_rows:
            row.set_choices(names)

    # ── Serializare și validare ──────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.probe_rows) and bool(self.condition_rows)

    def to_rule_fields(self) -> Dict[str, Any]:
        probes = [p for p in (row.to_dict() for row in self.probe_rows) if p]
        conditions = [c for c in (row.to_dict() for row in self.condition_rows) if c]
        marks = [m for m in (row.to_dict() for row in self.mark_rows) if m]
        return {
            "probes": probes,
            "conditions": conditions,
            "conditions_logic": "AND" if self.logic.get().startswith("AND") else "OR",
            "marks": marks,
        }

    def validate(self) -> Optional[str]:
        """
        Întoarce un mesaj de eroare, sau None dacă totul e în ordine.

        Regulile de validare stau în core.probe_engine, ca să poată fi testate
        fără interfață și ca să fie aceleași oriunde se creează o regulă.
        """
        return validate_rule_fields(self.to_rule_fields())


def _as_int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
