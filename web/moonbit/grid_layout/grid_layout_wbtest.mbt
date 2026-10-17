///|
// Source-derived tests of actual candidate core output. These are not Rust
// observations, browser pixel measurements, or callback-count parity evidence.
fn test_prefixes(width : Double) -> Array[Array[Double]] {
  labels(width).map(text => {
    Array::makei(text.to_array().length() + 1, index => index.to_double() * 8)
  })
}

///|
fn expect_bounds(
  frame : GridFrame,
  id : UInt64,
  x : Double,
  y : Double,
  width : Double,
  height : Double,
) -> Unit raise {
  assert_true(
    frame.prepainted.tree().node(id).unwrap().bounds() ==
    @primitives.Rect::new(x, y, width, height).unwrap(),
  )
}

///|
test "narrow measured query uses fixed siblings and genuine remaining flex content" {
  let frame = prepare(399, 500, 1)
  assert_eq(frame.callbacks, 1)
  assert_true(frame.measured == @primitives.Size::new(399, 500).unwrap())
  expect_bounds(frame, 10, 0, 0, 399, 48)
  expect_bounds(frame, 11, 0, 52, 399, 80)
  expect_bounds(frame, 12, 0, 136, 399, 228)
  expect_bounds(frame, 13, 0, 368, 399, 80)
  expect_bounds(frame, 14, 0, 452, 399, 48)
  // items_center on a Block does not center its children.
  expect_bounds(frame, 100, 1, 1, 397, 26)
  expect_bounds(frame, 102, 1, 137, 397, 26)
}

///|
test "threshold and wide profiles use core grid tracks spans and fixed TOC overflow" {
  for width in [400.0, 401.0, 500.0] {
    let frame = prepare(width, 500, 1)
    let track = (width - 16) / 5
    let left = (track + 4).round()
    let right = (4.0 * (track + 4) - 4).round()
    let ad_left = (4.0 * (track + 4)).round()
    assert_eq(frame.callbacks, 1)
    expect_bounds(frame, 10, 0, 0, width, 97)
    expect_bounds(frame, 11, 0, 101, track.round(), 224)
    expect_bounds(frame, 12, left, 101, right - left, 298)
    expect_bounds(frame, 13, ad_left, 101, width - ad_left, 298)
    expect_bounds(frame, 14, 0, 403, width, 97)
    expect_bounds(frame, 101, 1, 102, (track - 1).round() - 1, 26)
    assert_true(
      frame.prepainted.tree().node(11).unwrap().bounds().bottom() > 198,
    )
  }
}

///|
test "fresh resizing preserves old frames and restores original layout" {
  let first = prepare(500, 500, 1)
  let narrow = prepare(399, 500, 1)
  let threshold = prepare(400, 500, 1)
  let wide = prepare(401, 500, 1)
  let restored = prepare(500, 500, 1)
  assert_eq(narrow.measured.width(), 399.0)
  assert_eq(threshold.measured.width(), 400.0)
  assert_eq(wide.measured.width(), 401.0)
  assert_true(
    first.prepainted.tree().node(12).unwrap().bounds() ==
    restored.prepainted.tree().node(12).unwrap().bounds(),
  )
  expect_bounds(first, 12, 101, 101, 298, 298)
}

///|
test "source labels retain Pixels suffix and wrapping retains trailing spaces" {
  assert_eq(labels(500)[0], "Header — 500px")
  assert_eq(labels(399)[0], "Header — 399px")
  assert_true(
    wrapped_starts("Table of contents", test_prefixes(400)[1], 75) == [0, 9],
  )
  assert_eq(substring("Table of contents", 0, 9), "Table of ")
  assert_true(wrapped_starts("Content", test_prefixes(399)[2], 397) == [0])
  let snapshot = paint(prepare(400, 500, 1), test_prefixes(400), 1)
  let texts : Array[String] = []
  for item in snapshot.items() {
    match item {
      @scene.TextRunItem(text~, text_origin~, id~, ..) => {
        texts.push(text)
        if id == 1100 {
          assert_eq(text_origin.x(), 1.0)
          assert_eq(text_origin.y(), 102.0)
        }
        if id == 1101 {
          assert_eq(text_origin.x(), 1.0)
          assert_eq(text_origin.y(), 128.0)
        }
      }
      _ => ()
    }
  }
  assert_true(
    texts ==
    ["Header — 400px", "Table of ", "contents", "Content", "AD :(", "Footer"],
  )
}

///|
test "comparison profile remains bounded while live viewport accepts ordinary sizes" {
  for width in [399.0, 400.0, 401.0, 500.0] {
    assert_true(
      grid_layout_content(width, 500, 1).contains("\"layout_passes\":1"),
    )
    let frame = grid_layout_frame(width, 500, test_prefixes(width), 1)
    assert_true(frame.has_prefix("{\"ok\":true"))
    assert_true(frame.contains("\"frame_layout_passes\":1"))
    assert_true(
      frame.contains("not a Rust observation or callback-count parity"),
    )
    assert_true(frame.contains("\"conformance\":\"unverified\""))
    assert_true(frame.contains("\"kind\":\"shadow_lg\""))
  }
  for
    (width, height, scale) in [
      (800.0, 600.0, 2.0),
      (320.0, 240.0, 1.25),
      (399.5, 713.0, 1.25),
    ] {
    let measured = prepare(width, height, scale).measured.width()
    let frame = grid_layout_frame(width, height, test_prefixes(measured), scale)
    assert_true(frame.has_prefix("{\"ok\":true"))
    assert_true(frame.contains("\"comparison_profile_match\":false"))
    assert_true(
      grid_layout_content(width, height, scale).has_prefix("{\"ok\":true"),
    )
  }
  for
    (width, height, scale) in [
      (1.0, 1.0, 0.5),
      (0.1, 0.1, 8.0),
      (0.0, 500.0, 1.0),
      (-1.0, 500.0, 1.0),
      (0.0 / 0.0, 500.0, 1.0),
      (1.0 / 0.0, 500.0, 1.0),
      (500.0, 0.0, 1.0),
      (500.0, 500.0, 0.0),
      (500.0, 500.0, 0.0 / 0.0),
      (500.0, 500.0, 1.0 / 0.0),
      (1.0, 1.0, 0.25),
      (16385.0, 500.0, 1.0),
      (8193.0, 100.0, 2.0),
      (8192.0, 8192.0, 1.0),
      (500.0, 500.0, 8.01),
    ] {
    assert_true(
      grid_layout_content(width, height, scale).contains(
        "invalid_live_viewport",
      ),
    )
    assert_true(
      grid_layout_frame(width, height, [], scale).contains(
        "invalid_live_viewport",
      ),
    )
  }
}

///|
test "metrics rejects wrong cardinality nonfinite decreasing and unsupported values" {
  assert_true(grid_layout_frame(500, 500, [], 1).contains("invalid_metrics"))
  let short = test_prefixes(500)
  short[2] = [0, 8]
  assert_true(grid_layout_frame(500, 500, short, 1).contains("invalid_metrics"))
  for invalid in [0.0, -1.0, 4097.0, 0.0 / 0.0, 1.0 / 0.0] {
    let metrics = test_prefixes(500)
    metrics[2][1] = invalid
    assert_true(
      grid_layout_frame(500, 500, metrics, 1).contains("invalid_metrics"),
    )
  }
  let start = test_prefixes(500)
  start[0][0] = 1
  assert_true(grid_layout_frame(500, 500, start, 1).contains("invalid_metrics"))
}
