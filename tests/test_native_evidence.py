"""Adversarial validation of a retained real native run; no GUI launches."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from comparator import PREFIX, compare, digest, load_json
from contracts import validate_scenarios
from run import execute


class NativeEvidenceTests(unittest.TestCase):
    evidence_dir=None
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/"evidence"
        shutil.copytree(self.evidence_dir,self.root)
        self.manifest=load_json(self.root/"manifest.json")
        self.scenarios=load_json(self.root/"scenarios.json")
    def tearDown(self): self.temp.cleanup()
    def compare(self): return compare(self.manifest,self.scenarios,self.root)
    def unverified(self): self.assertEqual(self.compare()["summary"],{"pass":0,"mismatch":0,"unsupported":0,"unverified":2})
    def edit(self,callback):
        run=self.manifest["runs"]["moonbit"]
        path=self.root/run["stdout"]["path"]
        output=json.loads(path.read_text().split(PREFIX)[1])
        callback(output)
        path.write_text(PREFIX+json.dumps(output)+"\n")
        run["stdout"]["sha256"]=digest(path.read_bytes())
    def test_real_native_run(self):
        self.assertEqual(self.compare()["summary"],{"pass":2,"mismatch":0,"unsupported":0,"unverified":0})
    def test_missing_full_frame(self):
        self.edit(lambda p:p.pop("frame"))
        self.unverified()
    def test_short_frame(self):
        self.edit(lambda p:p["frame"]["rgba8"].pop())
        self.unverified()
    def test_sample_not_from_frame(self):
        self.edit(lambda p:p["cases"][1]["observation"]["samples"][1].__setitem__(0,0))
        self.unverified()
    def test_unknown_gpu_case(self):
        self.edit(lambda p:p["cases"][1].__setitem__("id","unexpected"))
        self.unverified()
    def test_missing_library(self):
        run=self.manifest["runs"]["moonbit"]
        (self.root/run["runtime_library"]["path"]).unlink()
        self.unverified()
    def test_tampered_library(self):
        run=self.manifest["runs"]["moonbit"]
        with (self.root/run["runtime_library"]["path"]).open("ab") as output: output.write(b"tampered")
        self.unverified()
    def test_failed_library_build(self):
        self.manifest["runs"]["moonbit"]["library_build"]["returncode"]=1
        self.unverified()
    def test_missing_library_build_log(self):
        run=self.manifest["runs"]["moonbit"]
        (self.root/run["library_build_stdout"]["path"]).unlink()
        self.unverified()
    def test_mock_mode_cannot_claim_native(self):
        self.manifest["runs"]["upstream"]["execution_mode"]="headless"
        self.unverified()
    def test_different_requested_viewports_rejected(self):
        self.scenarios["cases"][1]["width"]=512
        with self.assertRaises(ValueError): validate_scenarios(self.scenarios)
    def test_reversed_cases_rejected(self):
        self.scenarios["cases"].reverse()
        with self.assertRaises(ValueError): validate_scenarios(self.scenarios)
    def test_timeout_hook_receives_only_live_owned_child(self):
        seen=[]
        def guard(pid):
            os.kill(pid,0) # Existence check only; does not signal or alter it.
            seen.append(pid)
        result=execute([sys.executable,"-c","import time; time.sleep(10)"],os.environ.copy(),self.root/"timeout.out",self.root/"timeout.err",self.root,.05,before_terminate=guard)
        self.assertEqual(seen,[result["pid"]])
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["returncode"],0)
    def test_timeout_hook_exception_still_terminates_owned_child(self):
        seen=[]
        def guard(pid):
            seen.append(pid)
            raise RuntimeError("test cleanup failure")
        with self.assertRaises(RuntimeError):
            execute([sys.executable,"-c","import time; time.sleep(10)"],os.environ.copy(),self.root/"timeout.out",self.root/"timeout.err",self.root,.05,before_terminate=guard)
        with self.assertRaises(ProcessLookupError): os.kill(seen[0],0)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--evidence",type=Path,required=True)
    args,remaining=parser.parse_known_args()
    NativeEvidenceTests.evidence_dir=args.evidence.resolve()
    unittest.main(argv=[sys.argv[0],*remaining])
