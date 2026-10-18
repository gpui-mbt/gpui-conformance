///|
// Source-derived unit contracts, not observed Rust/browser equivalence.
fn test_widths() -> Array[Double] {
  [270, 480, 220, 420, 250, 460, 330, 330]
}

///|
fn render() -> @element.ElementTree raise {
  assert_true(focus_visible_frame(test_widths(), 1).has_prefix("{\"ok\":true"))
  focus_visible_state.val.tree.unwrap()
}

///|
fn start() -> @element.ElementTree raise {
  focus_visible_reset()
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
  assert_true(focus_visible_key(label, down, shift, control, alt, meta, repeat))
}

///|
fn pointer(
  kind : String,
  x : Double,
  y : Double,
  button~ : Int32 = 0,
) -> Unit raise {
  assert_true(
    focus_visible_pointer(kind, x, y, button, false, false, false, false),
  )
}

///|
fn pointer_on(
  id : UInt64,
  kind~ : String = "down",
  button~ : Int32 = 0,
) -> Unit raise {
  let bounds = focus_visible_state.val.tree.unwrap().node(id).unwrap().bounds()
  pointer(
    kind,
    bounds.left() + bounds.size().width() / 2,
    bounds.top() + bounds.size().height() / 2,
    button~,
  )
}

///|
fn expect_focus(id : UInt64) -> Unit raise {
  assert_true(focus_visible_state.val.tree.unwrap().is_focused(id))
}

///|
fn expect_bounds(
  tree : @element.ElementTree,
  id : UInt64,
  x : Double,
  y : Double,
  width : Double,
  height : Double,
) -> Unit raise {
  assert_true(
    tree.node(id).unwrap().bounds() ==
    @primitives.Rect::new(x, y, width, height).unwrap(),
  )
}

///|
fn snapshot_item(value : @scene.SceneSnapshot, id : UInt64) -> @scene.SceneItem {
  for item in value.items() {
    if item.id() == id {
      return item
    }
  }
  abort("expected snapshot item missing")
}

///|
fn fill(value : @scene.SceneSnapshot, id : UInt64) -> @primitives.Color {
  match snapshot_item(value, id) {
    @scene.QuadItem(color~, ..) => color
    _ => abort("expected quad missing")
  }
}

///|
test "source hierarchy derives padding gaps snapped phi boxes and measured text centers" {
  let tree = start()
  expect_bounds(tree, 1, 0, 0, 800, 600)
  expect_bounds(tree, 2, 32, 32, 270, 39)
  expect_bounds(tree, 3, 32, 95, 736, 58)
  expect_bounds(tree, 4, 48, 111, 480, 26)
  expect_bounds(tree, 5, 32, 177, 736, 317)
  expect_bounds(tree, 11, 32, 177, 220, 23)
  expect_bounds(tree, 12, 32, 208, 736, 64)
  expect_bounds(tree, 13, 190, 227, 420, 26)
  expect_bounds(tree, 21, 32, 288, 250, 23)
  expect_bounds(tree, 22, 32, 319, 736, 64)
  expect_bounds(tree, 31, 32, 399, 330, 23)
  expect_bounds(tree, 32, 32, 430, 736, 64)
  let changed = focus_layout([250, 300, 200, 400, 200, 400, 300, 300], 1).tree()
  expect_bounds(changed, 13, 200, 227, 400, 26)
  expect_bounds(changed, 12, 32, 208, 736, 64)
  assert_eq(line_height(24, 1), 39.0)
  assert_eq(line_height(16, 1), 26.0)
  assert_eq(line_height(14, 1), 23.0)
}

