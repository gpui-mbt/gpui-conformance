#!/usr/bin/env python3
"""Recompute retained image analysis without launching a program, window or capture."""
import argparse
from pathlib import Path

from comparator import digest, load_json, process_identity, sha
from native_images import diff_command, exact_comparison, frame_bytes, png_bytes, retained_frames, validate_analysis_metadata, validate_diff, validate_diff_invocation, verify_toolchain


def verify_report(directory, evidence, toolchain):
    directory, evidence, toolchain = (Path(p).resolve() for p in (directory, evidence, toolchain))
    report = load_json(directory / "report.json")
    validate_analysis_metadata(report)
    if report.get("status") not in ("pass", "mismatch"):
        raise ValueError("report is unverified")
    receipt = verify_toolchain(toolchain)
    if report["toolchain"]["pins"] != receipt["pins"] or report["toolchain"]["receipt_sha256"] != digest((toolchain / "toolchain.json").read_bytes()):
        raise ValueError("visual toolchain receipt binding differs")
    manifest, comparison, frames = retained_frames(evidence)
    expected_source = {"manifest_sha256": digest((evidence / "manifest.json").read_bytes()),
                       "scenarios_sha256": digest((evidence / "scenarios.json").read_bytes()),
                       "suite_revision": manifest["suite_revision"], "pins": manifest["pins"],
                       "platform": manifest["platform"], "comparison": comparison}
    if report["source_evidence"] != expected_source:
        raise ValueError("original retained native evidence binding differs")
    for name, frame in frames.items():
        info = report["frames"][name]
        path = (directory / info["png"]["path"]).resolve()
        if (not path.is_relative_to(directory) or
                any(info[k] != frame[k] for k in ("width", "height", "scale")) or
                info["rgba8_sha256"] != digest(frame_bytes(frame)) or
                digest(path.read_bytes()) != info["png"]["sha256"] or path.read_bytes() != png_bytes(frame)):
            raise ValueError("PNG does not encode the exact retained RGBA frame")
    exact = exact_comparison(frames["upstream"], frames["moonbit"])
    if report["exact"] != exact:
        raise ValueError("exact whole-frame comparison differs")
    status = exact["status"]
    if not exact["metadata_differences"]:
        validate_diff_invocation(report, receipt["pins"], receipt["build"])
        artifacts = report["diagnostic_artifacts"]
        paths = [a["path"] for a in artifacts]
        if len(paths) != len(set(paths)) or not {"diff.stdout", "diff.stderr"}.issubset(paths):
            raise ValueError("missing or duplicated diagnostic artifacts")
        for item in artifacts:
            path = (directory / item["path"]).resolve()
            if not path.is_relative_to(directory) or digest(path.read_bytes()) != item["sha256"]:
                raise ValueError("diagnostic artifact binding differs")
        diff = validate_diff(load_json(directory / "diff.stdout"), frames["upstream"]["width"], frames["upstream"]["height"])
        if report["vlmkit"] != diff:
            raise ValueError("recorded vlmkit JSON differs from retained execution stdout")
        if diff["status"] == "changed":
            status = "mismatch"
    if report["status"] != status:
        raise ValueError("reported image result differs from exact/diagnostic evidence")
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    args = parser.parse_args()
    status = verify_report(args.directory, args.evidence, args.toolchain)
    print("Verified retained image analysis:", status, "(native execution was not rerun)")


if __name__ == "__main__":
    main()
