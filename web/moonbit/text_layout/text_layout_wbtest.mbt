///|
test "text_layout uses candidate layout for aligned text and bordered rows" {
  let widths = Array::make(15, 80.0)
  let tree = text_layout_tree(widths).tree()
  assert_eq(tree.node(102).unwrap().bounds().left(), 16.0)
  assert_eq(tree.node(103).unwrap().bounds().left(), 360.0)
  assert_eq(tree.node(104).unwrap().bounds().left(), 704.0)
  assert_eq(tree.node(105).unwrap().bounds().top(), 118.0)
  assert_eq(tree.node(21).unwrap().bounds().left(), 16.0)
  assert_eq(tree.node(22).unwrap().bounds().left(), 656.0)
  assert_eq(tree.node(121).unwrap().bounds().left(), 176.0)
  assert_eq(tree.node(122).unwrap().bounds().left(), 699.0)
  assert_eq(tree.node(131).unwrap().bounds().top(), 366.0)
  assert_eq(tree.node(132).unwrap().bounds().left(), 96.0)
}

///|
test "text_layout rejects invalid browser metrics" {
  let error = "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  assert_eq(text_layout_frame([], 1.0), error)
  assert_eq(text_layout_frame(Array::make(15, -1.0), 1.0), error)
  assert_eq(text_layout_frame(Array::make(15, 80.0), 0.0), error)
}
