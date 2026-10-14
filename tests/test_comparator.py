"""Adversarial checks using a real retained run, never synthetic goldens.

Usage: python3 tests/test_comparator.py --evidence _build/baseline-03
The evidence directory is copied before each deliberately damaged test.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparator import PREFIX, compare, digest, load_json
from contracts import validate_scenarios


class ComparatorTests(unittest.TestCase):
    evidence_dir = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "evidence"
        shutil.copytree(self.evidence_dir, self.root)
        self.manifest = load_json(self.root / "manifest.json")
        self.scenarios = load_json(self.root / "scenarios.json")

    def tearDown(self):
        self.temp.cleanup()

    def compare(self):
        return compare(self.manifest, self.scenarios, self.root)

    def unverified(self):
        result = self.compare()
        self.assertEqual(result["summary"]["pass"], 0)
        self.assertEqual(result["summary"]["unverified"], len(self.scenarios["cases"]))

    def edit_output(self, name, edit):
        run = self.manifest["runs"][name]
        path = self.root / run["stdout"]["path"]
        payload = json.loads(path.read_text().split(PREFIX)[1])
        edit(payload)
        path.write_text(PREFIX + json.dumps(payload) + "\n")
        run["stdout"]["sha256"] = digest(path.read_bytes())

    def test_real_baseline_has_measured_passes_and_mismatches(self):
        result = self.compare()
        self.assertEqual(result["summary"], {"pass":6,"mismatch":2,"unsupported":1,"unverified":2})

    def test_paint_color_divergence_detected(self):
        self.edit_output("moonbit", lambda p: p["cases"][2]["observation"]["quads"][0]["rgba"].__setitem__(0, 33))
        self.assertEqual(self.compare()["cases"][2]["status"], "mismatch")

    def test_empty_paint_cannot_pass(self):
        for name in ("upstream", "moonbit"):
            self.edit_output(name, lambda p: p["cases"][2].__setitem__("observation", {"quads":[]}))
        self.assertEqual(self.compare()["cases"][2]["status"], "unverified")

    def test_dropped_quad_is_mismatch(self):
        self.edit_output("moonbit", lambda p: p["cases"][2]["observation"]["quads"].pop())
        self.assertEqual(self.compare()["cases"][2]["status"], "mismatch")

    def test_dropped_key_is_mismatch(self):
        def remove_key(p):
            next(c for c in p["cases"] if c["id"] == "key-modifiers")["observation"]["keys"].pop()
        self.edit_output("moonbit", remove_key)
        row = next(c for c in self.compare()["cases"] if c["id"] == "key-modifiers")
        self.assertEqual(row["status"], "mismatch")

    def test_semantic_divergence_detected(self):
        self.edit_output("moonbit", lambda p: p["cases"][0]["observation"]["bounds"][1].__setitem__(2, 21))
        row = self.compare()["cases"][0]
        self.assertEqual(row["status"], "mismatch")
        self.assertEqual(row["differences"][0]["path"], "observation.bounds[1][2]")

    def test_missing_execution(self):
        del self.manifest["runs"]["moonbit"]["execution"]
        self.unverified()

    def test_failed_build(self):
        self.manifest["runs"]["moonbit"]["build"]["returncode"] = 1
        self.unverified()

    def test_missing_build_identity(self):
        del self.manifest["runs"]["moonbit"]["build"]["pid"]
        self.unverified()

    def test_missing_start_time(self):
        del self.manifest["runs"]["moonbit"]["execution"]["started_at"]
        self.unverified()

    def test_missing_pins(self):
        del self.manifest["pins"]
        for run in self.manifest["runs"].values():
            run["revision"] = None
        self.unverified()

    def test_moving_pin(self):
        self.manifest["pins"]["upstream"]["revision"] = "main"
        self.manifest["runs"]["upstream"]["revision"] = "main"
        self.unverified()

    def test_invalid_tree(self):
        self.manifest["runs"]["moonbit"]["source_tree"] = "x" * 40
        self.unverified()

    def test_wrong_version(self):
        self.manifest["runs"]["moonbit"]["version"] = "99.99.99"
        self.unverified()

    def test_cross_platform(self):
        self.manifest["runs"]["moonbit"]["platform"] = {"os":"Windows"}
        self.unverified()

    def test_missing_architecture_everywhere(self):
        del self.manifest["platform"]["architecture"]
        for run in self.manifest["runs"].values():
            del run["platform"]["architecture"]
        self.unverified()

    def test_unknown_manifest_schema(self):
        self.manifest["schema_version"] = 99
        self.unverified()

    def test_missing_manifest_schema(self):
        del self.manifest["schema_version"]
        self.unverified()

    def test_failed_execution(self):
        self.manifest["runs"]["moonbit"]["execution"]["returncode"] = -9
        self.unverified()

    def test_timeout(self):
        self.manifest["runs"]["moonbit"]["execution"]["timed_out"] = True
        self.unverified()

    def test_missing_executable(self):
        (self.root / self.manifest["runs"]["moonbit"]["executable"]["path"]).unlink()
        self.unverified()

    def test_tampered_raw_trace(self):
        path = self.root / self.manifest["runs"]["moonbit"]["stdout"]["path"]
        path.write_text(path.read_text() + "tampered\n")
        self.unverified()

    def test_identical_fabricated_traces(self):
        for name in ("upstream", "moonbit"):
            run = self.manifest["runs"][name]
            path = self.root / run["stdout"]["path"]
            path.write_text(PREFIX + '{"cases":[],"implementation":"fake"}\n')
            run["stdout"]["sha256"] = digest(path.read_bytes())
        self.unverified()

    def test_same_execution_challenge(self):
        self.manifest["runs"]["moonbit"]["run_token"] = self.manifest["runs"]["upstream"]["run_token"]
        self.unverified()

    def test_empty_observation_cannot_pass(self):
        for name in ("upstream", "moonbit"):
            self.edit_output(name, lambda p: p["cases"][0].__setitem__("observation", {"bounds":[]}))
        self.assertEqual(self.compare()["cases"][0]["status"], "unverified")

    def test_relabelled_native_coverage_cannot_pass(self):
        self.edit_output("moonbit", lambda p: p["cases"][0].__setitem__("layer", "native-gpu"))
        self.assertEqual(self.compare()["cases"][0]["status"], "unverified")

    def test_duplicate_case(self):
        self.edit_output("moonbit", lambda p: p["cases"].append(p["cases"][0]))
        self.unverified()

    def test_missing_case(self):
        self.edit_output("moonbit", lambda p: p["cases"].pop())
        self.unverified()

    def test_escaping_artifact(self):
        self.manifest["runs"]["moonbit"]["stdout"]["path"] = "../../outside.log"
        self.unverified()

    def test_invalid_scenario_rejected(self):
        self.scenarios["cases"][0]["children"] = []
        with self.assertRaises(ValueError):
            validate_scenarios(self.scenarios)

    def test_disjoint_clips_rejected_for_first_slice(self):
        clip = next(s for s in self.scenarios["cases"] if s["kind"] == "clip")
        clip["clips"] = [[0,0,10,10],[30,30,10,10]]
        with self.assertRaises(ValueError):
            validate_scenarios(self.scenarios)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args, unittest_args = parser.parse_known_args()
    ComparatorTests.evidence_dir = args.evidence.resolve()
    unittest.main(argv=[sys.argv[0], *unittest_args])
