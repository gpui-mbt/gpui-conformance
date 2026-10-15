#!/usr/bin/env python3
"""Account for every exact RGB difference using saved scene geometry."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageChops


def font_metrics(path: Path, scene: dict) -> dict:
    data = path.read_bytes()
    tables = {}
    for i in range(struct.unpack_from(">H", data, 4)[0]):
        tag, _, offset, length = struct.unpack_from(">4sIII", data, 12 + i * 16)
        tables[tag] = data[offset:offset + length]
    units = struct.unpack_from(">H", tables[b"head"], 18)[0]
    ascent, descent, gap = struct.unpack_from(">hhh", tables[b"hhea"], 4)
    flags = struct.unpack_from(">H", tables[b"OS/2"], 62)[0]
    if flags & 128:
        raise ValueError("this fixture's hhea baseline calculation requires USE_TYPO_METRICS off")
    item = next(i for i in scene["frame"]["snapshot"]["items"] if i["kind"] == "text")
    scale = item["font_size"] / units
    scaled_ascent, scaled_descent = ascent * scale, -descent * scale
    return {"sha256": hashlib.sha256(data).hexdigest(), "units_per_em": units,
            "hhea": {"ascent": ascent, "descent": descent, "line_gap": gap},
            "use_typo_metrics": False, "scaled_ascent": scaled_ascent, "scaled_descent": scaled_descent,
            "derived_baseline": item["bounds"]["y"] + (item["bounds"]["height"] - scaled_ascent - scaled_descent) / 2 + scaled_ascent,
            "qualification": "font-table and pinned Cosmic/Skrifa source derivation, not live Rust layout telemetry"}


def analyze(root: Path, font: Path | None = None) -> dict:
    images = [Image.open(root / name).convert("RGB") for name in ("rust.png", "moonbit.png")]
    left, right = images
    if left.size != (500, 500) or right.size != left.size:
        raise ValueError("expected unchanged 500x500 screenshots")
    evidence = json.loads((root / "result.json").read_text())
    scene = json.loads((root / "moonbit-scene.json").read_text())
    offsets = evidence["capture_alignment"]["offsets"]
    if offsets["rust"] != offsets["moonbit"]:
        raise ValueError("different capture offsets cannot share a spatial partition")
    dx, dy = offsets["moonbit"]["x"], offsets["moonbit"]["y"]
    frame = scene["frame"]
    if scene["scale"] != 1 or frame["snapshot"]["viewport"] != {"x": 0, "y": 0, "width": 500, "height": 500}:
        raise ValueError("spatial attribution requires the retained 500x500 scale-1 fixture")
    items = frame["snapshot"]["items"]
    styles = {style["id"]: style for style in frame["decorations"]}
    texts = [item for item in items if item["kind"] == "text"]
    quads = [item for item in items if item["kind"] == "quad"]
    viewport = frame["snapshot"]["viewport"]
    roots = [q for q in quads if q["bounds"] == viewport]
    if len(roots) != 1:
        raise ValueError("expected one viewport-filling background quad")
    background = roots[0]
    swatches = [q for q in quads if q is not background]

    def overlaps(x: int, y: int, b: dict, padding: float = 0) -> bool:
        # The one-pixel support margin assigns compositor antialiasing to its
        # primitive; it never excludes a pixel from the exact global comparison.
        return (x + 1 + dx > b["x"] - padding and x + dx < b["x"] + b["width"] + padding
                and y + 1 + dy > b["y"] - padding and y + dy < b["y"] + b["height"] + padding)

    def region(x: int, y: int) -> tuple[str, str | None]:
        for item in texts:
            if overlaps(x, y, item["bounds"], 1):
                return "text", str(item["id"])
        for item in swatches:
            b = item["bounds"]
            if not overlaps(x, y, b, 1):
                continue
            radius = styles[item["id"]]["radius"]
            px, py = x + 0.5 + dx - b["x"], y + 0.5 + dy - b["y"]
            corner_x = min(px, b["width"] - px) < radius
            corner_y = min(py, b["height"] - py) < radius
            if corner_x and corner_y:
                return "swatch_rounded_corner", str(item["id"])
            edge = min(px, py, b["width"] - px, b["height"] - py)
            if edge <= styles[item["id"]]["border_width"] + 1:
                return "swatch_straight_border", str(item["id"])
            return "swatch_interior", str(item["id"])
        b = background["bounds"]
        if overlaps(x, y, b):
            edge = min(x + 0.5 + dx - b["x"], y + 0.5 + dy - b["y"],
                       b["x"] + b["width"] - x - 0.5 - dx,
                       b["y"] + b["height"] - y - 0.5 - dy)
            return ("outer_border" if edge <= 2 else "background"), None
        return "outside_root", None

    names = ["text", "swatch_rounded_corner", "swatch_straight_border", "swatch_interior",
             "outer_border", "background", "outside_root"]
    regions = {name: {"pixels": 0, "changed_pixels": 0, "max_channel_delta": 0,
                      "absolute_rgb_delta_sum": 0, "changed_bounds": None} for name in names}
    per_item = {str(q["id"]): Counter() for q in swatches}
    deltas = Counter()
    bounds = {name: [] for name in names}
    delta = ImageChops.difference(left, right)
    changed = 0
    for y in range(500):
        for x in range(500):
            name, item_id = region(x, y)
            row = regions[name]
            row["pixels"] += 1
            rgb = delta.getpixel((x, y))
            if rgb == (0, 0, 0):
                continue
            changed += 1
            row["changed_pixels"] += 1
            row["max_channel_delta"] = max(row["max_channel_delta"], max(rgb))
            row["absolute_rgb_delta_sum"] += sum(rgb)
            bounds[name].append((x, y))
            deltas[max(rgb)] += 1
            if item_id in per_item:
                per_item[item_id][name] += 1
    for name, points in bounds.items():
        if points:
            regions[name]["changed_bounds"] = [min(x for x, y in points), min(y for x, y in points),
                                                max(x for x, y in points) + 1, max(y for x, y in points) + 1]
    assert sum(row["pixels"] for row in regions.values()) == 250000
    assert sum(row["changed_pixels"] for row in regions.values()) == changed
    measured = evidence.get("raster_comparison")
    if measured and measured["changed_pixels"] != changed:
        raise ValueError("existing exact comparison disagrees with spatial accounting")

    text_bounds = texts[0]["bounds"]
    ink = {}
    bg = background["color"]
    bg_rgb = (bg["red"], bg["green"], bg["blue"])
    for name, im in zip(("rust", "moonbit"), images):
        points = [(x, y) for y in range(500) for x in range(500)
                  if overlaps(x, y, text_bounds) and im.getpixel((x, y)) != bg_rgb]
        ink[name] = ([min(x for x, y in points), min(y for x, y in points),
                      max(x for x, y in points) + 1, max(y for x, y in points) + 1] if points else None)
    shadow_outside = all(background["bounds"][k] == viewport[k] for k in ("x", "y", "width", "height"))
    return {
        "method": "all exact RGB differences partitioned by SceneSnapshot geometry; no tolerance, masking or resampling",
        "status": "different" if changed else "identical", "changed_pixels": changed,
        "total_pixels": 250000, "changed_ratio": changed / 250000,
        "capture_offset": offsets["moonbit"], "regions": regions,
        "swatches": {key: dict(value) for key, value in per_item.items()},
        "text_ink_bounds": ink,
        "canvas_text_metrics": evidence.get("text_metrics"),
        "font_table_metrics": font_metrics(font, scene) if font else None,
        "max_channel_delta_histogram": dict(sorted(deltas.items())),
        "shadow": {"status": "unobservable" if shadow_outside else "unverified",
                   "reason": "root fills the clipped viewport; its external shadow has no visible test area"},
        "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ("rust.png", "moonbit.png", "moonbit-scene.json")},
    }


def intervention(baseline: Path, current: Path) -> dict:
    rust = Image.open(current / "rust.png").convert("RGB")
    original_rust = Image.open(baseline / "rust.png").convert("RGB")
    if rust.size != original_rust.size or ImageChops.difference(rust, original_rust).getbbox():
        raise ValueError("intervention requires an unchanged Rust reference")
    before = Image.open(baseline / "moonbit.png").convert("RGB")
    after = Image.open(current / "moonbit.png").convert("RGB")
    if before.size != rust.size or after.size != rust.size:
        raise ValueError("intervention images differ in size")
    counts = Counter({"restored_equal": 0, "newly_different": 0, "still_different": 0, "always_equal": 0})
    for y in range(rust.height):
        for x in range(rust.width):
            reference = rust.getpixel((x, y))
            old, new = before.getpixel((x, y)) != reference, after.getpixel((x, y)) != reference
            key = "still_different" if old and new else "restored_equal" if old else "newly_different" if new else "always_equal"
            counts[key] += 1
    return {"method": "exact per-pixel before/after classification with unchanged Rust reference",
            **counts, "net_changed_pixel_reduction": counts["restored_equal"] - counts["newly_different"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--font", type=Path, help="actual bundled IBM Plex Sans TTF for baseline derivation")
    parser.add_argument("--baseline", type=Path, help="retained pre-fix evidence for exact intervention accounting")
    args = parser.parse_args()
    report = analyze(args.evidence, args.font)
    if args.baseline:
        report["intervention"] = intervention(args.baseline, args.evidence)
    (args.evidence / "pixel-regions.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"changed_pixels": report["changed_pixels"], "regions": {
        key: row["changed_pixels"] for key, row in report["regions"].items()}, "shadow": report["shadow"]}, indent=2))
