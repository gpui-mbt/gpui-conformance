"""Synthetic PNG decoder corruption sensitivity; not GPU evidence."""
import io
from pathlib import Path
import sys
import unittest
import PIL
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from decode_gradient_png import decode

class GradientPngTests(unittest.TestCase):
    def png(self, size):
        out = io.BytesIO()
        Image.new('RGB', size, (255, 0, 0)).save(out, format='PNG')
        return out.getvalue()

    @unittest.skipUnless(PIL.__version__ == "12.0.0", "Pinned Pillow 12.0.0 decoder runs in CI; no local version substitution")
    def test_both_actual_profile_sizes(self):
        for size in [(960, 600), (600, 960)]:
            self.assertEqual(len(decode(self.png(size))), 8 + size[0] * size[1] * 4)

    @unittest.skipUnless(PIL.__version__ == "12.0.0", "Pinned Pillow 12.0.0 decoder runs in CI; no local version substitution")
    def test_corruption_and_wrong_profile(self):
        good = self.png((960, 600))
        corrupt = bytearray(good)
        corrupt[len(corrupt) // 2] ^= 1
        for data in [bytes(corrupt), good[:-1], good + b'bad', self.png((750, 600)), b'not PNG']:
            with self.assertRaises(ValueError):
                decode(data)

if __name__ == '__main__':
    unittest.main()
