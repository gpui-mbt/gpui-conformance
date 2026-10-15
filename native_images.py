"""Strict retained-RGBA analysis. This module never captures a screen or launches a GUI."""
import json
import math
from pathlib import Path
import struct
import zlib

from comparator import PREFIX, compare, digest, load_json, process_identity

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


def verify_toolchain(directory):
    directory = Path(directory).resolve()
    receipt = load_json(directory / "toolchain.json")
    pins = load_json(PINS)
    if receipt.get("pins") != pins or receipt.get("status") != "ready":
        raise ValueError("toolchain does not match the reviewed visual pin")
    for key in ("install", "build"):
        process_identity(receipt[key])
    if receipt["install"]["finished_at"] > receipt["build"]["started_at"]:
        raise ValueError("visual build did not follow dependency preparation")
    artifacts = receipt.get("artifacts", [])
    paths = [item["path"] for item in artifacts]
    required = {pins["entrypoint"], "source.tar", "runtime/pnpm-lock.yaml", "install.stdout", "install.stderr", "build.stdout", "build.stderr"}
    if len(set(paths)) != len(paths) or not required.issubset(paths):
        raise ValueError("visual toolchain artifacts are missing or duplicated")
    for item in artifacts:
        path = (directory / item["path"]).resolve()
        if not path.is_relative_to(directory) or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError("visual toolchain artifact differs: " + item["path"])
    if digest((directory / "runtime/pnpm-lock.yaml").read_bytes()) != pins["lock_sha256"]:
        raise ValueError("visual dependency lock differs")
    return receipt
