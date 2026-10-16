///|
// Source-derived contracts. These are not paired browser or Rust observations.
fn test_widths() -> Array[Double] {
  [115, 54, 54, 54, 110, 33, 33, 33]
}

///|
fn render() -> @element.ElementTree raise {
  let result = drag_drop_frame(test_widths(), 1)
  assert_true(result.has_prefix("{\"ok\":true"), msg=result)
  drag_drop_state.val.tree.unwrap()
}

///|
fn start() -> @element.ElementTree raise {
  drag_drop_reset()
  render()
}

///|
fn send(
  kind : String,
  x : Double,
  y : Double,
  button~ : Int32 = 0,
) -> Unit raise {
  let result = drag_drop_pointer(kind, x, y, button, false, false, false, false)
  assert_true(result.has_prefix("{\"ok\":true"), msg=result)
  ignore(render())
}

///|
fn bounds(id : UInt64) -> @primitives.Rect {
  drag_drop_state.val.tree.unwrap().node(id).unwrap().bounds()
}

///|
fn on_source(ix~ : Int32 = 0) -> @primitives.Point {
  let b = bounds(source_ids()[ix])
  point(b.left() + 64, b.top() + 64)
}

///|
fn begin(ix~ : Int32 = 0) -> @primitives.Point raise {
  let p = on_source(ix~)
  send("down", p.x(), p.y())
  send("move", p.x() + 3, p.y(), button=-1)
  p
}

///|
fn target_center() -> @primitives.Point {
  let b = bounds(30)
  point(b.left() + b.size().width() / 2, b.top() + b.size().height() / 2)
}

///|
fn current_scene() -> @scene.SceneSnapshot {
  snapshot(drag_layout(test_widths(), 1), drag_drop_state.val, test_widths(), 1)
}

///|
fn item(id : UInt64) -> @scene.SceneItem? {
  for item in current_scene().items() {
    if item.id() == id {
      return Some(item)
    }
  }
  None
}

///|
fn expect_box(
  id : UInt64,
  x : Double,
  y : Double,
  w : Double,
  h : Double,
) -> Unit raise {
  assert_true(
    bounds(id) == @primitives.Rect::new(x, y, w, h).unwrap(),
    msg="bounds:\{id}",
  )
}

///|
test "source labels metrics and genuine core layout derive fixed authored geometry" {
  let tree = start()
  assert_true(
    colors() == [color(0, 0, 255), color(255, 0, 0), color(0, 128, 0)],
  )
  expect_box(1, 0, 0, 800, 600)
  expect_box(3, 0, 168, 800, 168)
  expect_box(4, 0, 168, 800, 128)
  expect_box(10, 192, 168, 128, 128)
  expect_box(11, 336, 168, 128, 128)
  expect_box(12, 480, 168, 128, 128)
  expect_box(30, 144, 356, 512, 128)
  assert_eq(bounds(30).top() - bounds(10).bottom(), 60.0)
  assert_eq(line_height(20, 1), 32.0)
  assert_eq(line_height(16, 1), 26.0)
  assert_eq(line_height(12, 1), 19.0)
  assert_eq(tree.nodes().length(), 12)
  assert_false(drag_layout(test_widths(), 1).overflow())
  assert_true(
    drag_drop_metadata().contains("8f038ef3308fee9b097e7289665c9fa47cd6945b"),
  )
  assert_true(
    labels() ==
    [
      "Drop & Drop", "Item (0)", "Item (1)", "Item (2)", "Drop items here", "Item 0",
      "Item 1", "Item 2",
    ],
  )
}

///|
test "real routed admission requires current source and primary button" {
  ignore(start())
  send("down", 0, 0)
  assert_true(drag_drop_state.val.session.snapshot() is @element.Idle)
  let p = on_source()
  for button in [1, 2, 3, 4] {
    send("down", p.x(), p.y(), button~)
    assert_true(drag_drop_state.val.session.snapshot() is @element.Idle)
  }
  send("down", p.x(), p.y())
  assert_true(
    drag_drop_state.val.session.snapshot() is @element.Pending(source=10, ..),
  )
  assert_true(drag_drop_state.val.drop_on is None)
}

