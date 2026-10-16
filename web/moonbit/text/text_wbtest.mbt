///|
fn test_prefixes(advance : Double) -> Array[Array[Double]] {
  text_scales().map(scale => Array::makei(specimen_text().length() + 1,
    i => i.to_double() * advance * scale))
}

///|
fn test_widths(prefixes : Array[Array[Double]], character_width : Double) -> Array[Double] {
  let widths = Array::make(8 + text_characters().length(), character_width)
  for prefix in prefixes { widths.push(prefix[prefix.length() - 1]) }
  widths
}

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
test "all twenty columns fit the viewport with changed font metrics and intrinsic minima" {
  let prefixes = test_prefixes(10.0)
  for character_width in [14.0, 25.0, 40.0] {
    let widths = test_widths(prefixes, character_width)
    // Force one cell to freeze above the equal-shrink share; others redistribute.
    widths[8+19] = 60.0
    let tree = text_tree(widths, prefixes.map(wrap_specimen), 0).tree()
    assert_eq(tree.node(200).unwrap().bounds().size().width(), 920.0)
    assert_eq(tree.node(210).unwrap().bounds().size().width(), 888.0)
    assert_eq(tree.node(3).unwrap().bounds().left(), 12.0)
    assert_eq(tree.node(100).unwrap().bounds().top(), 52.0)
    for i = 0; i < text_characters().length(); i = i + 1 {
      let cell = tree.node((300+i).to_uint64()).unwrap().bounds()
      let glyph = tree.node((500+i).to_uint64()).unwrap().bounds()
      assert_true(cell.left() >= 16.0 - 0.000001)
      assert_true(cell.left() + cell.size().width() <= 904.0 + 0.000001)
      assert_true(glyph.left() >= cell.left() - 0.000001)
      assert_true(glyph.left() + glyph.size().width() <= cell.left() + cell.size().width() + 0.000001)
    }
    assert_eq(tree.node(319).unwrap().bounds().size().width(), 60.0)
  }
}

///|
test "largest specimens retain the whole phrase in measured lines and grow scroll content" {
  let narrow_prefixes = test_prefixes(6.0)
  let wide_prefixes = test_prefixes(10.0)
  let narrow_runs = narrow_prefixes.map(wrap_specimen)
  let wide_runs = wide_prefixes.map(wrap_specimen)
  assert_eq(narrow_runs[17].lines.length(), 2)
  assert_eq(wide_runs[17].lines.length(), 3)
  let narrow_tree = text_tree(test_widths(narrow_prefixes, 14.0), narrow_runs, 0).tree()
  let wide_tree = text_tree(test_widths(wide_prefixes, 25.0), wide_runs, 1).tree()
  for i = 0; i < wide_runs.length(); i = i + 1 {
    assert_eq(wide_runs[i].lines.join(""), specimen_text())
    assert_eq(narrow_runs[i].lines.join(""), specimen_text())
    let specimen = wide_tree.node((800+i).to_uint64()).unwrap().bounds()
    let line_height = text_scales()[i] * 16.0 * 1.3
    assert_true((specimen.size().height() - (wide_runs[i].lines.length().to_double() * line_height + 20.0)).abs() < 0.000001)
    for j = 0; j < wide_runs[i].lines.length(); j = j + 1 {
      let line = wide_tree.node(specimen_line_id(i,j)).unwrap().bounds()
      assert_eq(line.left(), 10.0)
      assert_true(line.size().width() <= 900.0)
      assert_true(line.top() >= specimen.top() + 10.0 - 0.000001)
      assert_true(line.top() + line.size().height() <= specimen.top() + specimen.size().height() - 10.0 + 0.000001)
    }
  }
  let last = wide_tree.node(817).unwrap().bounds()
  let final_line = wide_tree.node(specimen_line_id(17,wide_runs[17].lines.length()-1)).unwrap().bounds()
  let scroll_max = last.top() + last.size().height() - 720.0
  assert_true(scroll_max > 0.0)
  assert_true(final_line.top() - scroll_max >= 52.0)
  assert_true((final_line.top() + final_line.size().height() - scroll_max - 710.0).abs() < 0.000001)
  assert_true(last.top() + last.size().height() > narrow_tree.node(817).unwrap().bounds().top() + narrow_tree.node(817).unwrap().bounds().size().height())
  assert_true(text_frame(test_widths(wide_prefixes,25.0), wide_prefixes, 0.0, 0, 1.0).contains("\"snapshot\""))
}

///|
test "specimen wrapping uses prefix shaping and falls back inside an oversized word" {
  let prefix = Array::makei(specimen_text().length() + 1, i => i.to_double() * 150.0)
  let run = wrap_specimen(prefix)
  assert_eq(run.lines.join(""), specimen_text())
  assert_true(run.widths.all(width => width <= 900.0))
  let shaped = Array::makei(specimen_text().length() + 1, i => i.to_double() * 20.0)
  assert_eq(wrap_specimen(shaped).lines.length(), 1)
}

///|
test "text rejects wrong metrics, prefixes, font selections, scroll and device scales" {
  let prefixes = test_prefixes(10.0)
  let widths = test_widths(prefixes, 25.0)
  let error = "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
  assert_eq(text_frame([], prefixes, 0.0, 0, 1.0), error)
  assert_eq(text_frame(widths, [], 0.0, 0, 1.0), error)
  assert_eq(text_frame(widths, prefixes, -1.0, 0, 1.0), error)
  assert_eq(text_frame(widths, prefixes, 0.0, -1, 1.0), error)
  assert_eq(text_frame(widths, prefixes, 0.0, 5, 1.0), error)
  assert_eq(text_frame(widths, prefixes, 0.0, 0, 0.0), error)
  assert_eq(text_frame(Array::make(widths.length(), 10001.0), prefixes, 0.0, 0, 1.0), error)
  assert_eq(text_frame(widths, Array::make(18,[0.0]), 0.0, 0, 1.0), error)
  prefixes[0][1] = -1.0
  assert_eq(text_frame(widths, prefixes, 0.0, 0, 1.0), error)
  let inconsistent = test_prefixes(8.0)
  assert_eq(text_frame(widths, inconsistent, 0.0, 0, 1.0), error)
  let large_prefixes = Array::makei(18, _ => Array::makei(specimen_text().length()+1,
    i => i.to_double() * 2500.0 / specimen_text().length().to_double()))
  let large = test_widths(large_prefixes,2500.0)
  assert_true(text_frame(large, large_prefixes, 0.0, 0, 1.0).contains("\"snapshot\""))
}
