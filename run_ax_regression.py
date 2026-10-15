#!/usr/bin/env python3
"""Isolate external AXWindow discovery using only owned stock AppKit windows."""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import time
import uuid

from comparator import digest
from observer_contracts import validate_observation, validate_ready
from run import artifact, command, execute, now

ROOT = Path(__file__).resolve().parent


def classify_attempt(observation, ready):
    """Local getters, permission and successful IPC cannot establish AXWindow identity."""
    if not isinstance(observation, dict):
        raise ValueError("invalid observer record: expected an object")
    window = observation.get("window", {})
    if not isinstance(window, dict):
        raise ValueError("invalid observer record: window must be an object")
    bounds = window.get("kCGWindowBounds", {})
    if not isinstance(bounds, dict):
        raise ValueError("invalid observer record: window bounds must be an object")
    for key in ("ax_owned_candidates", "ax_windows"):
        if key in observation:
            entries = observation[key]
            if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
                raise ValueError("invalid observer record: " + key + " must be a list of objects")
    validate_observation(observation, ready)
    if observation["ax_status"] == "pass":
        candidates = observation.get("ax_owned_candidates", [])
        if len(candidates) != 1 or candidates[0].get("same_application_element") is not False:
            raise ValueError("AXWindow must be distinct from the application element")
        return "external-window-matched"
    if not observation["ax_trusted"]:
        return "observer-untrusted"
    candidates = observation.get("ax_owned_candidates", [])
    if any(c.get("same_application_element") is True and c.get("role") == "AXApplication" for c in candidates):
        return "application-returned-as-window"
    return "external-window-unmatched"


def stop_owned(proc):
    if proc.poll() is None:
        proc.kill()
    return proc.wait(timeout=2)


