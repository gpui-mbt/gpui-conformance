"""Adversarial checks of a retained real nonactivating run; never launch GUI."""
import argparse
from pathlib import Path
import sys
import unittest

import test_native_evidence as native


class BackgroundEvidenceTests(native.NativeEvidenceTests):
    def test_missing_fixture_manifest_protocol_cannot_pass(self):
        del self.manifest["runs"]["moonbit"]["fixture_protocol"]
        self.unverified()

    def test_missing_fixture_output_protocol_cannot_pass(self):
        self.edit(lambda output: output.pop("native_fixture"))
        self.unverified()

    def test_wrong_executing_pid_cannot_pass(self):
        self.edit(lambda output: output["native_fixture"]["snapshots"][1].__setitem__("pid", 1))
        self.unverified()

    def test_visible_fixture_cannot_claim_hidden_execution(self):
        self.edit(lambda output: output["native_fixture"]["snapshots"][1].__setitem__("window_visible", True))
        self.unverified()

    def test_upstream_helper_identity_is_required(self):
        del self.manifest["runs"]["upstream"]["fixture_guard"]
        self.unverified()

    def test_upstream_helper_build_is_required(self):
        del self.manifest["runs"]["upstream"]["fixture_guard_build"]["pid"]
        self.unverified()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BackgroundEvidenceTests.evidence_dir = args.evidence.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
