///|
test "tree retains all 51 upstream nodes, padding, colors and paint order" {
  let prepainted = tree_layout(50)
  let items = prepainted.paint_snapshot(1.0).unwrap().items()
  assert_eq(items.length(), 51)
  for offset = 0; offset < 51; offset = offset + 1 {
    let index = 50 - offset
    let id = (index + 2).to_uint64()
    let node = prepainted.tree().node(id).unwrap()
    let bounds = node.bounds()
    assert_eq(items[offset].id(), id)
    assert_eq(bounds.left(), offset.to_double() * 2.0)
    assert_eq(bounds.top(), offset.to_double() * 2.0)
    assert_eq(bounds.size().width(), 300.0 - offset.to_double() * 4.0)
    assert_eq(bounds.size().height(), (index + 1).to_double() * 4.0)
    assert_true(node.background().unwrap() == tree_color(index))
  }
  assert_false(prepainted.overflow())
}

///|
test "tree auto measurement follows hierarchy changes rather than fixed boxes" {
  for depth in [0, 1, 3, 12, 50, 63] {
    let prepainted = tree_layout(depth)
    let outer = prepainted.tree().node((depth + 2).to_uint64()).unwrap()
    assert_eq(outer.bounds().size().height(), (depth + 1).to_double() * 4.0)
    assert_eq(outer.bounds().size().width(), 300.0)
    assert_eq(prepainted.tree().node(2).unwrap().bounds().size().height(), 4.0)
    assert_eq(
      prepainted.paint_snapshot(1.0).unwrap().items().length(),
      depth + 1,
    )
  }
}

///|
test "tree rejects invalid device scale before layout" {
  for scale in [-1.0, 0.0, 4.1, 0.0 / 0.0, 1.0 / 0.0] {
    assert_eq(tree_frame(scale), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  }
  assert_true(tree_frame(2.0).has_prefix("{\"ok\":true"))
}
