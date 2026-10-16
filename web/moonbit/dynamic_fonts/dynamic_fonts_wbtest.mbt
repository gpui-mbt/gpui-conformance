///|
test "dynamic fonts uses upstream phi line heights, padding and gaps" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  let tree = dynamic_fonts_layout(widths, 1.0).tree()
  // Pinned GPUI TextStyle defaults to phi(), snapped by TextLayout::layout.
  // Keep literal source-derived expectations independent of the layout helper.
  let heights = [39.0, 26.0, 65.0, 52.0, 26.0, 26.0, 26.0]
  let tops = [32.0, 87.0, 129.0, 210.0, 278.0, 320.0, 362.0]
  for index = 0; index < widths.length(); index = index + 1 {
    let bounds = tree.node((index + 2).to_uint64()).unwrap().bounds()
    assert_eq(bounds.left(), 32.0)
    assert_eq(bounds.top(), tops[index])
    assert_eq(bounds.size().height(), heights[index])
    assert_eq(bounds.size().width(), widths[index])
    if index > 0 {
      assert_eq(bounds.top() - tops[index - 1] - heights[index - 1], 16.0)
    }
  }
}

///|
test "dynamic fonts snaps phi line boxes to fractional and high DPR grids" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  // Expected device pixels, independently derived from the pinned source.
  let scales = [1.5, 2.0]
  let heights = [[58.0, 39.0, 97.0, 78.0, 39.0, 39.0, 39.0],
                 [78.0, 52.0, 129.0, 104.0, 52.0, 52.0, 52.0]]
  let tops = [[48.0, 130.0, 193.0, 314.0, 416.0, 479.0, 542.0],
              [64.0, 174.0, 258.0, 419.0, 555.0, 639.0, 723.0]]
  for run = 0; run < scales.length(); run = run + 1 {
    let scale = scales[run]
    let tree = dynamic_fonts_layout(widths, scale).tree()
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
  assert_eq(dynamic_fonts_frame([], "Waiting", 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, -1.0), "Waiting", 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, 100.0), "Waiting", 0.0), error)
}
