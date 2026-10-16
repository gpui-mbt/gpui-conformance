// Executed core regression only. This fractional input is NOT in the Rust corpus.
///|
test "pair fractional endpoint regression stays inside reserved namespace" {
  let h = 27.142077840697404
  let viewport = 1.4068746168049984e-14
  let position = 81.4262335220922
  let size = @primitives.Size::new(220, viewport).unwrap()
  let item = @layout.FlexItem::new(2, @layout.Dimension::points(viewport).unwrap(), @layout.Dimension::points(220).unwrap(), size).with_flex(0, 0).unwrap()
  let calls : Array[(Int, Int)] = []
  let list = @element.UniformList::new(item, 3, @element.UniformListIdSpace::new(100, 4).unwrap(), range => {
    calls.push((range.start(), range.end()))
    let rows : Array[@element.Element] = []
    for index = range.start(); index < range.end(); index = index + 1 {
      let row = @layout.FlexItem::new(range.id(index, 0).unwrap(), @layout.Dimension::auto(), @layout.Dimension::auto(), @primitives.Size::new(42, h).unwrap()).with_flex(0, 0).unwrap()
      rows.push(@element.Element::new(row))
    }
    Ok(rows)
  }).unwrap().with_scroll_offset(position).unwrap().into_element()
  let frame = @element.Element::root(1, @layout.FlexTreeStyle::new(@layout.FlowDirection::column()))
    .with_child(list).request_layout(@primitives.Size::new(220, 300).unwrap()).unwrap().prepaint().unwrap()
  let observed = frame.tree().uniform_list(2).unwrap()
  debug_inspect(calls, content="[(0, 1), (0, 1), (2, 3)]")
  assert_true(observed.visible_range().end() <= observed.item_count())
  assert_true(observed.visible_range().id(3, 0) is Err(_))
  assert_true(frame.tree().node(112) is None)
}
