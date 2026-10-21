#!/usr/bin/env python3
"""V2 current-source dedicated Ubuntu CI only. Preserve every attempted process's original output.

This additive runner supersedes the frozen seven-file README's prospective
manual invocation; it never changes those reviewed bytes. No local Rust runs.
Original artifact downloads: <=20MiB shared ZIP, <=128MiB /tmp extraction,
only after actual metadata/central-directory and free-space checks by reviewer.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid
from evidence import (ROOT, UPSTREAM, UPSTREAM_TREE, UPSTREAM_FILES,
                      ENVIRONMENT, FLOOR, digest, load, require)
from source_current_v2 import CURRENT_PATHS as ADDED, PROFILE, validate_suite, validate_source, git


def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value): path.write_text(json.dumps(value,indent=2)+"\n")
def disk(): return {"workspace":shutil.disk_usage(ROOT).free,"tmp":shutil.disk_usage("/tmp").free}


def execute(command, out, stem, environment, timeout, samples):
    started,begin=now(),time.monotonic()
    with (out/(stem+".stdout")).open("xb") as stdout, (out/(stem+".stderr")).open("xb") as stderr:
        process=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
        timed_out=resource_floor=False
        while process.poll() is None:
            sample=disk(); samples.append(sample)
            timed_out=time.monotonic()-begin>timeout
            resource_floor=min(sample.values())<FLOOR
            if timed_out or resource_floor:
                os.killpg(process.pid,signal.SIGKILL)
                break
            time.sleep(.5)
        code=process.wait()
    return {"command":command,"started_at":started,"finished_at":now(),"returncode":code,
            "timed_out":timed_out,"resource_floor_breached":resource_floor,"pid":process.pid}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--suite-commit",required=True)
    parser.add_argument("--suite-tree",required=True)
    args=parser.parse_args()
    out=args.output.resolve(); upstream=args.upstream_source.resolve()
    require(out.parent==ROOT/"_build","fresh output must be directly under ignored _build")
    require(min(disk().values())>=FLOOR,"disk floor before evidence creation")
    out.mkdir(parents=True,exist_ok=False)
    token=str(uuid.uuid4()); build=out.parent/("popover-build-"+token)
    manifest={"schema_version":2,"source_policy":PROFILE,"origin":"github_actions","run_token":token,"started_at":now(),
              "status":"preflight","execution_root":str(out),"build_root":str(build),
              "upstream_source_path":str(upstream),"disk_floor_bytes":FLOOR,"disk_samples":[disk()],
              "source_unchanged":False,"files":{}}
    failure=None
    try:
        require(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("RUNNER_OS")=="Linux"
                and os.environ.get("GITHUB_JOB")=="actual-gpui-popover-outside","dedicated Ubuntu CI required")
        commit,tree=args.suite_commit,args.suite_tree
        manifest["suite"]={"commit":commit,"tree":tree}
        manifest["upstream"]={"commit":UPSTREAM,"tree":UPSTREAM_TREE}
        manifest["session"]={"repository":os.environ["GITHUB_REPOSITORY"],"run_id":os.environ["GITHUB_RUN_ID"],
             "run_attempt":os.environ["GITHUB_RUN_ATTEMPT"],"sha":os.environ["GITHUB_SHA"],"job":os.environ["GITHUB_JOB"]}
        require(manifest["session"]["sha"]==commit,"CI checkout SHA")
        validate_suite(ROOT,commit,tree); validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
        require(shutil.disk_usage(ROOT).free>=8*1024**3,"8GiB build headroom required")
        for source,prefix,paths in ((ROOT,"suite",ADDED),(upstream,"upstream",UPSTREAM_FILES)):
            for relative in paths:
                destination=out/prefix/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source/relative,destination)
        build.mkdir();stage=build/"adapter"
        shutil.copytree(ROOT/"adapters/popover_outside_rust",stage)
        original=(stage/"Cargo.toml").read_text();placeholder='"../../../zed-source/crates/gpui"'
        require(original.count(placeholder)==1,"dependency placeholder")
        (stage/"Cargo.toml").write_text(original.replace(placeholder,json.dumps(str(upstream/"crates/gpui"))))
        shutil.copy2(stage/"Cargo.toml",out/"build-Cargo.toml")
        shutil.copy2(stage/"Cargo.lock",out/"build-Cargo.lock")
        environment=os.environ.copy()
        for name in ("DISPLAY","WAYLAND_DISPLAY","RUSTFLAGS","CARGO_ENCODED_RUSTFLAGS","RUSTDOCFLAGS",
                     "RUSTC_WRAPPER","RUSTC_WORKSPACE_WRAPPER","CARGO_BUILD_TARGET"):
            environment.pop(name,None)
        recorded_environment={**ENVIRONMENT,"CARGO_TARGET_DIR":str(build/"target"),"RUSTUP_TOOLCHAIN":"1.98.1"}
        environment.update({k:v for k,v in recorded_environment.items() if v is not None})
        manifest["environment"]=recorded_environment
        build_command=["cargo","+1.98.1","build","--locked","--manifest-path",str(stage/"Cargo.toml")]
        execution_command=[str(out/"probe"),str(out/"suite/diagnostics/popover_outside/scenarios.json"),token]
        save(out/"plan.json",{"build_command":build_command,"execution_command":execution_command,
             "environment":recorded_environment,"run_token":token,"manifest_sha256":digest(out/"build-Cargo.toml"),
             "lock_sha256":digest(out/"build-Cargo.lock")})
        for tool in ("rustc","cargo"):
            manifest["status"]="toolchain_failed"
            manifest[tool]=execute([tool,"+1.98.1","--version","--verbose"],out,tool,environment,120,manifest["disk_samples"])
            require(manifest[tool]["returncode"]==0,"toolchain invocation failed")
            require((out/(tool+".stdout")).read_text().startswith(tool+" 1.98.1 "),"wrong compiler/tool version")
        manifest["status"]="build_failed"
        manifest["build"]=execute(build_command,out,"build",environment,2100,manifest["disk_samples"])
        require((stage/"Cargo.lock").read_bytes()==(out/"build-Cargo.lock").read_bytes(),"build changed lock")
        require(manifest["build"]["returncode"]==0,"Rust build failed; original output retained")
        shutil.copy2(build/"target/debug/gpui-popover-outside-diagnostic",out/"probe")
        manifest["status"]="runtime_failed"
        manifest["execution"]=execute(execution_command,out,"raw",environment,120,manifest["disk_samples"])
        require(manifest["execution"]["returncode"]==0,"Rust execution failed; original output retained")
        manifest["status"]="hypothesis_failed"
        from verify import verify
        report=verify(load(out/"raw.stdout"),load(out/"suite/diagnostics/popover_outside/scenarios.json"))
        save(out/"hypotheses.json",report)
        require(load(out/"hypotheses.json")==report,"saved hypothesis report changed")
        manifest["status"]="executed"
    except Exception as caught:
        failure=caught
        save(out/"failure.json",{"stage":manifest["status"],"type":type(caught).__name__,"message":str(caught)})
    finally:
        try:
            if "suite" in manifest:
                validate_suite(ROOT,manifest["suite"]["commit"],manifest["suite"]["tree"])
                validate_source(upstream,UPSTREAM,UPSTREAM_TREE)
                manifest["source_unchanged"]=True
        except Exception as caught:
            manifest["source_check_error"]=str(caught)
            if failure is None: failure=caught
        manifest["disk_samples"].append(disk());manifest["finished_at"]=now()
        for path in sorted(out.rglob("*")):
            if path.is_file() and path.name!="hypotheses.json":
                manifest["files"][str(path.relative_to(out))]={"sha256":digest(path),"size":path.stat().st_size}
        save(out/"manifest.json",manifest)
    if failure is not None: raise failure
    print(json.dumps({"evidence":str(out),"status":manifest["status"],
                      "source_policy":PROFILE,"suite":manifest["suite"],"execution_authenticated":False}))


if __name__=="__main__":main()
