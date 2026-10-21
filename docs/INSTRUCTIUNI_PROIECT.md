# Instrucțiuni pentru proiectul FocusPilot

Conținutul de mai jos se lipește în câmpul de instrucțiuni al proiectului din
claude.ai. Nu îl ține doar aici: până nu e în proiect, nu are efect.

---

## ✂️ De aici în jos se copiază

Lucrăm pe **FocusPilot**, aplicația mea de formatare condițională vizuală peste
ecran: detectează text sau valori în browser și în aplicații desktop, apoi
desenează chenare, cercuri, highlight, săgeți și badge-uri peste ele. Ce face
formatarea condițională în Excel, dar peste suprafața de lucru.

Python + Tkinter, Windows, multi-monitor. Repo: `bogdanpaulmurar-hash/FocusPilot`,
branch de lucru `main` (branch-ul `fix/detection-and-stability` a fost unificat
în main pe 21.10 și nu mai primește commit-uri).

### Cum vreau să lucrezi

**Vorbește și scrie în română.** Comentariile din cod, documentația și mesajele
de commit la fel.

**Diagnostichează prin rulare, nu prin citit.** Când spun că ceva nu merge,
reprodu-l: rulează codul, scrie un test care prinde defectul, arată-mi rezultatul.
Nu-mi spune ce crezi că e problema — arată-mi. Dacă o bănuială se dovedește
greșită la verificare, spune-o.

**Rulează testele la fiecare modificare:** `python tests/run_all.py`. Nu-mi
raporta ceva ca rezolvat fără ele.

**Un test care trece și înainte de reparație nu valorează nimic.** Când repari un
defect, verifică că testul nou cade pe codul vechi.

**Comentariile explică DE CE.** Unde o linie repară un defect, spune în comentariu
care era comportamentul greșit, altfel reparația se pierde la următoarea
refactorizare.

**Nimic hardcodat pentru cazuri particulare.** Codul a conținut o excepție scrisă
special pentru cuvântul „status" și o dimensiune implicită care depindea de numele
regulii. O regulă trebuie să facă exact ce spun setările ei. Dacă vezi așa ceva,
semnalează-l.

**Nu înghiți erorile.** `except Exception: pass` a ascuns două dependențe lipsă
și detecția era moartă fără niciun indiciu. Dacă o cale nu poate funcționa,
utilizatorul trebuie să afle.

**Compatibilitate.** Regulile din `config.json` sunt reguli reale, de lucru, în
format clasic. Orice schimbare de schemă trebuie să le lase funcționale.

**Fără numele angajatorului** în README, ghiduri sau alte documente vizibile —
repo-ul e public. În codul sursă e în regulă.

**Spune-mi direct când nu sunt pe drumul bun.** Dacă ce cer are un defect de
proiectare, zi-mi, nu-l implementa în silence.

### Două modele de reguli

**Clasic:** `trigger.search_text` + `visual_cue`. Un text apare → se marchează.

**Pe condiții:** `probes` (câmpuri numite) + `conditions` (operatori, AND/OR) +
`marks` (ce câmp, ce formă). Echivalentul `=AND($B$4="x"; $D$7>0)` din Excel.

Ambele trebuie să funcționeze. Documentația pentru utilizator e `GHID_REGULI.md`.

### Ce să nu strici

Detaliile tehnice și motivele lor sunt în `CLAUDE.md` din repo. Cele mai ușor de
încălcat:

- chenarul e **patru bare opace**, nu un dreptunghi transparent — altfel nu se
  vede peste conținutul accelerat GPU din Chrome
- click-through cere `WS_EX_LAYERED` **plus** `WS_EX_TRANSPARENT`, iar
  `WS_EX_NOACTIVATE` împiedică overlay-ul să fure focusul
- arborele de accesibilitate se citește **o dată pe fereastră**, cu cache; o
  căutare per criteriu saturează procesorul
- UI Automation e COM și scanarea rulează pe fir de fundal: COM trebuie
  inițializat pe firul acela
- localizarea după etichetă urmărește scroll-ul, cea prin coordonate nu — prima
  rămâne varianta implicită

### Context util

Pe 3 monitoare, în portaluri web interne, omisiunile costă. Scopul aplicației e
să facă imposibil de ratat un câmp care trebuie modificat. De asta un marcaj
desenat în locul greșit e mai rău decât niciun marcaj — principiu valabil în tot
codul.

## ✂️ Până aici

---

## Ce se adaugă la cunoștințele proiectului

Separat de instrucțiuni, încarcă în proiect fișierele astea din repo:

| Fișier | De ce |
|---|---|
| `CLAUDE.md` | arhitectura, invariantele și motivele lor |
| `GHID_REGULI.md` | schema completă de reguli, operatori, forme |
| `examples/reguli_exemplu.json` | șase reguli funcționale, ca referință de schemă |

Când atașezi repo-ul la o sesiune de cod, `CLAUDE.md` se încarcă singur și nu mai
e nevoie să-l adaugi manual.

## Cum creezi proiectul

În claude.ai: **Projects → Create project** → nume `FocusPilot` → **Instructions**
→ lipești secțiunea dintre cele două foarfeci → **Add knowledge** → încarci cele
trei fișiere.

Apoi orice discuție despre FocusPilot pornită în proiectul acela are deja tot
contextul: nu mai trebuie să explici ce face aplicația sau ce convenții avem.
