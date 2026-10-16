#!/usr/bin/env python3
"""Compare saved text_layout screenshot bytes, preserving every differing pixel."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance

EXPECTED_SIZE = (800, 600)
INPUTS = ("text-layout-rust.png", "text-layout-moonbit.png")
REGIONS = (
    "plain_text", "underline_text", "strikethrough_text", "nowrap_text", "styled_text",
    "box_border", "box_interior", "background", "outside_root",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rect_contains_pixel(x: int, y: int, rect: dict, dx: float, dy: float, pad: float = 0) -> bool:
    # Support belongs to a primitive; nothing is excluded from the global diff.
    return (x + dx + 1 > rect["x"] - pad and x + dx < rect["x"] + rect["width"] + pad
            and y + dy + 1 > rect["y"] - pad and y + dy < rect["y"] + rect["height"] + pad)


def bounding(points: list[tuple[int, int]]) -> list[int] | None:
    if not points:
        return None
    return [min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points) + 1, max(p[1] for p in points) + 1]


def compare(root: Path) -> dict:
    paths = [root / name for name in INPUTS]
    rust, moonbit = [Image.open(path).convert("RGB") for path in paths]
    if rust.size != EXPECTED_SIZE or moonbit.size != EXPECTED_SIZE:
        raise ValueError(f"both original text_layout images must be {EXPECTED_SIZE[0]}x{EXPECTED_SIZE[1]}")
    capture = json.loads((root / "result.json").read_text())
    scene = json.loads((root / "text-layout-moonbit-scene.json").read_text())
    snapshot = scene["frame"]["snapshot"]
    if (scene["metadata"]["id"] != "text_layout" or scene["scale"] != 1
            or snapshot["viewport"] != {"x": 0, "y": 0, "width": 800, "height": 600}):
        raise ValueError("text_layout scene source/viewport/scale mismatch")
    items = snapshot["items"]
    texts = [item for item in items if item["kind"] == "text"]
    boxes = [item for item in items if item["kind"] == "quad" and item["id"] in (21, 22)]
    if (len(texts) != 15 or len(boxes) != 2 or len(snapshot["clip_chains"]) != 2
            or {c["id"] for c in snapshot["clip_chains"]} != {21, 22}):
        raise ValueError("text_layout retained text items/boxes/clips must be complete")
    styles = {s["id"]: s for s in scene["frame"]["text_styles"]}
    if len(styles) != 15:
        raise ValueError("text_layout requires all 15 text styles")
    captures = capture["captures"]
    def offset(name: str) -> dict:
        record = captures["text_layout_" + name]
        b, clip = record["bounds"], record["clip"]
        if (b["width"], b["height"]) != EXPECTED_SIZE or (clip["width"], clip["height"]) != EXPECTED_SIZE:
            raise ValueError("capture is not an unscaled complete 800x600 page clip")
        return {"x": clip["x"] - b["x"], "y": clip["y"] - b["y"]}
    offsets = {name: offset(name) for name in ("rust", "moonbit")}
    if any(abs(offsets["rust"][axis] - offsets["moonbit"][axis]) > 1e-7 for axis in ("x", "y")):
        raise ValueError("unaligned capture origins cannot support raw per-pixel attribution")
    dx, dy = offsets["moonbit"]["x"], offsets["moonbit"]["y"]
    decoration_rows = {}
    def category(item: dict) -> str:
        if item["id"] in (121, 122): return "nowrap_text"
        if item["id"] in (131, 132, 133, 134): return "styled_text"
        return {"underline": "underline_text", "line_through": "strikethrough_text"}.get(
            styles[item["id"]]["decoration"], "plain_text")

    def locate(x: int, y: int) -> tuple[str, str | None]:
        for item in texts:
            if rect_contains_pixel(x, y, item["bounds"], dx, dy, 1):
                return category(item), str(item["id"])
        for item in boxes:
            b = item["bounds"]
            if rect_contains_pixel(x, y, b, dx, dy, 1):
                px, py = x + .5 + dx - b["x"], y + .5 + dy - b["y"]
                if min(px, py, b["width"] - px, b["height"] - py) <= 2:
                    return "box_border", str(item["id"])
                return "box_interior", str(item["id"])
        if 0 <= x + .5 + dx < 800 and 0 <= y + .5 + dy < 600:
            return "background", None
        return "outside_root", None

    regions = {name: {"total_pixels": 0, "changed_pixels": 0, "max_channel_delta": 0,
                      "absolute_rgb_delta_sum": 0, "changed_bounds": None} for name in REGIONS}
    per_text = {str(item["id"]): {"text": item["text"], "category": category(item),
                "scene_bounds": item["bounds"], "changed_pixels": 0,
                "rust_ink_bounds": None, "moonbit_ink_bounds": None} for item in texts}
    per_box = {str(item["id"]): {"border_changed_pixels": 0, "interior_changed_pixels": 0} for item in boxes}
    changed_points = {name: [] for name in REGIONS}
    ink_points = {name: {str(item["id"]): [] for item in texts} for name in ("rust", "moonbit")}
    delta = ImageChops.difference(rust, moonbit)
    ld, rd, dd = rust.load(), moonbit.load(), delta.load()
    changed = 0
    for y in range(600):
        for x in range(800):
            region, item_id = locate(x, y)
            regions[region]["total_pixels"] += 1
            if item_id in per_text:
                for name, pix in (("rust", ld), ("moonbit", rd)):
                    if pix[x, y] != (255, 255, 255):
                        ink_points[name][item_id].append((x, y))
            rgb = dd[x, y]
            if rgb == (0, 0, 0):
                continue
            changed += 1
            row = regions[region]
            row["changed_pixels"] += 1
            row["max_channel_delta"] = max(row["max_channel_delta"], max(rgb))
            row["absolute_rgb_delta_sum"] += sum(rgb)
            changed_points[region].append((x, y))
            if item_id in per_text:
                per_text[item_id]["changed_pixels"] += 1
            if item_id in per_box:
                per_box[item_id]["border_changed_pixels" if region == "box_border" else "interior_changed_pixels"] += 1
    if sum(row["total_pixels"] for row in regions.values()) != 480000 or sum(row["changed_pixels"] for row in regions.values()) != changed:
        raise AssertionError("spatial accounting must include all 480,000 original pixels")
    for name, row in regions.items():
        row["changed_bounds"] = bounding(changed_points[name])
    for item_id, row in per_text.items():
        for side in ("rust", "moonbit"):
            row[side + "_ink_bounds"] = bounding(ink_points[side][item_id])
    for item in texts:
        if category(item) not in ("underline_text", "strikethrough_text"):
            continue
        b = item["bounds"]
        x0 = max(0, math.floor(b["x"] - dx) - 1)
        x1 = min(800, math.ceil(b["x"] + b["width"] - dx) + 1)
        y0 = max(0, math.floor(b["y"] - dy) - 1)
        y1 = min(600, math.ceil(b["y"] + b["height"] - dy) + 2)
        results = {}
        for name, image in (("rust", ld), ("moonbit", rd)):
            dense = []
            for y in range(y0, y1):
                near_black = sum(max(image[x, y]) < 192 for x in range(x0, x1))
                if near_black >= (x1 - x0) * .65:
                    dense.append({"y": y, "near_black_pixels": near_black})
            results[name] = dense
        decoration_rows[str(item["id"])] = results
    hashes = {name: sha256(root / name) for name in (*INPUTS, "text-layout-moonbit-scene.json")}
    result = {
        "fixture": "text_layout", "method": "exact RGB delta of original unscaled 800x600 saved page captures; no tolerance, mask or alignment shift",
        "status": "different" if changed else "identical", "width": 800, "height": 600,
        "total_pixels": 480000, "changed_pixels": changed, "changed_ratio": changed / 480000,
        "regions": regions, "text_items": per_text, "boxes": per_box,
        "decoration_scanlines": decoration_rows,
        "clip_chains": snapshot["clip_chains"],
        "capture_offsets": offsets,
        "environment": capture["environment"],
        "sources": {"upstream": capture["build"]["upstream"],
                    "moonbit": capture["build"]["moonbit"],
                    "lab_revision": capture["build"]["lab_revision"],
                    "runtime_sha256_by_example": capture["build"]["runtime_sha256_by_example"],
                    "font_sha256_by_file": capture["build"]["font_sha256_by_file"],
                    "rust": {"toolchain": capture["build"]["rust"]["toolchain"],
                             "bindings": capture["build"]["rust"]["bindings"],
                             "source_modified": capture["build"]["rust"]["source_modified"]}},
        "sha256": hashes,
        "verification_boundary": {
            "exact_pixel_equality": "failed" if changed else "passed",
            "scene_snapshot": "15 text items and 2 clip chains observed; Rust scene/layout telemetry unavailable",
            "layout_vs_rasterization": "unverified without matched Rust glyph/layout traces",
            "clipping": "clip chains exist; no forced overflow in fixture to prove clipping semantics",
            "other_browsers_native_hardware_gpu": "unverified",
        },
    }
    delta.save(root / "text-layout-difference-raw.png")
    ImageEnhance.Brightness(delta).enhance(4).save(root / "text-layout-difference-x4.png")
    (root / "text-layout-comparison.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    report = compare(args.evidence)
    print(json.dumps({"fixture": report["fixture"], "status": report["status"],
                      "changed_pixels": report["changed_pixels"],
                      "total_pixels": report["total_pixels"],
                      "regions": {k: v["changed_pixels"] for k, v in report["regions"].items()},
                      "sources": report["sources"], "environment": report["environment"]}, indent=2))