///|
test "source text styles colors and original preorder are retained" {
  ignore(start())
  let state = focus_visible_state.val
  let prepainted = focus_layout(test_widths(), 1)
  let original = prepainted.paint_snapshot(1).unwrap()
  let scene = snapshot(prepainted, state, 1)
  assert_true(
    scene.items().map(item => item.id()) ==
    [1, 2, 3, 4, 11, 12, 13, 21, 22, 23, 31, 32, 33],
  )
  assert_true(fill(scene, 1) == color(243, 244, 246))
  assert_true(fill(scene, 3) == color(219, 234, 254))
  for id in button_ids() {
    assert_true(fill(scene, id) == color(37, 99, 235))
  }
  let labels = texts(state.message)
  let sizes = font_sizes()
  let ids = text_ids()
  for index = 0; index < ids.length(); index = index + 1 {
    match snapshot_item(scene, ids[index]) {
      @scene.TextItem(text~, font_size~, color=ink, clip_chain_id~, ..) => {
        assert_eq(text, labels[index])
        assert_eq(font_size, sizes[index])
        let expected = if index == 0 {
          color(17, 24, 39)
        } else if index == 1 {
          color(30, 58, 138)
        } else if index % 2 == 0 {
          color(55, 65, 81)
        } else {
          color(255, 255, 255)
        }
        assert_true(ink == expected)
        assert_true(
          clip_chain_id == snapshot_item(original, ids[index]).clip_chain_id(),
        )
      }
      _ => fail("text replacement missing")
    }
  }
  assert_true([0, 2, 4, 6].map(font_weight) == [700, 700, 700, 700])
  assert_true([1, 3, 5, 7].map(font_weight) == [400, 400, 400, 400])
  let frame = focus_visible_frame(test_widths(), 1)
  assert_true(frame.contains("\"decorations\":[]"))
  assert_true(frame.contains("\"rounded_fills\":[{\"id\":3,\"radius\":6}"))
  assert_true(frame.contains("\"conformance\":\"unverified\""))
}

///|
test "initial root focus is non-stop mouse modality and exact original content" {
  let tree = start()
  expect_focus(1)
  assert_eq(tree.node(1).unwrap().tab_index(), 0)
  assert_false(tree.node(1).unwrap().is_tab_stop())
  assert_true(focus_visible_state.val.modality == @element.Mouse)
  assert_eq(
    focus_visible_state.val.message,
    "Try clicking vs tabbing! Click shows no border, Tab shows border.",
  )
  assert_true(
    texts("") ==
    [
      "CSS focus-visible Demo", "", "1. Regular .focus() - always visible:", "Button with .focus() - always shows border when focused",
      "2. New .focus_visible() - only keyboard:", "Button with .focus_visible() - only shows border with keyboard",
      "3. Both .focus() (yellow) and .focus_visible() (green):", "Button with both .focus() and .focus_visible()",
    ],
  )
  let ids = button_ids()
  for index = 0; index < ids.length(); index = index + 1 {
    let node = tree.node(ids[index]).unwrap()
    assert_true(node.is_focusable())
    assert_true(node.is_tab_stop())
    assert_eq(node.tab_index(), index + 1)
    assert_true(ring(focus_visible_state.val, ids[index]) is None)
  }
}

///|
test "Tab and Shift Tab traverse core stops in both directions and wrap" {
  ignore(start())
  for id in [12UL, 22UL, 32UL, 12UL] {
    send_key("Tab")
    expect_focus(id)
    assert_eq(
      focus_visible_state.val.message,
      "Pressed Tab - focus-visible border should appear!",
    )
  }
  for id in [32UL, 22UL, 12UL, 32UL] {
    send_key("Tab", shift=true)
    expect_focus(id)
    assert_eq(
      focus_visible_state.val.message,
      "Pressed Shift-Tab - focus-visible border should appear!",
    )
  }
  ignore(start())
  send_key("Tab", shift=true)
  expect_focus(32)
  assert_true(focus_visible_state.val.modality == @element.Keyboard)
}

///|
test "programmatic focus and traversal do not synthesize keyboard modality" {
  let tree = start()
  focus_visible_state.val.tree = Some(tree.focus_next().unwrap())
  expect_focus(12)
  assert_true(focus_visible_state.val.modality == @element.Mouse)
  assert_true(focus_target(focus_visible_state.val, 22))
  assert_true(ring(focus_visible_state.val, 22) is None)
  assert_true(focus_target(focus_visible_state.val, 32))
  assert_true(ring(focus_visible_state.val, 32) == Some("#fbbf24"))
}

