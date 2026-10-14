"""
FocusPilot — Overlay de repere vizuale pe toate monitoarele

Primește reperele detectate de MonitorEngine și le desenează prin ShapePool.

Există două feluri de reguli, dar un singur traseu de desen: regulile clasice
(`visual_cue`) sunt convertite în marcaje, exact ca regulile cu câmpuri și
condiții. Așa o singură implementare de desen deservește ambele, și orice
formă nouă devine disponibilă pentru ambele.
"""

import logging
import tkinter as tk
from typing import Dict, Any, List, Optional

from core.mark_geometry import marks_for_cue
from ui.shape_overlay import ShapePool

logger = logging.getLogger(__name__)

# Cadența animației de pulsare. Mai rar decât cele 90 ms din varianta
# anterioară: la fiecare tic se repoziționează toate ferestrele de formă.
PULSE_INTERVAL_MS = 140

MAX_CUES = 8          # câte reguli pot fi afișate simultan


class MultiScreenOverlay:
    """Desenează reperele vizuale pe toate monitoarele, fără a bloca mouse-ul."""

    def __init__(self):
        self.master: Optional[tk.Misc] = None
        self.active_cues: List[Dict[str, Any]] = []
        self._pool: Optional[ShapePool] = None
        self._pulse_phase = 0.0
        self._pulse_job = None
        self._last_signature = None

    def init_overlay(self, master: tk.Misc) -> None:
        self.master = master
        self._pool = ShapePool(master)
        self._schedule_pulse()

    # ── Interfață publică ────────────────────────────────────────────────────

    def update_cues(self, cues: List[Dict[str, Any]]) -> None:
        """
        Primește reperele de afișat.

        Apelat din firul de monitorizare, deci desenarea se programează pe
        firul de interfață Tkinter.
        """
        if not self.master:
            return
        try:
            self.master.after(0, self._render, list(cues or []))
        except RuntimeError:
            pass          # interfața se închide

    def shutdown(self) -> None:
        if self._pulse_job and self.master:
            try:
                self.master.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        if self._pool:
            self._pool.destroy()
            self._pool = None

    # ── Desenare ─────────────────────────────────────────────────────────────

    def _render(self, cues: List[Dict[str, Any]]) -> None:
        if not self.master or self._pool is None:
            return

        self.active_cues = cues[:MAX_CUES]
        marks: List[Dict[str, Any]] = []
        for cue in self.active_cues:
            marks.extend(marks_for_cue(cue))

        drawn = self._pool.draw_marks(marks, self._pulse_phase)

        signature = (len(self.active_cues),
                     tuple(str(c.get("rule_name", ""))[:40] for c in self.active_cues))
        if signature != self._last_signature:
            self._last_signature = signature
            if self.active_cues:
                logger.info("[OVERLAY] %d regulă(i), %d formă(e): %s",
                            len(self.active_cues), drawn,
                            ", ".join(signature[1]))
            else:
                logger.info("[OVERLAY] Repere ascunse.")

    # ── Animația de pulsare ──────────────────────────────────────────────────

    def _schedule_pulse(self) -> None:
        if not self.master:
            return
        try:
            self._pulse_job = self.master.after(PULSE_INTERVAL_MS, self._on_pulse)
        except RuntimeError:
            self._pulse_job = None

    def _on_pulse(self) -> None:
        self._pulse_phase += 0.35
        if self.active_cues and self._pool is not None:
            # Se recalculează doar geometria formelor. Varianta anterioară
            # reaplica deiconify / lift / stiluri pe fiecare fereastră la
            # fiecare tic, ceea ce muta focusul din câmpul în care scria
            # utilizatorul și producea pâlpâire.
            marks: List[Dict[str, Any]] = []
            for cue in self.active_cues:
                marks.extend(marks_for_cue(cue))
            try:
                self._pool.draw_marks(marks, self._pulse_phase)
            except Exception as exc:
                logger.debug("Reîmprospătarea formelor a eșuat: %s", exc)
        self._schedule_pulse()
