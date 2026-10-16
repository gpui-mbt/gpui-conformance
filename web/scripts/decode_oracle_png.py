#!/usr/bin/env python3
"""Decode untouched 800x600 PNG bytes to a bounded dimensions+RGBA stream."""
import io
import struct
import sys

import PIL
from PIL import Image

PILLOW_VERSION = "12.0.0"
MAX_PNG_BYTES = 8 * 1024 * 1024


def decode(data: bytes) -> bytes:
    if PIL.__version__ != PILLOW_VERSION:
        raise ValueError(f"Pillow {PILLOW_VERSION} required, found {PIL.__version__}")
    if not data or len(data) > MAX_PNG_BYTES:
        raise ValueError("PNG input must be nonempty and at most 8 MiB")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or image.size != (800, 600):
            raise ValueError("Original full-viewport 800x600 PNG required")
        if getattr(image, "n_frames", 1) != 1:
            raise ValueError("Animated PNG is not a screenshot")
        image.load()
        rgba = image.convert("RGBA").tobytes()
    if len(rgba) != 800 * 600 * 4:
        raise ValueError("Incomplete decoded RGBA")
    return struct.pack(">II", 800, 600) + rgba


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(decode(sys.stdin.buffer.read(MAX_PNG_BYTES + 1)))
    except Exception as error:
        print(f"PNG decode failed: {error}", file=sys.stderr)
        sys.exit(1)
