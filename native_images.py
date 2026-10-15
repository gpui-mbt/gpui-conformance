"""Strict retained-RGBA analysis. This module never captures a screen or launches a GUI."""
from datetime import datetime
import json
import math
import os
import stat
from pathlib import Path
import struct
import zlib

from comparator import PREFIX, compare, digest, load_json, process_identity, sha

PINS = Path(__file__).with_name("visual_pins.json")


def frame_bytes(frame):
    width, height, scale = (frame[k] for k in ("width", "height", "scale"))
    if (type(width) is not int or type(height) is not int or
            not 1 <= width <= 16384 or not 1 <= height <= 16384 or
            width * height > 16 * 1024 * 1024 or type(scale) not in (int, float) or
            not math.isfinite(scale) or scale <= 0):
        raise ValueError("invalid physical frame dimensions or device scale")
    rgba = frame["rgba8"]
    if (not isinstance(rgba, list) or len(rgba) != width * height * 4 or
            any(type(v) is not int or not 0 <= v <= 255 for v in rgba)):
        raise ValueError("complete RGBA8 readback is required")
    return bytes(rgba)


def png_bytes(frame):
    """Encode unchanged, top-down RGBA8 bytes: no scaling, filtering or color conversion."""
    rgba = frame_bytes(frame)
    width, height = frame["width"], frame["height"]
    stride = width * 4
    scanlines = b"".join(b"\0" + rgba[i:i + stride] for i in range(0, len(rgba), stride))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))


def retained_frames(root):
    """Require the existing comparator's full independent native execution evidence."""
    root = Path(root).resolve()
    manifest = load_json(root / "manifest.json")
    scenarios = load_json(root / "scenarios.json")
    comparison = compare(manifest, scenarios, root)
    pixels = [s for s in scenarios["cases"] if s["kind"] == "pixels"]
    if len(pixels) != 1:
        raise ValueError("exactly one retained native pixel scenario is required")
    pixel_id = pixels[0]["id"]
    row = next(c for c in comparison["cases"] if c["id"] == pixel_id)
    if row["status"] not in ("pass", "mismatch"):
        raise ValueError("retained native execution is unverified: " + str(row))
    frames = {}
    for name in ("upstream", "moonbit"):
        run = manifest["runs"][name]
        path = (root / run["stdout"]["path"]).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes()) != run["stdout"]["sha256"]:
            raise ValueError("retained stdout binding changed")
        lines = [line[len(PREFIX):] for line in path.read_text().splitlines() if line.startswith(PREFIX)]
        if len(lines) != 1:
            raise ValueError("invalid retained adapter envelope")
        frames[name] = json.loads(lines[0])["frame"]
        frame_bytes(frames[name])
    return manifest, comparison, frames


def exact_comparison(first, second):
    a, b = frame_bytes(first), frame_bytes(second)
    dimensions = {k: [first[k], second[k]] for k in ("width", "height", "scale") if first[k] != second[k]}
    if dimensions:
        return {"status": "mismatch", "metadata_differences": dimensions, "different_pixels": None}
    count = sum(a[i:i + 4] != b[i:i + 4] for i in range(0, len(a), 4))
    return {"status": "mismatch" if count else "pass", "metadata_differences": {},
            "different_pixels": count, "total_pixels": first["width"] * first["height"]}


def validate_diff(value, width, height):
    """Exit 0 alone means nothing; validate structured pixel metrics and dimensions."""
    if not isinstance(value, dict) or value.get("status") not in ("pass", "changed"):
        raise ValueError("missing or unknown vlmkit JSON status")
    for field, expected in (("baselineSize", {"width": width, "height": height}),
                            ("currentSize", {"width": width, "height": height}),
                            ("sizeDelta", {"width": 0, "height": 0})):
        dimensions = value.get(field)
        if (not isinstance(dimensions, dict) or dimensions != expected or
                any(type(dimensions[k]) is not int for k in ("width", "height"))):
            raise ValueError("vlmkit PNG dimensions differ from bound RGBA frames")
    if "mask" in value:
        raise ValueError("resized or masked comparisons cannot qualify")
    total, different, ratio = (value.get(k) for k in ("totalPixels", "diffPixels", "diffRatio"))
    if (type(total) is not int or total != width * height or type(different) is not int or
            not 0 <= different <= total or type(ratio) not in (int, float) or
            not math.isfinite(ratio) or abs(ratio - different / total) > 1e-12 or
            value["status"] != ("changed" if different else "pass")):
        raise ValueError("inconsistent vlmkit status or pixel metrics")
    return value


