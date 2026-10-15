"""Replay/tamper checks of real owned observer evidence; no GUI launches."""
import argparse
import json
from pathlib import Path
import sys
import unittest

import test_native_evidence as native
from comparator import digest


class ObserverEvidenceTests(native.NativeEvidenceTests):
    def observation(self): return self.manifest["runs"]["moonbit"]["observer"]

    def edit_artifact(self, record, callback):
        path = self.root/record["path"]
        value = json.loads(path.read_text())
        callback(value)
        path.write_text(json.dumps(value)+"\n")
        record["sha256"] = digest(path.read_bytes())

    def test_missing_observer_cannot_pass(self):
        del self.manifest["runs"]["moonbit"]["observer"]
        self.unverified()

    def test_wrong_ready_window_cannot_pass(self):
        self.edit_artifact(self.observation()["ready"], lambda r:r.__setitem__("native_window_id",789))
        self.unverified()

    def test_wrong_ready_scale_cannot_pass(self):
        self.edit_artifact(self.observation()["ready"], lambda r:r.__setitem__("scale",1))
        self.unverified()

    def test_stale_ready_cannot_pass(self):
        self.edit_artifact(self.observation()["ready"], lambda r:r.__setitem__("ready_unix_ns",0))
        self.unverified()

    def test_wrong_ack_challenge_cannot_pass(self):
        self.edit_artifact(self.observation()["ack"], lambda r:r.__setitem__("run_token","wrong"))
        self.unverified()

    def test_boolean_frame_ack_cannot_pass(self):
        self.edit_artifact(self.observation()["ack"], lambda r:r.__setitem__("frame_sequence",True))
        self.unverified()

    def test_unrelated_successful_command_cannot_pass(self):
        self.observation()["execution"]["command"][0] = "/usr/bin/true"
        self.unverified()

    def test_wrong_control_command_cannot_pass(self):
        self.observation()["negative_controls"][0]["execution"]["command"][0] = "/usr/bin/true"
        self.unverified()

    def test_control_before_owned_fixture_cannot_pass(self):
        record = self.observation()["negative_controls"][0]["execution"]
        record.update(started_at="2020-01-01T00:00:00+00:00",finished_at="2020-01-01T00:00:01+00:00")
        self.unverified()

    def test_missing_identity_controls_cannot_pass(self):
        self.observation()["negative_controls"].pop()
        self.unverified()

    def test_control_that_accepts_target_cannot_pass(self):
        self.edit_artifact(self.observation()["negative_controls"][0]["stdout"], lambda r:r.__setitem__("window_binding","pass"))
        self.unverified()

    def test_relabelled_ax_without_matched_fields_cannot_pass(self):
        self.observation()["ax_status"] = "pass"
        self.edit_artifact(self.observation()["stdout"], lambda r:r.update(ax_status="pass",ax_trusted=True,ax_matching_windows=1,ax_windows=[]))
        self.unverified()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    ObserverEvidenceTests.evidence_dir = args.evidence.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
