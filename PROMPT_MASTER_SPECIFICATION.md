# MASTER SPECIFICATION & PROMPT — FOCUSPILOT (v1.0)
> **Data:** 2026-10-09  
> **Autor:** Bogdan Paul Murar  
> **Nume Proiect:** `FocusPilot` — Intelligent Screen & Browser Conditional Formatter & Visual Cue Engine  
> **Scop:** Acest document servește ca specificație completă și PROMPT MASTER pentru realizarea sau continuarea dezvoltării aplicatiei de către orice asistent AI sau dezvoltator uman.

---

## 1. SCOPUL ȘI VIZIUNEA APLICAȚIEI

Utilizatorul lucrează pe un setup cu **3 monitoare** și accesează frecvent pagini web (în browser) și aplicații desktop unde anumite câmpuri, texte sau secțiuni necesită atenție critică (modificări obligatorii). Dacă aceste câmpuri sunt omise, apar erori umane în fluxul de lucru.

**FocusPilot** rezolvă această problemă printr-un sistem de **Formatare Condițională vizuală inteligentă (stil Microsoft Excel)** aplicat peste orice ecran sau browser:
1. **Always Awake / Resident Daemon**: Rulează silențios în background fără fereastră CMD (`.pyw` / VBS silent launcher).
2. **System Tray Integration**: Icoană dedicată în Windows System Tray cu indicator activ/pauză și meniu bogat la click dreapta (Quick toggle reguli, Deschide Dashboard, Adaugă regulă, Setări, Ieșire).
3. **Formatare Condițională Avansată**:
   - Criterii de detecție: URL / Titlu pagină browser, Titlu fereastră desktop, Nume proces (`msedge.exe`, `chrome.exe`, etc.), Text exact, Text conține, Expresie regulată (Regex) sau Constelație de cuvinte cheie.
   - Criterii de coordonate/zonă: Întreaga fereastră, selector interactiv (Bounding box / Snip area), sau selector DOM pentru browser.
4. **Repere Vizuale Frapante (Visual Cues)**:
   - Cadru roșu / chenar evidențiat (grosime și stil configurabil).
   - Culoare fundal semitransparentă (Highlighter effect).
   - **Săgeată roșie indicatoare** (`➔`, `⬇`, `⬆`, `⬅` sau simboluri de alertă `⚠️`, `🚨`, `⚡`) cu animație de pulsare / atenționare.
   - Badge / Etichetă plutitoare cu mesaj personalizat (ex: `MODIFICĂ AICI!`, `CAMP OBLIGATORIU`, `VERIFICĂ VALOARE`).
5. **Multi-Monitor Transparent Click-Through Overlay**:
   - Canvas transparent întins pe toate cele 3 monitoare (`SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`, `SM_CYVIRTUALSCREEN`).
   - Fereastra overlay folosește stilurile Windows `WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW` — utilizatorul poate da click și scrie prin overlay direct în câmpul evidențiat, fără ca overlay-ul să blocheze mouse-ul sau tastatura!
6. **Browser DOM Integration (Playwright / Userscript)**:
   - Pe lângă overlay-ul nativ Windows, aplicația poate injecta direct CSS/JS în browser prin Playwright sau poate genera un Userscript (Tampermonkey) actualizat automat cu toate regulile de formatare condițională.
7. **UI Siemens-Inspired**:
   - Paletă modernă corporativă Siemens (Teal `#00646E`, Petrol `#00A3A6`, Accent Orange `#EB780A`, Slate Gray).
   - Suport complet pentru **Light Mode** și **Dark Mode** toggleabil din GUI.
   - Setări standard: Start with Windows (Registry Run), Hide in tray on start, Keep PC awake (`SetThreadExecutionState`).

---

## 2. ARHITECTURA TEHNICĂ ȘI STRUCTURA DE FIȘIERE

