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

## 6. ARHITECTURA VIZUALĂ SOLID FRAME BORDER ȘI SINCRONIZAREA LA SCROLL (UPDATE v2.1)

### 6.1. Sistemul Solid Frame Border (4 Bare Opace TopMost):
* **Fără SilkTest:** Instrumentul SilkTest a fost doar un exemplu de referință conceptuală. FocusPilot folosește propriul sistem nativ Python numit **Solid Frame Border Overlay**.
* **Cum funcționează:** Se generează 4 ferestre independente `tk.Toplevel` opace de culoare solidă roșie (`#FF0000`) cu grosime configurabilă (3-6px), plus o fereastră dedicată pentru Săgeata triunghiulară și o fereastră pentru Badge-ul de text.
* **Avantaj:** 100% vizibilitate peste suprafețele DirectX/GPU din Google Chrome și Microsoft Edge, fără probleme de transparență DWM, păstrând în același timp stilul click-through (`WS_EX_TRANSPARENT`).

---

### 6.2. Sincronizarea cu Scroll-ul în Paginile Web (Problema & Soluția):
* **Problema Scroll-ului Desktop:** Un overlay desktop plasează barele roșii la coordonate fixe pe ecran față de fereastra Chrome. Când utilizatorul derulează (scroll) pagina web în jos sau în sus, textul din pagină se mișcă, dar chenarul desktop rămâne la poziția inițială a ferestrei.
* **Soluția Nativă Web (Userscript / DOM Injection):**
  Pentru pagini web scrollabile (cum este TIMA Web Gateway), FocusPilot include generatorul de Userscript din `integrations/focuspilot_browser_highlighter.user.js`:
  1. Scriptul se instalează cu 1 clic în browser prin extensia **Tampermonkey** sau **Violentmonkey**.
  2. Scriptul găsește automat elementul HTML după text (`XPath / querySelector`) și îi aplică stilul `outline: 4px solid #FF0000 !important;` direct pe nodul DOM.
  3. **Rezultat la Scroll:** Chenarul roșu este atașat fizic de elementul HTML — când dai scroll în pagină, chenarul se deplasează perfect sincronizat odată cu textul!

---

### 6.3. Durata de Afișare Configurabilă (`duration_sec`):
* Fiecare regulă permite setarea opțională a duratei de afișare:
  - `0` sau lăsat gol: Reperul rămâne afișat **permanent** cât timp fereastra țintă este deschisă și activă.
  - Valoare numerică (ex: `5` secunde): Reperul vizual atrage atenția timp de 5 secunde de la deschiderea/activarea ferestrei, după care se retrage automat pentru a nu deranja lucrul utilizatorului. La revenirea pe acea fereastră, timerul pornește din nou.

---

## 7. FOAIE DE PARCURS PENTRU CONTINUARE (ROADMAP PENTRU URMATORUL MODEL AI)

1. **Pasul 1:** Extinderea selectorului interactiv pentru a extrage și selectori CSS / XPath din DOM când fereastra țintă este un browser (Chrome/Edge).
2. **Pasul 2:** Conectarea automată a generatorului `integrations/focuspilot_browser_highlighter.user.js` cu extensia de browser a utilizatorului pentru sincronizare instantanee fără reîncărcare manuală.
3. **Pasul 3:** Suport pentru captură de control nativ Windows UI Automation (`UIAutomationCore.dll`) pentru aplicații desktop clasice (SAP, Office, ERP) unde ID-ul de control rămâne stabil la redimensionare.