///|
test "strict greater-than-two move-only activation remains sticky and preserves frozen original" {
  ignore(start())
  let p = on_source()
  send("down", p.x(), p.y())
  send("move", p.x() + 2, p.y(), button=-1)
  assert_false(active(drag_drop_state.val))
  assert_true(item(90) is None)
  send("move", p.x() + 3, p.y(), button=-1)
  assert_true(active(drag_drop_state.val))
  match drag_drop_state.val.session.snapshot() {
    @element.Active(source~, origin~, cursor_offset~, payload~, ..) => {
      assert_eq(source, 10UL)
      assert_true(origin == p)
      assert_true(cursor_offset == point(67, 64))
      assert_true(
        payload == { ix: 0, color: color(0, 0, 255), position: point(0, 0), },
      )
      assert_true(
        preview_value(drag_drop_state.val).unwrap().position == cursor_offset,
      )
    }
    _ => fail("real core must be active")
  }
  send("move", p.x() + 1, p.y(), button=-1)
  assert_true(active(drag_drop_state.val))
  assert_true(
    preview_value(drag_drop_state.val).unwrap().position == point(67, 64),
  )
  // The immutable old helper has a different >= threshold policy.
  let old = @element.DragGesture::new(2)
    .unwrap()
    .begin(10, p)
    .update(point(p.x() + 2, p.y()))
  assert_true(old.is_dragging())
}

///|
test "changed-coordinate release cannot activate a pending press" {
  ignore(start())
  let p = on_source()
  let target = target_center()
  send("down", p.x(), p.y())
  send("up", target.x(), target.y())
  assert_true(drag_drop_state.val.session.snapshot() is @element.Idle)
  assert_eq(drag_drop_state.val.drop_count, 0)
  assert_true(drag_drop_state.val.drop_on is None)
  assert_true(item(90) is None)
}

///|
test "three typed colors update target only after release and return original payload once" {
  ignore(start())
  let target = target_center()
  for ix = 0; ix < 3; ix = ix + 1 {
    let previous = drag_drop_state.val.drop_on
    ignore(begin(ix~))
    send("move", target.x(), target.y(), button=-1)
    assert_true(drag_drop_state.val.drop_on == previous)
    assert_eq(drag_drop_state.val.drop_count, ix)
    send("up", target.x(), target.y())
    assert_true(
      drag_drop_state.val.drop_on ==
      Some({ ix, color: colors()[ix], position: point(0, 0), }),
    )
    assert_eq(drag_drop_state.val.drop_count, ix + 1)
    assert_true(drag_drop_state.val.session.snapshot() is @element.Idle)
    assert_true(item(90) is None)
    send("up", target.x(), target.y())
    assert_eq(drag_drop_state.val.drop_count, ix + 1)
  }
}

///|
test "outside and half-open target releases preserve previous accepted payload" {
  ignore(start())
  let target = bounds(30)
  ignore(begin(ix=1))
  send("up", target.right() - 1, target.top() + 64)
  let previous = drag_drop_state.val.drop_on
  assert_eq(drag_drop_state.val.drop_count, 1)
  for x in [target.right(), target.right() + 1, -1.0] {
    ignore(begin(ix=2))
    send("up", x, target.top() + 64)
    assert_true(drag_drop_state.val.drop_on == previous)
    assert_eq(drag_drop_state.val.drop_count, 1)
    assert_false(active(drag_drop_state.val))
  }
}

///|
test "hover and cursor use real core path and are suppressed during active drag" {
  ignore(start())
  let p = on_source()
  send("move", p.x(), p.y(), button=-1)
  assert_true(hovered(drag_drop_state.val, 10))
  assert_eq(cursor(drag_drop_state.val), "move")
  match item(10).unwrap() {
    @scene.QuadItem(opacity~, color=ink, ..) => {
      assert_eq(opacity, 0.2)
      assert_true(ink == colors()[0])
    }
    _ => fail("hover fill missing")
  }
  ignore(begin())
  assert_false(hovered(drag_drop_state.val, 10))
  assert_true(item(10) is None)
  assert_true(drag_drop_leave().contains("\"ok\":true"))
  assert_true(active(drag_drop_state.val))
  assert_eq(cursor(drag_drop_state.val), "move")
  send("up", 0, 0)
  assert_eq(cursor(drag_drop_state.val), "default")
}

