"""Independent Python source-math fixtures; these do NOT execute MoonBit/JS.

Run with PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests
    -p test_measured_anchor_metrics.py

The numeric fixtures below follow pinned upstream source, not recorded bounds.
Static assertions check adapter wiring and refusal guards, but do not establish
MoonBit compilation, FFI linkage, real GPUI output, or end-to-end equivalence.
"""

from __future__ import annotations

import math
from pathlib import Path
import struct
import unittest


REVISION = "5a5fbe79917971a4d52a96b6ddb04da198a5012e"
SOURCE = (Path(__file__).resolve().parents[1] / "adapters" /
          "measured_anchor_moonbit" / "noop_metrics.mbt")


def f32(value: float) -> float:
    return struct.unpack("!f", struct.pack("!f", value))[0]


def finite_number(value: object) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def validate(text: str, font: float, width: float, scale: float) -> None:
    if not isinstance(text, str) or any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        raise ValueError("Rust UTF-8 strings require valid Unicode scalars")
    if len(text.encode("utf-16-le")) // 2 > 4096:
        raise ValueError("bounded text length")
    if not finite_number(font) or font not in (14, 16):
        raise ValueError("authored font at rem=16")
    if (not finite_number(width) or width < 0 or width > 16384
            or (width != 0 and width < 1 / 65536)):
        raise ValueError("authored width outside diagnostic scope")
    if not finite_number(scale) or not 1 / 16 <= scale <= 8:
        raise ValueError("device scale outside diagnostic scope")


def source_is_word(c: str) -> bool:
    """line_wrapper.rs:501-540, explicit ranges rather than Unicode categories."""
    n = ord(c)
    ranges = ((0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A),
              (0xC0, 0xFF), (0x100, 0x17F), (0x180, 0x24F),
              (0x400, 0x4FF), (0x1E00, 0x1EFF), (0x300, 0x36F),
              (0x980, 0x9FF))
    punctuation = "-_.'’‘$%@#^~,=:;!)]}\"”»…⋯\u202f\u00a0\u2011"
    return any(lo <= n <= hi for lo, hi in ranges) or c in punctuation


def source_snap(value: float, scale: float) -> float:
    """util.rs:130-141 and window.rs:3186-3187, every operation binary32."""
    physical = f32(f32(value) * f32(scale))
    rounded = math.copysign(math.ceil(f32(abs(physical) - 0.5)), physical)
    return f32(rounded / f32(scale))


def source_shape(line: str, font: float) -> tuple[list[float], float]:
    """platform.rs:1605-1636, add each scalar's UTF-16 advance repeatedly."""
    em = f32(f32(f32(font) * 600) / 1000)
    positions = [f32(0)]
    for c in line:
        advance = f32(em * 2) if ord(c) > 0xFFFF else em
        positions.append(f32(positions[-1] + advance))
    return positions[:-1], positions[-1]


def source_wrap(line: str, positions: list[float], total: float,
                width: float | None) -> list[int]:
    """line_layout.rs:193-271, including strict overflow and candidate reuse."""
    if width is None:
        return []
    first = None
    candidate = None
    candidate_x = f32(0)
    boundary = 0
    boundary_x = f32(0)
    previous = "\0"
    result = []
    for i, c in enumerate(line):
        if c != " " and first is not None:
            if not source_is_word(c) or previous == " ":
                candidate, candidate_x = i, positions[i]
        if c != " " and first is None:
            first = i
        next_x = positions[i + 1] if i + 1 < len(line) else total
        if f32(next_x - boundary_x) > width and i > boundary:
            if candidate is None:
                boundary, boundary_x = i, positions[i]
            else:
                boundary, boundary_x = candidate, candidate_x
                candidate = None
            result.append(boundary)
        previous = c
    return result


def source_metrics(text: str, font: float, width: float = 0,
                   scale: float = 1) -> dict:
    validate(text, font, width, scale)
    font, scale = f32(font), f32(scale)
    wrap = None if width == 0 else f32(width)
    line_height = source_snap(f32(font * f32(1.618034)), scale)
    result_width, result_height = f32(0), f32(0)
    lines = []
    for line in text.split("\n"):
        positions, total = source_shape(line, font)
        boundaries = source_wrap(line, positions, total, wrap)
        measured = total if wrap is None else min(wrap, total)
        height = f32(line_height * (len(boundaries) + 1))
        result_width = f32(math.ceil(max(result_width, measured)))
        result_height = f32(result_height + height)
        lines.append({"unwrapped_width": total, "wrap_scalar_indices": boundaries,
                      "wrap_utf8_indices": [len(line[:i].encode("utf-8"))
                                            for i in boundaries],
                      "height": height})
    return {"width": result_width, "height": result_height,
            "line_height": line_height, "lines": lines}


