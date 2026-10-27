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
   - **Filtru Țintă**: Titlu fereastră (ex: `*Portal Intern*`), URL browser, Proces (ex: `msedge.exe`, `chrome.exe`).
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
   - Injectare directă prin CDP (`integrations/playwright_highlighter.py`), pornită din Setări: același script ca userscript-ul, fără extensie, reaplicat în taburile noi și după fiecare salvare de regulă.
   - Generează automat script Tampermonkey/Violentmonkey (`integrations/focuspilot_browser_highlighter.user.js`) pentru injectare directă în DOM-ul paginii HTML.

6. **Interfață Corporate Style**:
   - Paletă corporativă: Petrol (`#00646E`), Mint/Teal (`#00A3A6`), Accent Orange (`#EB780A`).
   - Comutare instantanee între **Dark Mode** și **Light Mode**.

---

## 🚀 Instalare și Rulare

### Dependențe

```powershell
pip install -r requirements.txt
```

Două pachete sunt **obligatorii pentru detecție**, nu opționale:

| Pachet | Fără el |
|---|---|
| `uiautomation` | Aplicația nu poate citi textul din pagini și aplicații, deci **nicio regulă bazată pe text nu se declanșează**. |
| `opencv-python` | Urmărirea prin șablon imagine (snip) eșuează la fiecare încercare. |

FocusPilot verifică ambele la pornire și afișează un avertisment dacă lipsesc.

### Configurația ta

Regulile și setările stau în `config.json`, care **nu e în repo** (e în
`.gitignore`): regulile de lucru conțin de obicei URL-uri și nume de aplicații
interne. La prima pornire, FocusPilot îl creează din `config.example.json`, un
set de reguli exemplu cu domenii fictive. După aceea editezi regulile din
aplicație; `config.json` rămâne doar pe calculatorul tău.

Scriptul de browser generat (`integrations/focuspilot_browser_highlighter.user.js`)
conține aceleași reguli, așa că e ignorat de git din același motiv.

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
├── config.example.json             # Reguli exemplu; config.json local pornește de aici
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
│   ├── theme.py                    # Paletă culori corporate (Dark & Light)
│   ├── tray_manager.py             # Meniu System Tray pystray
│   ├── main_window.py              # Dashboard configurare reguli
│   ├── rule_editor_dialog.py       # Editor reguli cu Live Preview
│   ├── settings_dialog.py          # Setări autostart & scanare
│   ├── overlay_cue.py              # Overlay transparent click-through
│   └── interactive_picker.py       # Selector zonă interactiv de pe ecran
├── integrations/
│   ├── playwright_highlighter.py   # Injectare CDP a userscript-ului (Setări)
│   └── userscript_generator.py     # Generator script Tampermonkey
└── assets/
    ├── icon.png                    # Logo grafic
    └── tray_icon.ico               # Icoană Windows
```

---

## 📖 Cum se scriu reguli

**[GHID_REGULI.md](GHID_REGULI.md)** — ghidul complet: ce face fiecare setare,
referință de operatori și forme, și reguli-exemplu gata de folosit din
[`examples/reguli_exemplu.json`](examples/reguli_exemplu.json).

### Două feluri de reguli

**Regulă simplă** — „dacă textul *X* apare pe ecran, marchează-l".

**Regulă pe condiții**, ca formatarea condițională din Excel:

| Excel | FocusPilot |
|---|---|
| `$B$4`, `$D$7` | **câmp** numit, localizat pe ecran |
| `=AND($B$4="Merge"; $D$7>0)` | **condiții** pe câmpuri, legate prin AND / OR |
| format: fundal, chenar, font | **marcaje**: chenar, cerc, highlight, săgeți |

```
CÂMPURI          status      ← valoarea din dreapta etichetei "Status"
                 cantitate   ← valoarea din dreapta etichetei "Quantity"
                      ↓
CONDIȚII         status este exact "Wait for Merge"   AND
                 cantitate este mai mare decât 0
                      ↓
MARCAJE          încercuiește cantitate cu roșu
                 highlight galben pe status
                 3 săgeți ➔ spre cantitate