///|
test "scene preserves exact fill opacity opaque labels and full border rectangles after labels" {
  ignore(start())
  assert_true(
    current_scene().items().map(value => value.id()) ==
    [1, 2, 20, 1010, 21, 1011, 22, 1012, 31, 1030],
  )
  for
    (id, ink, size) in [
      (2UL, color(51, 51, 51), 20.0),
      (20UL, colors()[0], 16.0),
      (21UL, colors()[1], 16.0),
      (22UL, colors()[2], 16.0),
      (31UL, color(51, 51, 51), 16.0),
    ] {
    match item(id).unwrap() {
      @scene.TextItem(color=actual, font_size~, opacity~, ..) => {
        assert_true(actual == ink)
        assert_eq(font_size, size)
        assert_eq(opacity, 1.0)
      }
      _ => fail("text missing")
    }
  }
  for id in [10UL, 11UL, 12UL, 30UL] {
    match item(id + 1000).unwrap() {
      @scene.QuadItem(bounds=b, color=ink, opacity~, ..) => {
        assert_true(b == bounds(id))
        assert_true(ink == transparent())
        assert_eq(opacity, 1.0)
      }
      _ => fail("border marker missing")
    }
  }
  ignore(begin(ix=2))
  match item(90).unwrap() {
    @scene.QuadItem(bounds=b, color=ink, opacity~, transform~, ..) => {
      assert_eq(b.size().width(), 120.0)
      assert_eq(b.size().height(), 50.0)
      assert_true(ink == colors()[2])
      assert_eq(opacity, 0.5)
      assert_eq(transform.a(), 1.0)
      assert_eq(transform.b(), 0.0)
      assert_eq(transform.c(), 0.0)
      assert_eq(transform.d(), 1.0)
      assert_eq(transform.tx(), 0.0)
      assert_eq(transform.ty(), 0.0)
    }
    _ => fail("preview missing")
  }
  match item(91).unwrap() {
    @scene.TextItem(text~, color=ink, opacity~, font_size~, ..) => {
      assert_eq(text, "Item 2")
      assert_true(ink == color(255, 255, 255))
      assert_eq(opacity, 1.0)
      assert_eq(font_size, 12.0)
    }
    _ => fail("preview label missing")
  }
  assert_true(
    drag_drop_frame(test_widths(), 1).contains(
      "\"shadows\":[{\"id\":90,\"kind\":\"shadow_md\",\"element_opacity\":1}]",
    ),
  )
  let target = target_center()
  send("up", target.x(), target.y())
  match item(30).unwrap() {
    @scene.QuadItem(color=ink, opacity~, ..) => {
      assert_true(ink == colors()[2])
      assert_eq(opacity, 0.5)
    }
    _ => fail("target fill missing")
  }
}

///|
test "preview separate core layout never enters input tree or intercepts target hit" {
  ignore(start())
  ignore(begin())
  let target = target_center()
  send("move", target.x(), target.y(), button=-1)
  let tree = drag_drop_state.val.tree.unwrap()
  assert_true(tree.node(90) is None)
  assert_true(tree.node(91) is None)
  assert_true(tree.dispatch_pointer(target).bubble().contains(30))
  match item(90).unwrap() {
    @scene.QuadItem(bounds~, ..) =>
      assert_true(
        bounds ==
        @primitives.Rect::new(target.x() - 60, target.y() - 25, 120, 50).unwrap(),
      )
    _ => fail("preview body missing")
  }
  send("up", target.x(), target.y())
  assert_eq(drag_drop_state.val.drop_count, 1)
}

