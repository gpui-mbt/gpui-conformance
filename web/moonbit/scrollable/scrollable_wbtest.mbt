///|
// Source-derived fixture tests. Passing these is not Rust browser comparison.
fn test_widths() -> Array[Double] {
  [340.0, 132.0, 104.0]
}

///|
fn render_tree() -> @element.ElementTree raise {
  assert_true(scrollable_frame(test_widths(), 1.0).has_prefix("{\"ok\":true"))
  scrollable_state.val.tree.unwrap()
}

///|
fn expect_bounds(
  tree : @element.ElementTree,
  id : UInt64,
  x : Double,
  y : Double,
  w : Double,
  h : Double,
) -> Unit raise {
  assert_true(
    tree.node(id).unwrap().bounds() ==
    @primitives.Rect::new(x, y, w, h).unwrap(),
  )
}

///|
fn snapshot_item(
  snapshot : @scene.SceneSnapshot,
  id : UInt64,
) -> @scene.SceneItem {
  for item in snapshot.items() {
    if item.id() == id {
      return item
    }
  }
  abort("expected snapshot item missing")
}

///|
test "scrollable uses measured lifecycle boxes and direct child overflow limits" {
  scrollable_reset()
  let tree = render_tree()
  expect_bounds(tree, 1, 0, 0, 500, 500)
  expect_bounds(tree, 2, 16, 16, 340, 26)
  expect_bounds(tree, 3, 16, 42, 468, 5000)
  expect_bounds(tree, 4, 33, 59, 434, 150)
  expect_bounds(tree, 5, 33, 59, 2000, 150)
  expect_bounds(tree, 6, 50, 76, 132, 26)
  expect_bounds(tree, 8, 33, 229, 104, 26)
  assert_true(tree.scroll_viewport(1).unwrap().max_offset() == point(0, 4558))
  assert_true(tree.scroll_viewport(4).unwrap().max_offset() == point(1566, 0))
  assert_true(tree.scroll_viewport(3) is None)
}

///|
test "scrollable viewport size follows hierarchy and host label measurements" {
  let s = initial_state()
  let tree = scrollable_layout(s, [300, 101, 88], 1.0).tree()
  expect_bounds(tree, 2, 16, 16, 300, 26)
  expect_bounds(tree, 6, 50, 76, 101, 26)
  expect_bounds(tree, 8, 33, 229, 88, 26)
  expect_bounds(tree, 4, 33, 59, 434, 150)
  assert_true(tree.scroll_viewport(1).unwrap().max_offset() == point(0, 4558))
}

///|
test "scrollable same-delta nested wheel translates descendants and preserves sibling X" {
  scrollable_reset()
  ignore(render_tree())
  assert_true(scrollable_wheel(100, 134, 12, 0))
  let horizontal = render_tree()
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 0))
  assert_true(scrollable_state.val.updates.map(update => update.id()) == [4, 1])
  expect_bounds(horizontal, 4, 33, 59, 434, 150)
  expect_bounds(horizontal, 5, 21, 59, 2000, 150)
  expect_bounds(horizontal, 6, 38, 76, 132, 26)
  expect_bounds(horizontal, 8, 33, 229, 104, 26)
  assert_true(scrollable_wheel(100, 134, 0, 12))
  let vertical = render_tree()
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 12))
  expect_bounds(vertical, 2, 16, 4, 340, 26)
  expect_bounds(vertical, 3, 16, 30, 468, 5000)
  expect_bounds(vertical, 4, 33, 47, 434, 150)
  expect_bounds(vertical, 5, 21, 47, 2000, 150)
  expect_bounds(vertical, 6, 38, 64, 132, 26)
  expect_bounds(vertical, 8, 33, 217, 104, 26)
  assert_true(scrollable_wheel(8, 134, 12, 0))
  ignore(render_tree())
  assert_true(scrollable_state.val.updates.map(update => update.id()) == [1])
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 12))
}

