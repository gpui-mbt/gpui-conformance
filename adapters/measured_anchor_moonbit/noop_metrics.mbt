// Source-only diagnostic adapter. No native font shaping or runtime parity is
// claimed. All binary32 emulation is intentionally confined to this adapter;
// the public portable core remains Double-based.
//
// Pinned upstream: zed-industries/zed@5a5fbe79917971a4d52a96b6ddb04da198a5012e
// crates/gpui/src/platform.rs:1536-1653, NoopTextSystem: glyph id is UTF-16
// scalar length, advance is 600 * glyph id, units_per_em is 1000. layout_line
// computes em_width=(font_size*600)/1000, then repeatedly adds each advance.
// crates/gpui/src/text_system/line_layout.rs:193-271,305-317
//   blob f0bf1211114e4522a5310067e2549ba2727a4c1d
// crates/gpui/src/text_system/line_wrapper.rs:499-540, is_word_char only
//   blob ca821bbbb43a6fd17dd363b15f45165f86289b10
// crates/gpui/src/text_system.rs:750-878: split on literal LF, including empty
// trailing lines. No truncation, clamp, mixed fonts, or native shaping here.
// crates/gpui/src/elements/text.rs:638-780: snap line height, sum line heights,
// and ceil the maximum of each WrappedLineLayout::width().
// crates/gpui/src/style.rs:494: default line_height: phi().
// crates/gpui/src/geometry.rs:3508-3514,3722-3723: phi relative(1.618_034)
//   blob 1c87031c7aad8df10827152debe6f74672d7c07f
// crates/gpui/src/window.rs:3186-3187: Window::pixel_snap.
// crates/gpui/src/util.rs:128-141: f32 round-half-toward-zero
//   blob 13ee752dadf00ac0f4f2e450bb908ba544550943
//
// Contract: literal text; font_size 14 or 16 logical px (authored rem=16);
// available_width is authored content space, never a measured/observed bound.
// available_width == 0 explicitly means unbounded, not a zero-width constraint.
// Bounded diagnostic inputs: <=4096 UTF-16 units, finite positive scale in
// [1/16,8], positive widths in [1/65536,16384]. Invalid input throws before any
// metrics are returned. Lone UTF-16 surrogates are refused (Rust str is UTF-8).
// Pure JS FFI supplies binary32 arithmetic only: no environment, file, network,
// process, trace, scenario ID, or observed geometry is read by this module.