def run_control(executable, observer, folder, out, revision, packaging, pump):
    token = str(uuid.uuid4())
    scenario_hash = digest(json.dumps({"packaging": packaging, "pump": pump}).encode())
    run = {"implementation":"appkit-control", "revision":revision, "run_token":token,
           "scenarios_sha256":scenario_hash, "executable":artifact(executable, out),
           "packaging":packaging, "pump":pump, "status":"unverified", "attempts":[]}
    if packaging == "bundle":
        run["fixture_packaging"] = "app-bundle-v1"
    env = os.environ.copy()
    env.update(GPUI_RUN_TOKEN=token, GPUI_OBSERVER_DIR=str(folder),
               GPUI_AX_CONTROL_PUMP=pump, GPUI_AX_DIAGNOSTICS="1",
               GPUI_EXECUTABLE_SHA256=run["executable"]["sha256"],
               GPUI_SOURCE_REVISION=revision, GPUI_SCENE_SHA256=scenario_hash,
               GPUI_AX_CONTROL_BUNDLE_ID="", GPUI_AX_CONTROL_BUNDLE_PATH="")
    if packaging == "bundle":
        plist = executable.parents[1]/"Info.plist"
        info = plistlib.loads(plist.read_bytes())
        info["CFBundleIdentifier"] = "org.gpui-mbt.conformance.appkit-control."+token
        plist.write_bytes(plistlib.dumps(info))
        run["info_plist"] = artifact(plist, out)
        env.update(GPUI_AX_CONTROL_BUNDLE_ID=info["CFBundleIdentifier"],
                   GPUI_AX_CONTROL_BUNDLE_PATH=str(executable.parents[2]))
    started = now()
    start = time.monotonic()
    deadline = start+4.5
    proc = None
    with (folder/"fixture.stdout").open("wb") as stdout, (folder/"fixture.stderr").open("wb") as stderr:
        try:
            proc = subprocess.Popen([str(executable)], env=env, cwd=out, stdout=stdout, stderr=stderr)
            run["pid"] = proc.pid
            ready_path = folder/"ready.json"
            ready = None
            while proc.poll() is None and time.monotonic() < start+2:
                if ready_path.exists():
                    try:
                        ready = json.loads(ready_path.read_text())
                        break
                    except json.JSONDecodeError:
                        pass
                time.sleep(.01)
            if ready is None:
                raise ValueError("stock AppKit fixture did not publish a ready record")
            validate_ready(ready, run, proc.pid, executable, [256,192], started)
            local = ready.get("local_ax", {})
            local_windows = local.get("application_windows", [])
            if ready.get("control_kind") != "stock-appkit-no-gpu" or ready.get("pump") != pump or len(local_windows) != 1 or local_windows[0].get("same_owned_window") is not True or local_windows[0].get("role") != "AXWindow" or local_windows[0].get("title") != ready["title"] or local.get("button_role") != "AXButton":
                raise ValueError("stock local AppKit hierarchy differs")
            run["ready"] = artifact(ready_path, out)
            # Keep every early failure: later registration must not erase the initial projection.
            while proc.poll() is None and time.monotonic() < deadline-.05:
                number = len(run["attempts"])
                output, error = folder/f"observer-{number}.stdout", folder/f"observer-{number}.stderr"
                attempt = {"elapsed_before":time.monotonic()-start}
                attempt["execution"] = execute([str(observer),str(ready_path)], env, output, error, out,
                                                min(.75, deadline-time.monotonic()))
                attempt.update(stdout=artifact(output,out), stderr=artifact(error,out))
                run["attempts"].append(attempt)
                if attempt["execution"]["returncode"] == 0 and not attempt["execution"]["timed_out"]:
                    try:
                        result = json.loads(output.read_text())
                        attempt["classification"] = classify_attempt(result, ready)
                    except (ValueError, KeyError, TypeError) as exc:
                        attempt["classification"] = "invalid-observer-record"
                        attempt["reason"] = str(exc)
                    if attempt["classification"] == "external-window-matched":
                        run["status"] = "pass"
                        break
                time.sleep(min(.05, max(0,deadline-time.monotonic())))
            with (folder/"ack.json").open("x") as ack:
                json.dump({"run_token":token,"pid":proc.pid,"native_window_id":ready["native_window_id"],
                           "frame_sequence":1,"observer_completed":True}, ack)
            run["ack"] = artifact(folder/"ack.json",out)
            run["returncode"] = proc.wait(timeout=2)
            if run["returncode"] != 0:
                raise ValueError("stock fixture failed safety/lifecycle checks")
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            run.update(status="unverified",reason=str(exc))
        finally:
            if proc is not None:
                run["returncode"] = stop_owned(proc)
                run["cleanup"] = "owned-child-reaped"
    run.update(started_at=started, finished_at=now(),
               stdout=artifact(folder/"fixture.stdout",out),stderr=artifact(folder/"fixture.stderr",out))
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packaging", choices=("flat","bundle"), default="bundle")
    parser.add_argument("--pump", choices=("runloop","appkit"), default="runloop")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"protocol":1,"scope":"stock-appkit-external-window-only", "status":"unverified",
                "gpui_ax_compatibility":"unverified", "permission_prompted":False,
                "platform":{"os":platform.system(),"architecture":platform.machine(),"macos":platform.mac_ver()[0]},
                "suite_revision":command(["git","rev-parse","HEAD"],ROOT),
                "suite_dirty":bool(command(["git","status","--porcelain"],ROOT)),
                "packaging":args.packaging,"pump":args.pump}
    code = 1
    try:
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            manifest["reason"] = "requires macOS Apple Silicon; no native build or AX query attempted"
            code = 77
        else:
            sources = out/"sources"
            sources.mkdir()
            for name in ("ax_appkit_control.m","native_observer.m"):
                shutil.copy2(ROOT/"adapters"/name,sources/name)
            manifest["sources"] = [artifact(path,out) for path in sorted(sources.iterdir())]
            manifest["toolchain"] = command(["xcrun","clang","--version"])
            fixture_dir = out/"control"
            fixture_dir.mkdir()
            executable = fixture_dir/"probe"
            if args.packaging == "bundle":
                contents = fixture_dir/"Control.app/Contents"
                (contents/"MacOS").mkdir(parents=True)
                executable = contents/"MacOS/probe"
                (contents/"Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable":"probe",
                    "CFBundlePackageType":"APPL","CFBundleName":"AX AppKit control",
                    "NSPrincipalClass":"NSApplication","LSUIElement":True}))
            observer = out/"observer"
            for name, target in (("ax_appkit_control.m",executable),("native_observer.m",observer)):
                record = execute(["xcrun","clang","-fobjc-arc","-Wall","-Wextra","-Werror",
                    str(sources/name),"-framework","AppKit","-framework","ApplicationServices","-o",str(target)],
                    os.environ.copy(),out/(name+".stdout"),out/(name+".stderr"),out,60)
                manifest.setdefault("builds",[]).append(record)
                if record["returncode"] != 0 or record["timed_out"]:
                    raise ValueError("control build failed: "+name)
            manifest["observer"] = artifact(observer,out)
            manifest["run"] = run_control(executable,observer,fixture_dir,out,manifest["suite_revision"],args.packaging,args.pump)
            manifest["status"] = manifest["run"]["status"]
            code = 0 if manifest["status"] == "pass" else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        manifest["reason"] = str(exc)
    (out/"summary.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"status":manifest["status"],"summary":str(out/"summary.json"),"gpui_ax_compatibility":"unverified"}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