///|
test "button-specific focus rings preserve yellow then keyboard green precedence" {
  ignore(start())
  let state = focus_visible_state.val
  pointer_on(12)
  assert_true(ring(state, 12) == Some("#fbbf24"))
  send_key("x")
  assert_true(ring(state, 12) == Some("#fbbf24"))
  pointer_on(22)
  assert_true(ring(state, 22) is None)
  send_key("x")
  assert_true(ring(state, 22) == Some("#10b981"))
  pointer_on(32)
  assert_true(ring(state, 32) == Some("#fbbf24"))
  send_key("x")
  assert_true(ring(state, 32) == Some("#10b981"))
  let frame = focus_visible_frame(test_widths(), 1)
  assert_true(
    frame.contains(
      "\"decorations\":[{\"id\":32,\"radius\":6,\"border_width\":4,\"border\":\"#10b981\",\"border_style\":\"solid\"}]",
    ),
  )
}

///|
test "mouse movement hides keyboard-only ring but retains focus for next Tab" {
  ignore(start())
  send_key("Tab")
  send_key("Tab")
  let owner = focus_visible_state.val.tree.unwrap().focus_owner()
  assert_true(ring(focus_visible_state.val, 22) == Some("#10b981"))
  pointer("move", 10, 10, button=-1)
  expect_focus(22)
  assert_true(focus_visible_state.val.tree.unwrap().focus_owner() == owner)
  assert_true(ring(focus_visible_state.val, 22) is None)
  send_key("Tab")
  expect_focus(32)
  assert_true(ring(focus_visible_state.val, 32) == Some("#10b981"))
}

///|
test "keyboard suppresses resting pointer hover and movement restores blue hover" {
  ignore(start())
  pointer_on(22, kind="move", button=-1)
  let state = focus_visible_state.val
  assert_true(hovered(state, 22))
  let hovering = snapshot(focus_layout(test_widths(), 1), state, 1)
  assert_true(fill(hovering, 22) == color(29, 78, 216))
  let message = state.message
  send_key("x")
  assert_false(hovered(state, 22))
  assert_eq(state.message, message)
  let hidden = snapshot(focus_layout(test_widths(), 1), state, 1)
  assert_true(fill(hidden, 22) == color(37, 99, 235))
  send_key("x", down=false)
  assert_false(hovered(state, 22))
  pointer_on(22, kind="move")
  assert_true(hovered(state, 22))
  assert_true(focus_visible_leave())
  assert_false(hovered(state, 22))
  expect_focus(1)
}

///|
test "pointer down focuses without clicking and release outside cancels" {
  ignore(start())
  let original = focus_visible_state.val.message
  pointer_on(22)
  expect_focus(22)
  assert_eq(focus_visible_state.val.message, original)
  assert_true(focus_visible_state.val.pending_mouse == [false, true, false])
  pointer("up", -20, -20)
  assert_eq(focus_visible_state.val.message, original)
  assert_true(focus_visible_state.val.pending_mouse == [false, false, false])
  pointer_on(22, kind="up")
  assert_eq(focus_visible_state.val.message, original)
  expect_focus(22)
}

///|
test "pointer click messages are source-exact and a different up button still clicks" {
  ignore(start())
  let messages = [
    "Clicked button 1 - focus border is visible!", "Clicked button 2 - no border! Try Tab instead.",
    "Clicked button 3 - yellow border. Tab shows green!",
  ]
  let ids = button_ids()
  for index = 0; index < ids.length(); index = index + 1 {
    pointer_on(ids[index])
    pointer_on(ids[index], kind="up", button=if index == 2 { 2 } else { 0 })
    assert_eq(focus_visible_state.val.message, messages[index])
    assert_true(focus_visible_content().contains(quote(messages[index])))
  }
}

///|
test "root label and message presses focus root and root has no click callback" {
  ignore(start())
  for target in [2UL, 4UL, 11UL, 21UL, 31UL] {
    pointer_on(22)
    pointer_on(22, kind="up")
    let message = focus_visible_state.val.message
    pointer_on(target)
    expect_focus(1)
    pointer_on(target, kind="up")
    assert_eq(focus_visible_state.val.message, message)
    send_key("Enter")
    send_key("Enter", down=false)
    assert_eq(focus_visible_state.val.message, message)
  }
  pointer_on(32)
  pointer("down", 10, 10)
  expect_focus(1)
}

