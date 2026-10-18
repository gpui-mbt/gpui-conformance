"""Fail closed on incomplete evidence, including retained image bytes."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_lab.launcher import events, has_event, inspect_images, sha256


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_report(path, negative=False):
    report = json.loads(path.read_text())
    require(isinstance(report, dict), "report must be an object")
    require(report.get("schema_version") == 1, "unknown report schema")
    require(report.get("status") == ("mismatch" if negative else "pass"), "unexpected status")
    require(report.get("reasons") == [], "missing or nonempty reasons")
    require(report.get("negative_control") is negative, "wrong control mode")
    require(report.get("pins") == json.loads((ROOT / "pins.json").read_text()), "report differs from current source pins")
    root = path.parent
    scenarios_path = ROOT / "native_scenarios.json"
    scenarios = json.loads(scenarios_path.read_text())
    require(report.get("scenario_sha256") == sha256(scenarios_path), "wrong scenario digest")
    require(json.loads((root / "scenarios.json").read_text()) == scenarios, "wrong retained scenarios")
    require(report["resize"]["status"] == "pass", "resize unverified")
    require(report["resize"]["requested"] == scenarios["cases"][0]["resize"], "wrong resize request")
    token = report["run_token"]
    require(isinstance(token, str) and bool(token), "missing run token")
    pixel_case = scenarios["cases"][1]
    paths = {role: root / f"{role}.png" for role in ("upstream", "moonbit")}
    measured = inspect_images(paths, pixel_case, 1.0)
    require(report["pixels"] == measured, "pixel report differs from retained bytes")
    for role in paths:
        require(report["builds"][role]["returncode"] == 0, f"{role}: build failed")
        require(report["sources"][role]["revision"] == report["pins"][role]["revision"],
                f"{role}: source differs from pin")
        require(report["sources"][role]["dirty"] is False, f"{role}: dirty source")
        require(report["alive_after_observation"][role] is True, f"{role}: child terminated")
        records = events(root / f"{role}.stdout", role, token)
        require(records == report["native_events"][role], f"{role}: event log differs")
        require(has_event(records, "frame_ready", pixel_case["width"], pixel_case["height"], 1),
                f"{role}: initial frame missing")
        width, height = scenarios["cases"][0]["resize"]
        require(report["resize"]["event_confirmed"][role] is True and
                has_event(records, "resized", width, height, 1), f"{role}: resize missing")
        entry = report["resize"]["captures"][role]
        retained = root / f"{role}-resized.png"
        require(entry["path"] == retained.name and entry["sha256"] == sha256(retained),
                f"{role}: resized capture missing or corrupt")
        from PIL import Image
        with Image.open(retained) as image:
            require(image.size == (width, height), f"{role}: resized dimensions wrong")
        require(report["resize"]["actual_capture_sizes"][role] == [width, height],
                f"{role}: reported resize dimensions wrong")
    require(measured["captures"]["upstream"]["fixture_match"], "oracle fixture differs")
    if negative:
        blue_case = {**pixel_case, "color": [0, 0, 255, 255]}
        blue = inspect_images(paths, blue_case, 1.0)
        require(blue["captures"]["moonbit"]["fixture_match"], "control differs from exact blue fixture")
        require(measured["different_pixels"] == pixel_case["rect"][2] * pixel_case["rect"][3],
                "control changed unexpected pixels")
    else:
        require(measured["status"] == "pass" and measured["different_pixels"] == 0,
                "full-frame fixture mismatch")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--require-negative-control", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = validate_report(args.report)
        if args.require_negative_control:
            negative = validate_report(args.report.parent / "negative-control/comparison.json", True)
            require(negative["run_token"] != report["run_token"], "control reused run token")
            for key in ("pins", "sources", "scenario_sha256", "builds"):
                require(negative[key] == report[key], f"control changed {key}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"Native evidence rejected: {exc}", file=sys.stderr)
        return 1
    print("Native lab status: pass (retained full-frame evidence; physical GPU unverified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
