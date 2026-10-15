"""Adversarial checks using a real retained run, never synthetic goldens.

Usage: python3 tests/test_comparator.py --evidence _build/baseline
For a non-default corpus, pass both --corpus and --expected-summary. The
evidence directory is copied before each deliberately damaged test.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparator import PREFIX, STATUSES, compare, digest, load_json
from contracts import validate_scenarios


LEGACY_SUMMARY = {"pass": 6, "mismatch": 2, "unsupported": 1, "unverified": 2}
SUITE_ROOT = Path(__file__).resolve().parents[1]


def read_scenarios(path):
    scenarios = load_json(path)
    if not isinstance(scenarios, dict):
        raise ValueError("scenario corpus must be a JSON object")
    try:
        validate_scenarios(scenarios)
    except (AttributeError, KeyError, TypeError) as exc:
        raise ValueError(f"malformed scenario corpus: {exc}") from exc
    return scenarios


def read_expected_summary(path, scenario_count):
    summary = load_json(path)
    if not isinstance(summary, dict) or set(summary) != set(STATUSES):
        raise ValueError("expected summary must define exactly: " + ", ".join(STATUSES))
    if any(type(summary[key]) is not int or summary[key] < 0 for key in STATUSES):
        raise ValueError("expected summary counts must be nonnegative integers")
    if sum(summary.values()) != scenario_count:
        raise ValueError("expected summary counts must add up to the scenario corpus size")
    return summary


def checker_configuration(evidence_dir, corpus_path=None, summary_path=None):
    """Load an explicit corpus/summary pair and bind both to retained evidence."""
    if (corpus_path is None) != (summary_path is None):
        raise ValueError("--corpus and --expected-summary must be supplied together")

    retained = read_scenarios(Path(evidence_dir) / "scenarios.json")
    if corpus_path is None:
        expected = read_scenarios(SUITE_ROOT / "scenarios.json")
        if retained != expected:
            raise ValueError("non-default evidence requires explicit --corpus and --expected-summary")
        return expected, dict(LEGACY_SUMMARY)

    expected = read_scenarios(corpus_path)
    if expected != retained:
        raise ValueError("explicit corpus differs from retained evidence scenarios")
    first_slice = read_scenarios(SUITE_ROOT / "scenarios.json")
    if expected["cases"][:len(first_slice["cases"])] != first_slice["cases"]:
        raise ValueError("explicit corpus must retain the original first-slice cases in canonical order")
    summary = read_expected_summary(summary_path, len(expected["cases"]))
    return expected, summary


class ComparatorTests(unittest.TestCase):
    evidence_dir = None
    expected_scenarios = None
    expected_summary = None

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "evidence"
        shutil.copytree(self.evidence_dir, self.root)
        self.manifest = load_json(self.root / "manifest.json")
        self.scenarios = load_json(self.root / "scenarios.json")
        self.assertEqual(self.scenarios, self.expected_scenarios)

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

    def test_real_evidence_matches_expected_summary(self):
        result = self.compare()
        self.assertEqual(result["summary"], self.expected_summary)

    def test_default_configuration_stays_bound_to_original_corpus(self):
        if self.expected_scenarios == read_scenarios(SUITE_ROOT / "scenarios.json"):
            scenarios, summary = checker_configuration(self.evidence_dir)
            self.assertEqual(scenarios, self.expected_scenarios)
            self.assertEqual(summary, LEGACY_SUMMARY)
        else:
            with self.assertRaisesRegex(ValueError, "non-default evidence"):
                checker_configuration(self.evidence_dir)

    def test_explicit_configuration_requires_both_inputs(self):
        with self.assertRaisesRegex(ValueError, "supplied together"):
            checker_configuration(self.evidence_dir, corpus_path=self.root / "scenarios.json")

    def test_explicit_configuration_rejects_duplicate_scenario_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            corpus = load_json(self.root / "scenarios.json")
            corpus["cases"].append(dict(corpus["cases"][0]))
            corpus_path = Path(temp) / "scenarios.json"
            summary_path = Path(temp) / "summary.json"
            corpus_path.write_text(json.dumps(corpus))
            summary_path.write_text(json.dumps(self.expected_summary))
            with self.assertRaisesRegex(ValueError, "duplicate scenario ID"):
                checker_configuration(self.evidence_dir, corpus_path, summary_path)

    def test_explicit_configuration_rejects_missing_corpus_cases(self):
        with tempfile.TemporaryDirectory() as temp:
            corpus = load_json(self.root / "scenarios.json")
            corpus["cases"].pop()
            corpus_path = Path(temp) / "scenarios.json"
            summary_path = Path(temp) / "summary.json"
            corpus_path.write_text(json.dumps(corpus))
            summary_path.write_text(json.dumps(self.expected_summary))
            with self.assertRaisesRegex(ValueError, "differs from retained evidence"):
                checker_configuration(self.evidence_dir, corpus_path, summary_path)

    def test_explicit_configuration_requires_original_fixture_prefix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "evidence"
            root.mkdir()
            corpus = load_json(self.root / "scenarios.json")
            corpus["cases"] = corpus["cases"][1:]
            (root / "scenarios.json").write_text(json.dumps(corpus))
            corpus_path = Path(temp) / "corpus.json"
            summary_path = Path(temp) / "summary.json"
            corpus_path.write_text(json.dumps(corpus))
            summary_path.write_text(json.dumps({"pass": len(corpus["cases"]), "mismatch": 0, "unsupported": 0, "unverified": 0}))
            with self.assertRaisesRegex(ValueError, "original first-slice cases"):
                checker_configuration(root, corpus_path, summary_path)

    def test_explicit_configuration_rejects_malformed_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = dict(self.expected_summary)
            del summary["unverified"]
            summary_path = Path(temp) / "summary.json"
            summary_path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, "exactly"):
                checker_configuration(self.evidence_dir, self.root / "scenarios.json", summary_path)

    def test_explicit_configuration_rejects_incomplete_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = dict(self.expected_summary)
            summary["unverified"] += 1
            summary_path = Path(temp) / "summary.json"
            summary_path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, "add up"):
                checker_configuration(self.evidence_dir, self.root / "scenarios.json", summary_path)

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
    parser.add_argument("--corpus", type=Path, help="Explicit scenario corpus matching the retained evidence")
    parser.add_argument("--expected-summary", type=Path, help="JSON status counts for the explicit corpus")
    args, unittest_args = parser.parse_known_args()
    ComparatorTests.evidence_dir = args.evidence.resolve()
    try:
        (ComparatorTests.expected_scenarios,
         ComparatorTests.expected_summary) = checker_configuration(
             ComparatorTests.evidence_dir, args.corpus, args.expected_summary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    unittest.main(argv=[sys.argv[0], *unittest_args])
