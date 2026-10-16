"""Portable tests: describe what native evidence means; never emulate GPU proof."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from native_lab.launcher import (
    events, has_event, inspect_images, main, point_color, window_rows,
)


class NativeLabContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pixels = {
            "width": 256, "height": 192, "rect": [32, 32, 64, 48],
            "background": [0, 0, 0, 255], "color": [255, 0, 0, 255],
            "points": [[8, 8], [40, 40], [120, 100]],
        }

    def tearDown(self):
        self.temp.cleanup()

    def frame(self, path, color=(255, 0, 0), size=(256, 192)):
        image = Image.new("RGB", size, (0, 0, 0))
        ImageDraw.Draw(image).rectangle((32, 32, 95, 79), fill=color)
        image.save(path)

    def test_expected_samples_use_shared_scene_not_reported_answers(self):
        self.assertEqual(point_color(self.pixels, 8, 8), (0, 0, 0))
        self.assertEqual(point_color(self.pixels, 40, 40), (255, 0, 0))
        self.assertEqual(point_color(self.pixels, 120, 100), (0, 0, 0))

    def test_identical_retained_pixels_pass_and_retain_frame_hashes(self):
        a, b = self.root / "rust.png", self.root / "moonbit.png"
        self.frame(a)
        self.frame(b)
        result = inspect_images({"upstream": a, "moonbit": b}, self.pixels, 1.0)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["different_pixels"], 0)
        self.assertTrue(result["captures"]["moonbit"]["fixture_match"])
        self.assertEqual(len(result["captures"]["upstream"]["sha256"]), 64)

    def test_negative_control_is_mismatch_even_when_both_images_valid(self):
        a, b = self.root / "rust.png", self.root / "moonbit.png"
        self.frame(a)
        self.frame(b, color=(0, 0, 255))
        result = inspect_images({"upstream": a, "moonbit": b}, self.pixels, 1.0)
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["different_pixels"], 64 * 48)
        self.assertFalse(result["same_sample_colors"])

    def test_dimensions_cannot_pass_by_matching_sample_colors(self):
        a, b = self.root / "rust.png", self.root / "moonbit.png"
        self.frame(a)
        self.frame(b, size=(320, 224))
        result = inspect_images({"upstream": a, "moonbit": b}, self.pixels, 1.0)
        self.assertEqual(result["status"], "mismatch")
        self.assertIsNone(result["different_pixels"])
        self.assertFalse(result["captures"]["moonbit"]["fixture_match"])

    def test_events_are_bound_to_run_token_and_implementation(self):
        logfile = self.root / "native.stdout"
        valid = {"protocol": 1, "implementation": "moonbit", "run_token": "one",
                 "event": "frame_ready", "width": 256, "height": 192, "scale": 1}
        wrong = {**valid, "run_token": "another"}
        logfile.write_text("noise\n" + "".join(
            "GPUI_NATIVE_LAB " + json.dumps(obj) + "\n" for obj in [wrong, valid]
        ))
        self.assertEqual(events(logfile, "moonbit", "one"), [valid])
        self.assertFalse(events(logfile, "upstream", "one"))
        self.assertTrue(has_event(events(logfile, "moonbit", "one"), "frame_ready", 256, 192, 1))
        self.assertFalse(has_event([valid], "frame_ready", 256, 192, 2))

    def test_missing_frame_does_not_count_as_observed(self):
        self.assertFalse(has_event([], "frame_ready", 256, 192, 1))
        self.assertFalse(has_event(
            [{"event": "opened", "width": 256, "height": 192, "scale": 1}],
            "frame_ready", 256, 192, 1,
        ))

    def test_x11_window_mapping_uses_owned_pid(self):
        output = ("0x00abc 0 1234 40 40 256 192 desktop Rust\n"
                  "0x00def 0 5678 336 40 256 192 desktop Weston\n")
        with patch("native_lab.launcher.subprocess.run") as run:
            run.return_value.stdout = output
            rows = window_rows()
        self.assertEqual([r["pid"] for r in rows], [1234, 5678])
        self.assertEqual(rows[1]["width"], 256)

    def test_build_only_must_report_unverified_without_window_launch(self):
        out = self.root / "evidence"
        with patch("native_lab.launcher.build_pair", return_value={}):
            self.assertEqual(main(["--output", str(out), "--build-only"]), 2)
        report = json.loads((out / "comparison.json").read_text())
        self.assertEqual(report["status"], "unverified")
        self.assertNotIn("pixels", report)
        self.assertIn("build-only", report["reasons"][0])


if __name__ == "__main__":
    unittest.main()