```
FocusPilot/
├── PROMPT_MASTER_SPECIFICATION.md  # Această specificație completă și prompt master
├── PROMPT_MASTER.txt               # Versiune text simplu pentru copiere rapidă în LLM
├── README.md                       # Documentație de instalare, utilizare și comenzi rapide
├── requirements.txt                # Dependențe Python (pystray, Pillow, pywin32, pyautogui, playwright)
├── .gitignore                      # Reguli Git ignorare cache, loguri, fișiere OS
├── FocusPilot.pyw                  # Entry-point executabil fără consolă CMD
├── run_focuspilot.vbs              # Launcher VBS invizibil 100% fără flash de fereastră
├── start_FocusPilot.bat            # Script de pornire standard (cu verificare dependențe)
├── core/
│   ├── __init__.py
│   ├── config_manager.py          # Gestionare JSON pentru setări globale și lista de reguli
│   ├── rule_engine.py             # Motor de evaluare a condițiilor (Text, Regex, Window, URL)
│   ├── monitor_engine.py          # Scanner de fundal (detectează ferestre active pe cele 3 monitoare)
│   ├── autostart.py               # Integrare Windows Registry (HKCU\...\Run)
│   └── keep_awake.py              # Windows API kernel32.SetThreadExecutionState
├── ui/
│   ├── __init__.py
│   ├── theme.py                   # Temă Siemens (Paletă culori Light / Dark, fonturi, stiluri ttk)
│   ├── tray_manager.py            # Meniu de system tray (pystray) cu meniu dinamic de reguli
│   ├── main_window.py             # Dashboard principal (Listă reguli, Toggle, Adăugare, Editare, Ștergere)
│   ├── rule_editor_dialog.py      # Dialog de creare/editare regulă stil Excel cu Live Preview
│   ├── settings_dialog.py         # Setări aplicatie (Start with Windows, Hide on launch, Interval scan)
│   ├── overlay_cue.py             # Fereastră transparentă click-through pe cele 3 monitoare
│   └── interactive_picker.py      # Instrument interactiv de selectare zonă de pe ecran (Snipper / Crosshair)
├── integrations/
│   ├── __init__.py
│   ├── playwright_highlighter.py  # Conector Playwright pentru inspecție / evidențiere browser
│   └── userscript_generator.py    # Generator automat de script Tampermonkey/Violentmonkey
└── assets/
    ├── icon.png                   # Logo grafic de rezoluție înaltă
    └── tray_icon.ico              # Icoană format ICO pentru tray și ferestre
```

---

## 3. MODELUL DE DATE (RULE SCHEMA)

Fiecare regulă de formatare condițională este stocată în `config.json` conform următoarei structuri:

```json
{
  "id": "rule_20261009_001",
  "name": "Evidențiere Câmp Obligatoriu Portal Siemens",
  "enabled": true,
  "trigger": {
    "target_type": "browser_or_window", 
    "window_title_pattern": "*Siemens Portal*",
    "url_pattern": "*portal.siemens.cloud/*",
    "process_name": "msedge.exe",
    "text_condition": "contains",
    "search_text": "Câmp Obligatoriu",
    "case_sensitive": false,
    "is_regex": false
  },
  "visual_cue": {
    "box_enabled": true,
    "border_color": "#FF0000",
    "border_width": 3,
    "fill_color": "#FF4444",
    "fill_opacity": 0.25,
    "arrow_enabled": true,
    "arrow_direction": "right",
    "arrow_color": "#FF0000",
    "arrow_size": 32,
    "badge_enabled": true,
    "badge_text": "⚠️ VERIFICĂ / MODIFICĂ!",
    "badge_bg": "#FF0000",
    "badge_fg": "#FFFFFF",
    "pulse_animation": true
  },
  "region": {
    "mode": "window_relative",
    "rel_x": 0.15,
    "rel_y": 0.35,
    "width": 320,
    "height": 55,
    "monitor_index": -1
  }
}
```

---

## 4. DESIGN ȘI GHID DE CULORI (SIEMENS THEME)

- **Siemens Petrol / Teal Primar:** `#00646E`
- **Siemens Mint / Teal Secundar:** `#00A3A6`
- **Siemens Accent Orange:** `#EB780A`
- **Dark Mode Background:** `#181F25` (Card background: `#212A32`, Border: `#2C3742`)
- **Light Mode Background:** `#F4F6F8` (Card background: `#FFFFFF`, Border: `#DCE2E6`)
- **Alert / Highlighting Red:** `#E60000` (Glow: `#FF4D4D`, Soft fill: `rgba(230,0,0,0.18)`)
- **Warning Yellow/Amber:** `#FFB900`
- **Success Green:** `#009966`

---

## 5. EXTENSIA INTELIGENTĂ DE DETECȚIE ȘI SELECTARE INTERACTIVĂ (UPDATE v1.2)

1. **Interactive Snipper / Crosshair Picker (`ui/interactive_picker.py`)**:
   - Când utilizatorul apasă *Alege Interactiv de pe Ecran*, Dashboard-ul și dialogul de configurare se ascund (`withdraw()`) și eliberează grab-ul modal (`grab_release()`).
   - Ecranul devine complet curat, permițând utilizatorului să vadă pagina web sau aplicația țintă pe oricare din cele 3 monitoare.
   - Trasează un dreptunghi cu mouse-ul peste câmpul, butonul sau eticheta dorită.
   - Motorul parcurge ordinea Z (Z-Order) a ferestrelor Windows excluzând canvasul de selecție și identifică:
     * Fereastra reală (`window_title`, `HWND`, `window_rect`)
     * Numele procesului real (`chrome.exe`, `msedge.exe`, etc.)
     * Coordonatele absolute (`abs_x`, `abs_y`, `width`, `height`) și relative (`rel_x`, `rel_y`, `rel_w`, `rel_h`).
   - Apăsarea tastei `[Escape]` anulează imediat selecția și readuce ferestrele în prim-plan.

