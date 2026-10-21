"""V2 current-source runtime evidence. V1 historical evidence.py is unchanged.

All original evidence checks remain explicit below. Only the source boundary and
schema/profile differ. Never infer current execution from a historical bundle.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import re
from evidence import (ROOT, UPSTREAM, UPSTREAM_TREE, UPSTREAM_FILES, ENVIRONMENT,
                      FLOOR, digest, load, require, safe_file, process_ok,
                      json_equal, validate_raw)
from source_current_v2 import CURRENT_PATHS as ADDED, PROFILE, validate_suite, validate_source, git


def verify_bundle(directory, *, suite_source, upstream_source, suite_commit, suite_tree,
                  repository, run_id, run_attempt, recorded_execution_root):
    directory=Path(directory)
    manifest=load(safe_file(directory,"manifest.json"))
    require(type(manifest["schema_version"]) is int and manifest["schema_version"]==2 and manifest["origin"]=="github_actions","manifest origin")
    require(manifest["source_policy"] == PROFILE, "current evidence policy binding")
    require(Path(suite_source).resolve() == ROOT, "executing verifier source checkout")
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
    return {"schema_version":2, "source_policy":PROFILE,
            "suite":{"commit":suite_commit,"tree":suite_tree},
            "execution_authenticated":False,
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