```

Un câmp se localizează **după o etichetă** (urmărește elementul la scroll —
varianta recomandată) sau prin **coordonate fixe** capturate cu mouse-ul
(pentru ce stă mereu în același loc: bare de status, panouri fixe).

**17 operatori**: text (exact, conține, începe cu, regex...), numerici
(`>`, `<`, `între`), goliciune, și „s-a schimbat de la ultima verificare".
Comparațiile numerice înțeleg formatele reale de interfață: `1.234,50`,
`1,234.50` și `1 250 EUR`.

**7 forme de marcaj**: chenar, cerc/elipsă, highlight translucid, subliniere,
linie peste text, săgeți multiple, badge. Mai multe marcaje per regulă, pe
câmpuri diferite, cu culori diferite.

Regulile scrise înainte continuă să funcționeze neschimbat.

---

## 🧪 Teste

```powershell
python tests/run_all.py               # tot (190 teste Python + 20 JavaScript)
```

Sau separat:

```powershell
python tests/test_rule_engine.py      # motorul de reguli
python tests/test_probe_engine.py     # câmpuri, condiții, marcaje
python tests/test_examples.py          # regulile-exemplu din documentație
python tests/test_browser_injection.py  # injectarea CDP (+ 2 teste pe browser real)
node   tests/test_userscript.js       # logica de potrivire din browser
```

Testele Python nu au nevoie de Windows: modulele `win32*` și `uiautomation`
sunt înlocuite cu dubluri, iar textul „citit de pe ecran" e furnizat direct de
test. `test_examples.py` trece regulile din documentație prin motorul real,
ca un exemplu din ghid să nu poată fi unul care nu funcționează.

---

## 🔧 Dacă o regulă nu se declanșează

Apasă **🔍 Diagnosticare Live** în editorul de reguli. Butonul rulează
*exact același motor* ca monitorizarea, pe toate ferestrele deschise, și spune
pentru fiecare ce filtru a trecut și ce filtru a picat.

Ordinea în care sunt verificate filtrele:

| # | Filtru | Setare | Observații |
|---|---|---|---|
| 1 | Proces | `Aplicație / Browser` | `browser` acoperă Edge, Chrome, Firefox, Brave, Opera. |
| 2 | Titlu fereastră | `Titlu Fereastră / Tab` | Un cuvânt fără `*` devine `*cuvânt*`. `\|` separă alternative. |
| 3 | URL | `Link / URL Pagină Web` | Lasă `*` dacă adresa nu contează. |
| 4 | Text | `Criteriu Text #1` + criterii suplimentare | Conform `Condiție Text` și relației OR / AND. |

Un filtru lăsat pe `*` sau gol nu respinge nimic. Toate filtrele completate
trebuie să treacă.

### Unde se desenează chenarul

Prima variantă disponibilă, în această ordine:

1. **Pe elementul găsit în pagină** — chenarul urmărește textul la scroll.
2. **Pe șablonul imagine**, dacă regula are un snip și acesta e pe ecran.
3. **La coordonatele salvate** din regulă, conform `Mod Poziționare`.

Varianta 3 se folosește doar când potrivirea a venit din text sau titlu. Dacă
regula s-a potrivit *exclusiv* prin șablon imagine și acesta nu mai e pe ecran,
nu se desenează nimic: elementul s-a mutat, iar un chenar la poziția veche ar
indica locul greșit.

### Chenarul rămâne în urmă la scroll în browser

Un overlay desktop desenează la coordonate de ecran. Când textul e localizat
prin UI Automation, coordonatele se recalculează la fiecare scanare, deci
chenarul urmărește textul. Pentru sincronizare perfectă în pagini web,
instalează userscript-ul generat în `integrations/` prin Tampermonkey sau
Violentmonkey: acolo chenarul e atașat de nodul HTML.

Userscript-ul se regenerează automat la fiecare salvare de regulă.

#### Fără extensie: injectare directă prin portul de depanare (CDP)

Dacă extensiile nu se pot instala, FocusPilot poate pune același script direct
în taburile din Chrome sau Edge. În **Setări → Browser — injectare directă
(CDP)** bifează opțiunea și lasă portul 9222. Browserul trebuie pornit cu
portul de depanare deschis și cu un profil separat, de exemplu printr-o
scurtătură:

```powershell
msedge.exe --remote-debugging-port=9222 --user-data-dir=C:\FocusPilot\ProfilEdge
```

Profilul separat e obligatoriu: Chrome și Edge recente ignoră portul de
depanare pe profilul implicit. În acel profil trebuie să te autentifici o dată.

FocusPilot verifică taburile la câteva secunde și injectează scriptul în cele
noi, după navigare și după fiecare salvare de regulă. Linia **Stare** din
setări spune dacă e conectat, dacă browserul nu răspunde pe port sau dacă
lipsește pachetul `playwright`. La dezactivare marcajele dispar din pagini.
Dacă ai și userscript-ul în Tampermonkey, cele două nu se dublează.

Ca și userscript-ul, injectarea acoperă regulile clasice (text căutat +
reper vizual). Regulile pe condiții (câmpuri și marcaje) rămân pe overlay-ul
de pe ecran.

Portul de depanare permite oricărui program de pe calculator să controleze
browserul pornit așa. Folosește profilul separat doar pentru aplicațiile pe
care le marchezi.

### Jurnal

`focuspilot_log.txt`, rotativ la 2 MB. Pentru detalii complete:

```powershell
set FOCUSPILOT_DEBUG=1
pythonw.exe FocusPilot.pyw
```
