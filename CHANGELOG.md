# CHANGELOG — FocusPilot

## 2026-10-27
- `config.json` și userscript-ul generat ies din repo (conțin URL-uri interne); în repo rămâne `config.example.json`, cu reguli fictive.
- Testele userscript generează un script temporar din `config.example.json`, deci trec pe o clonă curată, fără configurația locală.
- Jurnalele rotite (`focuspilot_log.txt.1` etc.) sunt ignorate de git, ca să nu mai apară în `git status`.
- Teste: `python tests/run_all.py` — 172 Python + 20 JavaScript, toate trecute.
