"""
Rulează toate testele FocusPilot.

    python tests/run_all.py

Testele Python nu au nevoie de Windows: modulele win32* și uiautomation sunt
înlocuite cu dubluri. Testele pentru userscript au nevoie de Node.js; dacă
lipsește, sunt raportate ca sărite, nu ca eșuate.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def run_python_tests() -> bool:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for name in ("test_rule_engine", "test_probe_engine", "test_examples",
                 "test_browser_injection"):
        suite.addTests(loader.discover(HERE, pattern=f"{name}.py", top_level_dir=HERE))

    print("=" * 70)
    print("TESTE PYTHON")
    print("=" * 70)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful()


def _generate_test_userscript(tmp_dir: str) -> str:
    """Generează userscript-ul din config.example.json într-un folder temporar."""
    from core.config_manager import ConfigManager
    from integrations.userscript_generator import generate_userscript

    shutil.copy(os.path.join(ROOT, "config.example.json"), tmp_dir)
    output = os.path.join(tmp_dir, "focuspilot_browser_highlighter.user.js")
    generate_userscript(ConfigManager(base_dir=tmp_dir), output_path=output)
    return output


def run_userscript_tests() -> bool:
    script = os.path.join(HERE, "test_userscript.js")
    print()
    print("=" * 70)
    print("TESTE USERSCRIPT (Node.js)")
    print("=" * 70)

    if not os.path.exists(script):
        print("  test_userscript.js lipsește — sărit.")
        return True

    # Userscript-ul real e generat din config.json, care nu mai e în repo
    # (conține URL-uri interne). Fără pasul ăsta, testele cădeau pe orice
    # clonă curată cu „Userscript-ul lipsește”. Generăm unul temporar din
    # config.example.json, deci rezultatul nu depinde de configurația locală.
    tmp_dir = tempfile.mkdtemp(prefix="focuspilot_test_")
    try:
        env = dict(os.environ)
        env["FOCUSPILOT_USERSCRIPT"] = _generate_test_userscript(tmp_dir)
        for runner in ("node", "node.exe"):
            try:
                completed = subprocess.run([runner, script], cwd=ROOT,
                                           env=env, timeout=120)
                return completed.returncode == 0
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                print("  Testele userscript au depășit timpul alocat.")
                return False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("  Node.js nu este instalat — testele pentru browser au fost sărite.")
    print("  (Logica din aplicație este acoperită de testele Python.)")
    return True


def main() -> int:
    python_ok = run_python_tests()
    node_ok = run_userscript_tests()

    print()
    print("=" * 70)
    print(f"Python:     {'TRECUT' if python_ok else 'EȘUAT'}")
    print(f"Userscript: {'TRECUT' if node_ok else 'EȘUAT'}")
    print("=" * 70)
    return 0 if (python_ok and node_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
