///|
// Source-derived contracts plus separately labeled expectations from retained
// unchanged-Rust DPR1 discovery. These tests are not paired browser evidence.
fn test_widths() -> Array[Double] {
  [300, 90, 90, 90, 100, 90, 65, 65, 110, 110, 110, 110, 110, 110]
}

///|
fn render() -> @element.ElementTree raise {
  let frame = tab_stop_frame(test_widths(), 1)
  assert_true(frame.has_prefix("{\"ok\":true"), msg=frame)
  tab_stop_state.val.tree.unwrap()
}

///|
fn start() -> @element.ElementTree raise {
  tab_stop_reset()
  render()
}

///|
fn send_key(
  label : String,
  down~ : Bool = true,
  shift~ : Bool = false,
  control~ : Bool = false,
  alt~ : Bool = false,
  meta~ : Bool = false,
  repeat~ : Bool = false,
) -> Unit raise {
  assert_true(tab_stop_key(label, down, shift, control, alt, meta, repeat))
  ignore(render())
}

///|
fn pointer(
  kind : String,
  x : Double,
  y : Double,
  button~ : Int32 = 0,
) -> Unit raise {
  assert_true(tab_stop_pointer(kind, x, y, button, false, false, false, false))
  ignore(render())
}

///|
fn pointer_on(
  id : UInt64,
  kind~ : String = "down",
  button~ : Int32 = 0,
) -> Unit raise {
  let bounds = tab_stop_state.val.tree.unwrap().node(id).unwrap().bounds()
  pointer(
    kind,
    bounds.left() + bounds.size().width() / 2,
    bounds.top() + bounds.size().height() / 2,
    button~,
  )
}

///|
fn focus(id : UInt64) -> Unit raise {
  assert_true(focus_target(tab_stop_state.val, id))
  ignore(render())
}

///|
fn expect_focus(id : UInt64) -> Unit raise {
  assert_true(tab_stop_state.val.tree.unwrap().is_focused(id))
}

///|
fn bounds(id : UInt64) -> @primitives.Rect {
  tab_stop_state.val.tree.unwrap().node(id).unwrap().bounds()
}

///|
fn expect_box(
  id : UInt64,
  x : Double,
  y : Double,
  width : Double,
  height : Double,
) -> Unit raise {
  assert_true(
    bounds(id) == @primitives.Rect::new(x, y, width, height).unwrap(),
    msg="unexpected bounds for \{id}",
  )
}

///|
fn current_snapshot() -> @scene.SceneSnapshot {
  snapshot(
    tab_layout(test_widths(), 1, tab_stop_state.val),
    tab_stop_state.val,
    1,
  )
}

///|
fn item(scene : @scene.SceneSnapshot, id : UInt64) -> @scene.SceneItem? {
  for value in scene.items() {
    if value.id() == id {
      return Some(value)
    }
  }
  None
}

///|
test "original fourteen labels metadata non-stop root and independent group indices" {
  let tree = start()
  expect_focus(1)
  assert_false(tree.node(1).unwrap().is_tab_stop())
  assert_true(tab_stop_state.val.modality == @element.Mouse)
  assert_eq(
    tab_stop_state.val.message,
    "Press `Tab`, `Shift-Tab` to switch focus.",
  )
  assert_eq(texts("").length(), 14)
  assert_true(
    texts("") ==
    [
      "", "tab_index: 1", "tab_index: 2", "tab_index: 3", "tab_stop: false", "tab_index: 2",
      "Button 1", "Button 2", "Tab index [6, 1]", "Tab index [6, 2]", "Tab index [6, 3]",
      "Tab index [7, 1]", "Tab index [7, 2]", "Tab index [7, 3]",
    ],
  )
  assert_eq(tree.nodes().length(), 31)
  let indices = [1, 2, 3, 0, 2]
  for index = 0; index < 5; index = index + 1 {
    let node = tree.node(card_ids()[index]).unwrap()
    assert_eq(node.tab_index(), indices[index])
    assert_true(node.is_focusable())
    assert_eq(node.is_tab_stop(), index != 3)
  }
  for (id, index) in [(100UL, 6), (200UL, 7)] {
    let node = tree.node(id).unwrap()
    assert_true(node.is_focusable())
    assert_false(node.is_tab_stop())
    assert_eq(node.tab_index(), index)
    assert_true(node.tab_group_index() == Some(index))
    assert_eq(border_width(tab_stop_state.val, id), 0.0)
  }
  assert_true(
    tab_stop_metadata().contains("cc7c34a9979ce4027578ec2c358f503d944ee26f"),
  )
  assert_true(tab_stop_metadata().contains("\"conformance\":\"unverified\""))
}