extern "js" fn noop_metrics_source_json(
  text : String,
  font_size : Double,
  available_width : Double,
  scale : Double,
) -> String =
  #| (text, fontSize, availableWidth, scale) => {
  #|   if (typeof text !== "string" || text.length > 4096)
  #|     throw new RangeError("Noop metrics: text must have at most 4096 UTF-16 units");
  #|   if (!Number.isFinite(fontSize) || (fontSize !== 14 && fontSize !== 16))
  #|     throw new RangeError("Noop metrics: only authored 14px/16px fonts at rem=16");
  #|   if (!Number.isFinite(availableWidth) || availableWidth < 0 || availableWidth > 16384 ||
  #|       (availableWidth !== 0 && availableWidth < 1 / 65536))
  #|     throw new RangeError("Noop metrics: unsupported authored content width");
  #|   if (!Number.isFinite(scale) || scale < 1 / 16 || scale > 8)
  #|     throw new RangeError("Noop metrics: unsupported positive device scale");
  #|   for (let i = 0; i < text.length; i++) {
  #|     const unit = text.charCodeAt(i);
  #|     if (unit >= 0xD800 && unit <= 0xDBFF) {
  #|       const next = text.charCodeAt(++i);
  #|       if (!(next >= 0xDC00 && next <= 0xDFFF))
  #|         throw new RangeError("Noop metrics: lone UTF-16 high surrogate");
  #|     } else if (unit >= 0xDC00 && unit <= 0xDFFF) {
  #|       throw new RangeError("Noop metrics: lone UTF-16 low surrogate");
  #|     }
  #|   }
  #|   const f32 = Math.fround;
  #|   const font = f32(fontSize), deviceScale = f32(scale);
  #|   const wrapWidth = availableWidth === 0 ? null : f32(availableWidth);
  #|   const emWidth = f32(f32(font * 600) / 1000);
  #|   const phi = f32(1.618034);
  #|   const unsnappedLineHeight = f32(font * phi);
  #|   const scaledLineHeight = f32(unsnappedLineHeight * deviceScale);
  #|   const roundedDeviceHeight = Math.ceil(f32(Math.abs(scaledLineHeight) - 0.5));
  #|   const lineHeight = f32(roundedDeviceHeight / deviceScale);
  #|   const isWord = ch => {
  #|     const c = ch.codePointAt(0);
  #|     return (c >= 0x30 && c <= 0x39) || (c >= 0x41 && c <= 0x5A) ||
  #|       (c >= 0x61 && c <= 0x7A) || (c >= 0x00C0 && c <= 0x024F) ||
  #|       (c >= 0x0400 && c <= 0x04FF) || (c >= 0x1E00 && c <= 0x1EFF) ||
  #|       (c >= 0x0300 && c <= 0x036F) || (c >= 0x0980 && c <= 0x09FF) ||
  #|       "-_.\u0027\u2019\u2018$%@#^~,=:;!)]}\u0022\u201D\u00BB\u2026\u22EF\u202F\u00A0\u2011".includes(ch);
  #|   };
  #|   let width = f32(0), height = f32(0), visualLineCount = 0;
  #|   const lines = [];
  #|   for (const literalLine of text.split("\n")) {
  #|     const chars = Array.from(literalLine), positions = [], utf8Indices = [];
  #|     let position = f32(0), byteIndex = 0;
  #|     for (const ch of chars) {
  #|       positions.push(position);
  #|       utf8Indices.push(byteIndex);
  #|       const cp = ch.codePointAt(0);
  #|       byteIndex += cp <= 0x7F ? 1 : cp <= 0x7FF ? 2 : cp <= 0xFFFF ? 3 : 4;
  #|       const advance = ch.length === 2 ? f32(emWidth * 2) : emWidth;
  #|       position = f32(position + advance);
  #|     }
  #|     let firstNonWhitespace = null, lastCandidate = null, lastCandidateX = f32(0);
  #|     let lastBoundary = 0, lastBoundaryX = f32(0), previous = "\0";
  #|     const boundaries = [];
  #|     if (wrapWidth !== null) {
  #|       for (let i = 0; i < chars.length; i++) {
  #|         const ch = chars[i], x = positions[i];
  #|         if (isWord(ch)) {
  #|           if (previous === " " && ch !== " " && firstNonWhitespace !== null) {
  #|             lastCandidate = i;
  #|             lastCandidateX = x;
  #|           }
  #|         } else if (ch !== " " && firstNonWhitespace !== null) {
  #|           lastCandidate = i;
  #|           lastCandidateX = x;
  #|         }
  #|         if (ch !== " " && firstNonWhitespace === null) firstNonWhitespace = i;
  #|         const nextX = i + 1 < chars.length ? positions[i + 1] : position;
  #|         const rowWidth = f32(nextX - lastBoundaryX);
  #|         if (rowWidth > wrapWidth && i > lastBoundary) {
  #|           if (lastCandidate !== null) {
  #|             lastBoundary = lastCandidate;
  #|             lastBoundaryX = lastCandidateX;
  #|             lastCandidate = null;
  #|           } else {
  #|             lastBoundary = i;
  #|             lastBoundaryX = x;
  #|           }
  #|           boundaries.push(lastBoundary);
  #|         }
  #|         previous = ch;
  #|       }
  #|     }
  #|     const wrappedWidth = wrapWidth === null ? position : Math.min(wrapWidth, position);
  #|     const visualLines = boundaries.length + 1;
  #|     const lineSizeHeight = f32(lineHeight * visualLines);
  #|     width = f32(Math.ceil(Math.max(width, wrappedWidth)));
  #|     height = f32(height + lineSizeHeight);
  #|     visualLineCount += visualLines;
  #|     lines.push({utf8_bytes: byteIndex, utf16_units: literalLine.length,
  #|       scalar_count: chars.length, unwrapped_width: position, wrapped_width: wrappedWidth,
  #|       wrap_scalar_indices: boundaries, wrap_utf8_indices: boundaries.map(i => utf8Indices[i]),
  #|       visual_lines: visualLines, height: lineSizeHeight});
  #|   }
  #|   return JSON.stringify({schema_version: 1, qualification: "source-derived-NoopTextSystem-only",
  #|     upstream_revision: "5a5fbe79917971a4d52a96b6ddb04da198a5012e", arithmetic: "adapter-local-binary32",
  #|     font_size: font, rem_size: 16, scale: deviceScale, authored_content_width: wrapWidth,
  #|     unbounded: wrapWidth === null, units_per_em: 1000, glyph_advance_units: 600,
  #|     em_advance: emWidth, phi, unsnapped_line_height: unsnappedLineHeight, line_height: lineHeight,
  #|     ascent: f32(font * f32(1025 / 1000)), descent: f32(font * f32(-275 / 1000)),
  #|     width, height, physical_lines: lines.length, visual_lines: visualLineCount, lines});
  #| }

