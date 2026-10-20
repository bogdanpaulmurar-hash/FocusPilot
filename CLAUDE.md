# FocusPilot — context pentru sesiunile de lucru

Formatare condițională vizuală peste orice suprafață de lucru: detectează text
sau valori pe ecran și desenează chenare, cercuri, highlight, săgeți și badge-uri
peste browser sau aplicații desktop. Ce face formatarea condițională în Excel,
dar peste ecran.

**Platformă:** Windows. Depinde de `pywin32`, `uiautomation` și Tkinter.
Testele rulează oriunde: modulele `win32*` și `uiautomation` sunt înlocuite cu
dubluri, iar textul „citit de pe ecran" e furnizat direct de test.

---

## Verificare — rulează asta la fiecare modificare

```bash
python tests/run_all.py          # 164 teste Python + 20 JavaScript
```

Separat, când lucrezi punctual:

```bash
python tests/test_rule_engine.py    # filtre, condiții text, geometrie
python tests/test_probe_engine.py   # câmpuri, operatori, marcaje
python tests/test_examples.py       # regulile din GHID_REGULI.md
node   tests/test_userscript.js     # logica din userscript-ul generat
```

`test_examples.py` trece regulile din documentație prin motorul real. Dacă
modifici schema de reguli și el cade, documentația a rămas în urmă — nu
dezactiva testul, actualizează ghidul.

---

## Hartă

| Fișier | Rol |
|---|---|
| `FocusPilot.pyw` | punct de intrare, jurnal, ciclu de viață |
| `core/rule_engine.py` | filtre de fereastră, condiții text, geometrie; **citirea arborelui de accesibilitate** |
| `core/probe_engine.py` | câmpuri numite, operatori, condiții, rezolvarea marcajelor, validare |
| `core/mark_geometry.py` | marcaj → primitive de desen; conversia regulilor clasice. **Fără importuri de interfață** — de aici testabilitatea |
| `core/monitor_engine.py` | firul de scanare, enumerarea ferestrelor, citirea URL-ului |
| `core/config_manager.py` | `config.json`, thread-safe |
| `ui/shape_overlay.py` | ferestrele care desenează efectiv |
| `ui/overlay_cue.py` | orchestrarea reperelor, animația de pulsare |
| `ui/condition_builder.py` | panoul de câmpuri / condiții / marcaje |
| `ui/rule_editor_dialog.py` | editorul de reguli, diagnosticarea live |
| `ui/interactive_picker.py` | selectorul de pe ecran (zonă sau punct) |
| `integrations/userscript_generator.py` | generează userscript-ul Tampermonkey |

Documentația pentru utilizator: `GHID_REGULI.md`. Exemple: `examples/reguli_exemplu.json`.

---

## Două modele de reguli, ambele trebuie să funcționeze

**Clasic** — `trigger.search_text` + `visual_cue`. Un text apare → se marchează.

**Pe condiții** — `probes` + `conditions` + `marks`. Modelul Excel: câmpuri
numite, condiții pe ele, marcaje pe câmpuri. `probe_engine.uses_conditions()`
decide ce cale se folosește.

Regulile existente din `config.json` sunt în format clasic. **Orice schimbare de
schemă trebuie să le lase funcționale** — sunt reguli reale, de lucru.

---

## Invariante — se încalcă ușor și strică lucruri

**Chenarul = patru bare opace, nu un dreptunghi transparent.** O suprafață opacă
rămâne vizibilă peste conținutul accelerat GPU din Chrome și Edge, unde
transparența DWM nu e redată corect. Vezi `mark_geometry.expand_mark`.

**Click-through cere `WS_EX_LAYERED` împreună cu `WS_EX_TRANSPARENT`.** Singur,
`WS_EX_TRANSPARENT` nu oprește testarea la click. Plus `WS_EX_NOACTIVATE`, altfel
overlay-ul fură focusul din câmpul în care scrie utilizatorul.

**Bucla de animație nu apelează `deiconify` / `lift` / `focus`.** Reaplicate la
fiecare tic pe mai multe ferestre, mută focusul și produc pâlpâire.

**UI Automation e COM și scanarea rulează pe fir de fundal.** `_ensure_com_initialized()`
trebuie apelat pe firul respectiv, altfel orice apel UIA eșuează — simptom tipic:
detecția funcționează în dialogul de diagnostic (fir principal) dar nu în
monitorizare.