///|
test "source lowering derives initial observed DPR1 geometry without construction coordinate tables" {
  ignore(start())
  expect_box(1, 0, 0, 800, 600)
  expect_box(2, 16, 16, 300, 26)
  for
    (id, y, height) in [
      (10UL, 54.0, 33.0),
      (11UL, 99.0, 33.0),
      (12UL, 144.0, 34.0),
      (13UL, 190.0, 33.0),
      (14UL, 235.0, 33.0),
    ] {
    expect_box(id, 16, y, 768, height)
  }
  expect_box(20, 16, 280, 378, 40)
  expect_box(21, 406, 280, 378, 40)
  expect_box(100, 16, 332, 768, 120)
  expect_box(200, 16, 464, 768, 120)
  for
    (id, y) in [
      (101UL, 332.0),
      (102UL, 372.0),
      (103UL, 412.0),
      (201UL, 464.0),
      (202UL, 504.0),
      (203UL, 544.0),
    ] {
    expect_box(id, 16, y, 768, 40)
  }
  assert_false(tab_layout(test_widths(), 1, tab_stop_state.val).overflow())
}

///|
test "source focus border changes card inner shrink weights and current-frame rounding" {
  ignore(start())
  for
    (target, ys, heights) in [
      (10UL, [54.0, 100, 145, 190, 235], [34.0, 33, 33, 33, 33]),
      (11UL, [54.0, 99, 145, 190, 235], [33.0, 34, 33, 33, 33]),
      (12UL, [54.0, 99, 144, 190, 235], [33.0, 33, 34, 33, 33]),
      (14UL, [54.0, 99, 144, 189, 234], [33.0, 33, 33, 33, 34]),
    ] {
    focus(target)
    for index = 0; index < 5; index = index + 1 {
      expect_box(card_ids()[index], 16, ys[index], 768, heights[index])
    }
    expect_box(20, 16, 280, 378, 40)
    expect_box(101, 16, 332, 768, 40)
  }
}

///|
test "all twelve destinations use genuine group prefixes repeated-index order and global wrap" {
  ignore(start())
  for
    id in [
      10UL, 11UL, 14UL, 12UL, 20UL, 21UL, 101UL, 102UL, 103UL, 201UL, 202UL, 203UL,
      10UL,
    ] {
    send_key("Tab")
    expect_focus(id)
    assert_eq(tab_stop_state.val.message, "You have pressed `Tab`.")
  }
  for
    id in [
      203UL, 202UL, 201UL, 103UL, 102UL, 101UL, 21UL, 20UL, 12UL, 14UL, 11UL, 10UL,
      203UL,
    ] {
    send_key("Tab", shift=true)
    expect_focus(id)
    assert_eq(tab_stop_state.val.message, "You have pressed `Shift-Tab`.")
  }
  ignore(start())
  send_key("Tab", shift=true)
  expect_focus(203)
}

///|
test "non-stop anchors include group handles inside their own prefix" {
  ignore(start())
  for
    (anchor, next, previous) in [
      (1UL, 10UL, 203UL),
      (13UL, 10UL, 203UL),
      (100UL, 201UL, 103UL),
      (200UL, 10UL, 203UL),
    ] {
    focus(anchor)
    send_key("Tab")
    expect_focus(next)
    focus(anchor)
    send_key("Tab", shift=true)
    expect_focus(previous)
  }
}