def runtime_inventory(directory):
    """Cover every installed byte and every symlink route; never follow outside the runtime."""
    directory = Path(directory).resolve()
    result = []
    for parent, directories, files in os.walk(directory, followlinks=False):
        parent = Path(parent)
        for name in sorted(directories + files):
            path = parent / name
            relative = str(path.relative_to(directory))
            if path.is_symlink():
                if not path.resolve(strict=True).is_relative_to(directory):
                    raise ValueError("runtime symlink escapes its isolated directory: " + relative)
                result.append({"path": relative, "kind": "symlink", "target": os.readlink(path)})
            elif path.is_file():
                result.append({"path": relative, "kind": "file", "sha256": digest(path.read_bytes()),
                               "mode": stat.S_IMODE(path.stat().st_mode)})
            elif not path.is_dir():
                raise ValueError("unsupported runtime file kind: " + relative)
        directories[:] = [name for name in directories if not (parent / name).is_symlink()]
    return sorted(result, key=lambda item: item["path"])


def verify_runtime_inventory(directory, expected):
    if not isinstance(expected, list) or not expected or runtime_inventory(directory) != expected:
        raise ValueError("complete runtime code, dependency, or symlink inventory differs")


def validate_threshold(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("pixelmatch per-pixel threshold must be finite and between zero and one")
    return value


def diff_command(toolchain, output, threshold, pins):
    return ["node", str(Path(toolchain) / pins["entrypoint"]), str(Path(output) / "upstream.png"),
            str(Path(output) / "moonbit.png"), "--threshold", str(validate_threshold(threshold)),
            "--json", "--output-dir", str(Path(output) / "diff")]


def validate_analysis_metadata(report):
    if (type(report.get("schema_version")) is not int or report["schema_version"] != 1 or
            report.get("kind") != "retained-native-image-evaluation" or report.get("native_execution") != "not-rerun" or
            report.get("suite_dirty") is not False or not sha(report.get("suite_revision"), 40) or
            report.get("qualification") != "analysis of the recorded source revisions only"):
        raise ValueError("invalid retained image analysis identity")
    validate_threshold(report["pixelmatch_per_pixel_threshold"])
    original_output = Path(report["output_directory"])
    original_toolchain = Path(report["toolchain"]["directory"])
    if not original_output.is_absolute() or not original_toolchain.is_absolute():
        raise ValueError("recorded analysis/toolchain paths must be absolute")
    return original_output, original_toolchain


def require_ordered(first, second):
    earlier, later = datetime.fromisoformat(first), datetime.fromisoformat(second)
    if earlier.tzinfo is None or later.tzinfo is None or earlier > later:
        raise ValueError("invalid visual build/execution chronology")


def validate_diff_invocation(report, pins, build=None):
    original_output, original_toolchain = validate_analysis_metadata(report)
    process_identity(report["diff_execution"])
    if report["diff_execution"]["command"] != diff_command(original_toolchain, original_output, report["pixelmatch_per_pixel_threshold"], pins):
        raise ValueError("diagnostic command does not bind the pinned entrypoint, PNGs and threshold")
    if build is not None:
        require_ordered(build["finished_at"], report["diff_execution"]["started_at"])


def verify_toolchain(directory):
    directory = Path(directory).resolve()
    receipt = load_json(directory / "toolchain.json")
    pins = load_json(PINS)
    if (receipt.get("schema_version") != 1 or receipt.get("pins") != pins or
            receipt.get("status") != "ready" or receipt.get("suite_dirty") is not False or
            not sha(receipt.get("suite_revision"), 40)):
        raise ValueError("toolchain does not match the reviewed visual pin")
    verify_runtime_inventory(directory / "runtime", receipt.get("runtime_inventory"))
    if receipt["build"]["command"] != ["pnpm", "build:packages:js"] or receipt["moon_build"]["command"] != ["moon", "-C", "packages/vlmkit-markup", "build", "markup-core", "markup-core-api", "markup-core-cli", "--target", "js"]:
        raise ValueError("visual preparation build command differs")
    for key in ("install", "moon_build", "build"):
        process_identity(receipt[key])
    require_ordered(receipt["install"]["finished_at"], receipt["moon_build"]["started_at"])
    require_ordered(receipt["moon_build"]["finished_at"], receipt["build"]["started_at"])
    artifacts = receipt.get("artifacts", [])
    paths = [item["path"] for item in artifacts]
    required = {pins["entrypoint"], "source.tar", "runtime/pnpm-lock.yaml", "install.stdout", "install.stderr", "build.stdout", "build.stderr", "moon_build.stdout", "moon_build.stderr",
                "runtime/packages/vlmkit-markup/_build/js/debug/build/markup-core-api/markup-core-api.js",
                "runtime/packages/vlmkit-markup/_build/js/debug/build/markup-core-cli/markup-core-cli.js"}
    if len(set(paths)) != len(paths) or not required.issubset(paths):
        raise ValueError("visual toolchain artifacts are missing or duplicated")
    for item in artifacts:
        path = (directory / item["path"]).resolve()
        if not path.is_relative_to(directory) or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError("visual toolchain artifact differs: " + item["path"])
    if digest((directory / "source.tar").read_bytes()) != pins["archive_sha256"]:
        raise ValueError("visual source archive differs from the immutable pin")
    if digest((directory / "runtime/pnpm-lock.yaml").read_bytes()) != pins["lock_sha256"]:
        raise ValueError("visual dependency lock differs")
    return receipt
