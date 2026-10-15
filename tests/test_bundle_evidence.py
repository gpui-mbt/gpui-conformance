"""Replay/tamper actual bundled native evidence; no application launches."""
import argparse
import json
from pathlib import Path
import plistlib
import sys
import unittest

from test_observer_evidence import ObserverEvidenceTests
from comparator import digest


class BundleEvidenceTests(ObserverEvidenceTests):
    def run_record(self): return self.manifest["runs"]["moonbit"]

    def test_missing_packaging_identity_cannot_pass(self):
        del self.run_record()["fixture_packaging"]
        self.unverified()

    def test_unknown_packaging_identity_cannot_pass(self):
        self.run_record()["fixture_packaging"] = "unknown"
        self.unverified()

    def test_missing_or_tampered_plist_cannot_pass(self):
        (self.root/self.run_record()["bundle_info_plist"]["path"]).unlink()
        self.unverified()

    def test_rehashed_malformed_xml_plist_is_unverified(self):
        record = self.run_record()["bundle_info_plist"]
        path = self.root/record["path"]
        path.write_bytes(b'<?xml version="1.0"?><plist><dict>')
        record["sha256"] = digest(path.read_bytes())
        self.unverified()

    def test_rehashed_wrong_policy_or_identifier_plist_cannot_pass(self):
        record = self.run_record()["bundle_info_plist"]
        path = self.root/record["path"]
        original = plistlib.loads(path.read_bytes())
        for key,value in (("CFBundleIdentifier","foreign"),("LSUIElement",False),("LSUIElement",1),
                          ("NSPrincipalClass","ForeignApplication"),("CFBundleExecutable","foreign")):
            path.write_bytes(plistlib.dumps({**original,key:value}))
            record["sha256"] = digest(path.read_bytes())
            with self.subTest(key=key,value=value): self.unverified()

    def test_rehashed_runtime_bundle_identity_cannot_pass(self):
        self.edit_artifact(self.observation()["ready"],lambda r:r["local_ax"].__setitem__("running_bundle_identifier","foreign"))
        self.unverified()

    def test_unread_runtime_bundle_identity_cannot_pass(self):
        self.edit_artifact(self.observation()["ready"],lambda r:r.__setitem__("local_ax_read",False))
        self.unverified()

    def test_execution_outside_retained_bundle_layout_cannot_pass(self):
        self.run_record()["execution"]["command"][0] = "/foreign/probe"
        self.unverified()

    def test_extra_executable_arguments_cannot_pass(self):
        self.run_record()["execution"]["command"].append("foreign")
        self.unverified()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence",type=Path,required=True)
    args,remaining = parser.parse_known_args()
    BundleEvidenceTests.evidence_dir = args.evidence.resolve()
    unittest.main(argv=[sys.argv[0],*remaining],defaultTest="BundleEvidenceTests")
