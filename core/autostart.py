"""
FocusPilot — Autostart Manager (Windows Registry)
Gestionează lansarea automată la pornirea Windows prin cheia de registru:
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
"""

import sys
import os
import winreg

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "FocusPilot"


def get_launch_command() -> str:
    """Returnează comanda completă de rulare în mod silențios."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vbs_path = os.path.join(base_dir, "run_focuspilot.vbs")
    pyw_path = os.path.join(base_dir, "FocusPilot.pyw")

    if os.path.exists(vbs_path):
        return f'wscript.exe "{vbs_path}"'
    
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    return f'"{pythonw}" "{pyw_path}"'


def is_autostart_enabled() -> bool:
    """Verifică dacă aplicația este setată să pornească cu Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart(enable: bool) -> bool:
    """Activează sau dezactivează lansarea automată la pornirea Windows."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enable:
                cmd = get_launch_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            return True
    except Exception as exc:
        print(f"[Autostart] Eroare la modificarea registrului: {exc}")
        return False
