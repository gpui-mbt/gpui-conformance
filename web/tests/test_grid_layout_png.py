"""Synthetic decoder rejection cases only, never runtime screenshot evidence."""
import importlib.util
import io
from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import zlib

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/decode_grid_layout_png.py"
spec = importlib.util.spec_from_file_location("grid_layout_png", SCRIPT)
decoder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(decoder)


def chunk(kind, payload=b""):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def png(size=(500, 500), color=(12, 34, 56, 255)):
    output = io.BytesIO()
    Image.new("RGBA", size, color).save(output, format="PNG")
    return output.getvalue()


class GridLayoutPngTests(unittest.TestCase):
    def test_exact_unmodified_original_rgba_transport(self):
        original = png()
        decoded = decoder.decode(original)
        self.assertEqual(decoded[:8], struct.pack(">II", 500, 500))
        self.assertEqual(decoded[8:], bytes([12, 34, 56, 255]) * 500 * 500)
        self.assertEqual(original, png())

    def test_all_requested_widths_and_wrong_height(self):
        for width in [399, 400, 401, 500]:
            self.assertEqual(decoder.decode(png((width, 500)))[:8], struct.pack(">II", width, 500))
        for dimensions in [(398, 500), (402, 500), (500, 499), (800, 1000), (400, 5000)]:
            with self.assertRaises(ValueError):
                decoder.decode(png(dimensions))

    def test_rejects_version_corruption_bounds_animation_and_trailing_bytes(self):
        original = png()
        bad_crc = bytearray(original)
        bad_crc[29] ^= 1
        for data in [b"", b"bad", original[:-1], bytes(bad_crc), original + b"extra",
                     png((10, 10)), original[:-12] + chunk(b"acTL", struct.pack(">II", 2, 0)) + original[-12:],
                     original[:-12] + chunk(b"ABCD") + original[-12:], b"x" * (decoder.MAX_PNG_BYTES + 1)]:
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                decoder.decode(data)
        with patch.object(decoder.PIL, "__version__", "12.0.1"), self.assertRaisesRegex(ValueError, "Pillow 12.0.0"):
            decoder.decode(original)

    def test_rejects_overlong_incomplete_or_invalid_filter_raster(self):
        header = chunk(b"IHDR", struct.pack(">II", 500, 500) + bytes([8, 6, 0, 0, 0]))
        valid = (b"\0" + bytes([1, 2, 3, 255]) * 500) * 500
        for compressed in [zlib.compress(valid + b"extra"), zlib.compress(valid[:-1]),
                           zlib.compress(b"\5" + valid[1:]), zlib.compress(valid) + b"extra"]:
            data = b"\x89PNG\r\n\x1a\n" + header + chunk(b"IDAT", compressed) + chunk(b"IEND")
            with self.assertRaises(ValueError):
                decoder.decode(data)
