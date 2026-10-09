"""
FocusPilot — Keep Awake Manager
Folosește Windows API SetThreadExecutionState pentru a menține mașina trează
(previne intrarea în Sleep / suspendare ecran) atunci când monitorizarea este activă.
"""

import ctypes
import logging

logger = logging.getLogger(__name__)

ES_CONTINUOUS       = 0x80000000
ES_SYSTEM_REQUIRED  = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED= 0x00000040

_is_awake_active = False


def enable_keep_awake(keep_display_on: bool = False) -> bool:
    """Menține sistemul treaz (previne sleep automat)."""
    global _is_awake_active
    try:
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        if keep_display_on:
            flags |= ES_DISPLAY_REQUIRED
        res = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        _is_awake_active = (res != 0)
        return _is_awake_active
    except Exception as exc:
        logger.warning(f"Eroare SetThreadExecutionState(enable): {exc}")
        return False


def disable_keep_awake() -> bool:
    """Revine la comportamentul normal de economisire energie din Windows."""
    global _is_awake_active
    try:
        res = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        _is_awake_active = False
        return (res != 0)
    except Exception as exc:
        logger.warning(f"Eroare SetThreadExecutionState(disable): {exc}")
        return False


def is_keep_awake_active() -> bool:
    return _is_awake_active
