"""Adversarial checks derived from the retained real 13-case batch baseline."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparator import PREFIX, compare, digest, load_json


class BoundaryEvidenceTests(unittest.TestCase):
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

    def row(self, identifier):
        return next(c for c in self.compare()["cases"] if c["id"] == identifier)

    def edit(self, identifier, callback, names=("moonbit",)):
        for name in names:
            run = self.manifest["runs"][name]
            path = self.root / run["stdout"]["path"]
            payload = json.loads(next(line[len(PREFIX):] for line in path.read_text().splitlines() if line.startswith(PREFIX)))
            callback(next(c["observation"] for c in payload["cases"] if c["id"] == identifier))
            path.write_text(PREFIX + json.dumps(payload) + "\n")
            run["stdout"]["sha256"] = digest(path.read_bytes())

    def test_real_baseline(self):
        self.assertEqual(self.compare()["summary"], {"pass":9,"mismatch":4,"unsupported":0,"unverified":0})

    def test_changed_focus_detected(self):
        self.edit("focus-switch-and-blur", lambda o: o["steps"][0].__setitem__("focused", 3))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "mismatch")

    def test_dropped_capture_detected(self):
        self.edit("focus-switch-and-blur", lambda o: o["steps"][1]["events"].pop(0))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "mismatch")

    def test_changed_phase_detected(self):
        self.edit("pointer-route-phases", lambda o: o["events"][0][0].__setitem__(1, "bubble"))
        self.assertEqual(self.row("pointer-route-phases")["status"], "mismatch")

    def test_dropped_pointer_callback_detected(self):
        self.edit("pointer-route-phases", lambda o: o["events"][0].pop())
        self.assertEqual(self.row("pointer-route-phases")["status"], "mismatch")

    def test_empty_focus_traces_cannot_pass(self):
        self.edit("focus-switch-and-blur", lambda o: [step.__setitem__("events", []) for step in o["steps"]], ("upstream", "moonbit"))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "unverified")

    def test_empty_pointer_traces_cannot_pass(self):
        self.edit("pointer-route-phases", lambda o: o.__setitem__("events", [[] for _ in o["events"]]), ("upstream", "moonbit"))
        self.assertEqual(self.row("pointer-route-phases")["status"], "unverified")

    def test_short_focus_sequence_cannot_pass(self):
        self.edit("focus-switch-and-blur", lambda o: o["steps"].pop(), ("upstream", "moonbit"))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "unverified")

    def test_unknown_listener_cannot_pass(self):
        self.edit("pointer-route-phases", lambda o: o["events"][0][0].__setitem__(0, 99), ("upstream", "moonbit"))
        self.assertEqual(self.row("pointer-route-phases")["status"], "unverified")

    def test_boolean_focus_cannot_pass(self):
        self.edit("focus-switch-and-blur", lambda o: o["steps"][0].__setitem__("focused", True), ("upstream", "moonbit"))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "unverified")

    def test_missing_focus_field_cannot_pass(self):
        self.edit("focus-switch-and-blur", lambda o: o["steps"][0].pop("focused"), ("upstream", "moonbit"))
        self.assertEqual(self.row("focus-switch-and-blur")["status"], "unverified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BoundaryEvidenceTests.evidence_dir = args.evidence.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
