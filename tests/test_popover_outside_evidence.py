"""Synthetic integrity controls only: no Rust compile/execution or CI attestation."""
import copy
import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result
E=module("popover_evidence",ROOT/"diagnostics/popover_outside/evidence.py")
T=module("popover_source_tests",ROOT/"tests/test_popover_outside.py")


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


def fixture(directory):
    token="11111111-1111-4111-8111-111111111111"
    commit="a"*40;tree="b"*40
    recorded="/ci/suite/_build/popover-evidence"
    build="/ci/suite/_build/popover-build-"+token
    upstream="/ci/suite/_build/upstream-source"
    source_bytes={}
    for prefix,paths in (("suite",E.ADDED),("upstream",E.UPSTREAM_FILES)):
        for path in paths:
            data=(ROOT/path).read_bytes() if prefix=="suite" else ("SYNTHETIC SOURCE "+path).encode()
            target=directory/prefix/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            source_bytes[(commit if prefix=="suite" else E.UPSTREAM)+":"+path]=data
    original=(directory/"suite/adapters/popover_outside_rust/Cargo.toml").read_text()
    (directory/"build-Cargo.toml").write_text(original.replace('"../../../zed-source/crates/gpui"',json.dumps(upstream+"/crates/gpui")))
    (directory/"build-Cargo.lock").write_bytes((directory/"suite/adapters/popover_outside_rust/Cargo.lock").read_bytes())
    environment={**E.ENVIRONMENT,"CARGO_TARGET_DIR":build+"/target","RUSTUP_TOOLCHAIN":"1.98.1"}
    build_command=["cargo","+1.98.1","build","--locked","--manifest-path",build+"/adapter/Cargo.toml"]
    execute_command=[recorded+"/probe",recorded+"/suite/diagnostics/popover_outside/scenarios.json",token]
    write(directory/"plan.json",dict(build_command=build_command,execution_command=execute_command,
        environment=environment,run_token=token,manifest_sha256=E.digest(directory/"build-Cargo.toml"),lock_sha256=E.digest(directory/"build-Cargo.lock")))
    raw=T.synthetic_trace();raw["run_token"]=token
    write(directory/"raw.stdout",raw)
    write(directory/"hypotheses.json",T.VERIFY.verify(raw))
    (directory/"probe").write_bytes(b"\x7fELFSYNTHETIC-NOT-EXECUTABLE")
    for stem in ("rustc","cargo","build","raw"):
        (directory/(stem+".stderr")).write_bytes(b"")
        if stem!="raw": (directory/(stem+".stdout")).write_text(stem+" 1.98.1 synthetic\n")
    def process(command,index):
        return dict(command=command,returncode=0,timed_out=False,resource_floor_breached=False,pid=index+1,
                    started_at=f"2026-10-17T12:00:{index*2:02d}+00:00",finished_at=f"2026-10-17T12:00:{index*2+1:02d}+00:00")
    manifest=dict(schema_version=1,origin="github_actions",run_token=token,status="executed",
        suite=dict(commit=commit,tree=tree),upstream=dict(commit=E.UPSTREAM,tree=E.UPSTREAM_TREE),
        session=dict(repository="synthetic/example",run_id="123",run_attempt="1",sha=commit,job="actual-gpui-popover-outside"),
        source_unchanged=True,environment=environment,disk_floor_bytes=E.FLOOR,
        disk_samples=[dict(workspace=8*1024**3+1,tmp=E.FLOOR+1)]*2,
        execution_root=recorded,build_root=build,upstream_source_path=upstream,
        rustc=process(["rustc","+1.98.1","--version","--verbose"],0),
        cargo=process(["cargo","+1.98.1","--version","--verbose"],1),
        build=process(build_command,2),execution=process(execute_command,3),files={})
    for path in directory.rglob("*"):
        if path.is_file() and path.name!="hypotheses.json":
            manifest["files"][str(path.relative_to(directory))]=dict(sha256=E.digest(path),size=path.stat().st_size)
    write(directory/"manifest.json",manifest)
    args=dict(suite_source=ROOT,upstream_source="SYNTHETIC",suite_commit=commit,suite_tree=tree,
              repository="synthetic/example",run_id="123",run_attempt="1",recorded_execution_root=recorded)
    return args,source_bytes


