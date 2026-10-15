"""Portable CI guards; published indexes never substitute for real artifacts."""
import copy
import io
import math
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparator import STATUSES, compare, differences, load_json
from contracts import validate_scenarios
from run import prepare_moonbit


class PortableContractTests(unittest.TestCase):
    def test_committed_corpora_are_valid(self):
        for name in ("scenarios.json", "native_scenarios.json", "boundary_scenarios.json"):
            with self.subTest(corpus=name):
                validate_scenarios(load_json(ROOT / name))

    def test_unknown_alignment_and_invalid_flex_factors_rejected(self):
        for field, value in (("justify", "arbitrary"), ("direction", "diagonal"), ("align", "unsafe"), ("grow", [-1, 0]), ("shrink", [1])):
            corpus = load_json(ROOT / "boundary_scenarios.json")
            corpus["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_invalid_routing_and_focus_inputs_rejected(self):
        for kind, field, value in (("route", "stop", [True, "capture"]), ("route", "points", []), ("focus", "focuses", [True]), ("focus", "key", "\n"), ("focus", "event", "arbitrary")):
            corpus = load_json(ROOT / "boundary_scenarios.json")
            scenario = next(s for s in corpus["cases"] if s["kind"] == kind)
            scenario[field] = value
            with self.subTest(kind=kind, field=field), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_native_preparation_does_not_mix_headless_sources(self):
        # This checks copying only, never invents executable oracle evidence.
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as tar:
            content = b'version = "0.7.2"\n'
            info = tarfile.TarInfo("moon.mod")
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = root / "adapter"
            adapter.mkdir()
            (adapter / "native-only.mbt").write_text("native fixture source")
            with patch("run.subprocess.check_output", return_value=archive.getvalue()):
                runtime = prepare_moonbit(root, root / "build", adapter)
            self.assertEqual({p.name for p in (runtime / "conformance_probe").iterdir()}, {"native-only.mbt"})

    def test_duplicate_scenario_ids_rejected(self):
        corpus = load_json(ROOT / "scenarios.json")
        corpus["cases"].append(copy.deepcopy(corpus["cases"][0]))
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)

    def test_native_sample_outside_viewport_rejected(self):
        corpus = load_json(ROOT / "native_scenarios.json")
        pixels = corpus["cases"][1]
        pixels["points"][0][0] = pixels["width"]
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)

    def test_numeric_tolerance_and_nonfinite_values(self):
        self.assertEqual(differences(1, 1.00001), [])
        self.assertTrue(differences(1, 1.001))
        self.assertTrue(differences(math.nan, math.nan))
        self.assertTrue(differences(math.inf, math.inf))
        self.assertTrue(differences(True, 1))

    def test_structure_and_field_path_divergence(self):
        result = differences({"samples": [[0, 255]]}, {"samples": [[0, 0]]})
        self.assertEqual(result, [{"path": "observation.samples[0][1]", "upstream": 255, "moonbit": 0}])
        self.assertTrue(differences([1], [1, 2]))
        self.assertTrue(differences({"a": 1}, {"b": 1}))

    def test_published_index_summaries_match_rows(self):
        for path in (ROOT / "results").glob("*.json"):
            index = load_json(path)
            for name, execution in index["executions"].items():
                with self.subTest(index=path.name, execution=name):
                    result = execution.get("comparison", execution)
                    self.assertTrue(result["cases"])
                    self.assertEqual(len({c["id"] for c in result["cases"]}), len(result["cases"]))
                    self.assertTrue(all(c["status"] in STATUSES for c in result["cases"]))
                    self.assertEqual(result["summary"], {s: sum(c["status"] == s for c in result["cases"]) for s in STATUSES})

    def test_index_without_artifacts_cannot_establish_passes(self):
        for path in (ROOT / "results").glob("*.json"):
            index = load_json(path)
            native = path.name.startswith("native-")
            corpus_name = index.get("corpus", "native_scenarios.json" if native else "scenarios.json")
            self.assertIn(corpus_name, ("scenarios.json", "native_scenarios.json", "boundary_scenarios.json"))
            scenario_path = ROOT / corpus_name
            corpus = load_json(scenario_path)
            for name, execution in index["executions"].items():
                with self.subTest(index=path.name, execution=name), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / "scenarios.json").write_bytes(scenario_path.read_bytes())
                    manifest = execution.get("manifest", {
                        "schema_version": 1,
                        "platform": index.get("platform"),
                        "pins": execution.get("pins"),
                        "runs": execution.get("process_evidence"),
                    })
                    result = compare(manifest, corpus, root)
                    self.assertEqual(result["summary"], {"pass": 0, "mismatch": 0, "unsupported": 0, "unverified": len(corpus["cases"])})


if __name__ == "__main__":
    unittest.main()
