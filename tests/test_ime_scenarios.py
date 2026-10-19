"""Validate the declared Web TextField/IME corpus without executing a browser."""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "ime_scenarios.json"
ALLOWED_CASE_STATUSES = {"candidate-only", "unsupported", "unverified"}


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