///|
test "signed preview lowering handles negative padding and independently snaps fractional terms" {
  ignore(start())
  let source = bounds(10)
  send("down", source.left() + 1, source.top() + 1)
  send("move", source.left() + 4, source.top() + 1, button=-1)
  assert_true(
    preview_value(drag_drop_state.val).unwrap().position == point(4, 1),
  )
  match item(90).unwrap() {
    @scene.QuadItem(bounds=b, ..) =>
      assert_true(
        b ==
        @primitives.Rect::new(
          source.left() + 4 - 60,
          source.top() + 1 - 25,
          120,
          50,
        ).unwrap(),
      )
    _ => fail("ordinary negative-padding grip must render")
  }
  let value : DragInfo = {
    ix: 0,
    color: colors()[0],
    position: point(4.5, 1.5),
  }
  assert_true(preview_origin(point(100.5, 100.5), value, 1) == point(41, 76))
  assert_eq(snap(-55.5, 1), -55.0)
  assert_eq(snap(95.5, 1), 95.0)
  assert_eq(snap(-1.25, 2), -1.0)
}

///|
test "rerenders and old shared_sessiones share one-shot typed consumption and reset cancels all shared_sessiones" {
  ignore(start())
  ignore(begin())
  let state = drag_drop_state.val
  let shared_session = state.session
  let frozen = shared_session.snapshot()
  for _i = 0; _i < 4; _i = _i + 1 {
    ignore(render())
    assert_true(shared_session.snapshot() == frozen)
  }
  let p = target_center()
  send("up", p.x(), p.y())
  assert_true(shared_session.snapshot() is @element.Idle)
  let event = @primitives.PointerButtonReleased(
    position=p,
    button=@primitives.Primary,
    modifiers=@primitives.Modifiers::none(),
  )
  assert_true(
    shared_session.dispatch(state.tree.unwrap(), event, sources(), targets())
    is Ok(@element.Unchanged),
  )
  assert_eq(state.drop_count, 1)
  ignore(begin())
  drag_drop_reset()
  assert_true(shared_session.snapshot() is @element.Idle)
  assert_true(drag_drop_state.val.drop_on is None)
}

///|
test "current binding supplies activation payload while preview uses a separate render copy" {
  let tree = start()
  let state = drag_drop_state.val
  let p = on_source()
  send("down", p.x(), p.y())
  let actual : DragInfo = { ix: 2, color: colors()[2], position: point(0, 0), }
  let result = dispatch(
    state,
    tree,
    @primitives.PointerMoved(position=point(p.x() + 3, p.y())),
    [@element.DragSource::new(10, actual)],
    targets(),
  )
  assert_true(result.contains("\"outcome\":\"activated\""))
  match state.session.snapshot() {
    @element.Active(payload~, ..) => assert_true(payload == actual)
    _ => fail("not active")
  }
  assert_true(preview_value(state).unwrap().position == point(67, 64))
  let target = target_center()
  send("up", target.x(), target.y())
  assert_true(state.drop_on == Some(actual))
}

///|
test "missing current source cannot activate and missing current target consumes without drop" {
  let tree = start()
  let state = drag_drop_state.val
  let p = on_source()
  send("down", p.x(), p.y())
  ignore(
    dispatch(
      state,
      tree,
      @primitives.PointerMoved(position=point(p.x() + 3, p.y())),
      [],
      targets(),
    ),
  )
  assert_false(active(state))
  drag_drop_reset()
  ignore(render())
  ignore(begin())
  let state = drag_drop_state.val
  let target = target_center()
  ignore(
    dispatch(
      state,
      state.tree.unwrap(),
      @primitives.PointerButtonReleased(
        position=target,
        button=@primitives.Primary,
        modifiers=@primitives.Modifiers::none(),
      ),
      sources(),
      [],
    ),
  )
  assert_true(state.session.snapshot() is @element.Idle)
  assert_true(state.drop_on is None)
}