///|
test "all supported mouse buttons focus but secondary-only press cannot click" {
  ignore(start())
  let original = focus_visible_state.val.message
  for button in [1, 2, 3, 4] {
    pointer_on(22, button~)
    expect_focus(22)
    pointer_on(22, kind="up", button~)
    assert_eq(focus_visible_state.val.message, original)
    assert_true(focus_target(focus_visible_state.val, 1))
  }
}

///|
test "same-target mouse and programmatic focus preserve the acquisition" {
  ignore(start())
  assert_true(focus_target(focus_visible_state.val, 22))
  let owner = focus_visible_state.val.tree.unwrap().focus_owner()
  send_key("Enter")
  pointer_on(22, button=2)
  assert_true(focus_visible_state.val.tree.unwrap().focus_owner() == owner)
  assert_true(focus_target(focus_visible_state.val, 22))
  assert_true(focus_visible_state.val.tree.unwrap().focus_owner() == owner)
  send_key("Enter", down=false)
  assert_eq(
    focus_visible_state.val.message,
    "Clicked button 2 - no border! Try Tab instead.",
  )
}

///|
test "Enter Space and cross-activation release use one generation marker" {
  for
    (down, up) in [
      ("Enter", "Enter"),
      (" ", " "),
      (" ", "Enter"),
      ("Enter", " "),
    ] {
    ignore(start())
    send_key("Tab")
    let before = focus_visible_state.val.message
    send_key(down)
    assert_eq(focus_visible_state.val.message, before)
    assert_true(
      focus_visible_state.val.pending_keyboard ==
      focus_visible_state.val.tree.unwrap().focus_owner(),
    )
    send_key(up, down=false)
    assert_eq(
      focus_visible_state.val.message,
      "Clicked button 1 - focus border is visible!",
    )
    assert_true(focus_visible_state.val.pending_keyboard is None)
  }
}

///|
test "ordinary intervening down or up and modified activation cancel pending click" {
  for intervening_down in [true, false] {
    ignore(start())
    send_key("Tab")
    let before = focus_visible_state.val.message
    send_key("Enter")
    send_key("x", down=intervening_down)
    send_key("Enter", down=false)
    assert_eq(focus_visible_state.val.message, before)
  }
  for which in [0, 1, 2, 3] {
    ignore(start())
    send_key("Tab")
    let before = focus_visible_state.val.message
    send_key(
      "Enter",
      shift=which == 0,
      control=which == 1,
      alt=which == 2,
      meta=which == 3,
    )
    send_key("Enter", down=false)
    assert_eq(focus_visible_state.val.message, before)
    send_key("Enter")
    send_key(
      "Enter",
      down=false,
      shift=which == 0,
      control=which == 1,
      alt=which == 2,
      meta=which == 3,
    )
    assert_eq(focus_visible_state.val.message, before)
  }
}

///|
test "unpaired release cannot click and repeated keydown keeps the current owner" {
  ignore(start())
  send_key("Tab")
  let before = focus_visible_state.val.message
  send_key("Enter", down=false)
  assert_eq(focus_visible_state.val.message, before)
  send_key("Enter")
  let owner = focus_visible_state.val.pending_keyboard
  send_key("Enter", repeat=true)
  assert_true(focus_visible_state.val.pending_keyboard == owner)
  send_key("Enter", down=false)
  assert_eq(
    focus_visible_state.val.message,
    "Clicked button 1 - focus border is visible!",
  )
}

///|
test "focus-away and away-back ABA invalidate pending keyboard activation" {
  for return_to_start in [false, true] {
    ignore(start())
    send_key("Tab")
    let before = focus_visible_state.val.message
    send_key("Enter")
    let owner = focus_visible_state.val.pending_keyboard
    assert_true(focus_target(focus_visible_state.val, 22))
    if return_to_start {
      assert_true(focus_target(focus_visible_state.val, 12))
    }
    assert_true(focus_visible_state.val.tree.unwrap().focus_owner() != owner)
    send_key("Enter", down=false)
    assert_eq(focus_visible_state.val.message, before)
  }
}