///|
test "scrollable hover follows current translated core hit path and ancestor clips" {
  scrollable_reset()
  ignore(render_tree())
  assert_false(scrollable_pointer(100, 134))
  assert_false(scrollable_state.val.hovered)
  assert_false(scrollable_pointer(101, 134))
  assert_false(scrollable_wheel(101, 134, 0, 0))
  assert_false(scrollable_state.val.hovered)
  // The source's clamped-top nonzero wheel still notifies and repaints hover.
  assert_true(scrollable_wheel(100, 134, 0, -1))
  ignore(render_tree())
  assert_true(scrollable_state.val.hovered)
  assert_true(scrollable_state.val.outer == point(0, 0))
  assert_true(scrollable_wheel(100, 134, 12, 0))
  let tree = render_tree()
  assert_true(tree.node(5).unwrap().bounds().contains(point(29, 134)))
  assert_false(tree.dispatch_pointer(point(29, 134)).bubble().contains(5))
  assert_false(scrollable_pointer(29, 134))
  assert_true(scrollable_state.val.hovered)
  ignore(render_tree())
  assert_false(scrollable_state.val.hovered)
  assert_false(scrollable_pointer(100, 134))
  ignore(render_tree())
  assert_true(scrollable_state.val.hovered)
  assert_false(scrollable_leave())
  assert_true(scrollable_state.val.hovered)
  ignore(render_tree())
  assert_false(scrollable_state.val.hovered)
  assert_false(scrollable_leave())
  assert_true(scrollable_wheel(8, 300, 0, 500))
  ignore(render_tree())
  assert_false(scrollable_pointer(100, 134))
  assert_false(scrollable_state.val.hovered)
}

///|
test "scrollable both endpoints clamp and recover without losing retained state" {
  scrollable_reset()
  ignore(render_tree())
  assert_true(scrollable_wheel(100, 134, 100000, 0))
  let right = render_tree()
  assert_true(scrollable_state.val.inner == point(1566, 0))
  assert_eq(right.node(5).unwrap().bounds().right(), 467.0)
  assert_true(scrollable_wheel(100, 134, 100000, 0))
  ignore(render_tree())
  assert_true(scrollable_state.val.inner == point(1566, 0))
  assert_true(scrollable_wheel(100, 134, -100000, 0))
  ignore(render_tree())
  assert_true(scrollable_state.val.inner == point(0, 0))
  assert_true(scrollable_wheel(8, 300, 0, 100000))
  let bottom = render_tree()
  assert_true(scrollable_state.val.outer == point(0, 4558))
  assert_eq(bottom.node(3).unwrap().bounds().bottom(), 484.0)
  assert_true(scrollable_wheel(8, 300, 0, 100000))
  ignore(render_tree())
  assert_true(scrollable_state.val.outer == point(0, 4558))
  assert_true(scrollable_wheel(8, 300, 0, -100000))
  ignore(render_tree())
  assert_true(scrollable_state.val.outer == point(0, 0))
}

///|
test "scrollable dominant-axis ties and outside-root routing come from core" {
  scrollable_reset()
  ignore(render_tree())
  assert_true(scrollable_wheel(100, 134, 12, 4))
  ignore(render_tree())
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 0))
  assert_true(scrollable_wheel(100, 134, 12, 12))
  ignore(render_tree())
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 12))
  assert_false(scrollable_wheel(500, 134, 50, 0))
  ignore(render_tree())
  assert_true(scrollable_state.val.updates.is_empty())
  assert_true(scrollable_state.val.inner == point(12, 0))
}

///|
test "scrollable outside wheel cannot repaint deferred anonymous hover" {
  scrollable_reset()
  ignore(render_tree())
  assert_true(scrollable_wheel(100, 134, 0, -1))
  ignore(render_tree())
  assert_true(scrollable_state.val.hovered)
  assert_false(scrollable_pointer(8, 300))
  assert_true(scrollable_state.val.hovered)
  assert_false(scrollable_wheel(500, 134, 12, 0))
  assert_true(scrollable_state.val.updates.is_empty())
  assert_true(scrollable_state.val.hovered)
  assert_true(scrollable_wheel(8, 300, 0, -1))
  ignore(render_tree())
  assert_false(scrollable_state.val.hovered)
}