///|
test "ordinary button border-box flex bases move both live hit bounds while owners survive redraw" {
  let initial = start()
  let initial_first = initial.node(20).unwrap().bounds()
  let initial_second = initial.node(21).unwrap().bounds()
  focus(20)
  expect_box(20, 16, 280, 380, 40)
  expect_box(21, 408, 280, 376, 40)
  let owner = tab_stop_state.val.tree.unwrap().focus_owner()
  let x = initial_first.right() + 1
  assert_true(x < bounds(20).right())
  pointer("move", x, 300, button=-1)
  pointer("down", x, 300)
  assert_true(tab_stop_state.val.tree.unwrap().focus_owner() == owner)
  pointer("up", x, 300)
  assert_eq(tab_stop_state.val.message, "You have clicked Button 1.")
  send_key("Tab")
  expect_focus(21)
  expect_box(20, 16, 280, 376, 40)
  expect_box(21, 404, 280, 380, 40)
  let x = bounds(21).left() + 0.5
  assert_true(x < initial_second.left())
  pointer("move", x, 300, button=-1)
  pointer("down", x, 300)
  pointer("up", x, 300)
  expect_focus(21)
  assert_eq(tab_stop_state.val.message, "You have clicked Button 2.")
  send_key("Tab")
  expect_focus(101)
}

///|
test "new one-pixel focused card bottom row routes current geometry and invents no click" {
  let initial = start()
  let old_bottom = initial.node(10).unwrap().bounds().bottom()
  send_key("Tab")
  expect_focus(10)
  let owner = tab_stop_state.val.tree.unwrap().focus_owner()
  let message = tab_stop_state.val.message
  let y = old_bottom + 0.5
  assert_true(y < bounds(10).bottom())
  pointer("move", 400, y, button=-1)
  pointer("down", 400, y)
  pointer("up", 400, y)
  expect_focus(10)
  assert_true(tab_stop_state.val.tree.unwrap().focus_owner() == owner)
  assert_eq(tab_stop_state.val.message, message)
  assert_true(tab_stop_state.val.pending_mouse == [false, false])
  send_key("Tab")
  expect_focus(11)
}

///|
test "cards disabled card and group buttons have focus but no authored click listeners" {
  ignore(start())
  for
    id in [
      10UL, 11UL, 12UL, 13UL, 14UL, 101UL, 102UL, 103UL, 201UL, 202UL, 203UL,
    ] {
    let message = tab_stop_state.val.message
    pointer_on(id)
    expect_focus(id)
    pointer_on(id, kind="up")
    assert_eq(tab_stop_state.val.message, message)
    send_key(" ")
    send_key(" ", down=false)
    send_key("Enter")
    send_key("Enter", down=false)
    assert_eq(tab_stop_state.val.message, message)
    assert_true(tab_stop_state.val.pending_keyboard is None)
    assert_true(tab_stop_state.val.pending_mouse == [false, false])
  }
  for id in [1UL, 100UL, 200UL] {
    focus(id)
    let message = tab_stop_state.val.message
    send_key("Enter")
    send_key("Enter", down=false)
    assert_eq(tab_stop_state.val.message, message)
  }
}

///|
test "only ordinary pointer listeners author exact messages and recorded primary controls release" {
  ignore(start())
  for
    (id, message) in [
      (20UL, "You have clicked Button 1."),
      (21UL, "You have clicked Button 2."),
    ] {
    let before = tab_stop_state.val.message
    pointer_on(id)
    assert_eq(tab_stop_state.val.message, before)
    pointer_on(id, kind="up", button=2)
    assert_eq(tab_stop_state.val.message, message)
    assert_true(tab_stop_content().contains(quote(message)))
  }
  let message = tab_stop_state.val.message
  for button in [1, 2, 3, 4] {
    pointer_on(20, button~)
    pointer_on(20, kind="up", button~)
    expect_focus(20)
    assert_eq(tab_stop_state.val.message, message)
  }
  pointer_on(20)
  pointer("up", -10, -10)
  assert_eq(tab_stop_state.val.message, message)
  pointer_on(20, kind="up")
  assert_eq(tab_stop_state.val.message, message)
}

///|
test "keyboard modality suppresses retained pointer hover and pending pointer click" {
  ignore(start())
  pointer_on(20)
  let message = tab_stop_state.val.message
  send_key("x")
  pointer_on(20, kind="up")
  assert_eq(tab_stop_state.val.message, message)
  pointer_on(10, kind="move", button=-1)
  assert_true(hovered(tab_stop_state.val, 10))
  assert_true(item(current_snapshot(), 4010) is Some(_))
  send_key("x")
  assert_false(hovered(tab_stop_state.val, 10))
  assert_true(item(current_snapshot(), 4010) is None)
  pointer_on(10, kind="move", button=-1)
  assert_true(item(current_snapshot(), 4010) is Some(_))
  assert_true(tab_stop_leave())
  assert_false(hovered(tab_stop_state.val, 10))
}