///|
test "mouse move wheel and repeated painting preserve pending acquisition" {
  ignore(start())
  send_key("Tab")
  send_key("Enter")
  let state = focus_visible_state.val
  let owner = state.tree.unwrap().focus_owner()
  pointer("move", 790, 590)
  assert_true(focus_visible_wheel(790, 590, 0, 12))
  for _index = 0; _index < 5; _index = _index + 1 {
    ignore(render())
    assert_true(state.tree.unwrap().focus_owner() == owner)
  }
  assert_true(
    focus_visible_frame([270, 300, 210, 410, 240, 450, 320, 320], 1).has_prefix(
      "{\"ok\":true",
    ),
  )
  assert_true(state.tree.unwrap().focus_owner() == owner)
  assert_true(state.pending_keyboard == owner)
  send_key(" ", down=false)
  assert_eq(state.message, "Clicked button 1 - focus border is visible!")
}

///|
test "painting never borrows owners across lineage and explicit reset invalidates old owner" {
  ignore(start())
  send_key("Tab")
  let old = focus_visible_state.val.tree.unwrap().focus_owner().unwrap()
  let fresh_paint = focus_layout(test_widths(), 1).tree()
  assert_true(fresh_paint.with_focus_owner(old) is Err(@element.UnknownElement))
  send_key("Enter")
  focus_visible_reset()
  let reset = render()
  expect_focus(1)
  assert_true(reset.with_focus_owner(old) is Err(@element.UnknownElement))
  assert_true(focus_visible_state.val.pending_keyboard is None)
  assert_true(focus_visible_state.val.modality == @element.Mouse)
  send_key("Enter", down=false)
  assert_eq(focus_visible_state.val.message, initial_state().message)
}

///|
test "key release mouse release and wheel retain modality while keydown and mousedown change it" {
  ignore(start())
  pointer_on(22)
  send_key("x", down=false)
  assert_true(focus_visible_state.val.modality == @element.Mouse)
  send_key("x")
  assert_true(focus_visible_state.val.modality == @element.Keyboard)
  let before = focus_visible_state.val.message
  pointer_on(22, kind="up")
  assert_true(focus_visible_state.val.modality == @element.Keyboard)
  assert_eq(focus_visible_state.val.message, before)
  assert_true(focus_visible_wheel(100, 100, 1, 1))
  assert_true(focus_visible_state.val.modality == @element.Keyboard)
  pointer_on(22, button=2)
  assert_true(focus_visible_state.val.modality == @element.Mouse)
}

///|
test "modified Tab is not a bound action and unrelated keydown only changes modality" {
  ignore(start())
  pointer_on(22, button=2)
  let message = focus_visible_state.val.message
  for which in [0, 1, 2] {
    send_key("Tab", control=which == 0, alt=which == 1, meta=which == 2)
    expect_focus(22)
    assert_eq(focus_visible_state.val.message, message)
  }
  send_key("x")
  assert_true(ring(focus_visible_state.val, 22) == Some("#10b981"))
  assert_eq(focus_visible_state.val.message, message)
}