class EvidenceTests(unittest.TestCase):
    def verify_synthetic(self,directory,args,source_bytes):
        # These mocks deliberately remove external authentication. The result
        # must remain execution_authenticated=False even if every record matches.
        with patch.object(E,"validate_suite"),patch.object(E,"validate_source"),patch.object(E,"git",side_effect=lambda source,action,key:source_bytes[key]):
            return E.verify_bundle(directory,**args)

    def test_synthetic_bundle_never_authenticates_execution(self):
        with tempfile.TemporaryDirectory(prefix="popover-evidence-test-") as temporary:
            directory=Path(temporary);args,source=fixture(directory)
            report=self.verify_synthetic(directory,args,source)
            self.assertIs(report["execution_authenticated"],False)
            self.assertIs(report["source_hypotheses"]["execution_authenticated"],False)
            self.assertEqual(report,json.loads(json.dumps(report)))
            self.assertEqual(report,self.verify_synthetic(directory,args,source))

    def test_corrupt_records_rejected(self):
        for mutation in ("compiler_exit","build_exit","runtime_exit","token","session","source_changed","lock","binary","raw","inventory","hypotheses","chronology"):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory(prefix="popover-evidence-test-") as temporary:
                directory=Path(temporary);args,source=fixture(directory);manifest=E.load(directory/"manifest.json")
                if mutation=="compiler_exit":manifest["rustc"]["returncode"]=1
                elif mutation=="build_exit":manifest["build"]["returncode"]=101
                elif mutation=="runtime_exit":manifest["execution"]["returncode"]=-9
                elif mutation=="token":manifest["run_token"]="2"*36
                elif mutation=="session":args["run_id"]="456"
                elif mutation=="source_changed":manifest["source_unchanged"]=False
                elif mutation=="inventory":manifest["files"].pop("probe")
                elif mutation=="chronology":manifest["execution"]["started_at"]="2026-10-17T11:00:00+00:00"
                elif mutation=="hypotheses":write(directory/"hypotheses.json",{"execution_authenticated":True})
                else:
                    path={"lock":"build-Cargo.lock","binary":"probe","raw":"raw.stdout"}[mutation]
                    with (directory/path).open("ab") as stream:stream.write(b"corruption")
                write(directory/"manifest.json",manifest)
                with self.assertRaises(ValueError):self.verify_synthetic(directory,args,source)

    def test_source_bytes_checked_independently_of_inventory(self):
        with tempfile.TemporaryDirectory(prefix="popover-evidence-test-") as temporary:
            directory=Path(temporary);args,source=fixture(directory)
            path="suite/adapters/popover_outside_rust/src/main.rs"
            (directory/path).write_text("SYNTHETIC CORRUPTION")
            manifest=E.load(directory/"manifest.json")
            manifest["files"][path]=dict(sha256=E.digest(directory/path),size=(directory/path).stat().st_size)
            write(directory/"manifest.json",manifest)
            with self.assertRaisesRegex(ValueError,"source bytes"):
                self.verify_synthetic(directory,args,source)

    def test_excluded_sidecar_symlinks_rejected_even_when_contents_match(self):
        for name in ("hypotheses.json", "manifest.json"):
            with self.subTest(name=name),tempfile.TemporaryDirectory(prefix="popover-evidence-test-") as temporary:
                parent=Path(temporary);directory=parent/"bundle";directory.mkdir()
                args,source=fixture(directory)
                external=parent/("external-"+name)
                # Exact matching bytes outside the bundle used to pass for the
                # hypothesis report; content equality must not waive containment.
                (directory/name).rename(external)
                (directory/name).symlink_to(external)
                with self.assertRaisesRegex(ValueError,"symlink"):
                    self.verify_synthetic(directory,args,source)

    def test_safe_paths_and_strict_json(self):
        with tempfile.TemporaryDirectory(prefix="popover-evidence-test-") as temporary:
            directory=Path(temporary);(directory/"file").write_text("{}")
            (directory/"link").symlink_to(directory/"file")
            for path in ("../file","/file","link","./file"):
                with self.assertRaises(ValueError):E.safe_file(directory,path)
            for data in ('{"a":1,"a":2}','{"a":NaN}'):
                (directory/"file").write_text(data)
                with self.assertRaises(ValueError):E.load(directory/"file")

    def test_boolean_numeric_coercion_rejected(self):
        raw=T.synthetic_trace()
        raw["events"][0]["sequence"]=False
        with self.assertRaisesRegex(ValueError,"row types"):E.validate_raw(raw,T.FIXTURE)
        raw=T.synthetic_trace()
        row=next(r for r in raw["events"] if r["event"]["type"]=="operation_end")
        row["event"]["state"]=[0,0]
        with self.assertRaisesRegex(ValueError,"state types"):E.validate_raw(raw,T.FIXTURE)

    def test_outside_callbacks_pin_upstream_event_type(self):
        source=(ROOT/"adapters/popover_outside_rust/src/main.rs").read_text()
        self.assertEqual(source.count("event: &MouseDownEvent"),2)
        self.assertNotIn("|this, event, _, cx|",source)

    def test_frozen_seven_files(self):
        self.assertEqual(len(E.ADDED),11)
        for path,sha in E.FROZEN.items():self.assertEqual(E.digest(ROOT/path),sha,path)

    def test_missing_external_binding_cannot_verify(self):
        with self.assertRaises(TypeError):E.verify_bundle(Path("unused"))

    def test_runner_preserves_nonzero_process_bytes(self):
        # A tiny Python process tests capture only; this is not a Rust build.
        with patch.dict(sys.modules,{"evidence":E}):
            runner=module("popover_runner",ROOT/"diagnostics/popover_outside/run.py")
        with tempfile.TemporaryDirectory(prefix="popover-process-test-") as temporary:
            directory=Path(temporary);samples=[]
            command=[sys.executable,"-c","import sys;sys.stdout.buffer.write(b'not-json\\x00');sys.stderr.buffer.write(b'compile-failed\\n');sys.exit(101)"]
            import os
            # Capture is independent of the host's current free disk space.
            with patch.object(runner,"disk",return_value={"workspace":E.FLOOR,"tmp":E.FLOOR}):
                record=runner.execute(command,directory,"failed",os.environ.copy(),10,samples)
            self.assertEqual(record["returncode"],101)
            self.assertFalse(record["timed_out"])
            self.assertFalse(record["resource_floor_breached"])
            self.assertEqual((directory/"failed.stdout").read_bytes(),b"not-json\x00")
            self.assertEqual((directory/"failed.stderr").read_bytes(),b"compile-failed\n")
            with self.assertRaisesRegex(ValueError,"process exit"):E.process_ok(record,command)

    def test_runner_kills_process_below_disk_floor(self):
        with patch.dict(sys.modules,{"evidence":E}):
            runner=module("popover_runner",ROOT/"diagnostics/popover_outside/run.py")
        for location in ("workspace","tmp"):
            with self.subTest(location=location), tempfile.TemporaryDirectory(prefix="popover-disk-test-") as temporary:
                sample={"workspace":E.FLOOR,"tmp":E.FLOOR}
                sample[location]-=1
                process=Mock(pid=12345)
                process.poll.side_effect=[None,-signal.SIGKILL]
                process.wait.return_value=-signal.SIGKILL
                samples=[]
                with patch.object(runner.subprocess,"Popen",return_value=process), \
                     patch.object(runner,"disk",return_value=sample), \
                     patch.object(runner.time,"monotonic",return_value=0), \
                     patch.object(runner.os,"killpg") as killpg:
                    record=runner.execute(["synthetic-process"],Path(temporary),"low-disk",{},10,samples)
                killpg.assert_called_once_with(process.pid,signal.SIGKILL)
                process.wait.assert_called_once_with()
                self.assertEqual(samples,[sample])
                self.assertEqual(record["returncode"],-signal.SIGKILL)
                self.assertTrue(record["resource_floor_breached"])
                self.assertFalse(record["timed_out"])

    def test_runner_is_ci_only_and_workflow_scoped(self):
        source=(ROOT/"diagnostics/popover_outside/run.py").read_text()
        self.assertIn('os.environ.get("GITHUB_ACTIONS")=="true"',source)
        self.assertIn('"build_failed"',source)
        self.assertIn('"runtime_failed"',source)
        workflow=(ROOT/".github/workflows/popover-outside-diagnostic.yml").read_text()
        self.assertIn("workflow_dispatch:",workflow)
        self.assertIn("pull_request:",workflow)
        self.assertIn("ref: ${{ github.sha }}",workflow)
        self.assertIn("tests/test_popover_outside*.py",workflow)
        self.assertIn("if: always()",workflow)


if __name__=="__main__":unittest.main()