///|
test "blue three-pixel focus is modality independent while non-stop card remains one-pixel" {
  ignore(start())
  for id in [10UL, 20UL, 101UL] {
    pointer_on(id)
    assert_eq(border_width(tab_stop_state.val, id), 3.0)
    send_key("x")
    assert_eq(border_width(tab_stop_state.val, id), 3.0)
    pointer("move", 0, 0, button=-1)
    assert_eq(border_width(tab_stop_state.val, id), 3.0)
  }
  pointer_on(13)
  assert_eq(border_width(tab_stop_state.val, 13), 1.0)
  assert_false(
    tab_stop_frame(test_widths(), 1).contains("\"border\":\"#0000ff\""),
  )
}

///|
test "scene preserves source paint order exact opacity and separate ten-percent card background" {
  ignore(start())
  let scene = current_snapshot()
  assert_true(
    scene.items().map(value => value.id()) ==
    [
      1, 2, 10, 50, 11, 51, 12, 52, 13, 53, 14, 54, 20, 60, 21, 61, 101, 110, 102,
      111, 103, 112, 201, 210, 202, 211, 203, 212,
    ],
  )
  for id in [13UL, 53UL] {
    match item(scene, id).unwrap() {
      @scene.QuadItem(opacity~, ..) | @scene.TextItem(opacity~, ..) =>
        assert_eq(opacity, 0.4)
      _ => fail("missing opacity")
    }
  }
  pointer_on(10, kind="move", button=-1)
  match item(current_snapshot(), 4010).unwrap() {
    @scene.QuadItem(opacity~, color=ink, ..) => {
      assert_eq(opacity, 0.1)
      assert_true(ink == color(0, 0, 0))
    }
    _ => fail("missing hover fill")
  }
  pointer_on(13, kind="move", button=-1)
  assert_true(item(current_snapshot(), 4013) is None)
  pointer_on(101, kind="move", button=-1)
  assert_true(item(current_snapshot(), 4101) is None)
  assert_true(
    tab_stop_frame(test_widths(), 1).contains("\"kind\":\"shadow_sm\""),
  )
}

///|
test "native core Enter waits for release and cross-key activation shares current owner" {
  ignore(start())
  focus(20)
  let before = tab_stop_state.val.message
  send_key("Enter")
  assert_eq(tab_stop_state.val.message, before)
  send_key("Enter", down=false)
  assert_eq(tab_stop_state.val.message, "You have clicked Button 1.")
  focus(21)
  send_key(" ")
  send_key("Enter", down=false)
  assert_eq(tab_stop_state.val.message, "You have clicked Button 2.")
  let message = tab_stop_state.val.message
  send_key("Enter", down=false)
  assert_eq(tab_stop_state.val.message, message)
}

///|
test "fresh paint geometry retains pending acquisition and reset forbids old ownership" {
  ignore(start())
  send_key("Tab")
  send_key("Tab")
  send_key("Tab")
  send_key("Tab")
  send_key("Tab")
  expect_focus(20)
  send_key("Enter")
  let state = tab_stop_state.val
  let owner = state.tree.unwrap().focus_owner().unwrap()
  for _index = 0; _index < 4; _index = _index + 1 {
    ignore(render())
    assert_true(state.tree.unwrap().focus_owner() == Some(owner))
    assert_true(state.pending_keyboard == Some(owner))
  }
  let fresh = tab_layout(test_widths(), 1, state).tree()
  assert_true(fresh.with_focus_owner(owner) is Err(@element.UnknownElement))
  pointer_on(20, button=2)
  assert_true(state.tree.unwrap().focus_owner() == Some(owner))
  send_key(" ", down=false)
  assert_eq(state.message, "You have clicked Button 1.")
  tab_stop_reset()
  ignore(render())
  assert_true(
    tab_stop_state.val.tree.unwrap().with_focus_owner(owner)
    is Err(@element.UnknownElement),
  )
  send_key("Enter", down=false)
  assert_eq(tab_stop_state.val.message, initial_state().message)
}

