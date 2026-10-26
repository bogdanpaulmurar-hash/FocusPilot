# CHANGELOG — FocusPilot

## 2026-10-27
- Injectare directă în browser prin CDP, pornită din Setări → Browser: livrează userscript-ul generat în toate taburile Chrome / Edge, fără extensie; reaplicat în taburile noi, după navigare și după salvarea regulilor, cu stare vizibilă în setări. Userscript-ul nu se mai dublează la reinjectare. Teste: 190 Python (2 pe browser real) + 20 JavaScript, trecute.
- `config.json` și userscript-ul generat ies din repo (conțin URL-uri interne); în repo rămâne `config.example.json`, cu reguli fictive.
- Testele userscript generează un script temporar din `config.example.json`, deci trec pe o clonă curată, fără configurația locală.
- Teste: `python tests/run_all.py` — 172 Python + 20 JavaScript, toate trecute.
- `.gitignore` acoperă și jurnalele rotite (`focuspilot_log.txt.*`). Teste: 172 Python + 20 JavaScript, trecute.
