"""Keep synthetic diagnostic units independent of the global ``verify`` module."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

# A fresh interpreter prevents this regression test from changing discovery's own
# module cache. Both orders use the real unrelated checker, not a permissive stub.
PROBE = r'''
import importlib.util
from pathlib import Path
import sys
import unittest

root = Path(sys.argv[1])
order = sys.argv[2]
original_path = list(sys.path)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_foreign():
    module = load("verify", root / "diagnostics/nested_deferred/verify.py")
    sys.modules["verify"] = module
    return module

if order == "foreign-first":
    foreign = load_foreign()
units = load("uniform_list_units_probe", root / "tests/test_uniform_list_diagnostic.py")
if order == "uniform-first":
    assert "verify" not in sys.modules, "uniform-list import polluted the generic module name"
    foreign = load_foreign()
assert sys.path == original_path, "uniform-list import changed the global module search path"
assert sys.modules["verify"] is foreign
assert units.verify is not foreign
assert Path(units.verify.__file__).resolve() == root / "diagnostics/uniform_list/verify.py"
suite = unittest.defaultTestLoader.loadTestsFromModule(units)
assert suite.countTestCases() == 17
result = unittest.TextTestRunner(verbosity=1).run(suite)
assert result.wasSuccessful()
assert sys.modules["verify"] is foreign
assert sys.path == original_path
'''


class UniformListImportIsolation(unittest.TestCase):
    def check_order(self, order):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, "-c", PROBE, str(ROOT), order],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foreign_checker_imported_first(self):
        self.check_order("foreign-first")

    def test_uniform_list_imported_first(self):
        self.check_order("uniform-first")


if __name__ == "__main__":
    unittest.main()