///|
test "invalid events and metrics leave live state and acquisition untouched" {
  focus_visible_reset()
  assert_false(
    focus_visible_key("Tab", true, false, false, false, false, false),
  )
  assert_false(
    focus_visible_pointer("move", 0, 0, -1, false, false, false, false),
  )
  assert_false(focus_visible_wheel(0, 0, 0, 1))
  assert_false(focus_visible_leave())
  ignore(render())
  send_key("Tab")
  send_key("Enter")
  let state = focus_visible_state.val
  let owner = state.tree.unwrap().focus_owner()
  let message = state.message
  for invalid in [0.0 / 0.0, 1.0 / 0.0, -1.0 / 0.0] {
    for kind in ["move", "down", "up"] {
      assert_false(
        focus_visible_pointer(kind, invalid, 0, 0, false, false, false, false),
      )
      assert_false(
        focus_visible_pointer(kind, 0, invalid, 0, false, false, false, false),
      )
    }
    assert_false(focus_visible_wheel(0, 0, invalid, 0))
    assert_false(focus_visible_wheel(invalid, 0, 0, 1))
    let widths = test_widths()
    widths[1] = invalid
    assert_eq(
      focus_visible_frame(widths, 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for bad in [0.0, -1.0, 4.1, 0.0 / 0.0, 1.0 / 0.0] {
    assert_eq(
      focus_visible_frame(test_widths(), bad),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  for
    widths in [
      [],
      [1.0],
      [0.0, 10, 10, 10, 10, 10, 10, 10],
      [737.0, 10, 10, 10, 10, 10, 10, 10],
      [10.0, 705, 10, 10, 10, 10, 10, 10],
      [10.0, 10, 10, 729, 10, 10, 10, 10],
    ] {
    assert_eq(
      focus_visible_frame(widths, 1),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
  }
  assert_false(
    focus_visible_pointer("cancel", 0, 0, 0, false, false, false, false),
  )
  assert_false(
    focus_visible_pointer("down", 0, 0, -1, false, false, false, false),
  )
  assert_false(focus_visible_pointer("up", 0, 0, 5, false, false, false, false))
  assert_false(focus_visible_key("", true, false, false, false, false, false))
  assert_eq(
    focus_visible_frame(test_widths(), 2),
    "{\"ok\":false,\"error\":\"scale_changed_requires_reset\"}",
  )
  assert_true(state.tree.unwrap().focus_owner() == owner)
  assert_true(state.pending_keyboard == owner)
  assert_true(state.modality == @element.Keyboard)
  assert_eq(state.message, message)
}

///|
test "device scale stays fixed per session and collapsed paint dimensions are rejected" {
  for scale in [0.1, 0.25, 0.5, 1.0, 1.25, 1.5, 2.0, 4.0] {
    focus_visible_reset()
    assert_true(
      focus_visible_frame(test_widths(), scale).has_prefix("{\"ok\":true"),
    )
    send_key("Tab")
    let owner = focus_visible_state.val.tree.unwrap().focus_owner()
    assert_true(
      focus_visible_frame(test_widths(), scale).has_prefix("{\"ok\":true"),
    )
    assert_true(focus_visible_state.val.tree.unwrap().focus_owner() == owner)
  }
  for scale in [0.001, 0.01] {
    focus_visible_reset()
    assert_eq(
      focus_visible_frame(test_widths(), scale),
      "{\"ok\":false,\"error\":\"invalid_metrics\"}",
    )
    assert_true(focus_visible_state.val.tree is None)
    assert_true(focus_visible_state.val.scale is None)
  }
}

///|
test "web beforeinput core sequence consumes arming before physical Enter release" {
  ignore(start())
  send_key("Tab")
  // Physical desktop keydown. The browser's beforeinput then delivers its
  // own complete unmodified core keystroke, not a second DOM keydown.
  send_key("Enter")
  send_key("Enter")
  send_key("Enter", down=false)
  assert_eq(
    focus_visible_state.val.message,
    "Clicked button 1 - focus border is visible!",
  )
  assert_true(focus_visible_state.val.pending_keyboard is None)
  // A sentinel makes a duplicate callback observable despite the production
  // click message otherwise being idempotent.
  focus_visible_state.val.message = "after synthetic release"
  send_key("Enter", down=false)
  assert_eq(focus_visible_state.val.message, "after synthetic release")
  assert_true(focus_visible_state.val.pending_keyboard is None)
}

///|
test "physical release after web beforeinput cannot activate a later focus owner" {
  ignore(start())
  send_key("Tab")
  send_key("Enter")
  send_key("Enter")
  send_key("Enter", down=false)
  assert_true(focus_target(focus_visible_state.val, 22))
  focus_visible_state.val.message = "new focus owner"
  send_key("Enter", down=false)
  assert_eq(focus_visible_state.val.message, "new focus owner")
  assert_true(focus_visible_state.val.pending_keyboard is None)
  expect_focus(22)
}
