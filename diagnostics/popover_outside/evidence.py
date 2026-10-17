"""Reopen immutable CI records against external Git/session identities.
JSON records alone are not cryptographic proof that a program executed.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
# Published baseline shares the local review base 717506fb tree; the local
# commit is intentionally not required in a fresh public CI checkout.
BASE = "cd205b17b6650bd7e518560640fc31084e723eeb"
BASE_TREE = "96d216f94a10d73591416ca09a74cfbb3ca80311"
UPSTREAM = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
UPSTREAM_TREE = "990fb995914d51a546b20e5cf0382dafc105c299"
FROZEN = {
 "adapters/popover_outside_rust/Cargo.toml":"ed6ece3ea5594ffdd3e9f80cf8e741bd06bc410ad98ba19933f1ca1e60ed5f5d",
 "adapters/popover_outside_rust/Cargo.lock":"25285cd666a15821a6a939d65e464040386b6185982139c8f0857d8e8c7e09d8",
 "adapters/popover_outside_rust/src/main.rs":"ce9326dbe8fde78fb97b7bafdbc4cd0ff02ea3c62ce680edf4f01c4fc62ead64",
 "diagnostics/popover_outside/README.md":"805d211863e4db2d70c92f841ca3796923e61d5cbd6b3d97ac572a45a84a47e7",
 "diagnostics/popover_outside/scenarios.json":"6e8995f1748926208547d68c372678b0d0db12bc661ad7fb2fdbbb45dbb6facb",
 "diagnostics/popover_outside/verify.py":"aa632457173d9ae6321a0a8ea8c8428d472fd300d2b9c3dad329ba0142414f6a",
 "tests/test_popover_outside.py":"b635d2cd93973e44ac873e13ba61b6bf18a7cebd8414add3bccfc3b952c942c4",
}
ADDED = list(FROZEN) + ["diagnostics/popover_outside/run.py", "diagnostics/popover_outside/evidence.py",
 "tests/test_popover_outside_evidence.py", ".github/workflows/popover-outside-diagnostic.yml"]
UPSTREAM_FILES = ["Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "crates/gpui/Cargo.toml",
 "crates/gpui/examples/popover.rs", "crates/gpui/src/elements/div.rs", "crates/gpui/src/elements/anchored.rs",
 "crates/gpui/src/elements/deferred.rs", "crates/gpui/src/window.rs", "crates/gpui/src/app.rs",
 "crates/gpui/src/app/test_context.rs", "crates/gpui/src/platform/test/window.rs",
 "crates/gpui/src/platform/test/platform.rs"]
ENVIRONMENT = {"CARGO_BUILD_JOBS":"2", "CARGO_INCREMENTAL":"0", "DISPLAY":None, "WAYLAND_DISPLAY":None}
FLOOR = 1024**3 + 32*1024**2


def require(ok, message):
    if not ok: raise ValueError(message)


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(value): raise ValueError("non-finite JSON constant: " + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=pairs, parse_constant=invalid)


def git(source, *args): return subprocess.check_output(["git", "-C", str(source), *args])


def entries(source, revision):
    result = {}
    for entry in git(source,"ls-tree","-rz",revision).split(b"\0"):
        if entry:
            metadata,path=entry.split(b"\t",1)
            result[path.decode()] = metadata.decode()
    return result


def validate_source(source, commit, tree):
    require(re.fullmatch(r"[0-9a-f]{40}",commit) and re.fullmatch(r"[0-9a-f]{40}",tree), "Git identity shape")
    require(git(source,"rev-parse",commit+"^{tree}").decode().strip()==tree,"Git tree identity")
    require(git(source,"rev-parse","HEAD").decode().strip()==commit,"checkout identity")
    require(not git(source,"status","--porcelain","--untracked-files=all").strip(),"dirty checkout")


def validate_suite(source, commit, tree):
    validate_source(source,commit,tree)
    require(git(source,"rev-parse",BASE+"^{tree}").decode().strip()==BASE_TREE,"baseline tree")
    original,current=entries(source,BASE),entries(source,commit)
    require(len(original)==723,"baseline count")
    require(set(current)==set(original)|set(ADDED),"exact eleven additions")
    require(all(current[path]==identity for path,identity in original.items()),"historical mode/blob changed")
    for path,sha in FROZEN.items():
        require(hashlib.sha256(git(source,"show",commit+":"+path)).hexdigest()==sha,"reviewed source changed: "+path)
    for path in ADDED: require(current[path].startswith("100644 blob "),"added source mode/type")


def safe_file(directory, relative):
    require(isinstance(relative,str),"inventory path type")
    path=PurePosixPath(relative)
    require(str(path)==relative and not path.is_absolute() and ".." not in path.parts and bool(path.parts),"unsafe inventory path")
    current=Path(directory)
    require(not current.is_symlink(),"symlink evidence root")
    for part in path.parts:
        current=current/part
        require(not current.is_symlink(),"symlink in evidence")
    require(current.is_file(),"missing evidence file: "+relative)
    return current


def process_ok(record, command):
    require(record["command"]==command,"command binding")
    require(type(record["returncode"]) is int and record["returncode"]==0,"process exit")
    require(record["timed_out"] is False and record["resource_floor_breached"] is False,"process stopped")
    require(type(record["pid"]) is int and record["pid"]>0,"process pid")
    started,finished=(datetime.fromisoformat(record[k]) for k in ("started_at","finished_at"))
    require(started.tzinfo is not None and finished.tzinfo is not None and started<=finished,"process timestamps")
    return started,finished


def json_equal(actual, expected):
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and actual == expected
    if type(actual) is not type(expected): return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(json_equal(actual[k],v) for k,v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(json_equal(a,b) for a,b in zip(actual,expected))
    return actual == expected


def validate_raw(raw, fixture):
    require(set(raw)=={"schema_version","layer","fixture","upstream_revision","run_token","input","events"},"raw root fields")
    require(type(raw["schema_version"]) is int and raw["schema_version"]==1,"raw schema type")
    require(json_equal(raw["input"],fixture),"typed fixture identity")
    fields={"operation_start":{"type","input"},"operation_end":{"type","state"},
            "frame_start":{"type","scale"},"render":{"type","state","parent_outside_registered","child_outside_registered"},
            "prepaint":{"type","node","bounds"},"paint":{"type","node","bounds"},
            "host_paint_return":{"type"},"callback":{"type","name","before","after","button"}}
    require(type(raw["events"]) is list,"events type")
    for row in raw["events"]:
        require(set(row)=={"sequence","operation","frame","event"},"row fields")
        require(type(row["sequence"]) is int and type(row["frame"]) is int and type(row["operation"]) is str,"row types")
        event=row["event"];kind=event["type"]
        require(kind in fields and set(event)==fields[kind],"event fields")
        for key in ("state","before","after"):
            if key in event:
                require(type(event[key]) is list and len(event[key])==2 and all(type(v) is bool for v in event[key]),"state types")
        for key in ("parent_outside_registered","child_outside_registered"):
            if key in event: require(type(event[key]) is bool,"registration type")
        if "bounds" in event:
            require(type(event["bounds"]) is list and len(event["bounds"])==4 and all(type(v) in (int,float) and math.isfinite(v) for v in event["bounds"]),"bounds types")
        if "scale" in event: require(type(event["scale"]) in (int,float),"scale type")
        if kind=="operation_start" and "point" in event["input"]:
            require(type(event["input"]["point"]) is list and len(event["input"]["point"])==2 and all(type(v) in (int,float) and math.isfinite(v) for v in event["input"]["point"]),"input point type")


def verify_bundle(directory, *, suite_source, upstream_source, suite_commit, suite_tree,
                  repository, run_id, run_attempt, recorded_execution_root):
    directory=Path(directory)
    manifest=load(safe_file(directory,"manifest.json"))
    require(manifest["schema_version"]==1 and manifest["origin"]=="github_actions","manifest origin")
    require(manifest["suite"]=={"commit":suite_commit,"tree":suite_tree},"external suite identity")
    require(manifest["upstream"]=={"commit":UPSTREAM,"tree":UPSTREAM_TREE},"upstream identity")
    require(manifest["session"]=={"repository":repository,"run_id":run_id,"run_attempt":run_attempt,
            "sha":suite_commit,"job":"actual-gpui-popover-outside"},"external session identity")
    require(re.fullmatch(r"\d+",run_id) and re.fullmatch(r"[1-9]\d*",run_attempt),"session shape")
    require(re.fullmatch(r"[0-9a-f-]{36}",manifest["run_token"]),"run token")
    require(manifest["source_unchanged"] is True,"source changed during run")
    validate_suite(suite_source,suite_commit,suite_tree)
    validate_source(upstream_source,UPSTREAM,UPSTREAM_TREE)
    required={"build-Cargo.toml","build-Cargo.lock","plan.json","probe","raw.stdout","raw.stderr",
              "build.stdout","build.stderr","rustc.stdout","rustc.stderr","cargo.stdout","cargo.stderr"}
    required|={"suite/"+p for p in ADDED}|{"upstream/"+p for p in UPSTREAM_FILES}
    require(set(manifest["files"])==required,"exact successful inventory")
    actual={str(p.relative_to(directory)) for p in directory.rglob("*") if p.is_file() or p.is_symlink()}
    require(actual==required|{"manifest.json","hypotheses.json"},"missing/extra bundle files")
    # Sidecars omitted from the content-hash inventory still must be regular,
    # in-bundle files. Validate the complete inventory, including both sidecars.
    for relative in actual: safe_file(directory,relative)
    for relative,metadata in manifest["files"].items():
        path=safe_file(directory,relative)
        require(metadata=={"sha256":digest(path),"size":path.stat().st_size},"changed evidence: "+relative)
    for source,commit,prefix,paths in ((suite_source,suite_commit,"suite/",ADDED),
                                     (upstream_source,UPSTREAM,"upstream/",UPSTREAM_FILES)):
        for path in paths:
            require(safe_file(directory,prefix+path).read_bytes()==git(source,"show",commit+":"+path),"source bytes: "+path)
    require(manifest["status"]=="executed","run did not execute successfully")
    require(manifest["disk_floor_bytes"]==FLOOR,"disk floor")
    require(len(manifest["disk_samples"])>=2 and all(set(sample)=={"workspace","tmp"} and
            all(type(v) is int and v>=FLOOR for v in sample.values()) for sample in manifest["disk_samples"]),"disk sampling/floor")
    require(manifest["disk_samples"][0]["workspace"]>=8*1024**3,"initial build headroom")
    root=Path(recorded_execution_root)
    require(root.is_absolute() and str(root)==manifest["execution_root"] and ".." not in root.parts,"execution root")
    build=Path(manifest["build_root"])
    require(build.is_absolute() and build.parent==root.parent and build.name=="popover-build-"+manifest["run_token"],"build root")
    upstream=Path(manifest["upstream_source_path"])
    require(upstream.is_absolute() and ".." not in upstream.parts,"upstream build path")
    original=safe_file(directory,"suite/adapters/popover_outside_rust/Cargo.toml").read_text()
    placeholder='"../../../zed-source/crates/gpui"'
    require(original.count(placeholder)==1,"manifest placeholder")
    require(safe_file(directory,"build-Cargo.toml").read_text()==original.replace(placeholder,json.dumps(str(upstream/"crates/gpui"))),"manifest relocation")
    require(safe_file(directory,"build-Cargo.lock").read_bytes()==safe_file(directory,"suite/adapters/popover_outside_rust/Cargo.lock").read_bytes(),"lock changed")
    build_command=["cargo","+1.98.1","build","--locked","--manifest-path",str(build/"adapter/Cargo.toml")]
    execute_command=[str(root/"probe"),str(root/"suite/diagnostics/popover_outside/scenarios.json"),manifest["run_token"]]
    expected_environment={**ENVIRONMENT,"CARGO_TARGET_DIR":str(build/"target"),"RUSTUP_TOOLCHAIN":"1.98.1"}
    require(manifest["environment"]==expected_environment,"environment binding")
    plan={"build_command":build_command,"execution_command":execute_command,"environment":expected_environment,
          "run_token":manifest["run_token"],"manifest_sha256":digest(directory/"build-Cargo.toml"),
          "lock_sha256":digest(directory/"build-Cargo.lock")}
    require(load(safe_file(directory,"plan.json"))==plan,"plan binding")
    intervals=[]
    for tool in ("rustc","cargo"):
        intervals.append(process_ok(manifest[tool],[tool,"+1.98.1","--version","--verbose"]))
        require(safe_file(directory,tool+".stdout").read_text().startswith(tool+" 1.98.1 "),"tool version")
        require(safe_file(directory,tool+".stderr").stat().st_size==0,"tool stderr")
    intervals.append(process_ok(manifest["build"],build_command))
    intervals.append(process_ok(manifest["execution"],execute_command))
    require(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),"process chronology")
    with safe_file(directory,"probe").open("rb") as stream: require(stream.read(4)==b"\x7fELF","not an ELF executable")
    require(safe_file(directory,"raw.stderr").stat().st_size==0,"runtime stderr")
    raw=load(safe_file(directory,"raw.stdout"))
    require(raw["run_token"]==manifest["run_token"],"cross-session raw trace")
    fixture=load(safe_file(directory,"suite/diagnostics/popover_outside/scenarios.json"))
    validate_raw(raw,fixture)
    # Execute only the externally source-bound checker, never bundle-supplied code.
    spec=importlib.util.spec_from_file_location("popover_raw_checker",Path(suite_source)/"diagnostics/popover_outside/verify.py")
    checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
    result=checker.verify(raw,fixture)
    require(json_equal(load(safe_file(directory,"hypotheses.json")),result),"saved hypothesis report differs")
    require(json.loads(json.dumps(result))==result,"report JSON roundtrip")
    return {"execution_authenticated":False,
            "run_attestation":{"status":"external_git_and_ci_session_bound",
                "repository":repository,"run_id":run_id,"run_attempt":run_attempt,
                "limitation":"Corroborate process records with original CI logs/artifact provenance; JSON alone is not execution proof."},
            "source_hypotheses":result}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    for name in ("suite-source","upstream-source","suite-commit","suite-tree","repository","run-id","run-attempt","recorded-execution-root"):
        parser.add_argument("--"+name,required=True)
    print(json.dumps(verify_bundle(**vars(parser.parse_args())),indent=2))


if __name__=="__main__":main()