///|
test "atomic malformed release is explicitly reported and cancelled by application policy" {
  ignore(start())
  ignore(begin())
  let state = drag_drop_state.val
  let tree = state.tree.unwrap()
  let before = state.session.snapshot()
  let event = @primitives.PointerButtonReleased(
    position=target_center(),
    button=@primitives.Primary,
    modifiers=@primitives.Modifiers::none(),
  )
  let malformed : Array[@element.DropTarget[DragInfo]] = [
    @element.DropTarget::new(999),
  ]
  assert_true(
    state.session.dispatch(tree, event, sources(), malformed)
    is Err(@element.UnknownTargetBinding(999)),
  )
  assert_true(state.session.snapshot() == before)
  let result = dispatch(state, tree, event, sources(), malformed)
  assert_true(result.contains("\"ok\":false"))
  assert_true(result.contains("unknown_target_binding:999"))
  assert_true(result.contains("\"cancelled\":true"))
  assert_true(state.session.snapshot() is @element.Idle)
  assert_true(state.drop_on is None)
  assert_eq(state.drop_count, 0)
}

///|
test "rejecting predicate consumes typed attempt without applying callback" {
  ignore(start())
  ignore(begin())
  let state = drag_drop_state.val
  let result = dispatch(
    state,
    state.tree.unwrap(),
    @primitives.PointerButtonReleased(
      position=target_center(),
      button=@primitives.Primary,
      modifiers=@primitives.Modifiers::none(),
    ),
    sources(),
    [@element.DropTarget::new(30, can_drop=info => info.ix == 1)],
  )
  assert_true(result.contains("\"outcome\":\"rejected\""))
  assert_true(state.session.snapshot() is @element.Idle)
  assert_true(state.drop_on is None)
  assert_eq(state.drop_count, 0)
}

///|
test "invalid metrics input and scale changes are explicit and never fake a drop" {
  drag_drop_reset()
  assert_true(
    drag_drop_pointer("down", 1, 1, 0, false, false, false, false).contains(
      "layout_required",
    ),
  )
  ignore(render())
  ignore(begin())
  let before = drag_drop_state.val.session.snapshot()
  for value in [0.0 / 0.0, 1.0 / 0.0, -1.0 / 0.0] {
    assert_true(
      drag_drop_pointer("up", value, 1, 0, false, false, false, false).contains(
        "invalid_pointer",
      ),
    )
    let widths = test_widths()
    widths[1] = value
    assert_true(drag_drop_frame(widths, 1).contains("invalid_metrics"))
  }
  for
    widths in [
      [],
      [1.0],
      [801.0, 54, 54, 54, 110, 33, 33, 33],
      [115.0, 125, 54, 54, 110, 33, 33, 33],
    ] {
    assert_true(drag_drop_frame(widths, 1).contains("invalid_metrics"))
  }
  for scale in [0.0, -1, 4.1, 0.0 / 0.0, 1.0 / 0.0] {
    assert_true(
      drag_drop_frame(test_widths(), scale).contains("invalid_metrics"),
    )
  }
  assert_true(
    drag_drop_frame(test_widths(), 2).contains("scale_changed_requires_reset"),
  )
  assert_true(
    drag_drop_pointer("cancel", 1, 1, 0, false, false, false, false).contains(
      "invalid_pointer_kind",
    ),
  )
  assert_true(
    drag_drop_pointer("up", 1, 1, -1, false, false, false, false).contains(
      "invalid_button",
    ),
  )
  assert_true(drag_drop_state.val.session.snapshot() == before)
  assert_true(drag_drop_state.val.drop_on is None)
  assert_eq(drag_drop_state.val.drop_count, 0)
}

///|
test "typed drop outcome routes only to the authored target callback" {
  ignore(start())
  ignore(begin())
  let state = drag_drop_state.val
  let result = dispatch(
    state,
    state.tree.unwrap(),
    @primitives.PointerButtonReleased(
      position=on_source(),
      button=@primitives.Primary,
      modifiers=@primitives.Modifiers::none(),
    ),
    sources(),
    [@element.DropTarget::new(10)],
  )
  assert_true(result.contains("dropped_unhandled_target"))
  assert_true(state.session.snapshot() is @element.Idle)
  assert_true(state.drop_on is None)
  assert_eq(state.drop_count, 0)
}
