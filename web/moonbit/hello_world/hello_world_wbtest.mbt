///|
test "hello_world keeps the upstream six swatches and centered layout" {
  let frame = hello_world_layout(120.0)
  let tree = frame.tree()
  let title = tree.node(2).unwrap().bounds()
  assert_eq(title.left(), 190.0)
  assert_eq(title.top(), 212.0)
  assert_eq(title.size().height(), 32.0)
  let first = tree.node(4).unwrap()
  assert_eq(first.bounds().left(), 134.0)
  assert_eq(first.bounds().top(), 256.0)
  assert_eq(first.bounds().size().width(), 32.0)
  assert_eq(first.background().unwrap(), color(255, 0, 0))
  let last = tree.node(9).unwrap()
  assert_eq(last.bounds().left(), 334.0)
  assert_eq(last.background().unwrap(), color(255, 255, 255))
  assert_eq(frame.paint_snapshot(1.0).unwrap().items().length(), 7)
}

///|
test "hello_world rejects invalid browser metrics before layout" {
  assert_eq(hello_world_frame(-1.0, 1.0), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  assert_eq(hello_world_frame(120.0, 0.0), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  assert_eq(hello_world_frame(499.0, 1.0), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
}
