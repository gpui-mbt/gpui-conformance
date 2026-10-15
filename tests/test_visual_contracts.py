"""Synthetic unit guards, never fabricated framework execution evidence."""
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluate_native_images import evaluate
from native_images import exact_comparison, frame_bytes, png_bytes, retained_frames, validate_diff


def frame(width=2, height=1, scale=2):
    return {"width": width, "height": height, "scale": scale, "rgba8": [10, 20, 30, 255] * width * height}


def diff():
    return {"status": "pass", "baselineSize": {"width": 2, "height": 1}, "currentSize": {"width": 2, "height": 1},
            "sizeDelta": {"width": 0, "height": 0}, "diffPixels": 0, "totalPixels": 2, "diffRatio": 0}


class VisualContractTests(unittest.TestCase):
    def test_png_preserves_exact_rgba_bytes_and_dimensions(self):
        source = frame()
        source["rgba8"] = [1, 2, 3, 0, 255, 6, 7, 128]
        png = png_bytes(source)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        offset, compressed = 8, b""
        while offset < len(png):
            length = struct.unpack(">I", png[offset:offset + 4])[0]
            kind = png[offset + 4:offset + 8]
            data = png[offset + 8:offset + 8 + length]
            crc = struct.unpack(">I", png[offset + 8 + length:offset + 12 + length])[0]
            self.assertEqual(crc, zlib.crc32(kind + data))
            if kind == b"IHDR":
                self.assertEqual(struct.unpack(">IIBBBBB", data), (2, 1, 8, 6, 0, 0, 0))
            if kind == b"IDAT":
                compressed += data
            offset += 12 + length
        self.assertEqual(zlib.decompress(compressed), b"\0" + bytes(source["rgba8"]))

    def test_partial_invalid_or_oversized_frames_rejected(self):
        for key, value in (("width", True), ("width", 0), ("width", 16385), ("height", 0),
                           ("scale", 0), ("scale", True), ("scale", math.nan), ("scale", math.inf),
                           ("rgba8", [0] * 7), ("rgba8", [256] * 8), ("rgba8", [True] * 8)):
            value_frame = frame()
            value_frame[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                frame_bytes(value_frame)

    def test_exact_full_frame_check_detects_unsampled_pixel_changes(self):
        first, second = frame(), frame()
        second["rgba8"][4] += 1
        result = exact_comparison(first, second)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["different_pixels"], 1)
        self.assertEqual(exact_comparison(first, first)["status"], "pass")

    def test_scale_and_size_differences_cannot_be_resampled_into_passes(self):
        for second in (frame(scale=1), frame(width=1, height=2)):
            result = exact_comparison(frame(), second)
            self.assertEqual(result["status"], "mismatch")
            self.assertTrue(result["metadata_differences"])
            self.assertIsNone(result["different_pixels"])

    def test_changed_json_is_recognized_even_when_the_cli_exits_normally(self):
        result = diff()
        result.update(status="changed", diffPixels=1, diffRatio=0.5)
        self.assertEqual(validate_diff(result, 2, 1)["status"], "changed")

    def test_bad_status_metrics_dimensions_and_masks_fail_closed(self):
        variants = [dict(status="success"), dict(status="pass", diffPixels=1, diffRatio=.5),
                    dict(totalPixels=100), dict(diffPixels=True), dict(diffRatio=math.nan), dict(diffRatio=.1),
                    dict(baselineSize={"width": 1, "height": 1}), dict(currentSize={"width": 2, "height": True}), dict(sizeDelta={"width": 1, "height": 0}), dict(mask={})]
        for changes in variants:
            value = diff()
            value.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_diff(value, 2, 1)

    def test_raw_json_or_build_only_placeholders_do_not_qualify(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({"schema_version": 1, "runs": {}}))
            (root / "scenarios.json").write_bytes((ROOT / "native_scenarios.json").read_bytes())
            with self.assertRaises((ValueError, KeyError)):
                retained_frames(root)

    def test_missing_toolchain_records_unverified_and_no_new_native_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = evaluate(root / "missing-evidence", root / "missing-toolchain", root / "output")
            self.assertEqual(report["status"], "unverified")
            self.assertEqual(report["native_execution"], "not-rerun")
            self.assertFalse((root / "output/upstream.png").exists())
            with self.assertRaises(ValueError):
                evaluate(root, root, root / "output")

    def test_invalid_per_pixel_threshold_rejected(self):
        for threshold in (True, -.1, 1.1, math.nan, math.inf):
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
                evaluate(directory, directory, Path(directory) / "output", threshold)


if __name__ == "__main__":
    unittest.main()
