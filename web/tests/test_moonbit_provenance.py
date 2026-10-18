"""Current candidate source and shipped host-byte identity, not runtime parity."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_moonbit.py"
SPEC = importlib.util.spec_from_file_location("moonbit_build_provenance", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MoonBitProvenanceTests(unittest.TestCase):
    def test_current_candidate_requires_revision_clean_source_and_exact_tree(self):
        pin = {"revision": "a" * 40, "tree": "b" * 40}
        with patch.object(MODULE, "run", side_effect=[pin["revision"], "", pin["tree"]]):
            MODULE.check_candidate_source(Path("candidate"), pin)
        for answers in [["c" * 40], [pin["revision"], " M element/core.mbt"],
                        [pin["revision"], "", "c" * 40]]:
            with self.subTest(answers=answers), patch.object(MODULE, "run", side_effect=answers), self.assertRaises(ValueError):
                MODULE.check_candidate_source(Path("candidate"), pin)
        for tree in [None, "", "b" * 39, "B" * 40]:
            bad = {"revision": pin["revision"], "tree": tree}
            with self.subTest(tree=tree), patch.object(MODULE, "run", side_effect=[pin["revision"], ""]), self.assertRaises(ValueError):
                MODULE.check_candidate_source(Path("candidate"), bad)
        with patch.object(MODULE, "run", side_effect=[pin["revision"], ""]), self.assertRaises(ValueError):
            MODULE.check_candidate_source(Path("candidate"), {"revision": pin["revision"]})

    def test_host_map_hashes_shipped_bytes_and_excludes_compiled_modules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources, site = root / "sources", root / "site"
            sources.mkdir()
            (site / "moonbit").mkdir(parents=True)
            for name in ["host.mjs", "render.mjs", "focus-visible-host.mjs"]:
                (sources / name).write_text("source marker")
                (site / "moonbit" / name).write_text("shipped " + name)
            (site / "load-timing.mjs").write_text("timing")
            (site / "moonbit/focus_visible.mjs").write_text("compiled runtime")
            actual = MODULE.moonbit_host_hashes(site, sources)
            self.assertEqual(set(actual), {"load-timing.mjs", "moonbit/host.mjs",
                                          "moonbit/render.mjs", "moonbit/focus-visible-host.mjs"})
            for path, digest in actual.items():
                self.assertEqual(digest, hashlib.sha256((site / path).read_bytes()).hexdigest())
            (site / "moonbit/render.mjs").write_text("changed shipped renderer")
            self.assertNotEqual(actual["moonbit/render.mjs"], MODULE.moonbit_host_hashes(site, sources)["moonbit/render.mjs"])
            (site / "moonbit/host.mjs").unlink()
            with self.assertRaises(FileNotFoundError):
                MODULE.moonbit_host_hashes(site, sources)


if __name__ == "__main__":
    unittest.main()
