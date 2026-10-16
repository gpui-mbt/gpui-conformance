"""Saved, unmodified pixels remain fully accounted for, including regressions."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from PIL import Image

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pixel_regions", WEB / "scripts/analyze_screenshots.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PixelRegionTests(unittest.TestCase):
    def test_before_after_accounting_rejects_a_changed_rust_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.open(WEB / "evidence/20261015/rust.png").convert("RGB")
            image.putpixel((50, 50), (1, 2, 3))
            image.save(root / "rust.png")
            with self.assertRaisesRegex(ValueError, "unchanged Rust reference"):
                module.intervention(WEB / "evidence/20261015", root)

    def test_retained_baseline_accounts_for_all_1641_pixels(self):
        result = module.analyze(WEB / "evidence/20261015")
        self.assertEqual(result["changed_pixels"], 1641)
        self.assertEqual({key: value["changed_pixels"] for key, value in result["regions"].items()}, {
            "text": 856, "swatch_rounded_corner": 377, "swatch_straight_border": 408,
            "swatch_interior": 0, "outer_border": 0, "background": 0, "outside_root": 0})
        self.assertEqual(result["shadow"]["status"], "unobservable")
        self.assertEqual(sum(r["pixels"] for r in result["regions"].values()), 250000)

    def test_unexpected_background_and_fill_changes_are_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ["rust.png", "moonbit.png", "result.json", "moonbit-scene.json"]:
                shutil.copy2(WEB / "evidence/20261015" / name, root / name)
            image = Image.open(root / "moonbit.png").convert("RGB")
            for point in [(50, 50), (150, 272)]:
                image.putpixel(point, (1, 2, 3))
            image.save(root / "moonbit.png")
            report = json.loads((root / "result.json").read_text())
            report.pop("raster_comparison")
            (root / "result.json").write_text(json.dumps(report))
            result = module.analyze(root)
            self.assertEqual(result["changed_pixels"], 1643)
            self.assertEqual(result["regions"]["background"]["changed_pixels"], 1)
            self.assertEqual(result["regions"]["swatch_interior"]["changed_pixels"], 1)


if __name__ == "__main__":
    unittest.main()
