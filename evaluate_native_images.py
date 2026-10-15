#!/usr/bin/env python3
"""Evaluate already-retained native readbacks; never create a new native execution claim."""
import argparse
import json
import math
import os
from pathlib import Path
import zlib

from comparator import digest, load_json, process_identity
from native_images import exact_comparison, frame_bytes, png_bytes, retained_frames, validate_diff, verify_toolchain
from run import artifact, command, execute


def evaluate(evidence, toolchain, output, threshold=0.0):
    evidence, toolchain, output = (Path(p).resolve() for p in (evidence, toolchain, output))
    if output.exists():
        raise ValueError("output already exists; prior evidence cannot be overwritten")
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("pixelmatch per-pixel threshold must be finite and between zero and one")
    output.mkdir(parents=True)
    report = {"schema_version": 1, "kind": "retained-native-image-evaluation", "status": "unverified",
              "native_execution": "not-rerun", "evidence_directory": str(evidence),
              "qualification": "analysis of the recorded source revisions only",
              "policy": "identical complete RGBA8 bytes, physical dimensions and device scale; vlmkit is a diagnostic",
              "pixelmatch_per_pixel_threshold": threshold, "zlib": zlib.ZLIB_RUNTIME_VERSION,
              "suite_revision": command(["git", "rev-parse", "HEAD"], Path(__file__).parent),
              "suite_dirty": bool(command(["git", "status", "--porcelain", "--untracked-files=no"], Path(__file__).parent))}
    try:
        if report["suite_dirty"]:
            raise ValueError("image evaluator tracked source is dirty")
        receipt = verify_toolchain(toolchain)
        report["toolchain"] = {"directory": str(toolchain), "receipt_sha256": digest((toolchain / "toolchain.json").read_bytes()), "pins": receipt["pins"]}
        manifest, comparison, frames = retained_frames(evidence)
        report["source_evidence"] = {"manifest_sha256": digest((evidence / "manifest.json").read_bytes()),
                                     "scenarios_sha256": digest((evidence / "scenarios.json").read_bytes()),
                                     "suite_revision": manifest["suite_revision"], "pins": manifest["pins"],
                                     "platform": manifest["platform"], "comparison": comparison}
        report["frames"] = {}
        for name, frame in frames.items():
            path = output / (name + ".png")
            path.write_bytes(png_bytes(frame))
            report["frames"][name] = {"width": frame["width"], "height": frame["height"], "scale": frame["scale"],
                                      "rgba8_sha256": digest(frame_bytes(frame)), "png": artifact(path, output)}
        exact = exact_comparison(frames["upstream"], frames["moonbit"])
        report["exact"] = exact
        if exact["metadata_differences"]:
            report["status"] = "mismatch"
            report["reason"] = "physical dimensions/device scale differ; no resampling or coerced PNG comparison"
        else:
            argv = ["node", str(toolchain / receipt["pins"]["entrypoint"]), str(output / "upstream.png"), str(output / "moonbit.png"),
                    "--threshold", str(threshold), "--json", "--output-dir", str(output / "diff")]
            report["diff_execution"] = execute(argv, os.environ.copy(), output / "diff.stdout", output / "diff.stderr", toolchain, 60)
            process_identity(report["diff_execution"])
            value = validate_diff(load_json(output / "diff.stdout"), frames["upstream"]["width"], frames["upstream"]["height"])
            report["vlmkit"] = value
            report["status"] = "mismatch" if exact["status"] == "mismatch" or value["status"] == "changed" else "pass"
            report["diagnostic_artifacts"] = [artifact(p, output) for p in sorted(output.rglob("*")) if p.is_file() and p.suffix != ".json"]
        verify_toolchain(toolchain)
    except (ValueError, KeyError, OSError, TypeError) as error:
        report["status"] = "unverified"
        report["reason"] = str(error)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pixel-threshold", type=float, default=0.0)
    args = parser.parse_args()
    result = evaluate(args.evidence, args.toolchain, args.output, args.pixel_threshold)
    print(json.dumps({"status": result["status"], "native_execution": result["native_execution"], "reason": result.get("reason"), "exact": result.get("exact")}))
    return {"pass": 0, "mismatch": 1, "unverified": 2}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
