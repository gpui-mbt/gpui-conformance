"""Compare only observations bound to retained, successful process executions.

Evidence is an audit trail, not a cryptographic attestation of an untrusted host.
No stand-alone observation JSON or golden trace can establish conformance.
"""
import hashlib
import json
import math
from pathlib import Path

PREFIX = "GPUI_CONFORMANCE "
STATUSES = ("pass", "mismatch", "unsupported", "unverified")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def evidence(run, root, implementation, scenarios_hash, expected_revision):
    """Return verified raw observations or a reason this run is unverified."""
    try:
        if run["implementation"] != implementation:
            raise ValueError("wrong implementation")
        if run["revision"] != expected_revision or run["dirty"]:
            raise ValueError("source revision or clean-tree check differs")
        if run["scenarios_sha256"] != scenarios_hash:
            raise ValueError("scenario digest differs")
        if run["execution"]["returncode"] != 0 or run["execution"]["timed_out"]:
            raise ValueError("process failed or timed out")
        if run["execution"]["pid"] <= 0 or not run["execution"]["command"]:
            raise ValueError("missing process identity")
        if not run["execution"]["finished_at"] or not run["toolchain"] or not run["platform"]:
            raise ValueError("missing execution/platform/toolchain metadata")
        # Relocatable evidence; never read a path outside its result directory.
        def read_artifact(name):
            path = (root / run[name]["path"]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError("artifact path escapes result directory")
            data = path.read_bytes()
            if digest(data) != run[name]["sha256"]:
                raise ValueError(name + " digest differs")
            return data
        raw = read_artifact("stdout")
        read_artifact("stderr")
        # The built executable is retained independently for replay/audit.
        read_artifact("executable")
        lines = [line[len(PREFIX):] for line in raw.decode().splitlines() if line.startswith(PREFIX)]
        if len(lines) != 1:
            raise ValueError("expected exactly one adapter output envelope")
        output = json.loads(lines[0])
        if output["implementation"] != implementation or output["run_token"] != run["run_token"]:
            raise ValueError("adapter execution challenge differs")
        cases = output["cases"]
        if len({case["id"] for case in cases}) != len(cases):
            raise ValueError("duplicate case IDs")
        if any(case.get("status") not in ("observed", "unsupported", "unverified") for case in cases):
            raise ValueError("invalid adapter status")
        return {case["id"]: case for case in cases}, None
    except (KeyError, ValueError, TypeError, OSError, UnicodeError) as exc:
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
    scenario_hash = digest(scenario_bytes)
    results = {}
    errors = {}
    for name in ("upstream", "moonbit"):
        run = manifest.get("runs", {}).get(name, {})
        results[name], errors[name] = evidence(run, root, name, scenario_hash, manifest.get("pins", {}).get(name, {}).get("revision"))
    # Independent executions may have equal semantic observations. Reusing an
    # identical raw trace/challenge for both implementations must never pass.
    u, m = (manifest.get("runs", {}).get(name, {}) for name in ("upstream", "moonbit"))
    if u.get("run_token") == m.get("run_token") or u.get("stdout", {}).get("sha256") == m.get("stdout", {}).get("sha256"):
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
            row.update(status="unsupported", reason=[case.get("reason") for case in pair])
        elif any(case.get("layer") != scenario["layer"] for case in pair):
            row.update(status="unverified", reason="execution layers differ from requested coverage")
        elif any("observation" not in case or not case["observation"] for case in pair):
            row.update(status="unverified", reason="empty observation")
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