class SourceMathFixtures(unittest.TestCase):
    def test_source_derived_em_advance_and_repeated_accumulation(self):
        self.assertEqual(source_shape("m", 16)[1], 9.600000381469727)
        self.assertEqual(source_shape("m", 14)[1], 8.399999618530273)
        repeated = source_shape("x" * 40, 16)[1]
        self.assertEqual(repeated, 384.0001525878906)
        self.assertEqual(source_metrics("x" * 40, 16)["width"], 385)
        self.assertEqual(f32(source_shape("m", 16)[1] * 40), 384)

    def test_authored_trigger_literals(self):
        self.assertEqual(source_metrics("Open Popover", 16)["width"], 116)
        self.assertEqual(source_metrics("Child Popover", 14)["width"], 110)

    def test_authored_popover_literals_and_content_space(self):
        first = ("This is first level Popover, we can use deferred to render it "
                 "in a floating layer.\nClick outside to close.")
        second = "This is second level Popover with nested deferred!"
        # Authored w_96, p_3, border_1 at rem16, snapped separately. No bounds input.
        for scale, expected_height in [(1, 69), (1.25, 67.19999694824219),
                                       (1.5, 68), (2, 67.5)]:
            authored_content = (source_snap(96 / 4 * 16, scale)
                                - 2 * source_snap(3 / 4 * 16, scale)
                                - 2 * max(source_snap(1, scale), 1 / scale))
            result = source_metrics(first, 14, authored_content, scale)
            self.assertEqual(result["height"], expected_height)
            self.assertEqual(result["width"], math.ceil(f32(authored_content)))
            self.assertEqual([line["wrap_scalar_indices"] for line in result["lines"]],
                             [[40], []])
        self.assertEqual(source_metrics(second, 14)["width"], 420)

    def test_utf16_advance_is_per_scalar_not_grapheme(self):
        self.assertEqual(source_metrics("😀a", 16)["width"], 29)
        self.assertEqual(source_metrics("e\u0301", 16)["width"], 20)
        self.assertEqual(source_shape("😀a", 16)[0], [0, 19.200000762939453])
        line = source_metrics("😀😀", 16, 20)["lines"][0]
        self.assertEqual(line["wrap_scalar_indices"], [1])
        self.assertEqual(line["wrap_utf8_indices"], [4])

    def test_literal_newline_preserves_empty_and_trailing_lines(self):
        empty = source_metrics("", 16)
        self.assertEqual((empty["width"], empty["height"], len(empty["lines"])),
                         (0, 26, 1))
        split = source_metrics("a\n\nb\n", 16)
        self.assertEqual((split["width"], split["height"], len(split["lines"])),
                         (10, 104, 4))
        # CR is an ordinary glyph in the pinned literal-LF split.
        self.assertEqual(source_metrics("a\r\n", 16)["width"], 20)

    def test_strict_wrap_threshold(self):
        exactly_two = source_shape("ab", 16)[1]
        one_ulp_less = struct.unpack("!f", struct.pack("!I",
            struct.unpack("!I", struct.pack("!f", exactly_two))[0] - 1))[0]
        self.assertEqual(source_metrics("ab", 16, exactly_two)["lines"][0]
                         ["wrap_scalar_indices"], [])
        self.assertEqual(source_metrics("ab", 16, one_ulp_less)["lines"][0]
                         ["wrap_scalar_indices"], [1])

    def test_word_boundary_preference_and_long_word_fallback(self):
        self.assertEqual(source_metrics("a bc", 16, 30)["lines"][0]
                         ["wrap_scalar_indices"], [2])
        self.assertEqual(source_metrics("abcd", 16, 20)["lines"][0]
                         ["wrap_scalar_indices"], [2])
        self.assertEqual(source_metrics("a/b", 16, 20)["lines"][0]
                         ["wrap_scalar_indices"], [1])

    def test_width_uses_wrap_limit_not_longest_wrapped_row(self):
        result = source_metrics("a bc", 16, 30)
        self.assertEqual(result["width"], 30)
        self.assertEqual(result["height"], 52)
        narrow = source_metrics("x", 16, 0.25)
        self.assertEqual((narrow["width"], narrow["height"]), (1, 26))
        self.assertEqual(narrow["lines"][0]["wrap_scalar_indices"], [])

    def test_word_class_exact_ranges_and_punctuation(self):
        for c in "Az09é÷ĀɏЖở\u0301ক-_.'’‘$%@#^~,=:;!)]}\"”»…⋯\u202f\u00a0\u2011":
            with self.subTest(c=c):
                self.assertTrue(source_is_word(c))
        for c in " /?&\\([<{你好한😀\t\r":
            with self.subTest(c=c):
                self.assertFalse(source_is_word(c))

    def test_source_phi_device_scale_table(self):
        expected = {
            (16, 1): 26.0, (16, 1.25): 25.600000381469727,
            (16, 1.5): 26.0, (16, 2): 26.0,
            (14, 1): 23.0, (14, 1.25): 22.399999618530273,
            (14, 1.5): 22.66666603088379, (14, 2): 22.5,
        }
        for (font, scale), height in expected.items():
            with self.subTest(font=font, scale=scale):
                self.assertEqual(source_metrics("x", font, 0, scale)["line_height"], height)

    def test_half_ties_toward_zero_and_fractional_scale(self):
        self.assertEqual(source_snap(2.5, 1), 2)
        self.assertEqual(source_snap(3.5, 1), 3)
        self.assertEqual(source_snap(-2.5, 1), -2)
        self.assertEqual(source_snap(1.25, 2), 1)

    def test_multiline_sum_is_binary32_per_physical_line(self):
        result = source_metrics("\n".join(["a"] * 7), 14, 0, 1.25)
        height = f32(0)
        for _ in range(7):
            height = f32(height + f32(22.4))
        self.assertEqual(result["height"], height)
        self.assertNotEqual(result["height"], f32(7 * f32(22.4)))

    def test_refusal_boundaries(self):
        invalid = [
            ("x", 12, 0, 1), ("x", 14, -1, 1), ("x", 14, math.nan, 1),
            ("x", 14, 16385, 1), ("x", 14, 1 / 131072, 1),
            ("x", 14, 0, 0), ("x", 14, 0, 1 / 32), ("x", 14, 0, 9),
            ("x", 14, 0, math.inf), ("x", math.nan, 0, 1),
            ("x" * 4097, 14, 0, 1), ("😀" * 2049, 14, 0, 1),
            ("\ud800", 14, 0, 1), ("\udc00", 14, 0, 1),
            ("\ud800x", 14, 0, 1), (None, 14, 0, 1),
        ]
        for args in invalid:
            with self.subTest(args=repr(args)[:100]):
                with self.assertRaises(ValueError):
                    source_metrics(*args)
        for args in [("😀" * 2048, 14, 0, 1), ("x", 16, 16384, 8),
                     ("x", 14, 1 / 65536, 1 / 16)]:
            source_metrics(*args)


class AdapterStaticContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")
        cls.ffi = "\n".join(line.split("#|", 1)[1]
                             for line in cls.source.splitlines() if "#|" in line)

    def test_api_and_source_qualification(self):
        for token in ["pub fn measured_text(", "pub fn measured_text_metadata(",
                      "-> @primitives.Size", REVISION,
                      "f0bf1211114e4522a5310067e2549ba2727a4c1d",
                      "ca821bbbb43a6fd17dd363b15f45165f86289b10",
                      "source-derived-NoopTextSystem-only"]:
            self.assertIn(token, self.source)
        self.assertIn("let metadata = noop_metrics_source_json(text, font_size, available_width, scale)",
                      self.source)
        self.assertIn("noop_metrics_width(metadata), noop_metrics_height(metadata)", self.source)

    def test_binary32_and_wrapping_wiring(self):
        for token in ["const f32 = Math.fround", "f32(f32(font * 600) / 1000)",
                      "f32(1.618034)", "f32(font * phi)",
                      "Math.ceil(f32(Math.abs(scaledLineHeight) - 0.5))",
                      "f32(roundedDeviceHeight / deviceScale)",
                      'text.split("\\n")', "Array.from(literalLine)",
                      "ch.length === 2 ? f32(emWidth * 2) : emWidth",
                      "position = f32(position + advance)",
                      "const rowWidth = f32(nextX - lastBoundaryX)",
                      "rowWidth > wrapWidth && i > lastBoundary",
                      "Math.min(wrapWidth, position)",
                      "width = f32(Math.ceil(Math.max(width, wrappedWidth)))",
                      "height = f32(height + lineSizeHeight)"]:
            self.assertIn(token, self.ffi)

    def test_refusals_are_wired_before_measurement(self):
        before_math = self.ffi.split("const f32 = Math.fround", 1)[0]
        for token in ["text.length > 4096", "fontSize !== 14 && fontSize !== 16",
                      "!Number.isFinite(availableWidth)", "availableWidth < 0",
                      "availableWidth > 16384", "availableWidth < 1 / 65536",
                      "!Number.isFinite(scale)", "scale < 1 / 16 || scale > 8",
                      "0xD800", "0xDBFF", "0xDC00", "0xDFFF",
                      "lone UTF-16 high surrogate", "lone UTF-16 low surrogate"]:
            self.assertIn(token, before_math)
        self.assertIn("availableWidth === 0 ? null : f32(availableWidth)", self.ffi)

    def test_no_observed_geometry_or_host_inputs(self):
        for token in ["process.", "require(", "fetch(", "readFile", "trace.",
                      "observed_bounds", "scenario_id", "GPUI_SCENARIOS"]:
            self.assertNotIn(token, self.ffi)
        # Derived line heights must never be substituted into the adapter.
        self.assertNotRegex(self.ffi, r"lineHeight\s*=\s*(?:26|23)(?:[.;,\s]|$)")
        self.assertNotIn("Math.round", self.ffi)


if __name__ == "__main__":
    unittest.main()
