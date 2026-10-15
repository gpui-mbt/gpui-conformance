#!/usr/bin/env python3
"""Bounded, self-closing native window/Metal readback probes.

Run only in a coordinated graphical session. --build-only never launches them.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import uuid

from comparator import compare, digest
from contracts import validate_scenarios
from run import ROOT, artifact, command, execute, prepare_moonbit, source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-source",type=Path,default=ROOT.parent/"zed-source")
    parser.add_argument("--moonbit-source",type=Path,default=ROOT.parent/"gpui-reference")
    parser.add_argument("--candidate-revision")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--build-only",action="store_true")
    parser.add_argument("--negative-control",action="store_true",help="Actually paint the MoonBit rectangle blue instead of the shared red")
    parser.add_argument("--online",action="store_true")
    args=parser.parse_args()
    if platform.system() != "Darwin": parser.error("native slice requires macOS")
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    build=ROOT/"_build"
    pins=json.loads((ROOT/"pins.json").read_text())
    if args.candidate_revision:
        if len(args.candidate_revision)!=40 or any(x not in "0123456789abcdef" for x in args.candidate_revision): parser.error("full candidate SHA required")
        pins["moonbit"].update(baseline_revision=pins["moonbit"]["revision"],revision=args.candidate_revision)
    paths={"upstream":args.upstream_source.resolve(),"moonbit":args.moonbit_source.resolve()}
    identities={name:source(path,pins[name]["revision"],name,pins[name]["version"]) for name,path in paths.items()}
    scenarios=(ROOT/"native_scenarios.json").read_bytes()
    validate_scenarios(json.loads(scenarios))
    (out/"scenarios.json").write_bytes(scenarios)
    host={"os":platform.system(),"architecture":platform.machine(),"release":platform.release(),"macos":platform.mac_ver()[0]}
    manifest={"schema_version":1,"pins":pins,"platform":host,"negative_control":args.negative_control,
              "suite_revision":command(["git","rev-parse","HEAD"],ROOT),"suite_dirty":bool(command(["git","status","--porcelain"],ROOT)),"runs":{}}
    adapter=build/"native-rust-adapter"
    shutil.copytree(ROOT/"adapters/native_rust",adapter,dirs_exist_ok=True)
    cargo=adapter/"Cargo.toml"
    cargo.write_text(cargo.read_text().replace('"../../../zed-source/crates/gpui"',json.dumps(str(paths["upstream"]/"crates/gpui"))).replace('"../../../zed-source/crates/gpui_platform"',json.dumps(str(paths["upstream"]/"crates/gpui_platform"))))
    runtime=prepare_moonbit(paths["moonbit"],build,ROOT/"adapters/native_moonbit")
    env=os.environ.copy()
    env.update(CARGO_TARGET_DIR=str(build/"native-rust"),GPUI_SCENARIOS=scenarios.decode(),GPUI_NATIVE_E2E="1",GPUI_NEGATIVE_CONTROL="1" if args.negative_control else "0")
    configs={
        "upstream":{"build":["cargo","+1.98.1","build","--locked"]+([] if args.online else ["--offline"])+["--manifest-path",str(cargo)],"cwd":ROOT,"exe":build/"native-rust/debug/gpui-conformance-native-probe","toolchain":command(["rustc","+1.98.1","--version"])},
        "moonbit":{"build":["moon","build","--target","native","--deny-warn","conformance_probe"],"cwd":runtime,"exe":runtime/"_build/native/debug/build/conformance_probe/conformance_probe.exe","toolchain":command(["moon","version"])+"; "+command(["xcrun","clang","--version"]).splitlines()[0]},
    }
    # Build both probes completely before any window is opened.
    for name,config in configs.items():
        folder=out/name
        folder.mkdir()
        run={**identities[name],"implementation":name,"execution_mode":"native","backend":"appkit-metal","platform":host,"toolchain":config["toolchain"],"scenarios_sha256":digest(scenarios),"run_token":str(uuid.uuid4())}
        if name=="moonbit":
            library=folder/"libgpui_macos.dylib"
            library_command=["xcrun","clang","-dynamiclib","-DGPUI_TESTING","-fobjc-arc","-Wall","-Wextra","-Werror",str(runtime/"platform/macos/native.m"),str(runtime/"platform/macos/accessibility.m"),str(runtime/"platform/macos_text/core_text.c")]
            for framework in ("AppKit","QuartzCore","Metal","CoreText","CoreGraphics","CoreFoundation"):
                library_command += ["-framework",framework]
            library_command += ["-o",str(library)]
            run["library_build"]=execute(library_command,env,folder/"library-build.stdout",folder/"library-build.stderr",ROOT,120)
            run["library_build_stdout"]=artifact(folder/"library-build.stdout",out)
            run["library_build_stderr"]=artifact(folder/"library-build.stderr",out)
            if run["library_build"]["returncode"]==0: run["runtime_library"]=artifact(library,out)
            guard=folder/"foreground_guard.dylib"
            guard_command=["xcrun","clang","-dynamiclib","-fobjc-arc","-Wall","-Wextra","-Werror",str(ROOT/"adapters/native_moonbit/foreground.m"),"-framework","AppKit","-o",str(guard)]
            run["guard_build"]=execute(guard_command,env,folder/"guard-build.stdout",folder/"guard-build.stderr",ROOT,60)
            run["guard_build_stdout"]=artifact(folder/"guard-build.stdout",out)
            run["guard_build_stderr"]=artifact(folder/"guard-build.stderr",out)
            if run["guard_build"]["returncode"]==0: run["foreground_guard"]=artifact(guard,out)
        run["build"]=execute(config["build"],env,folder/"build.stdout",folder/"build.stderr",config["cwd"],600)
        run["build_stdout"]=artifact(folder/"build.stdout",out)
        run["build_stderr"]=artifact(folder/"build.stderr",out)
        if run["build"]["returncode"]==0:
            shutil.copy2(config["exe"],folder/"probe")
            run["executable"]=artifact(folder/"probe",out)
        manifest["runs"][name]=run
    builds_ok=all(record["returncode"]==0 and record["timed_out"] is False for run in manifest["runs"].values() for key,record in run.items() if key in ("build","library_build","guard_build"))
    if builds_ok and not args.build_only:
        for name,run in manifest["runs"].items():
            folder=out/name
            child_env=env.copy()
            child_env["GPUI_RUN_TOKEN"]=run["run_token"]
            if name=="moonbit": child_env["GPUI_MACOS_LIBRARY"]=str(folder/"libgpui_macos.dylib")
            restore=None
            if name=="moonbit":
                guard=ctypes.CDLL(str(folder/"foreground_guard.dylib"))
                guard.conformance_frontmost_pid.restype=ctypes.c_int
                guard.conformance_restore_owned.argtypes=[ctypes.c_int,ctypes.c_int]
                previous=guard.conformance_frontmost_pid()
                restore=lambda owned: guard.conformance_restore_owned(owned,previous)
            run["execution"]=execute([str(folder/"probe")],child_env,folder/"stdout.log",folder/"stderr.log",ROOT,15,before_terminate=restore)
            run["stdout"]=artifact(folder/"stdout.log",out)
            run["stderr"]=artifact(folder/"stderr.log",out)
    for name,path in paths.items(): source(path,pins[name]["revision"],name,pins[name]["version"])
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    result=compare(manifest,json.loads(scenarios),out)
    (out/"comparison.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result["summary"]))
    print(out/"comparison.json")
    return 1 if result["summary"]["mismatch"] else 2 if result["summary"]["unverified"] else 0


if __name__=="__main__": raise SystemExit(main())