// Upstream taffy.rs:261-264,412-414 and util.rs:159-161 quantize the
// callback's binary32 logical dimensions into physical pixel counts.
// Preserve that boundary before entering the portable Double intrinsic API.
extern "js" fn noop_handoff_json(metadata : String, actual_scale : Double) -> String =
  #| (metadata, actualScale) => {
  #|   if (![1, 1.25, 1.5, 2].includes(actualScale))
  #|     throw new RangeError("Noop handoff: unsupported actual layout scale");
  #|   const raw = JSON.parse(metadata), dimensions = [raw.width, raw.height];
  #|   const products = [], counts = [], logical = [];
  #|   for (const value of dimensions) {
  #|     if (!Number.isFinite(value) || value < 0 || Math.fround(value) !== value)
  #|       throw new RangeError("Noop handoff: invalid raw binary32 dimension");
  #|     const product = Math.fround(Math.max(value, 0) * Math.fround(actualScale));
  #|     const count = Math.ceil(product), intrinsic = count / actualScale;
  #|     if (!Number.isFinite(product) || !Number.isSafeInteger(count) ||
  #|         !Number.isFinite(intrinsic) || Math.ceil(intrinsic * actualScale) !== count)
  #|       throw new RangeError("Noop handoff: exact core-ceil invariant failed");
  #|     products.push(product); counts.push(count); logical.push(intrinsic);
  #|   }
  #|   raw.schema_version = 2;
  #|   raw.measurement_handoff = {schema_version: 1,
  #|     quantizer: "upstream-f32-physical-ceil-to-core-Double-logical",
  #|     actual_scale: actualScale, raw_dimensions: dimensions,
  #|     physical_products: products, physical_counts: counts, logical_intrinsic: logical};
  #|   return JSON.stringify(raw);
  #| }

extern "js" fn noop_metrics_width(metadata : String) -> Double =
  #| metadata => JSON.parse(metadata).measurement_handoff.logical_intrinsic[0]

extern "js" fn noop_metrics_height(metadata : String) -> Double =
  #| metadata => JSON.parse(metadata).measurement_handoff.logical_intrinsic[1]

// The result supplies only text's intrinsic content size to the portable core.
// Padding, border, flex sizing, anchoring, snapping, and geometry remain core.
pub fn measured_text(
  text : String,
  font_size : Double,
  available_width : Double,
  scale : Double,
  actual_scale : Double,
) -> @primitives.Size {
  let metadata = measured_text_metadata(text, font_size, available_width, scale, actual_scale)
  @primitives.Size::new(
    noop_metrics_width(metadata), noop_metrics_height(metadata),
  ).unwrap()
}

pub fn measured_text_metadata(
  text : String,
  font_size : Double,
  available_width : Double,
  scale : Double,
  actual_scale : Double,
) -> String {
  noop_handoff_json(
    noop_metrics_source_json(text, font_size, available_width, scale), actual_scale,
  )
}
