# Ghid de reguli FocusPilot

Cum se scrie o regulă, ce face fiecare setare, și reguli-exemplu gata de folosit.

---

## Cuprins

1. [Ideea](#1-ideea)
2. [Regulă simplă: un text, un chenar](#2-regulă-simplă-un-text-un-chenar)
3. [Regulă pe condiții: mai multe câmpuri](#3-regulă-pe-condiții-mai-multe-câmpuri)
4. [Câmpuri — de unde se citesc valorile](#4-câmpuri--de-unde-se-citesc-valorile)
5. [Operatori — referință completă](#5-operatori--referință-completă)
6. [Marcaje — forme și culori](#6-marcaje--forme-și-culori)
7. [Filtrele de fereastră](#7-filtrele-de-fereastră)
8. [Unde se desenează marcajul](#8-unde-se-desenează-marcajul)
9. [Reguli-exemplu](#9-reguli-exemplu)
10. [Când o regulă nu se declanșează](#10-când-o-regulă-nu-se-declanșează)

---

## 1. Ideea

FocusPilot face peste ecran ce face formatarea condițională în Excel:

| Excel | FocusPilot |
|---|---|
| `$B$4`, `$D$7` | **câmp** numit, localizat pe ecran |
| `=AND($B$4="Merge"; $D$7>0)` | **condiții** pe câmpuri, legate prin AND / OR |
| format: fundal, chenar, font | **marcaje**: chenar, cerc, highlight, săgeți, badge |

Există două feluri de reguli, și poți folosi oricare:

- **Regulă simplă** — „dacă textul *X* apare pe ecran, marchează-l". Se
  configurează în secțiunile 1–4 din editor.
- **Regulă pe condiții** — „dacă câmpul *status* este *Wait for Merge* **și**
  câmpul *cantitate* este mai mare decât *0*, încercuiește *cantitate*". Se
  configurează în secțiunea 4b.

Regulile existente, scrise înainte, continuă să funcționeze neschimbat.

---

## 2. Regulă simplă: un text, un chenar

Cel mai scurt drum de la zero la ceva care funcționează.

1. **Dashboard → ➕ Adaugă Regulă Nouă**
2. **Nume:** `Categorie greșită în TIMA`
3. **Titlu Fereastră / Tab:** `*TIMA*`
   Un cuvânt fără `*` devine automat `*cuvânt*`.
4. **Aplicație / Browser:** `browser (Edge + Chrome)`
5. **Condiție Text:** `Conține text (Contains)`
6. **Criteriu Text #1:** `Please change category`
7. **Secțiunea 3:** bifează chenar, alege culoarea, scrie textul badge-ului.
8. **Secțiunea 4 → 🎯 Alege Interactiv de pe Ecran** — trage un dreptunghi
   peste zona respectivă. Se salvează coordonatele și o captură a zonei.
9. **🔍 Diagnosticare Live** — verifică *acum* dacă regula se declanșează.
10. **💾 Salvează Regula**

### Condițiile de text

| Setare | Ce face | Exemplu |
|---|---|---|
| `Conține text` | textul apare oriunde | `change` găsește `Please change category` |
| `Este exact` | întregul rând este exact acel text | `Merge` **nu** găsește `Wait for Merge` |
| `Începe cu` | rândul începe cu textul | `Please` găsește `Please change category` |
| `Constelație` | **toate** cuvintele, separate prin `;` | `merge;waiting` cere ambele |
| `Expresie regulată` | regex | `ID-\d{4}` găsește `ID-2048` |

Textul căutat e tratat **literal**. O frază care conține `;`, `|`, apostrof sau
ghilimele se caută întreagă:

```
Changed from 'Merge' to 'Wait for Merge'     ← se caută exact așa
Priority: high; escalate                     ← nu se desparte la ';'
```

Pentru mai multe criterii independente, folosește butonul **➕ Criteriu** și
alege relația **OR** (oricare) sau **AND** (toate).

---

## 3. Regulă pe condiții: mai multe câmpuri

Pentru „dacă câmpul X are valoarea Z **și** câmpul Y are valoarea C".

Se completează în trei pași, în ordine, în **secțiunea 4b**:

```
┌─ 1. CÂMPURI ─────────────────────────────────────────────────┐
│  status      ← valoarea din dreapta etichetei "Status"       │
│  cantitate   ← valoarea din dreapta etichetei "Quantity"     │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ 2. CONDIȚII ────────────────────────────────────────────────┐
│  Dacă  status     este exact            "Wait for Merge"     │
│  Dacă  cantitate  este mai mare decât   "0"                  │
│  Relația: AND (toate simultan)                               │
└──────────────────────────────────────────────────────────────┘
                              ↓
┌─ 3. MARCAJE ─────────────────────────────────────────────────┐
│  Marchează  cantitate  cu  Cerc            roșu              │
│  Marchează  status     cu  Highlight       galben            │
│  Marchează  cantitate  cu  3 săgeți ➔      roșii             │
└──────────────────────────────────────────────────────────────┘
```

**Numele câmpului e referința.** Condițiile și marcajele îl folosesc exact ca
Excel folosește `$B$4`. Dacă redenumești un câmp, listele se actualizează
singure.

### Pașii concreți

1. **➕ Adaugă Câmp.** Scrie un nume — `status`.
2. Alege cum se găsește: `Lângă o etichetă`, și scrie eticheta — `Status`.
   Alege direcția: `la dreapta etichetei`.
3. **➕ Adaugă Câmp** pentru al doilea — `cantitate`, eticheta `Quantity`.
4. **➕ Adaugă Condiție.** Alege `status`, operatorul `este exact`, valoarea
   `Wait for Merge`.
5. **➕ Adaugă Condiție** pentru a doua: `cantitate`, `este mai mare decât`, `0`.
6. Relația dintre condiții: `AND (toate simultan)`.
7. **➕ Adaugă Marcaj.** Alege `cantitate`, forma `Cerc / elipsă`, culoarea roșu.
8. Adaugă câte marcaje vrei, pe câmpuri diferite.
9. **🔍 Diagnosticare Live** — arată, condiție cu condiție, ce valoare s-a citit.

---

## 4. Câmpuri — de unde se citesc valorile

Patru moduri de localizare. **Alegerea contează mai mult decât orice altă
setare**, pentru că de ea depinde dacă regula rezistă la scroll.

### `Lângă o etichetă` — recomandat

Caută eticheta, apoi citește primul text de lângă ea, în direcția cerută.

```
   Status:  [ Wait for Merge ]
   ───┬───    ──────┬───────
  eticheta        valoarea citită
```

**Avantaj decisiv:** eticheta se recaută la fiecare scanare, deci când pagina
derulează, câmpul urmărește rândul. Asta e varianta de folosit implicit.

| Setare | Ce face |
|---|---|
| `Eticheta` | textul după care se caută (potrivire parțială) |
| direcția | `la dreapta` / `la stânga` / `sub` / `deasupra` etichetei |
| `sari peste` | `0` = primul element de lângă etichetă, `1` = al doilea |

Folosește `sari peste` când între etichetă și valoare mai e ceva — o unitate de
măsură, un separator, o pictogramă.

### `Punct fix pe ecran`

Citește ce se află sub un punct de coordonate fixe.

**Folosește-l doar pentru ce stă mereu în același loc:** bare de status,
panouri fixe, toolbar-uri, ferestre maximizate care nu derulează.

**Dacă pagina derulează, punctul arată spre alt element** și câmpul va citi
valoarea greșită. De asta nu e varianta implicită.

Apasă **🎯 Alege de pe Ecran** și dă un clic pe valoare. La selecție se citește
imediat textul de acolo și se afișează ca previzualizare, deci vezi pe loc dacă
ai nimerit elementul corect.

### `Zonă fixă pe ecran`

Ca punctul, dar citește tot textul dintr-un dreptunghi și îl unește. Util când
valoarea e spartă în mai multe elemente, sau pentru un rând întreg.

### `Textul în sine`

Întoarce textul căutat, dacă apare pe ecran. Util pentru „apare / nu apare",
combinat cu operatorii `este gol` și `nu este gol`.

---

## 5. Operatori — referință completă

### Text

| Operator | Adevărat când | Exemplu |
|---|---|---|
| `este exact` | valoarea e identică | `Merge` nu se potrivește cu `Wait for Merge` |
| `este diferit de` | valoarea diferă | |
| `conține` | textul apare oriunde în valoare | `Merge` se potrivește cu `Wait for Merge` |
| `nu conține` | textul nu apare | `nu conține "Rejected"` |
| `începe cu` | valoarea începe astfel | |
| `se termină cu` | valoarea se termină astfel | |
| `se potrivește cu expresia` | regex | `^TKT-\d{6}$` |

Bifa **Aa** de pe rândul condiției face comparația sensibilă la majuscule.
Implicit nu este.

### Numere

| Operator | Exemplu |
|---|---|
| `este mai mare decât` | `cantitate > 0` |
| `este mai mic decât` | `stoc < 5` |
| `este mai mare sau egal cu` | |
| `este mai mic sau egal cu` | |
| `este între` | `10;20` — două valori separate prin `;` |
| `este un număr` | adevărat dacă valoarea se poate citi ca număr |

Numerele se citesc din formate reale de interfață:

| Pe ecran | Valoare |
|---|---|
| `1.234,50` | 1234.5 |
| `1,234.50` | 1234.5 |
| `1 250 EUR` | 1250 |
| `qty: 18 buc` | 18 |
| `Wait for Merge` | nu e număr — condiția e falsă, nu o eroare |

### Prezență și schimbare

| Operator | Adevărat când |
|---|---|
| `este gol` | câmpul nu are text |
| `nu este gol` | câmpul are text |
| `s-a schimbat de la ultima verificare` | valoarea diferă de scanarea anterioară |

`s-a schimbat` e fals la prima verificare: nu există încă o valoare anterioară
cu care să compare.

---

## 6. Marcaje — forme și culori

Un marcaj spune **ce câmp** se evidențiază și **cu ce**. Poți pune oricâte, pe
câmpuri diferite, cu culori diferite.

| Formă | Aspect | Parametri |
|---|---|---|
| `Chenar dreptunghiular` | patru bare în jurul zonei | grosime, culoare, pulsare |
| `Cerc / elipsă` | contur oval în jurul zonei | grosime, culoare, pulsare |
| `Highlight translucid` | ca trecerea unui marker | opacitate, culoare |
| `Subliniere` | linie sub text | grosime, culoare |
| `Linie peste text` | linie prin mijloc | grosime, culoare |
| `Săgeată` | 1–5 săgeți care indică zona | direcție, număr, culoare |
| `Etichetă cu text` | badge deasupra zonei | text, culoare |

Note practice:

- **Ordinea contează la suprapunere.** Pune highlight-ul primul, ca să stea sub
  chenar.
- **Săgeata stă pe latura opusă direcției.** O săgeată „spre dreapta" se
  desenează la stânga zonei, ca să arate spre ea.
- **Pulsarea** variază ușor grosimea și opacitatea. Oprește-o dacă marcajul
  stă permanent pe ecran și distrage.
- **Un marcaj al cărui câmp nu e vizibil pe ecran nu se desenează.** Un cerc
  într-un loc greșit e mai rău decât niciun cerc.
- **Marcajele nu blochează mouse-ul.** Poți da clic și scrie prin ele.

### Culorile

Paleta Siemens, pentru consecvență:

| Culoare | Cod | Pentru |
|---|---|---|
| Roșu alertă | `#E60000` | eroare, câmp obligatoriu |
| Portocaliu | `#EB780A` | atenție, de verificat |
| Galben | `#FFB900` | informativ |
| Verde | `#009966` | confirmare, în regulă |
| Petrol | `#00646E` | neutru |

---

## 7. Filtrele de fereastră

Se aplică în această ordine, și **toate cele completate trebuie să treacă**.
Un filtru lăsat pe `*` sau gol nu respinge nimic.

| # | Filtru | Exemple |
|---|---|---|
| 1 | **Aplicație / Browser** | `browser (Edge + Chrome)` acoperă Edge, Chrome, Firefox, Brave, Opera. Sau un executabil: `excel.exe` |
| 2 | **Titlu Fereastră / Tab** | `*TIMA*` · `TIMA` (devine `*TIMA*`) · `*Service Platform*\|*GSP*` (alternative) |
| 3 | **Link / URL** | `*tima.siemens.com/otwg20*` · lasă `*` dacă adresa nu contează |
| 4 | **Text sau condiții** | vezi secțiunile 2 și 3 |

Bara verticală `|` separă alternative, la titlu și la URL. Se potrivește oricare.

> URL-ul se citește din bara de adrese a browserului. Dacă nu poate fi citit,
> regula nu e respinsă pe nedrept — rămâne pe celelalte filtre.

---

## 8. Unde se desenează marcajul

Prima variantă disponibilă, în această ordine:

1. **Pe elementul găsit în pagină.** Coordonatele se recalculează la fiecare
   scanare, deci marcajul urmărește textul la scroll.
2. **Pe șablonul imagine**, dacă regula are o captură și aceasta e pe ecran.
3. **La coordonatele salvate** din regulă, conform `Mod Poziționare`.

Varianta 3 se folosește doar când potrivirea a venit din **text sau titlu**.
Dacă regula s-a potrivit *exclusiv* prin șablon imagine și acesta nu mai e pe
ecran, nu se desenează nimic: elementul s-a mutat, iar un marcaj la poziția
veche ar indica locul greșit.

### Acoperirea chenarului

| Setare | Ce încadrează |
|---|---|
| `Fix pe Textul Detectat` | strict textul găsit |
| `Zonă Extinsă (W x H)` | lățimea și înălțimea configurate, aliniate la text |
| `Tot Rândul Orizontal` | toată lățimea ferestrei, la înălțimea textului |

### Modurile de poziționare

| Mod | Coordonatele de rezervă |
|---|---|
| `visual_track` | cele capturate cu selectorul (absolute) |
| `screen_absolute` | `abs_x` / `abs_y` exacte |
| `window_relative` | proporțional cu fereastra — rezistă la mutarea ferestrei |
| `entire_window` | toată fereastra; are prioritate față de orice ancorare |

### Durata de afișare

`Durată Afișare Reper`: `0` = permanent cât timp fereastra se potrivește. O
valoare în secunde ascunde marcajul după acel timp, iar cronometrul repornește
când revii pe fereastră.

---

## 9. Reguli-exemplu

Fișierul [`examples/reguli_exemplu.json`](examples/reguli_exemplu.json)
conține regulile de mai jos, gata de copiat în `config.json`, în lista `rules`.

### A. Text simplu cu chenar și badge

Cea mai simplă formă. Un text apare în pagină → chenar roșu și etichetă.

```json
{
  "id": "exemplu_text_simplu",
  "name": "A. Categorie de schimbat în TIMA",
  "enabled": true,
  "trigger": {
    "process_name": "browser",
    "window_title_pattern": "*TIMA*",
    "url_pattern": "*",
    "text_condition": "contains",
    "search_text": "Please change category",
    "case_sensitive": false
  },
  "visual_cue": {
    "box_enabled": true, "box_scope": "exact_text",
    "border_color": "#E60000", "border_width": 3,
    "arrow_enabled": true, "arrow_direction": "right",
    "arrow_color": "#E60000", "arrow_count": 2,
    "badge_enabled": true, "badge_text": "🚨 SCHIMBĂ CATEGORIA",
    "badge_bg": "#E60000", "badge_fg": "#FFFFFF",
    "pulse_animation": true, "duration_sec": 0
  },
  "region": { "mode": "window_relative", "width": 320, "height": 30 }
}
```

### B. Două câmpuri cu AND — cerința „câmpul X și câmpul Y"

Marchează doar când **ambele** condiții sunt îndeplinite simultan. Trei marcaje
diferite, pe două câmpuri.

```json
{
  "id": "exemplu_doua_campuri",
  "name": "B. Status în așteptare ȘI cantitate peste zero",
  "enabled": true,
  "trigger": {
    "process_name": "browser",
    "window_title_pattern": "*GSP*|*Service Platform*"
  },
  "probes": [
    { "name": "status",
      "locator": { "kind": "text_near", "text": "Status", "offset": "right" } },
    { "name": "cantitate",
      "locator": { "kind": "text_near", "text": "Quantity", "offset": "right" } }
  ],
  "conditions": [
    { "probe": "status", "operator": "equals", "value": "Wait for Merge" },
    { "probe": "cantitate", "operator": "greater_than", "value": "0" }
  ],
  "conditions_logic": "AND",
  "marks": [
    { "target": "status", "shape": "highlight", "color": "#FFB900",
      "opacity": 0.30 },
    { "target": "cantitate", "shape": "circle", "color": "#E60000",
      "thickness": 3, "pulse": true },
    { "target": "cantitate", "shape": "arrow", "color": "#E60000",
      "arrow_direction": "right", "arrow_count": 3 }
  ]
}
```

### C. Valoare numerică în afara intervalului

Un preț sub sau peste limitele admise. Subliniere plus badge.

```json
{
  "id": "exemplu_interval",
  "name": "C. Preț în afara intervalului admis",
  "enabled": true,
  "trigger": { "process_name": "browser", "window_title_pattern": "*Portal*" },
  "probes": [
    { "name": "pret",
      "locator": { "kind": "text_near", "text": "Total", "offset": "right" } }
  ],
  "conditions": [
    { "probe": "pret", "operator": "is_number", "value": "" },
    { "probe": "pret", "operator": "between", "value": "100;5000" }
  ],
  "conditions_logic": "AND",
  "marks": [
    { "target": "pret", "shape": "underline", "color": "#EB780A",
      "thickness": 3 },
    { "target": "pret", "shape": "badge", "color": "#EB780A",
      "text": "⚠️ VERIFICĂ PREȚUL" }
  ]
}
```

> Pentru „**în afara** intervalului" se folosește relația `OR` cu două condiții:
> `este mai mic decât 100` sau `este mai mare decât 5000`.

### D. Câmp obligatoriu rămas gol

Prinde omisiunea înainte de salvare. `este gol` nu are nevoie de o valoare.

```json
{
  "id": "exemplu_camp_gol",
  "name": "D. Câmp obligatoriu necompletat",
  "enabled": true,
  "trigger": { "process_name": "browser", "window_title_pattern": "*Formular*" },
  "probes": [
    { "name": "cost_center",
      "locator": { "kind": "text_near", "text": "Cost Center", "offset": "right" } }
  ],
  "conditions": [
    { "probe": "cost_center", "operator": "is_empty", "value": "" }
  ],
  "conditions_logic": "AND",
  "marks": [
    { "target": "cost_center", "shape": "box", "color": "#E60000",
      "thickness": 4, "pulse": true },
    { "target": "cost_center", "shape": "arrow", "color": "#E60000",
      "arrow_direction": "right", "arrow_count": 2 },
    { "target": "cost_center", "shape": "badge", "color": "#E60000",
      "text": "CÂMP OBLIGATORIU" }
  ]
}
```

### E. Coordonate fixe — bară de status

Pentru ce stă mereu în același loc. Înlocuiește `x` și `y` cu valorile tale,
capturate prin **🎯 Alege de pe Ecran**.

```json
{
  "id": "exemplu_coordonate_fixe",
  "name": "E. Bară de status pe eroare (coordonate fixe)",
  "enabled": true,
  "trigger": { "process_name": "" },
  "probes": [
    { "name": "bara_status",
      "locator": { "kind": "screen_region",
                   "x": 12, "y": 1040, "w": 420, "h": 24 } }
  ],
  "conditions": [
    { "probe": "bara_status", "operator": "contains", "value": "error" }
  ],
  "conditions_logic": "AND",
  "marks": [
    { "target": "bara_status", "shape": "highlight", "color": "#E60000",
      "opacity": 0.35 },
    { "target": "bara_status", "shape": "box", "color": "#E60000",
      "thickness": 2 }
  ]
}
```

### F. Valoare care se schimbă

Atrage atenția exact când o valoare s-a modificat față de scanarea anterioară.

```json
{
  "id": "exemplu_schimbare",
  "name": "F. Statusul s-a schimbat",
  "enabled": true,
  "trigger": { "process_name": "browser", "window_title_pattern": "*Portal*" },
  "probes": [
    { "name": "status",
      "locator": { "kind": "text_near", "text": "Status", "offset": "right" } }
  ],
  "conditions": [
    { "probe": "status", "operator": "changed", "value": "" }
  ],
  "conditions_logic": "AND",
  "marks": [
    { "target": "status", "shape": "circle", "color": "#009966",
      "thickness": 3 },
    { "target": "status", "shape": "badge", "color": "#009966",
      "text": "S-A SCHIMBAT" }
  ]
}
```

### Cum le folosești

1. Oprește FocusPilot din tray (**❌ Ieșire**).
2. Deschide `config.json` și copiază regulile dorite în lista `rules`.
3. Pornește FocusPilot.
4. Deschide fiecare regulă în editor și apasă **🔍 Diagnosticare Live**.
5. Ajustează etichetele și coordonatele pentru ecranele tale.

Etichetele din exemple (`Status`, `Quantity`, `Total`, `Cost Center`) sunt
exemple: înlocuiește-le cu textele reale din aplicațiile tale.

---

## 10. Când o regulă nu se declanșează

**Apasă 🔍 Diagnosticare Live în editor.** Rulează *exact același motor* ca
monitorizarea, pe toate ferestrele deschise, și spune pentru fiecare ce filtru a
trecut și ce a picat. Pentru regulile pe condiții arată fiecare condiție cu
valoarea citită efectiv:

```
✅ TIMA Web Gateway — Ticket 48213
     proces: chrome.exe
     URL:    https://tima.siemens.com/otwg20/#/main
     ✅ status este exact 'Wait for Merge' — valoare citită: 'Wait for Merge'
     ❌ cantitate este mai mare decât '0' — valoare citită: '(negăsit)'
       ⚠️ cantitate: Eticheta 'Quantity' nu e vizibilă pe ecran.
     Logică: AND
```

### Cauze frecvente

| Simptom | Cauză probabilă |
|---|---|
| „Eticheta nu e vizibilă pe ecran" | eticheta e scrisă altfel decât în pagină, sau e mai jos și trebuie derulat |
| „Niciun element cu text la punct" | pagina a derulat — folosește `Lângă o etichetă` |
| se citește valoarea greșită | între etichetă și valoare mai e un element: crește `sari peste` |
| condițiile trec, nimic nu se desenează | câmpul-țintă al marcajului nu e vizibil |
| nimic nu se declanșează, deloc | lipsește `uiautomation` — vezi mai jos |

### Dependențele obligatorii

```powershell
pip install -r requirements.txt
```

Fără `uiautomation` aplicația nu poate citi textul din pagini, deci **nicio
regulă bazată pe text sau pe câmpuri nu se declanșează**. Fără `opencv-python`
nu funcționează urmărirea prin șablon imagine. FocusPilot verifică ambele la
pornire și te avertizează dacă lipsesc.

### Chenarul rămâne în urmă la scroll

Un overlay desktop desenează la coordonate de ecran. Când textul e localizat
prin UI Automation, coordonatele se recalculează la fiecare scanare, deci
marcajul urmărește textul. Pentru sincronizare perfectă în pagini web,
instalează userscript-ul din `integrations/` prin **Tampermonkey** sau
**Violentmonkey**: acolo chenarul e atașat de nodul HTML. Se regenerează automat
la fiecare salvare de regulă.

### Jurnal

`focuspilot_log.txt`, rotativ la 2 MB. Pentru detalii complete:

```powershell
set FOCUSPILOT_DEBUG=1
pythonw.exe FocusPilot.pyw
```