///|
test "scrollable scene text and borders inherit core clips and exact fill opacities" {
  let prepainted = scrollable_layout(initial_state(), test_widths(), 1.0)
  let plain = scrollable_snapshot(prepainted, 1.0, false)
  let hover = scrollable_snapshot(prepainted, 1.0, true)
  assert_eq(plain.items().length(), 15)
  assert_eq(plain.clip_chains().length(), 2)
  assert_true(
    plain.items().map(item => item.id()) ==
    [1, 2, 3, 31, 32, 33, 34, 4, 5, 51, 52, 53, 54, 6, 8],
  )
  assert_true(snapshot_item(plain, 1).clip_chain_id() is None)
  assert_true(
    snapshot_item(plain, 6).clip_chain_id() ==
    snapshot_item(plain, 5).clip_chain_id(),
  )
  assert_true(
    snapshot_item(plain, 8).clip_chain_id() ==
    snapshot_item(plain, 3).clip_chain_id(),
  )
  assert_true(
    snapshot_item(plain, 6).clip_chain_id() !=
    snapshot_item(plain, 8).clip_chain_id(),
  )
  for id in [3UL, 5UL] {
    match snapshot_item(plain, id) {
      @scene.QuadItem(opacity~, color~, ..) => {
        assert_eq(opacity, if id == 3 { 0.05 } else { 0.1 })
        assert_eq(color.alpha(), 255)
      }
      _ => fail("fill quad missing")
    }
  }
  match snapshot_item(hover, 5) {
    @scene.QuadItem(opacity~, ..) => assert_eq(opacity, 0.2)
    _ => fail("hover quad missing")
  }
  for id in [31UL, 32UL, 33UL, 34UL, 51UL, 52UL, 53UL, 54UL] {
    match snapshot_item(plain, id) {
      @scene.QuadItem(opacity~, ..) => assert_eq(opacity, 1.0)
      _ => fail("border quad missing")
    }
  }
}

///|
test "scrollable rejects invalid metrics and events without mutating live offsets" {
  scrollable_reset()
  assert_false(scrollable_wheel(100, 100, 12, 0))
  ignore(render_tree())
  assert_true(scrollable_wheel(100, 134, 12, 0))
  ignore(render_tree())
  let cases : Array[Array[Double]] = [
    [],
    [1, 2],
    [0, 10, 10],
    [-1, 10, 10],
    [469, 10, 10],
    [10, 1967, 10],
    [10, 10, 435],
  ]
  for widths in cases {
    assert_eq(
      scrollable_frame(widths, 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for invalid in [0.0 / 0.0, 1.0 / 0.0, -1.0 / 0.0] {
    assert_false(scrollable_wheel(100, 134, invalid, 0))
    assert_false(scrollable_wheel(invalid, 134, 1, 0))
    assert_false(scrollable_pointer(invalid, 134))
    assert_eq(
      scrollable_frame([invalid, 100, 100], 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for scale in [0.0, -1.0, 4.1, 0.0 / 0.0, 1.0 / 0.0] {
    assert_eq(
      scrollable_frame(test_widths(), scale),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  assert_true(scrollable_state.val.inner == point(12, 0))
  assert_true(scrollable_state.val.outer == point(0, 0))
}

///|
test "scrollable valid device scales cannot underflow border strip geometry" {
  for scale in [0.001, 0.01, 0.25, 0.5, 1.0, 1.25, 1.5, 2.0, 4.0] {
    scrollable_reset()
    assert_true(
      scrollable_frame(test_widths(), scale).has_prefix("{\"ok\":true"),
    )
  }
  let prepainted = scrollable_layout(initial_state(), test_widths(), 1.25)
  match snapshot_item(scrollable_snapshot(prepainted, 1.25, false), 31) {
    @scene.QuadItem(bounds~, ..) => assert_eq(bounds.size().height(), 0.8)
    _ => fail("source-derived device-rounded top border missing")
  }
}
