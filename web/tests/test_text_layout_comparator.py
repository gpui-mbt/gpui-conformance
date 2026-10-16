"""What: assert all raw pixels, region accounting, provenance and input guards."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

SRC = Path(__file__).resolve().parents[1] / "scripts/compare_text_layout.py"
spec = importlib.util.spec_from_file_location("text_comparison", SRC)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TextLayoutComparisonTests(unittest.TestCase):
    def create_inputs(self, root: Path):
        Image.new("RGB", (800, 600), "white").save(root / "text-layout-rust.png")
        Image.new("RGB", (800, 600), "white").save(root / "text-layout-moonbit.png")
        names = ["plain"] * 3 + ["underline"] * 3 + ["line_through"] * 3 + ["none"] * 6
        items = [{"kind": "quad", "id": i, "bounds": {"x": 16 if i == 21 else 656,
                  "y": 322, "width": 400 if i == 21 else 128, "height": 36}} for i in (21, 22)]
        ids = [102,103,104,105,106,107,108,109,110,121,122,131,132,133,134]
        items += [{"id": id, "kind": "text", "bounds": {"x": 16 + (n % 3) * 230,
                   "y": 16 + n * 27, "width": 50, "height": 26}, "text": str(id)}
                  for n, id in enumerate(ids)]
        scene = {"metadata": {"id": "text_layout"}, "scale": 1, "frame": {
            "snapshot": {"viewport": {"x":0,"y":0,"width":800,"height":600},
                         "items": items, "clip_chains": [{"id":21,"rects":[]},{"id":22,"rects":[]}]},
            "text_styles": [{"id": id, "decoration": name} for id, name in zip(ids, names)]}}
        (root / "text-layout-moonbit-scene.json").write_text(json.dumps(scene))
        (root / "result.json").write_text(json.dumps({
            "captures": {"text_layout_rust": {"bounds": {"x":1,"y":0.359375,"width":800,"height":600},
                          "clip": {"x":1,"y":1,"width":800,"height":600}},
                         "text_layout_moonbit": {"bounds": {"x":1000,"y":0.359375,"width":800,"height":600},
                          "clip": {"x":1000,"y":1,"width":800,"height":600}}},
            "environment": {"browser": "synthetic"},
            "build": {"upstream": {"revision":"upstream"},"moonbit":{"revision":"port"},
                      "lab_revision":"fixture","runtime_sha256_by_example":{},"font_sha256_by_file":{},
                      "rust":{"toolchain":"test","bindings":"test","source_modified":False}}
        }))

    def test_counts_all_pixels_including_background_and_borders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inputs(root)
            image = Image.open(root / "text-layout-moonbit.png").convert("RGB")
            image.putpixel((200, 50), (254, 255, 255))
            image.putpixel((16, 322), (0, 0, 255))
            image.putpixel((16, 22), (0, 0, 0))
            image.save(root / "text-layout-moonbit.png")
            report = module.compare(root)
            self.assertEqual(report["changed_pixels"], 3)
            self.assertEqual(sum(x["total_pixels"] for x in report["regions"].values()), 480000)
            self.assertEqual(sum(x["changed_pixels"] for x in report["regions"].values()), 3)
            self.assertEqual(report["regions"]["background"]["changed_pixels"], 1)
            self.assertEqual(report["regions"]["box_border"]["changed_pixels"], 1)
            self.assertEqual(report["regions"]["plain_text"]["changed_pixels"], 1)
            self.assertEqual(report["status"], "different")
            self.assertTrue((root / "text-layout-difference-raw.png").exists())
            self.assertEqual(json.loads((root / "text-layout-comparison.json").read_text())["changed_pixels"], 3)
            self.assertEqual(report["environment"]["browser"], "synthetic")

    def test_decoration_scan_uses_scene_to_image_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inputs(root)
            record = json.loads((root / "result.json").read_text())
            for side in ("rust", "moonbit"):
                capture = record["captures"]["text_layout_" + side]
                for axis in ("x", "y"):
                    capture["clip"][axis] = capture["bounds"][axis] + 10
                image = Image.open(root / ("text-layout-" + side + ".png")).convert("RGB")
                # Scene item 105 starts at (16, 97); capture translation maps
                # this dense scene row (16..65, 100) to (6..55, 90).
                for x in range(6, 56):
                    image.putpixel((x, 90), (0, 0, 0))
                image.save(root / ("text-layout-" + side + ".png"))
            (root / "result.json").write_text(json.dumps(record))
            report = module.compare(root)
            self.assertEqual(report["changed_pixels"], 0)
            for side in ("rust", "moonbit"):
                self.assertEqual(report["decoration_scanlines"]["105"][side],
                                 [{"y": 90, "near_black_pixels": 50}])

    def test_exact_equality_is_zero_and_does_not_infer_layout_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inputs(root)
            report = module.compare(root)
            self.assertEqual(report["status"], "identical")
            self.assertEqual(report["changed_pixels"], 0)
            self.assertIn("unverified", report["verification_boundary"]["layout_vs_rasterization"])

    def test_rejects_wrong_image_size_and_capture_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.create_inputs(root)
            Image.new("RGB", (500, 500), "white").save(root / "text-layout-rust.png")
            with self.assertRaisesRegex(ValueError, "800x600"):
                module.compare(root)
            Image.new("RGB", (800, 600), "white").save(root / "text-layout-rust.png")
            record = json.loads((root / "result.json").read_text())
            record["captures"]["text_layout_rust"]["clip"]["y"] += 1
            (root / "result.json").write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "unaligned"):
                module.compare(root)


if __name__ == "__main__":
    unittest.main()
