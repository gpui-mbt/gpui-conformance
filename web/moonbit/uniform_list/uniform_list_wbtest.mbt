///|
fn widths() -> Array[Double] { Array::make(50, 52.0) }

///|
fn test_prefixes(widths : Array[Double]) -> Array[Array[Double]] {
  let result : Array[Array[Double]] = []
  for index = 0; index < widths.length(); index = index + 1 {
    let length = label(index).to_array().length()
    result.push(Array::makei(length + 1, slot => slot.to_double() * widths[index] / length.to_double()))
  }
  result
}

///|
fn test_advances(widths : Array[Double]) -> Array[Array[Double]] {
  let result : Array[Array[Double]] = []
  for index = 0; index < widths.length(); index = index + 1 {
    let length = label(index).to_array().length()
    result.push(Array::make(length, widths[index] / length.to_double()))
  }
  result
}

///|
fn test_frame(widths : Array[Double], scale : Double) -> String {
  uniform_list_frame(widths, test_prefixes(widths), test_advances(widths), scale)
}

///|
fn render_tree() -> @element.ElementTree raise {
  assert_true(test_frame(widths(), 1).has_prefix("{\"ok\":true"))
  list_state.val.tree.unwrap()
}

///|
test "uniform list real measurement and source-sized virtual extent" {
  uniform_list_reset()
  let tree = render_tree()
  let list = tree.uniform_list(2).unwrap()
  assert_eq(list.measured_item_size().unwrap().height(), 26.0)
  assert_eq(list.measured_item_size().unwrap().width(), 68.0)
  assert_eq(list.content_size().height(), 1300.0)
  assert_eq(list.max_offset(), 1000.0)
  assert_eq(list.visible_range().start(), 0)
  assert_eq(list.visible_range().end(), 12)
  assert_eq(tree.nodes().length(), 26)
  assert_true(tree.node(101).unwrap().bounds() == @primitives.Rect::new(8, 0, 284, 26).unwrap())
}

///|
test "uniform list core remeasures intrinsic leaf and preserves real scene lowering" {
  let state = initial_state()
  state.offset = 32
  let calls : Array[String] = []
  let anchors : Map[UInt64, Int] = Map([])
  let frame = layout_list(state, widths(), 31, 1, calls, anchors)
  let list = frame.tree().uniform_list(2).unwrap()
  assert_eq(list.measured_item_size().unwrap().height(), 31.0)
  assert_eq(list.content_size().height(), 1550.0)
  assert_eq(list.visible_range().start(), 1)
  assert_eq(calls.length(), 3)
  let base = frame.paint_snapshot(1).unwrap()
  let text = text_snapshot(frame, 1, anchors, test_prefixes(widths()), test_advances(widths()))
  assert_eq(base.clip_chains().length(), text.clip_chains().length())
  for i = 0; i < base.clip_chains().length(); i = i + 1 {
    assert_eq(base.clip_chains()[i].id(), text.clip_chains()[i].id())
    assert_true(base.clip_chains()[i].rects() == text.clip_chains()[i].rects())
  }
  assert_true(text.items().length() > base.items().length())
  for item in text.items() {
    match item {
      @scene.TextRunItem(id~, bounds~, text_origin~, clip_chain_id~, ..) => {
        let anchor = frame.tree().node(id / 10).unwrap()
        assert_true(bounds == anchor.bounds())
        assert_eq(text_origin.y(), bounds.top())
        assert_true(text_origin.x() >= bounds.left())
        assert_true(clip_chain_id == Some(0))
      }
      @scene.QuadItem(id~, ..) => assert_eq(id, 1UL)
      _ => fail("Unexpected lowering")
    }
  }
}

///|
test "uniform list trusted transport delegates vertical axis and endpoints to core" {
  uniform_list_reset()
  ignore(render_tree())
  assert_true(uniform_list_wheel(150, 150, 25, 0))
  let old = render_tree()
  assert_eq(old.uniform_list(2).unwrap().offset(), 25.0)
  assert_true(uniform_list_wheel(150, 150, 130, 1))
  let next = render_tree()
  assert_eq(next.uniform_list(2).unwrap().offset(), 26.0)
  assert_true(next.node(100) is None)
  assert_true(next.node(102).unwrap().bounds() == @primitives.Rect::new(0, 0, 300, 26).unwrap())
  assert_eq(old.uniform_list(2).unwrap().offset(), 25.0)
  assert_true(uniform_list_wheel(150, 150, 0, 100000))
  let bottom = render_tree()
  assert_eq(bottom.uniform_list(2).unwrap().offset(), 1000.0)
  assert_true(bottom.node(198).unwrap().bounds() == @primitives.Rect::new(0, 274, 300, 26).unwrap())
  assert_true(uniform_list_wheel(150, 150, 0, -100000))
  assert_eq(render_tree().uniform_list(2).unwrap().offset(), 0.0)
  assert_false(uniform_list_wheel(300, 150, 0, 1))
  assert_false(uniform_list_wheel(150, 300, 0, 1))
}

///|
test "uniform list clicks use current core route and one-shot stable identity" {
  uniform_list_reset()
  ignore(render_tree())
  assert_false(uniform_list_pointer("up", 10, 10, 0))
  assert_false(uniform_list_pointer("down", 10, 40, 0))
  assert_true(uniform_list_wheel(150, 150, 0, 26))
  ignore(render_tree())
  assert_true(uniform_list_pointer("up", 10, 10, 0))
  assert_true(list_state.val.clicked == Some(1))
  assert_false(uniform_list_pointer("up", 10, 10, 0))
}

///|
test "uniform list invalid inputs do not publish new state" {
  uniform_list_reset()
  ignore(render_tree())
  assert_true(uniform_list_wheel(150, 150, 0, 25))
  ignore(render_tree())
  for invalid in [0.0, -1.0, 285.0, 0.0 / 0.0, 1.0 / 0.0] {
    let bad = widths()
    bad[0] = invalid
    assert_eq(test_frame(bad, 1), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  }
  for invalid in [0.0 / 0.0, 1.0 / 0.0] {
    assert_false(uniform_list_wheel(150, 150, 0, invalid))
    assert_false(uniform_list_pointer("down", invalid, 20, 0))
  }
  assert_eq(list_state.val.offset, 25.0)
}

///|
test "uniform list rejects missing inconsistent and nonfinite shaping inputs" {
  uniform_list_reset()
  ignore(render_tree())
  assert_eq(uniform_list_frame(widths(), [], [], 1), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  let prefixes = test_prefixes(widths())
  let advances = test_advances(widths())
  prefixes[0][1] = 0
  assert_eq(uniform_list_frame(widths(), prefixes, advances, 1), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  let prefixes = test_prefixes(widths())
  advances[0][0] = 1.0 / 0.0
  assert_eq(uniform_list_frame(widths(), prefixes, advances, 1), "{\"ok\":false,\"error\":\"invalid_metrics\"}")
  assert_eq(list_state.val.offset, 0.0)
}
