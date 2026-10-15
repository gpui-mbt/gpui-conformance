#!/usr/bin/env python3
"""Retain exact screenshot differences without qualifying native conformance."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance

parser = argparse.ArgumentParser()
parser.add_argument("evidence", type=Path)
args = parser.parse_args()
root = args.evidence
left = Image.open(root / "rust.png").convert("RGB")
right = Image.open(root / "moonbit.png").convert("RGB")
if left.size != (500, 500) or right.size != left.size:
    raise ValueError("both screenshots must contain exactly the 500x500 fixture")
delta = ImageChops.difference(left, right)
changed = sum(pixel != (0, 0, 0) for pixel in delta.getdata())
metrics = {"method": "exact RGB pixel difference; no tolerance or masking",
           "width": 500, "height": 500, "changed_pixels": changed,
           "total_pixels": 250000, "changed_ratio": changed / 250000,
           "status": "different" if changed else "identical",
           "native_conformance": "unverified",
           "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                      for name in ["rust.png", "moonbit.png"]}}
ImageEnhance.Brightness(delta).enhance(4).save(root / "difference-x4.png")
report_path = root / "result.json"
report = json.loads(report_path.read_text())
report["raster_comparison"] = metrics
report_path.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(metrics, indent=2))
