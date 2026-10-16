///|
test "dynamic fonts uses MoonBit layout with upstream padding and gaps" {
  let widths = [280.0, 750.0, 600.0, 570.0, 400.0, 610.0, 730.0]
  let wrapped = wrap_status("Waiting", Array::makei(8, i => i.to_double() * 12.0))
  let tree = dynamic_fonts_layout(widths, wrapped).tree()
  assert_eq(tree.node(2).unwrap().bounds().left(), 32.0)
  assert_eq(tree.node(2).unwrap().bounds().top(), 32.0)
  assert_eq(tree.node(3).unwrap().bounds().top(), 84.0)
  assert_eq(tree.node(4).unwrap().bounds().top(), 126.0)
  assert_eq(tree.node(6).unwrap().bounds().top(), 252.0)
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
  let tree = dynamic_fonts_layout(widths, wrapped).tree()
  assert_eq(tree.node(6).unwrap().bounds().top(), 252.0)
  assert_eq(tree.node(7).unwrap().bounds().top(),
    252.0 + wrapped.lines.length().to_double() * 26.0 + 16.0)
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
