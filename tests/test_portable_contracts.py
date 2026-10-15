"""Portable CI guards; published indexes never substitute for real artifacts."""
import contextlib
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
from contracts import valid_observation, validate_scenarios
from run import prepare_moonbit
import run_native


class PortableContractTests(unittest.TestCase):
    def test_committed_corpora_are_valid(self):
        for name in ("scenarios.json", "native_scenarios.json", "boundary_scenarios.json", "fractional_grow_scenarios.json", "gap_budget_scenarios.json", "fractional_shrink_scenarios.json", "minmax_scenarios.json", "flex_wrap_scenarios.json", "justify_between_scenarios.json"):
            with self.subTest(corpus=name):
                validate_scenarios(load_json(ROOT / name))

    def test_space_between_allows_empty_singleton_and_four_children(self):
        corpus = load_json(ROOT / "justify_between_scenarios.json")
        validate_scenarios(corpus)
        expected_counts = {
            "justify-between-empty": 0,
            "justify-between-singleton": 1,
            "justify-between-wrap-line-local": 4,
        }
        for scenario_id, expected_count in expected_counts.items():
            scenario = next(s for s in corpus["cases"] if s["id"] == scenario_id)
            self.assertEqual(len(scenario["children"]), expected_count)

        for scenario_id in (
            "justify-between-empty",
            "justify-between-singleton",
            "justify-between-wrap-line-local",
        ):
            invalid = copy.deepcopy(corpus)
            scenario = next(s for s in invalid["cases"] if s["id"] == scenario_id)
            scenario["justify"] = "start"
            with self.subTest(scenario_id=scenario_id), self.assertRaises(ValueError):
                validate_scenarios(invalid)

    def test_wrapping_is_bounded_to_three_layout_or_pointer_children(self):
        corpus = load_json(ROOT / "flex_wrap_scenarios.json")
        validate_scenarios(corpus)
        invalid_wrap = copy.deepcopy(corpus)
        invalid_wrap["cases"][0]["wrap"] = "wrap_always"
        with self.assertRaises(ValueError):
            validate_scenarios(invalid_wrap)
        too_many = copy.deepcopy(corpus)
        scenario = too_many["cases"][0]
        scenario["children"].append([10, 10])
        scenario["grow"].append(0)
        scenario["shrink"].append(0)
        scenario["min_main"].append(0)
        scenario["max_main"].append(None)
        with self.assertRaises(ValueError):
            validate_scenarios(too_many)

    def test_layout_line_origin_projection_is_explicit_and_shape_checked(self):
        corpus = load_json(ROOT / "flex_wrap_scenarios.json")
        validate_scenarios(corpus)
        exact_fit = next(s for s in corpus["cases"] if s["id"] == "wrap-decimal-exact-fit")
        self.assertTrue(valid_observation(exact_fit, {"line_origins": [0, 0]}))
        self.assertFalse(valid_observation(exact_fit, {"line_origins": [0]}))
        self.assertFalse(valid_observation(exact_fit, {"line_origins": [0, 0], "bounds": []}))

        invalid_mode = copy.deepcopy(corpus)
        invalid_mode["cases"][-1]["layout_observation"] = "rounded_bounds"
        with self.assertRaises(ValueError):
            validate_scenarios(invalid_mode)
        non_layout_mode = copy.deepcopy(corpus)
        pointer = next(s for s in non_layout_mode["cases"] if s["kind"] == "pointer")
        pointer["layout_observation"] = "line_origins"
        with self.assertRaises(ValueError):
            validate_scenarios(non_layout_mode)

    def test_layout_device_scale_is_bounded_and_layout_specific(self):
        corpus = load_json(ROOT / "flex_wrap_scenarios.json")
        validate_scenarios(corpus)
        scaled = copy.deepcopy(corpus)
        scaled["cases"][-1]["device_scale_factor"] = 2
        validate_scenarios(scaled)

        for value in (None, True, 0, -1, math.nan, math.inf, 8.1):
            invalid = copy.deepcopy(corpus)
            invalid["cases"][-1]["device_scale_factor"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_scenarios(invalid)

        non_layout = copy.deepcopy(corpus)
        pointer = next(s for s in non_layout["cases"] if s["kind"] == "pointer")
        pointer["device_scale_factor"] = 2
        with self.assertRaises(ValueError):
            validate_scenarios(non_layout)

    def test_layout_auto_cross_dimension_and_stretch_are_bounded(self):
        corpus = load_json(ROOT / "flex_wrap_scenarios.json")
        scenario = next(s for s in corpus["cases"] if s["id"] == "wrap-auto-cross-stretch-minimum")
        validate_scenarios(corpus)
        scenario["align"] = "not-stretch"
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)
        scenario["align"] = "stretch"
        scenario["children"][0][0] = None
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)
        pointer_corpus = load_json(ROOT / "flex_wrap_scenarios.json")
        pointer = next(s for s in pointer_corpus["cases"] if s["kind"] == "pointer")
        pointer["children"][0][1] = None
        with self.assertRaises(ValueError):
            validate_scenarios(pointer_corpus)

    def test_unknown_alignment_and_invalid_flex_factors_rejected(self):
        for field, value in (("justify", "arbitrary"), ("direction", "diagonal"), ("align", "unsafe"), ("grow", [-1, 0]), ("shrink", [1])):
            corpus = load_json(ROOT / "boundary_scenarios.json")
            corpus["cases"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_fractional_grow_factors_require_finite_bounded_numbers(self):
        for value in ([True, .25], [math.nan, .25], [math.inf, .25], [-1e-9, .25], [16.0001, 0], [.25]):
            corpus = load_json(ROOT / "fractional_grow_scenarios.json")
            corpus["cases"][0]["grow"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_fractional_shrink_factors_require_finite_bounded_numbers(self):
        for value in ([True, .25], [math.nan, .25], [math.inf, .25], [-1e-9, .25], [16.0001, 0], [.25]):
            corpus = load_json(ROOT / "fractional_shrink_scenarios.json")
            corpus["cases"][0]["shrink"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_main_axis_limits_require_valid_finite_bounded_pairs(self):
        for field, value in (("min_main", [True, 0]), ("min_main", [None, 0]), ("min_main", [math.nan, 0]), ("min_main", [-1, 0]), ("min_main", [4097, 0]), ("min_main", [0]), ("max_main", [math.inf, None]), ("max_main", [True, None]), ("max_main", [-1, None]), ("max_main", [4097, None]), ("max_main", [30]), ("max_main", None)):
            corpus = load_json(ROOT / "minmax_scenarios.json")
            corpus["cases"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_scenarios(corpus)
        corpus = load_json(ROOT / "minmax_scenarios.json")
        corpus["cases"][0]["min_main"] = [31, 0]
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)

    def test_limit_fields_cannot_be_silently_ignored_by_other_kinds(self):
        corpus = load_json(ROOT / "scenarios.json")
        scenario = next(s for s in corpus["cases"] if s["kind"] == "scene")
        scenario["max_main"] = [30, None]
        with self.assertRaises(ValueError):
            validate_scenarios(corpus)

    def test_invalid_routing_and_focus_inputs_rejected(self):
        for kind, field, value in (("route", "stop", [True, "capture"]), ("route", "points", []), ("focus", "focuses", [True]), ("focus", "key", "\n"), ("focus", "event", "arbitrary")):
            corpus = load_json(ROOT / "boundary_scenarios.json")
            scenario = next(s for s in corpus["cases"] if s["kind"] == kind)
            scenario[field] = value
            with self.subTest(kind=kind, field=field), self.assertRaises(ValueError):
                validate_scenarios(corpus)

    def test_native_runner_rejects_linux_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ([], ["--build-only"]):
                with self.subTest(mode=mode):
                    output = Path(directory) / ("native-output-" + str(len(mode)))
                    argv = ["run_native.py", *mode, "--output", str(output)]
                    with patch.object(sys, "argv", argv), \
                         patch("run_native.platform.system", return_value="Linux"), \
                         contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as error:
                            run_native.main()
                    self.assertEqual(error.exception.code, 2)
                    self.assertFalse(output.exists())

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
            self.assertIn(corpus_name, ("scenarios.json", "native_scenarios.json", "boundary_scenarios.json", "fractional_grow_scenarios.json", "gap_budget_scenarios.json", "fractional_shrink_scenarios.json", "minmax_scenarios.json", "flex_wrap_scenarios.json", "justify_between_scenarios.json"))
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
