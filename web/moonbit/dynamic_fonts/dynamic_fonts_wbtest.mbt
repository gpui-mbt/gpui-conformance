///|
test "dynamic fonts uses MoonBit layout with upstream padding and gaps" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  let tree = dynamic_fonts_layout(widths).tree()
  assert_eq(tree.node(2).unwrap().bounds().left(), 32.0)
  assert_eq(tree.node(2).unwrap().bounds().top(), 32.0)
  assert_eq(tree.node(3).unwrap().bounds().top(), 84.0)
  assert_eq(tree.node(4).unwrap().bounds().top(), 126.0)
  assert_eq(tree.node(6).unwrap().bounds().top(), 252.0)
}

///|
test "dynamic fonts rejects invalid host measurements" {
  let error = "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  assert_eq(dynamic_fonts_frame([], "Waiting", 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, -1.0), "Waiting", 1.0), error)
  assert_eq(dynamic_fonts_frame(Array::make(7, 100.0), "Waiting", 0.0), error)
}
