///|
test "source phi line boxes, grid allocation, and source-shaped popup measurement" {
  assert_eq(line_height(16), 26)
  assert_eq(line_height(14), 23)
  let widths = Array::make(19, 80.0)
  for viewport in [750.0, 480.0, 750.0] {
    let idle = prepare(viewport, 600, widths, -1)
    let tree = idle.tree()
    assert_eq(tree.node(10).unwrap().bounds().size().width(), 120)
    assert_eq(tree.node(10).unwrap().bounds().size().height(), 65)
    assert_true(tree.node(200) is None)
    for index in [0, 1, 2, 3, 5, 6, 7, 8] {
      let frame = prepare(viewport, 600, widths, index)
      let popup = frame.tree().node(200).unwrap().bounds()
      let text = frame.tree().node(201).unwrap().bounds()
      assert_eq(popup.size().width(), 100)
      assert_eq(popup.size().height(), line_height(14) + 4)
      assert_eq(text.left(), popup.left() + 8)
      assert_eq(text.top(), popup.top() + 2)
      assert_eq(frame.tree().node(200).unwrap().accepts_pointer_events(), false)
      assert_true(popup.left() >= 0 && popup.right() <= viewport)
      assert_true(popup.top() >= 0 && popup.bottom() <= 600)
    }
  }
}

///|
test "popup text width changes actual core-measured popup extent" {
  let widths = Array::make(19, 80.0)
  widths[10] = 150
  let frame = prepare(750, 600, widths, 0)
  assert_eq(frame.tree().node(200).unwrap().bounds().size().width(), 166)
  assert_eq(frame.tree().node(201).unwrap().bounds().size().width(), 150)
}

///|
test "public exports reject unsupported viewport and malformed shaping inputs" {
  anchor_reset()
  assert_eq(
    anchor_frame(749, 600, [], 1),
    "{\"ok\":false,\"error\":\"unsupported_viewport_profile\"}",
  )
  assert_eq(
    anchor_frame(750, 600, [], 2),
    "{\"ok\":false,\"error\":\"unsupported_viewport_profile\"}",
  )
  assert_eq(
    anchor_frame(750, 600, [], 1),
    "{\"ok\":false,\"error\":\"invalid_metrics\"}",
  )
}
