///|
test "text source includes five font choices, Unicode samples and nine inverse pairs" {
  assert_eq(text_families().length(), 5)
  assert_eq(text_intro().length(), 3)
  assert_true(text_intro()[0].contains("日本語"))
  assert_true(text_intro()[2].contains("👩‍💻"))
  assert_true(text_characters().length() > 120)
  assert_eq(text_scales().length(), 18)
  assert_eq(text_scales()[0], text_scales()[1])
  assert_true(text_scales()[16] > text_scales()[2])
}

///|
test "text has a persistent header and a layout-computed overflowing content column" {
  let widths = Array::make(8 + text_characters().length() + 18, 25.0)
  let tree = text_tree(widths, 0).tree()
  assert_eq(tree.node(3).unwrap().bounds().left(), 12.0)
  assert_eq(tree.node(100).unwrap().bounds().top(), 52.0)
  assert_true(tree.node(817).unwrap().bounds().top() > 720.0)
  assert_true(tree.node(500).unwrap().bounds().left() >= 0.0)
}

///|
test "text rejects wrong metrics, font selections, scroll and device scales" {
  let widths = Array::make(8 + text_characters().length() + 18, 25.0)
  let error = "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
  assert_eq(text_frame([], 0.0, 0, 1.0), error)
  assert_eq(text_frame(widths, -1.0, 0, 1.0), error)
  assert_eq(text_frame(widths, 0.0, -1, 1.0), error)
  assert_eq(text_frame(widths, 0.0, 5, 1.0), error)
  assert_eq(text_frame(widths, 0.0, 0, 0.0), error)
  let large = Array::make(8 + text_characters().length() + 18, 2500.0)
  assert_true(text_frame(large, 0.0, 0, 1.0).contains("conformance"))
  assert_eq(text_frame(Array::make(8 + text_characters().length() + 18, 10001.0), 0.0, 0, 1.0), error)
}
