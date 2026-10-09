# FocusPilot — Smart Screen & Browser Conditional Formatter

**FocusPilot** este un instrument rezident (Always Awake) creat pentru a preveni erorile de omisiune pe setup-uri multi-monitor (**3 ecrane**). Monitorizează paginile web din browser și aplicațiile desktop deschise, aplicând **formatare condițională vizuală stil Microsoft Excel** (chenare roșii pulsante, săgeți mari de atenționare, badge-uri de alertă) peste secțiunile sau câmpurile critice.

---

## 🌟 Funcționalități Principale

1. **Rulează Permanent & Silențios**:
   - Fără ferestre CMD (`FocusPilot.pyw` / `run_focuspilot.vbs`).
   - Icoană dedicată în Windows System Tray cu punct de stare activ/pauză.
   - Păstrează PC-ul treaz automat (`Always Awake` prin Windows API `SetThreadExecutionState`).
   - Opțiune `Start with Windows` direct din interfață (registru Windows `Run`).

2. **Meniu Bogat în System Tray (Click Dreapta)**:
   - 🖥️ **Deschide Dashboard** (panou principal)
   - ➕ **Creează regulă nouă**
   - 📋 **Reguli Existente** (submeniu dinamic cu fiecare regulă, bifă activ/inactiv și comutare la clic)
   - ⏸️ / ▶️ **Pauză / Reia monitorizarea**
   - 🎯 **Testează repere vizuale** (afișează demo pe ecran)
   - ⚙️ **Setări** (Start with Windows, Hide on launch, interval scanare)
   - ❌ **Ieșire FocusPilot**

3. **Formatare Condițională Stil Excel**:
   - **Filtru Țintă**: Titlu fereastră (ex: `*Siemens Portal*`), URL browser, Proces (ex: `msedge.exe`, `chrome.exe`).
   - **Condiții Text**: Conține text (*contains*), Text exact (*equals*), Începe cu (*starts_with*), Constelație de cuvinte cheie (*cuvinte separate prin ;*), Expresie regulată (*regex*).
   - **Repere Vizuale (Visual Cues)**:
     - Chenar roșu configurabil (culoare, grosime, glow).
     - **Săgeată roșie indicatoare** (`➔`, `⬅`, `⬇`, `⬆`) cu mărime și direcție ajustabile.
     - **Badge de alertă** (ex: `⚠️ MODIFICĂ AICI!`, `CAMP OBLIGATORIU`).
     - Animație de pulsare continuă pentru atragerea atenției.

4. **Multi-Monitor Transparent Click-Through Overlay (3 Ecrane)**:
   - Canvas transparent întins automat peste toate cele 3 monitoare (`SM_XVIRTUALSCREEN`).
   - Utilizează stilurile native Windows `WS_EX_TRANSPARENT | WS_EX_LAYERED` — **utilizatorul poate da click și tasta prin overlay** direct în câmpul formularului, fără blocaje!
   - Selector interactiv de pe ecran: Tragi un dreptunghi peste câmpul dorit și aplicația calculează automat coordonatele și titlul ferestrei.

5. **Integrare Nativă Browser (Playwright & Userscript)**:
   - Include modul Playwright (`integrations/playwright_highlighter.py`) pentru conectare la browser prin CDP.
   - Generează automat script Tampermonkey/Violentmonkey (`integrations/focuspilot_browser_highlighter.user.js`) pentru injectare directă în DOM-ul paginii HTML.

6. **Interfață Siemens Style**:
   - Paletă corporativă: Siemens Petrol (`#00646E`), Siemens Mint/Teal (`#00A3A6`), Accent Orange (`#EB780A`).
   - Comutare instantanee între **Dark Mode** și **Light Mode**.

---

## 🚀 Instalare și Rulare

### Dependențe
Dependențele sunt deja disponibile în mediul tău Python:
```powershell
pip install pystray pillow pywin32 pyautogui playwright
```

### Pornire
- **Dublu clic pe `run_focuspilot.vbs`** (pornire invizibilă 100%, fără flash de consolă).
- Sau dublu clic pe `FocusPilot.pyw`.
- Sau din terminal:
  ```powershell
  pythonw.exe FocusPilot.pyw
  ```

---

## 📁 Structura Proiectului

```
FocusPilot/
├── PROMPT_MASTER_SPECIFICATION.md  # Specificație completă și prompt master
├── PROMPT_MASTER.txt               # Format text pentru copiere în alt asistent AI
├── README.md                       # Acest ghid
├── requirements.txt                # Dependențe
├── .gitignore                      # Reguli ignorare Git
├── FocusPilot.pyw                  # Entry-point executabil fără consolă
├── run_focuspilot.vbs              # Launcher VBS silențios
├── start_FocusPilot.bat            # Script de pornire .bat
├── core/
│   ├── config_manager.py           # Persistență JSON și setări
│   ├── rule_engine.py              # Evaluator de condiții Excel-like
│   ├── monitor_engine.py           # Scanner de fundal pe 3 ecrane
│   ├── autostart.py                # Integrare Windows Registry Run
│   └── keep_awake.py               # SetThreadExecutionState
├── ui/
│   ├── theme.py                    # Paletă culori Siemens (Dark & Light)
│   ├── tray_manager.py             # Meniu System Tray pystray
│   ├── main_window.py              # Dashboard configurare reguli
│   ├── rule_editor_dialog.py       # Editor reguli cu Live Preview
│   ├── settings_dialog.py          # Setări autostart & scanare
│   ├── overlay_cue.py              # Overlay transparent click-through
│   └── interactive_picker.py       # Selector zonă interactiv de pe ecran
├── integrations/
│   ├── playwright_highlighter.py   # Conector Playwright CDP
│   └── userscript_generator.py     # Generator script Tampermonkey
└── assets/
    ├── icon.png                    # Logo grafic
    └── tray_icon.ico               # Icoană Windows
```