///|
test "focus-away-back ABA cancels activation despite same numeric target" {
  for return_to_start in [false, true] {
    ignore(start())
    focus(20)
    let before = tab_stop_state.val.message
    send_key("Enter")
    let owner = tab_stop_state.val.pending_keyboard
    focus(21)
    if return_to_start {
      focus(20)
    }
    assert_true(tab_stop_state.val.tree.unwrap().focus_owner() != owner)
    send_key("Enter", down=false)
    assert_eq(tab_stop_state.val.message, before)
  }
}

///|
test "modified and intervening keys cancel activation while repeats keep same owner" {
  ignore(start())
  focus(20)
  let before = tab_stop_state.val.message
  for down in [true, false] {
    send_key("Enter")
    send_key("x", down~)
    send_key("Enter", down=false)
    assert_eq(tab_stop_state.val.message, before)
  }
  for which in [0, 1, 2, 3] {
    send_key(
      "Enter",
      shift=which == 0,
      control=which == 1,
      alt=which == 2,
      meta=which == 3,
    )
    send_key("Enter", down=false)
    assert_eq(tab_stop_state.val.message, before)
    send_key("Enter")
    send_key(
      "Enter",
      down=false,
      shift=which == 0,
      control=which == 1,
      alt=which == 2,
      meta=which == 3,
    )
    assert_eq(tab_stop_state.val.message, before)
  }
  send_key("Enter")
  let owner = tab_stop_state.val.pending_keyboard
  send_key("Enter", repeat=true)
  assert_true(tab_stop_state.val.pending_keyboard == owner)
  send_key("Enter", down=false)
  assert_eq(tab_stop_state.val.message, "You have clicked Button 1.")
}

///|
test "wheel releases and modified Tab preserve focus and do not invent messages" {
  ignore(start())
  focus(20)
  let owner = tab_stop_state.val.tree.unwrap().focus_owner()
  let before = tab_stop_state.val.message
  for which in [0, 1, 2] {
    send_key("Tab", control=which == 0, alt=which == 1, meta=which == 2)
    expect_focus(20)
    assert_eq(tab_stop_state.val.message, before)
  }
  assert_true(tab_stop_wheel(400, 300, 0, 50))
  assert_true(tab_stop_state.val.modality == @element.Keyboard)
  assert_true(tab_stop_state.val.tree.unwrap().focus_owner() == owner)
  assert_eq(tab_stop_state.val.message, before)
}

///|
test "invalid metrics input and scale changes cannot mutate live ownership or pending gestures" {
  tab_stop_reset()
  assert_false(tab_stop_key("Tab", true, false, false, false, false, false))
  assert_false(tab_stop_leave())
  assert_false(tab_stop_wheel(0, 0, 0, 1))
  ignore(render())
  focus(20)
  send_key("Enter")
  let state = tab_stop_state.val
  let owner = state.tree.unwrap().focus_owner()
  let message = state.message
  for value in [0.0 / 0.0, 1.0 / 0.0, -1.0 / 0.0] {
    assert_false(
      tab_stop_pointer("down", value, 0, 0, false, false, false, false),
    )
    assert_false(tab_stop_wheel(0, 0, value, 0))
    let widths = test_widths()
    widths[0] = value
    assert_eq(
      tab_stop_frame(widths, 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for
    widths in [
      [],
      [1.0],
      [769.0, 90, 90, 90, 100, 90, 65, 65, 110, 110, 110, 110, 110, 110],
    ] {
    assert_eq(
      tab_stop_frame(widths, 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for value in [0.0, -1.0, 4.1, 0.0 / 0.0, 1.0 / 0.0] {
    assert_eq(
      tab_stop_frame(test_widths(), value),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  assert_eq(
    tab_stop_frame(test_widths(), 2),
    "{\"ok\":false,\"error\":\"scale_changed_requires_reset\"}",
  )
  assert_false(tab_stop_pointer("cancel", 0, 0, 0, false, false, false, false))
  assert_false(tab_stop_pointer("down", 0, 0, -1, false, false, false, false))
  assert_false(tab_stop_key("", true, false, false, false, false, false))
  assert_true(state.tree.unwrap().focus_owner() == owner)
  assert_true(state.pending_keyboard == owner)
  assert_eq(state.message, message)
}
