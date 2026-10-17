#!/usr/bin/env python3
"""Strictly decode original bounded gradient diagnostic viewport screenshots, without rewriting PNGs."""
import io
import struct
import sys
import zlib

import PIL
from PIL import Image

PILLOW_VERSION = "12.0.0"
MAX_PNG_BYTES = 8 * 1024 * 1024


def decode(data: bytes) -> bytes:
    if PIL.__version__ != PILLOW_VERSION:
        raise ValueError(f"Pillow {PILLOW_VERSION} required, found {PIL.__version__}")
    if not data or len(data) > MAX_PNG_BYTES or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Original PNG must be nonempty, valid and at most 8 MiB")
    offset, kinds, idat_finished = 8, [], False
    compressed = bytearray()
    channels = 0
    width = height = 0
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data) or not all(65 <= byte <= 90 or 97 <= byte <= 122 for byte in kind):
            raise ValueError("Invalid PNG chunk bounds or name")
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise ValueError("PNG chunk CRC mismatch")
        if kind in {b"acTL", b"fcTL", b"fdAT"}:
            raise ValueError("Animated PNG is not an original screenshot")
        if kind[0] < 97 and kind not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
            raise ValueError("Unknown critical PNG chunk")
        if not kinds and (kind != b"IHDR" or length != 13):
            raise ValueError("PNG must begin with its unique IHDR")
        if kind == b"IHDR":
            width, height = struct.unpack_from(">II", payload)
            if kinds or width != 1000 or height != 900:
                raise ValueError("Original full-viewport 1000x900 PNG required")
            if payload[8:] not in {bytes([8, 2, 0, 0, 0]), bytes([8, 6, 0, 0, 0])}:
                raise ValueError("Original noninterlaced RGB/RGBA8 screenshot required")
            channels = 3 if payload[9] == 2 else 4
        if kind == b"PLTE" and (b"PLTE" in kinds or b"IDAT" in kinds):
            raise ValueError("Duplicate or late PNG palette")
        if kind == b"IDAT":
            if idat_finished:
                raise ValueError("Noncontiguous PNG image chunks")
            compressed.extend(payload)
        if b"IDAT" in kinds and kind != b"IDAT":
            idat_finished = True
        kinds.append(kind)
        if kind == b"IEND":
            if length or b"IDAT" not in kinds or end != len(data):
                raise ValueError("Incomplete PNG or trailing bytes")
            break
        offset = end
    if not kinds or kinds[-1] != b"IEND":
        raise ValueError("Missing PNG end chunk")
    stride = 1 + width * channels
    decompressor = zlib.decompressobj()
    raster = decompressor.decompress(compressed, height * stride + 1)
    if (len(raster) != height * stride or not decompressor.eof
            or decompressor.unused_data or decompressor.unconsumed_tail):
        raise ValueError("Incomplete or overlong PNG raster stream")
    if any(raster[row * stride] > 4 for row in range(height)):
        raise ValueError("Invalid PNG row filter")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "PNG" or image.size != (width, height) or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Original full-viewport single-frame PNG required")
        image.load()
        rgba = image.convert("RGBA").tobytes()
    if len(rgba) != width * height * 4:
        raise ValueError("Incomplete decoded RGBA")
    return struct.pack(">II", width, height) + rgba


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(decode(sys.stdin.buffer.read(MAX_PNG_BYTES + 1)))
    except Exception as error:
        print(f"PNG decode failed: {error}", file=sys.stderr)
        sys.exit(1)
