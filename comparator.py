"""Compare only observations bound to retained, successful process executions.

Evidence is an audit trail, not a cryptographic attestation of an untrusted host.
No stand-alone observation JSON or golden trace can establish conformance.
"""
import hashlib
import json
import math
import plistlib
from pathlib import Path
from datetime import datetime
import re
import uuid
from fixture_contracts import validate_native_fixture
from observer_contracts import execution_root, validate_ack, validate_frame_binding, validate_observation, validate_ready
from contracts import validate_scenarios, valid_observation

PREFIX = "GPUI_CONFORMANCE "
STATUSES = ("pass", "mismatch", "unsupported", "unverified")
PIN_FILE = Path(__file__).resolve().parent / "pins.json"


def sha(value, length):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{" + str(length) + "}", value) is not None


def process_identity(value):
    if type(value["pid"]) is not int or value["pid"] <= 0:
        raise ValueError("missing process identity")
    if not isinstance(value["command"], list) or not value["command"] or any(not isinstance(x, str) or not x for x in value["command"]):
        raise ValueError("missing process command")
    if type(value["returncode"]) is not int or value["returncode"] != 0 or value["timed_out"] is not False:
        raise ValueError("process failed or timed out")
    start, end = (datetime.fromisoformat(value[k]) for k in ("started_at", "finished_at"))
    if start.tzinfo is None or end.tzinfo is None or end < start:
        raise ValueError("invalid process timestamps")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def evidence(run, root, implementation, scenarios_hash, expected_revision, expected_version, expected_platform):
    """Return verified raw observations or a reason this run is unverified."""
    try:
        if run["implementation"] != implementation:
            raise ValueError("wrong implementation")
        if not sha(expected_revision, 40) or run["revision"] != expected_revision or run["dirty"] is not False:
            raise ValueError("source revision or clean-tree check differs")
        if run["scenarios_sha256"] != scenarios_hash:
            raise ValueError("scenario digest differs")
        process_identity(run["execution"])
        process_identity(run["build"])
        if run["platform"] != expected_platform or run["version"] != expected_version or not sha(run["source_tree"], 40):
            raise ValueError("platform/version/source identity differs or is absent")
        uuid.UUID(run["run_token"])
        if not isinstance(run["toolchain"], str) or not run["toolchain"] or not run["platform"]:
            raise ValueError("missing execution/platform/toolchain metadata")
        # Relocatable evidence; never read a path outside its result directory.
        def read_record(record):
            path = (root / record["path"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("artifact path escapes result directory")
            data = path.read_bytes()
            if digest(data) != record["sha256"]:
                raise ValueError("artifact digest differs")
            return data
        def read_artifact(name):
            return read_record(run[name])
        raw = read_artifact("stdout")
        read_artifact("stderr")
        read_artifact("build_stdout")
        read_artifact("build_stderr")
        # The built executable is retained independently for replay/audit.
        read_artifact("executable")
        executable_path = Path(run["executable"]["path"])
        bundled = executable_path.parts[-3:] == ("Contents","MacOS","probe")
        if bundled and "fixture_packaging" not in run:
            raise ValueError("missing fixture bundle packaging identity")
        if "fixture_packaging" in run:
            if run["fixture_packaging"] != "app-bundle-v1":
                raise ValueError("unknown fixture packaging")
            expected_bundle = {"CFBundlePackageType":"APPL", "CFBundleExecutable":"probe",
                "CFBundleIdentifier":"org.gpui-mbt.conformance."+implementation+"."+run["run_token"],
                "CFBundleName":"GPUI Conformance Fixture", "CFBundleVersion":"1",
                "CFBundleShortVersionString":"1.0", "LSMinimumSystemVersion":"13.0",
                "LSUIElement":True, "NSPrincipalClass":"NSApplication", "NSHighResolutionCapable":True}
            actual_bundle = plistlib.loads(read_artifact("bundle_info_plist"))
            if actual_bundle != expected_bundle or any(type(actual_bundle[k]) is not type(v) for k,v in expected_bundle.items()):
                raise ValueError("fixture bundle identity/policy differs")
            if executable_path.parts[-3:] != ("Contents","MacOS","probe") or executable_path.parent.parent.parent.suffix != ".app" or Path(run["bundle_info_plist"]["path"]) != executable_path.parent.parent/"Info.plist":
                raise ValueError("fixture bundle paths differ")
        lines = [line[len(PREFIX):] for line in raw.decode().splitlines() if line.startswith(PREFIX)]
        if len(lines) != 1:
            raise ValueError("expected exactly one adapter output envelope")
        output = json.loads(lines[0])
        if output["implementation"] != implementation or output["run_token"] != run["run_token"]:
            raise ValueError("adapter execution challenge differs")
        if "fixture_protocol" in run or "native_fixture" in output:
            if type(run["fixture_protocol"]) is not int or run["fixture_protocol"] != 1:
                raise ValueError("unknown native fixture evidence protocol")
            read_artifact("fixture_guard")
            process_identity(run["fixture_guard_build"])
            read_artifact("fixture_guard_build_stdout")
            read_artifact("fixture_guard_build_stderr")
            validate_native_fixture(output.get("native_fixture"), run["execution"]["pid"], run.get("fixture_mode", "hidden"))
            if run.get("fixture_mode") == "visible":
                observation = run["observer"]
                if observation["status"] != "pass":
                    raise ValueError("owned observer handshake was not completed")
                process_identity(observation["execution"])
                process_identity(run["observer_build"])
                for key in ("observer_executable", "observer_build_stdout", "observer_build_stderr"):
                    read_artifact(key)
                ready = json.loads(read_record(observation["ready"]))
                window_scenario = load_json(root / "scenarios.json")["cases"][0]
                validate_ready(ready, run, run["execution"]["pid"], run["execution"]["command"][0],
                               [window_scenario[k] for k in ("width", "height")],
                               run["execution"]["started_at"], run["execution"]["finished_at"])
                validate_frame_binding(ready, output)
                original_root = execution_root(run)
                observer_executable = str(original_root / run["observer_executable"]["path"])
                if run["observer_build"]["command"][-1] != observer_executable or observation["execution"]["command"] != [observer_executable, str(original_root / observation["ready"]["path"])]:
                    raise ValueError("observer execution command differs from built observer/ready record")
                observed = json.loads(read_record(observation["stdout"]))
                read_record(observation["stderr"])
                validate_observation(observed, ready)
                if observation["ax_status"] != observed["ax_status"]:
                    raise ValueError("observer AX summary differs from raw observation")
                ack = json.loads(read_record(observation["ack"]))
                validate_ack(ack, ready)
                controls = observation["negative_controls"]
                expected_controls = [("stale-start", "process_start_sec", ready["process_start_sec"]-1), ("invalid-window", "native_window_id", 0), ("invalid-pid", "pid", 0)]
                if not isinstance(controls, list) or len(controls) != len(expected_controls):
                    raise ValueError("missing owned observer negative controls")
                previous_control_end = datetime.fromisoformat(run["execution"]["started_at"])
                for control, (name, key, value) in zip(controls, expected_controls):
                    if control["name"] != name or json.loads(read_record(control["ready"])) != {**ready, key: value}:
                        raise ValueError("observer negative control identity differs")
                    process_identity(control["execution"])
                    if control["execution"]["command"] != [observer_executable, str(original_root / control["ready"]["path"])]:
                        raise ValueError("observer negative control command differs")
                    control_start, control_end = (datetime.fromisoformat(control["execution"][k]) for k in ("started_at", "finished_at"))
                    if not (previous_control_end <= control_start <= control_end <= datetime.fromisoformat(observation["execution"]["started_at"])) or int(control_start.timestamp()*1e9) < ready["ready_unix_ns"]:
                        raise ValueError("observer negative control falls outside ready fixture lifetime")
                    previous_control_end = control_end
                    result = json.loads(read_record(control["stdout"]))
                    read_record(control["stderr"])
                    if result.get("window_binding") != "unverified" or "window" in result or result.get("permission_prompted") is not False:
                        raise ValueError("observer negative control accepted a target")
                if not (datetime.fromisoformat(run["execution"]["started_at"]) <= datetime.fromisoformat(observation["execution"]["started_at"]) <= datetime.fromisoformat(observation["execution"]["finished_at"]) <= datetime.fromisoformat(run["execution"]["finished_at"])):
                    raise ValueError("observer execution falls outside owned fixture lifetime")
        cases = output["cases"]
        if len({case["id"] for case in cases}) != len(cases):
            raise ValueError("duplicate case IDs")
        if any(case.get("status") not in ("observed", "unsupported", "unverified") for case in cases):
            raise ValueError("invalid adapter status")
        native = [c for c in cases if c["status"] == "observed" and c.get("layer") in ("native-window","native-gpu")]
        if native:
            if run.get("execution_mode") != "native" or run.get("backend") != "appkit-metal":
                raise ValueError("native layer lacks native backend execution identity")
            if implementation == "moonbit":
                read_artifact("runtime_library")
                process_identity(run["library_build"])
                read_artifact("library_build_stdout")
                read_artifact("library_build_stderr")
                read_artifact("foreground_guard")
                process_identity(run["guard_build"])
                read_artifact("guard_build_stdout")
                read_artifact("guard_build_stderr")
            for case in native:
                if case["layer"] == "native-gpu":
                    s = next((s for s in load_json(root / "scenarios.json")["cases"] if s["id"] == case["id"]), None)
                    if s is None:
                        raise ValueError("unexpected native case ID")
                    frame = output["frame"]
                    observation = case["observation"]
                    if not valid_observation(s, observation) or any(frame[k] != observation[k] for k in ("width","height","scale")):
                        raise ValueError("GPU readback metadata differs from observation")
                    if abs(frame["width"]/frame["scale"]-s["width"]) > 0.0001 or abs(frame["height"]/frame["scale"]-s["height"]) > 0.0001:
                        raise ValueError("GPU readback viewport differs from requested scenario")
                    pixels = frame["rgba8"]
                    if not isinstance(pixels,list) or len(pixels) != frame["width"] * frame["height"] * 4 or len(pixels) > 16*1024*1024*4 or any(type(x) is not int or not 0 <= x <= 255 for x in pixels):
                        raise ValueError("missing or malformed complete GPU readback")
                    for point, observed_pixel in zip(s["points"], observation["samples"]):
                        x,y=(math.floor(coordinate * frame["scale"]) for coordinate in point)
                        if not (0 <= x < frame["width"] and 0 <= y < frame["height"]):
                            raise ValueError("sample outside GPU readback")
                        offset=(y*frame["width"]+x)*4
                        if pixels[offset:offset+4] != observed_pixel:
                            raise ValueError("pixel samples do not come from retained readback")
        return {case["id"]: case for case in cases}, None
    except (KeyError, ValueError, TypeError, OSError, UnicodeError, AttributeError) as exc:
        return {}, str(exc)


def differences(a, b, path="observation"):
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if type(a) is type(b) and a == b else [{"path": path, "upstream": a, "moonbit": b}]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        same = math.isfinite(a) and math.isfinite(b) and abs(a - b) <= 0.0001
        return [] if same else [{"path": path, "upstream": a, "moonbit": b}]
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        return [d for key in a for d in differences(a[key], b[key], path + "." + key)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, f"{path}[{i}]")]
    return [] if type(a) is type(b) and a == b else [{"path": path, "upstream": a, "moonbit": b}]


def compare(manifest, scenarios, root):
    root = Path(root)
    scenario_bytes = (root / "scenarios.json").read_bytes()
    validate_scenarios(scenarios)
    if json.loads(scenario_bytes) != scenarios:
        raise ValueError("comparison scenarios differ from retained scenario artifact")
    scenario_hash = digest(scenario_bytes)
    results = {}
    errors = {}
    canonical_pins = load_json(PIN_FILE)
    host = manifest.get("platform", {})
    protocol_error = None
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or manifest.get("pins", {}).get("schema_version") != 1:
        protocol_error = "unsupported or missing manifest/pins schema version"
    elif not isinstance(host, dict) or any(not isinstance(host.get(k), str) or not host[k] for k in ("os", "architecture", "release")) or (host["os"] == "Darwin" and (not isinstance(host.get("macos"), str) or not host["macos"])):
        protocol_error = "missing platform OS/architecture/release identity"
    for name in ("upstream", "moonbit"):
        run = manifest.get("runs", {}).get(name, {})
        pin = manifest.get("pins", {}).get(name, {})
        results[name], errors[name] = evidence(run, root, name, scenario_hash, pin.get("revision"), pin.get("version"), manifest.get("platform"))
        expected_pin = canonical_pins[name]
        accepted_pin = dict(expected_pin)
        if name == "moonbit" and pin.get("baseline_revision") == expected_pin["revision"] and sha(pin.get("revision"), 40):
            accepted_pin.update(revision=pin["revision"], baseline_revision=expected_pin["revision"])
        if pin != accepted_pin:
            errors[name] = "manifest pin differs from reviewed pins or explicit candidate mapping"
        if protocol_error:
            errors[name] = protocol_error
        if results[name].keys() != {s["id"] for s in scenarios["cases"]}:
            errors[name] = errors[name] or "missing or unexpected executed cases"
    # Independent executions may have equal semantic observations. Reusing an
    # identical raw trace/challenge for both implementations must never pass.
    u, m = (manifest.get("runs", {}).get(name, {}) for name in ("upstream", "moonbit"))
    if u.get("run_token") == m.get("run_token") or u.get("stdout", {}).get("sha256") == m.get("stdout", {}).get("sha256") or u.get("executable", {}).get("sha256") == m.get("executable", {}).get("sha256"):
        errors["upstream"] = errors["moonbit"] = "duplicated execution trace or challenge"
    cases = []
    for scenario in scenarios["cases"]:
        row = {"id": scenario["id"], "layer": scenario["layer"]}
        pair = [results[name].get(scenario["id"]) for name in ("upstream", "moonbit")]
        if any(errors.values()) or any(case is None for case in pair):
            row.update(status="unverified", reason={k: v for k, v in errors.items() if v} or "missing case execution")
        elif any(case["status"] == "unverified" for case in pair):
            row.update(status="unverified", reason=[case.get("reason") for case in pair])
        elif any(case["status"] == "unsupported" for case in pair):
            row.update(status="unsupported" if all(case.get("reason") for case in pair if case["status"] == "unsupported") else "unverified", reason=[case.get("reason") for case in pair])
        elif any(case.get("layer") != scenario["layer"] for case in pair):
            row.update(status="unverified", reason="execution layers differ from requested coverage")
        elif any(not valid_observation(scenario, case.get("observation")) for case in pair):
            row.update(status="unverified", reason="empty or malformed observation for requested scenario")
        else:
            diff = differences(pair[0]["observation"], pair[1]["observation"])
            row.update(status="mismatch" if diff else "pass", differences=diff)
            row["upstream"] = pair[0]["observation"]
            row["moonbit"] = pair[1]["observation"]
        cases.append(row)
    return {"schema_version": 1, "platform": manifest.get("platform"), "pins": manifest.get("pins"),
            "scenarios_sha256": scenario_hash, "cases": cases,
            "summary": {status: sum(c["status"] == status for c in cases) for status in STATUSES}}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("result_dir", type=Path)
    args = parser.parse_args()
    result = compare(load_json(args.result_dir / "manifest.json"), load_json(args.result_dir / "scenarios.json"), args.result_dir)
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["summary"]["mismatch"] else 2 if result["summary"]["unverified"] else 0)
