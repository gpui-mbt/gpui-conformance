"""Validate the declared Web TextField/IME corpus without executing a browser."""
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "ime_scenarios.json"
ALLOWED_CASE_STATUSES = {"candidate-only", "unsupported", "unverified"}
TEST_DECLARATION = re.compile(r"^test\(\s*'([^']+)'", re.MULTILINE)


class ImeCorpusTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads(CORPUS.read_text(encoding="utf-8"))

    def test_corpus_shape_and_unique_cases(self):
        self.assertEqual(self.corpus["schema_version"], 1)
        self.assertEqual(self.corpus["layer"], "ime")
        cases = self.corpus["cases"]
        self.assertGreaterEqual(len(cases), 7)
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["kind"], "ime")
                self.assertEqual(case["layer"], "ime")
                self.assertIn(case["status"], ALLOWED_CASE_STATUSES)
                self.assertTrue((ROOT / case["source"]).is_file())

    def declared_tests(self) -> list[str]:
        runner = self.corpus["runner"]
        source = runner.removeprefix("node --test ").strip()
        return TEST_DECLARATION.findall((ROOT / source).read_text(encoding="utf-8"))

    def validate_case_tests(self, cases: list[dict], tests: list[str]) -> None:
        declared = [case.get("test") for case in cases]
        self.assertTrue(all(isinstance(name, str) and name for name in declared))
        self.assertEqual(len(declared), len(set(declared)))
        self.assertEqual(set(declared), set(tests))

    def test_case_ids_bind_to_exact_node_tests(self):
        self.validate_case_tests(self.corpus["cases"], self.declared_tests())

    def test_renamed_or_missing_node_test_is_rejected(self):
        cases = [dict(case) for case in self.corpus["cases"]]
        cases[0]["test"] = "renamed test that does not exist"
        with self.assertRaises(AssertionError):
            self.validate_case_tests(cases, self.declared_tests())
        with self.assertRaises(AssertionError):
            self.validate_case_tests(cases[1:], self.declared_tests())

    def test_runner_is_the_existing_web_lane(self):
        runner = self.corpus["runner"]
        self.assertTrue(runner.startswith("node --test "))
        source = runner.removeprefix("node --test ").strip()
        self.assertTrue((ROOT / source).is_file())
        for case in self.corpus["cases"]:
            self.assertEqual(case["source"], source)

    def test_no_differential_or_live_ime_claim(self):
        reference = self.corpus["reference"]
        self.assertEqual(reference["status"], "unsupported")
        self.assertIn("no TextField or IME transport", reference["reason"])
        raw = CORPUS.read_text(encoding="utf-8").lower()
        self.assertNotIn('"status": "pass"', raw)
        self.assertNotIn("live japanese ime", raw)


if __name__ == "__main__":
    unittest.main()