**Arborele de accesibilitate se citește O DATĂ pe fereastră, cu limită de noduri
și cache.** `capture_window_text()` deservește toate regulile și toate criteriile
dintr-un ciclu. O pagină web are zeci de mii de noduri; o căutare per criteriu
saturează procesorul.

**Potrivirea de șabloane imagine e scumpă** (captură pe tot spațiul virtual +
OpenCV). Are cache propriu; nu o apela în buclă.

**Jurnalul nu se scrie la fiecare redare.** Nivelul e INFO, cu rotație la 2 MB.
`FOCUSPILOT_DEBUG=1` ridică la DEBUG.

---

## Localizarea câmpurilor: etichetă vs coordonate

`text_near` (valoarea de lângă o etichetă) se recaută la fiecare scanare, deci
**urmărește elementul la scroll**. Asta e varianta implicită și cea recomandată
în documentație.

`screen_point` / `screen_region` sunt coordonate fixe: corecte doar pentru ce stă
mereu în același loc (bare de status, panouri fixe). Dacă pagina derulează,
punctul arată spre alt element. Nu promova coordonatele ca implicite.

Toleranțele de proximitate din `_read_near_label` se leagă de **dimensiunea
etichetei**, nu de valori fixe: o toleranță fixă prinde rânduri sau coloane
vecine, iar câmpul citește valoarea greșită — cel mai rău fel de eroare aici.

---

## Unde se desenează

Prima variantă disponibilă:

1. Elementul găsit prin UI Automation — urmărește scroll-ul.
2. Șablonul imagine, dacă e pe ecran.
3. Coordonatele salvate în regulă.

Varianta 3 **doar** când potrivirea a venit din text sau titlu. Dacă regula s-a
potrivit exclusiv prin șablon și acesta nu mai e pe ecran, nu se desenează nimic:
elementul s-a mutat. Un marcaj în locul greșit e mai rău decât niciun marcaj —
același principiu în `resolve_marks`, care omite marcajele pe câmpuri nelocalizate.

---

## Convenții

**Comentarii și documentație în română.** Mesajele de commit la fel.

**Comentariile explică DE CE, nu CE.** Unde o linie repară un defect anume,
comentariul spune care era comportamentul greșit — altfel reparația se pierde la
următoarea refactorizare. Exemplu din `monitor_engine`:

```python
# Inițializat ÎNAINTE de try: în varianta anterioară `poll_interval` era
# definit în interiorul blocului try, iar `time.sleep(poll_interval)` de la
# finalul buclei era în afara lui. O excepție la prima iterație lăsa numele
# nelegat, iar UnboundLocalError — neprins — omora firul în silence.
```

**Nimic hardcodat pentru cazuri particulare.** Motorul a conținut o excepție
scrisă în cod pentru cuvântul `"status"` și o lățime implicită care depindea de
numele regulii. O regulă face exact ce spun setările ei.

**Eșecurile se raportează, nu se înghit.** `except Exception: pass` a ascuns două
dependențe lipsă, iar detecția era moartă fără niciun indiciu. Dacă o cale de
detecție nu poate funcționa, utilizatorul trebuie să afle.

**Fără numele angajatorului în documentele vizibile** (README, ghiduri, specificații)
— repo-ul e public. În codul sursă e în regulă.

**Logica separată de interfață.** `core/mark_geometry.py` nu importă tkinter, de
aceea geometria se testează fără GUI. Când adaugi ceva calculabil, pune-l în
`core/`, nu în `ui/`.

---

## Dependențe obligatorii pentru detecție

`uiautomation` și `opencv-python` nu sunt opționale: fără prima, nicio regulă pe
text sau câmpuri nu se declanșează; fără a doua, urmărirea prin șablon eșuează.
Ambele sunt verificate la pornire (`rule_engine.CAPABILITIES`) și lipsa lor e
raportată în interfață.

---

## Stare

Branch: `fix/detection-and-stability`, publicat. `main` e versiunea veche, care
**nu pornește** (importuri lipsă) — nu te întoarce la ea ca referință.

De făcut, când apare nevoia:

- `config.json` conține URL-uri interne reale și e commit-at în repo public
- regulile existente referă `assets/rules/snip_*.png`, fișiere care nu există în
  repo; acum cad pe coordonatele salvate, dar merită recapturate
- `playwright_highlighter.py` nu e conectat la interfață; userscript-ul acoperă
  același scop