2. **Dropdown Inteligent pentru Aplicații & Browsere**:
   - Include opțiunea unificată `browser (Edge + Chrome)` — regula se aplică indiferent dacă pagina este deschisă în Microsoft Edge sau Google Chrome.
   - Scanează automat la deschidere toate aplicațiile active pe mașină și le listează în dropdown cu nume proces și titlu fereastră pentru selecție cu un singur clic.

3. **Formatare Coordonate Exacte la Testare și Rulare**:
   - Dacă o regulă a fost capturată interactiv, butonul *Testează* desenează reperul vizual (chenar, săgeată, badge) exact la coordonatele fizice selectate de utilizator, nu doar în centrul ecranului.
   - Evaluarea regulilor pe ferestre active (`core/rule_engine.py`) declanșează reperul când fereastra țintă este activă, chiar dacă textul din interiorul DOM-ului HTML nu se află în bara de titlu a ferestrei.

---

## 6. ANALIZĂ TEHNICĂ: DE CE METODA CLASICĂ OVERLAY TKINTER A EȘUAT ȘI SOLUȚIA SILKTEST-LIKE (UPDATE v2.0)

### 6.1. De ce a eșuat Overlay-ul Tkinter `-transparentcolor`:
1. **Compositing Hardware Chrome/Edge (DirectX/DWM):**
   Browserele moderne folosesc accelerare GPU cu suprafețe DirectX swapchain. O fereastră Tkinter `WS_EX_LAYERED` cu transparență cromatică (`-transparentcolor`) este deseori ignorată de DWM sau acoperită de swapchain-ul GPU al browserului.
2. **Absența Mapării Reale de Controale (Lipsa arborelui de obiecte):**
   Spre deosebire de unelte profesionale de testare precum **SilkTest, TestComplete sau Playwright Inspect**, capturarea doar prin coordonate relative de fereastră e vulnerabilă la scroll, zoom, tab-uri deschise și redimensionare.

---

### 6.2. Arhitectura SilkTest-Like Propusă (Plan de Implementare):

#### Pilonul 1: Inspecție și Formatare Nativă DOM în Browser (DevTools / CDP / Userscript)
* **Cum funcționează SilkTest în Web:** SilkTest injectează un agent sau comunică prin DevTools Protocol (CDP) direct cu pagina web.
* **Formatare directă în DOM:** În loc să desenăm o fereastră deasupra browserului, injectăm stilul direct pe elementul HTML:
  ```javascript
  // SilkTest-like element highlighter
  element.style.setProperty('outline', '4px solid #FF0000', 'important');
  element.style.setProperty('box-shadow', '0 0 12px rgba(255,0,0,0.8)', 'important');
  ```
* **Selectare Interactivă ca în F12 DevTools:**
  La activarea selecției, utilizatorul trece mouse-ul peste elementele paginii, elementele se aprind cu contur albastru/roșu (hover inspector), iar la clic se capturează:
  - Selectorul CSS (`#categoryId`, `input[name="category"]`, `div.gsp-ticket-header`)
  - XPath-ul exact
  - Textul interior (`innerText`)
  - Poziția `getBoundingClientRect()`

#### Pilonul 2: SilkTest-Like Desktop Control Inspector (Windows UI Automation / UIA)
* Pentru aplicațiile desktop native (non-browser), se folosește arborele Windows UI Automation (`UIAutomationCore.dll`):
  - Fiecare buton, câmp text, listă este un `AutomationElement`.
  - Proprietăți extrase: `AutomationId`, `Name`, `ClassName`, `ControlType`, `BoundingRectangle`.
* **Evidențiere Vizuală prin 4 Bare Solid-Color (Frame Border):**
  În loc de o fereastră gigant transparentă pe 3 ecrane care se pierde în DWM, se creează **4 mici ferestre TopMost opace de 3px grosime** (Sus, Jos, Stânga, Dreapta) care încadrează fizic dreptunghiul elementului. Această metodă nu folosește transparență și este 100% garantată vizual peste orice aplicație cu accelerare hardware.

---

## 7. FOAIE DE PARCURS PENTRU CONTINUARE (ROADMAP PENTRU URMATORUL MODEL AI)

Când se reia dezvoltarea cu buget reîncărcat sau alt model AI:
1. **Pasul 1:** Implementarea modului `4-Bar Frame Border` în `ui/overlay_cue.py` — înlocuirea canvasului transparent cu 4 bare subțiri de culoare solidă roșie care îmbracă zona selectată fără erori de transparență.
2. **Pasul 2:** Implementarea modulului `integrations/browser_inspector.py` bazat pe Playwright / CDP pentru a deschide Chrome/Edge cu portul de depanare activat (`--remote-debugging-port=9222`) și a culege selectorii DOM la clic (SilkTest style).
3. **Pasul 3:** Conectarea scriptului Tampermonkey din `integrations/focuspilot_browser_highlighter.user.js` direct în browserul de zi cu zi pentru formatare nativă fără consum de resurse.
