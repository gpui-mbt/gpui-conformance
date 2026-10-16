///|
test "dynamic fonts uses upstream phi line heights, padding and gaps" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  // A single-line status leaves the phi-derived row heights below unchanged.
  let wrapped = wrap_status("Waiting", Array::makei(8, i => i.to_double() * 12.0))
  let tree = dynamic_fonts_layout(widths, wrapped, 1.0).tree()
  // Pinned GPUI TextStyle defaults to phi(), snapped by TextLayout::layout.
  // Keep literal source-derived expectations independent of the layout helper.
  let heights = [39.0, 26.0, 65.0, 52.0, 26.0, 26.0, 26.0]
  let tops = [32.0, 87.0, 129.0, 210.0, 278.0, 320.0, 362.0]
  for index = 0; index < widths.length(); index = index + 1 {
    let bounds = tree.node((index + 2).to_uint64()).unwrap().bounds()
    assert_eq(bounds.left(), 32.0)
    assert_eq(bounds.top(), tops[index])
    assert_eq(bounds.size().height(), heights[index])
    // The wrapped status row spans the upstream 836px content area.
    assert_eq(bounds.size().width(), if index == 4 { 836.0 } else { widths[index] })
    if index > 0 {
      assert_eq(bounds.top() - tops[index - 1] - heights[index - 1], 16.0)
    }
  }
}

///|
test "dynamic fonts snaps phi line boxes to fractional and high DPR grids" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  let wrapped = wrap_status("Waiting", Array::makei(8, i => i.to_double() * 12.0))
  // Expected device pixels, independently derived from the pinned source.
  let scales = [1.5, 2.0]
  let heights = [[58.0, 39.0, 97.0, 78.0, 39.0, 39.0, 39.0],
                 [78.0, 52.0, 129.0, 104.0, 52.0, 52.0, 52.0]]
  let tops = [[48.0, 130.0, 193.0, 314.0, 416.0, 479.0, 542.0],
              [64.0, 174.0, 258.0, 419.0, 555.0, 639.0, 723.0]]
  for run = 0; run < scales.length(); run = run + 1 {
    let scale = scales[run]
    let tree = dynamic_fonts_layout(widths, wrapped, scale).tree()
    for index = 0; index < widths.length(); index = index + 1 {
      let bounds = tree.node((index + 2).to_uint64()).unwrap().bounds()
      // The tolerance only covers binary floating-point logical/device conversion.
      assert_true((bounds.top() * scale - tops[run][index]).abs() < 0.000001)
      assert_true((bounds.size().height() * scale - heights[run][index]).abs() < 0.000001)
      assert_eq(bounds.left() * scale, 32.0 * scale)
    }
  }
}

///|
test "dynamic fonts rejects invalid host measurements" {
  let error = "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  assert_eq(dynamic_fonts_frame([], "Waiting", Array::makei(8, i => i.to_double() * 12.0), 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, -1.0), "Waiting", Array::makei(8, i => i.to_double() * 12.0), 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, 100.0), "Waiting", Array::makei(8, i => i.to_double() * 12.0), 0.0), error)
}

///|
test "long font load errors wrap entirely within the 836px content area" {
  let status = "Font loading failed: Remote provider refused the request. The required font could not be downloaded. Reload to retry."
  let prefixes = Array::makei(status.to_array().length() + 1, i => i.to_double() * 12.0)
  let wrapped = wrap_status(status, prefixes)
  assert_true(wrapped.lines.length() >= 2)
  assert_eq(wrapped.lines.join(""), status)
  assert_true(wrapped.widths.all(width => width <= 836.0))
  let widths = [280.0, 750.0, 600.0, 570.0, prefixes[prefixes.length() - 1], 610.0, 730.0]
  let tree = dynamic_fonts_layout(widths, wrapped, 1.0).tree()
  assert_eq(tree.node(6).unwrap().bounds().top(), 278.0)
  assert_eq(tree.node(7).unwrap().bounds().top(),
    278.0 + wrapped.lines.length().to_double() * 26.0 + 16.0)
  assert_true(dynamic_fonts_frame(widths, status, prefixes, 1.0).contains("\"status_lines\""))
}

///|
test "font status prefix metrics must match the status and its measured width" {
  let widths = [280.0, 750.0, 600.0, 570.0, 84.0, 610.0, 730.0]
  let prefixes = Array::makei(8, i => i.to_double() * 12.0)
  let error = "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  assert_eq(dynamic_fonts_frame(widths, "Waiting", [0.0], 1.0), error)
  prefixes[2] = -1.0
  assert_eq(dynamic_fonts_frame(widths, "Waiting", prefixes, 1.0), error)
  let inconsistent = Array::makei(8, i => i.to_double() * 10.0)
  assert_eq(dynamic_fonts_frame(widths, "Waiting", inconsistent, 1.0), error)
}
