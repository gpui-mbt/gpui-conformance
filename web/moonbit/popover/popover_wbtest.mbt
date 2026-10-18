///|
// Unit-only deliberately non-font metrics. These exercise production control
// flow; they cannot qualify actual-font rendering or replace browser evidence.
fn fixture_prefixes() -> Array[Array[Double]] {
  source_segments().map(text => {
    let values = [0.0]
    let mut width = 0.0
    for c in text.to_array() {
      width = width + if c == ' ' { 3.0 } else if c == 'i' { 2.0 } else { 7.0 }
      values.push(width)
    }
    values
  })
}

///|
fn fixture_frame() -> @element.ElementTree raise {
  assert_true(popover_frame(800, 600, 1, fixture_prefixes()).has_prefix("{\"ok\":true"))
  popover_state.val.tree.unwrap()
}

///|
fn point_in(id : UInt64) -> (Double, Double) raise {
  let tree = fixture_frame()
  let bounds = tree.node(id).unwrap().bounds()
  // The authored trigger top padding is outside its below-leaf anchored popup.
  // A measured point, not an observed or fixed popup-coordinate oracle.
  (bounds.left() + bounds.size().width() / 2, bounds.top() + 1)
}

///|
fn click_trigger(id : UInt64) -> Unit raise {
  let (x, y) = point_in(id)
  assert_true(popover_pointer("down", x, y, 0))
  ignore(fixture_frame())
  assert_true(popover_pointer("up", x, y, 0))
  ignore(fixture_frame())
}

///|
test "popover source inventory and independent source units" {
  let texts = source_texts()
  assert_eq(texts.length(), 7)
  assert_eq(source_segments().length(), 8)
  assert_eq(texts[0], "Opened Popover")
  assert_eq(texts[1], "Open Popover")
  assert_eq(texts[3], "Child Popover")
  assert_eq(source_segments()[5] + "\n" + source_segments()[6], texts[5])
  assert_eq(paragraph_width(1), 358.0)
  assert_true(paragraph_width(1.25) != 358.0)
  assert_eq(line_height(16, 1), 26.0)
  assert_eq(line_height(14, 1), 23.0)
  assert_eq(line_height(14, 1.25), 22.4)
}

///|
test "popover initial always-open layer and source layout" {
  popover_reset()
  let tree = fixture_frame()
  assert_true(tree.node(6) is Some(_))
  assert_true(tree.node(11) is None)
  assert_true(tree.node(17) is None)
  assert_false(popover_state.val.parent.val)
  let popup = tree.node(6).unwrap().bounds()
  let leaf = tree.node(4).unwrap().bounds()
  assert_eq(popup.size().width(), 384.0)
  assert_eq(popup.left(), leaf.left())
  assert_eq(popup.top(), leaf.bottom())
  assert_eq(tree.node(8).unwrap().bounds().left() - tree.node(3).unwrap().bounds().right(), 16.0)
  for id in [20UL, 21UL, 22UL, 23UL] {
    assert_eq(tree.node(id).unwrap().bounds().size().width(), 480.0)
    assert_eq(tree.node(id).unwrap().bounds().size().height(), 8.0)
  }
}

///|
test "popover parent child and child-only then parent dismissal" {
  popover_reset()
  click_trigger(8)
  assert_true(popover_state.val.parent.val)
  assert_false(popover_state.val.child.val)
  let tree = fixture_frame()
  assert_eq(tree.node(14).unwrap().bounds().top() - tree.node(12).unwrap().bounds().bottom(), 20.0)
  click_trigger(14)
  assert_true(popover_state.val.parent.val)
  assert_true(popover_state.val.child.val)
  assert_true(fixture_frame().node(17) is Some(_))
  assert_true(popover_pointer("down", 0, 0, 2))
  assert_true(popover_state.val.parent.val)
  assert_false(popover_state.val.child.val)
  // No registry is rebuilt mid-event: stale same-event calls are rejected.
  assert_false(popover_pointer("down", 0, 0, 2))
  ignore(fixture_frame())
  assert_false(popover_pointer("up", 0, 0, 2))
  assert_true(popover_state.val.parent.val)
  assert_true(popover_pointer("down", 0, 0, 2))
  assert_false(popover_state.val.parent.val)
  assert_false(popover_state.val.child.val)
  assert_true(fixture_frame().node(6) is Some(_))
}

///|
test "popover inside presses release and repeated opens" {
  popover_reset()
  for iteration = 0; iteration < 2; iteration = iteration + 1 {
    click_trigger(8)
    let tree = fixture_frame()
    let bounds = tree.node(11).unwrap().bounds()
    assert_false(popover_pointer("down", bounds.left() + 2, bounds.top() + 2, 2))
    assert_false(popover_pointer("up", 0, 0, 2))
    assert_true(popover_state.val.parent.val)
    assert_true(popover_pointer("down", 0, 0, 0))
    ignore(fixture_frame())
  }
}

///|
test "popover interrupted press cancelled before later release" {
  popover_reset()
  let (x, y) = point_in(8)
  assert_true(popover_pointer("down", x, y, 0))
  popover_cancel()
  ignore(fixture_frame())
  assert_false(popover_pointer("up", x, y, 0))
  assert_false(popover_state.val.parent.val)
  assert_true(popover_pointer("down", x, y, 0))
  ignore(fixture_frame())
  assert_true(popover_pointer("up", 0, 0, 0))
  ignore(fixture_frame())
  assert_false(popover_pointer("up", x, y, 0))
  assert_false(popover_state.val.parent.val)
}

///|
test "popover resize scale and font metrics invalidate gestures" {
  for variant = 0; variant < 3; variant = variant + 1 {
    popover_reset()
    let (x, y) = point_in(8)
    assert_true(popover_pointer("down", x, y, 0))
    let prefixes = fixture_prefixes()
    if variant == 2 { prefixes[1][1] = prefixes[1][1] + 0.5 }
    let width = if variant == 0 { 640.0 } else { 800.0 }
    let scale = if variant == 1 { 1.25 } else { 1.0 }
    assert_true(popover_frame(width, 600, scale, prefixes).has_prefix("{\"ok\":true"))
    assert_false(popover_state.val.primary.val.unwrap().is_pressed())
    ignore(popover_pointer("up", x, y, 0))
    assert_false(popover_state.val.parent.val)
  }
}

///|
test "popover invalid metrics fail closed and valid inputs recover" {
  popover_reset()
  ignore(fixture_frame())
  for invalid in [-1.0, 0.0 / 0.0, 1.0 / 0.0, 20000.0] {
    let bad = fixture_prefixes()
    bad[4][2] = invalid
    assert_false(valid_inputs(800, 600, 1, bad))
    assert_true(popover_frame(800, 600, 1, bad).has_prefix("{\"ok\":false"))
    assert_true(popover_state.val.frame is None)
    assert_false(popover_pointer("down", 0, 0, 0))
    ignore(fixture_frame())
  }
  assert_false(valid_inputs(800, 600, 1, []))
  assert_false(valid_inputs(0, 600, 1, fixture_prefixes()))
  assert_false(valid_inputs(800, 600, 0, fixture_prefixes()))
}

///|
test "popover wrapping preserves source LF and derives width from metrics" {
  let prefixes = fixture_prefixes()
  let wide = text_block([5, 6], prefixes, 358, 14, 1, false)
  assert_true(wide.lines.length() > 2)
  assert_eq(wide.lines[wide.lines.length() - 1], "Click outside to close.")
  assert_eq(wide.height, wide.lines.length().to_double() * 23)
  let narrow = text_block([2], prefixes, 200, 16, 1, false)
  let broad = text_block([2], prefixes, 800, 16, 1, false)
  assert_true(narrow.lines.length() > broad.lines.length())
  assert_eq(narrow.width, 200.0)
  let child = text_block([7], prefixes, 0, 14, 1, false)
  assert_eq(child.lines.length(), 1)
  assert_eq(child.width, prefixes[7][prefixes[7].length() - 1].ceil())
}

///|
test "popover text substitution preserves production paint order transform and clips" {
  let state = initial_state()
  state.parent.val = true
  state.child.val = true
  let blocks = text_blocks(800, 1, fixture_prefixes())
  let prepared = build_view(state, blocks).request_layout_with_device_scale(size(800, 600), 1)
    .unwrap().prepaint().unwrap()
  let base = prepared.paint_snapshot(1).unwrap()
  let text = paint_text(prepared, blocks, 1)
  assert_eq(base.clip_chains().length(), text.clip_chains().length())
  for i = 0; i < base.clip_chains().length(); i = i + 1 {
    assert_eq(base.clip_chains()[i].id(), text.clip_chains()[i].id())
    assert_true(base.clip_chains()[i].rects() == text.clip_chains()[i].rects())
  }
  let popup_order : Array[UInt64] = []
  let mut cursor = 0
  for item in base.items() {
    match blocks.get(item.id()) {
      None => {
        assert_eq(text.items()[cursor].id(), item.id())
        if [6UL, 11UL, 17UL].contains(item.id()) { popup_order.push(item.id()) }
        cursor = cursor + 1
      }
      Some(block) => {
        for line = 0; line < block.lines.length(); line = line + 1 {
          match (item, text.items()[cursor]) {
            (@scene.QuadItem(bounds~, transform~, opacity~, clip_chain_id~, ..),
              @scene.TextRunItem(id~, bounds=text_bounds, text=painted_text,
                transform=paint_transform, opacity=paint_opacity, clip_chain_id=paint_clip, ..)) => {
              assert_eq(id, item.id() * 1024 + line.to_uint64())
              assert_eq(painted_text, block.lines[line])
              assert_eq(text_bounds.left(), bounds.left())
              assert_eq(text_bounds.top(), bounds.top() + line.to_double() * block.line_height)
              assert_eq(text_bounds.size().height(), block.line_height)
              assert_eq(paint_transform.a(), transform.a())
              assert_eq(paint_transform.b(), transform.b())
              assert_eq(paint_transform.c(), transform.c())
              assert_eq(paint_transform.d(), transform.d())
              assert_eq(paint_transform.tx(), transform.tx())
              assert_eq(paint_transform.ty(), transform.ty())
              assert_eq(paint_opacity, opacity)
              assert_true(paint_clip == clip_chain_id)
            }
            _ => fail("Text replacement must stay at its core placeholder's scene position")
          }
          cursor = cursor + 1
        }
      }
    }
  }
  assert_eq(cursor, text.items().length())
  assert_true(popup_order == [6UL, 11UL, 17UL])
}

///|
test "popover changing host widths changes intrinsic geometry without observed bounds" {
  popover_reset()
  let first = fixture_frame().node(8).unwrap().bounds().size().width()
  let prefixes = fixture_prefixes()
  prefixes[1] = prefixes[1].map(value => value * 1.1)
  assert_true(popover_frame(800, 600, 1, prefixes).has_prefix("{\"ok\":true"))
  let next = popover_state.val.tree.unwrap().node(8).unwrap().bounds().size().width()
  assert_true(next > first)
  let small = text_blocks(200, 1.25, prefixes)
  let large = text_blocks(800, 1.25, prefixes)
  assert_true(small.get(19).unwrap().height > large.get(19).unwrap().height)
  assert_eq(small.get(18).unwrap().height, large.get(18).unwrap().height)
}

///|
test "popover creates bounded core buttons lazily from measured source geometry" {
  popover_reset()
  assert_true(popover_state.val.primary.val is None)
  assert_true(popover_state.val.secondary.val is None)
  assert_false(popover_pointer("down", 0, 0, 0))
  let tree = fixture_frame()
  assert_true(popover_state.val.primary.val.unwrap().bounds() == tree.node(8).unwrap().bounds())
  assert_true(popover_state.val.secondary.val is None)
  click_trigger(8)
  let tree = fixture_frame()
  assert_true(popover_state.val.secondary.val.unwrap().bounds() == tree.node(14).unwrap().bounds())
  let valid = @primitives.Rect::new(0, 0, 24, 24).unwrap()
  let tiny = @primitives.Rect::new(0, 0, 23, 24).unwrap()
  assert_true(measured_button(None, 8, tiny, "Open Popover") is Err(_))
  let previous = measured_button(None, 8, valid, "Open Popover").unwrap()
  assert_true(measured_button(Some(previous), 8, tiny, "Open Popover") is Err(_))
}

///|
test "popover narrow metrics never enlarge hit bounds or panic on minimum button rejection" {
  for scale in [0.25, 1.0, 1.25, 4.0] {
    popover_reset()
    popover_state.val.parent.val = true
    let tiny = source_segments().map(text =>
      Array::makei(text.to_array().length() + 1, index => index.to_double() * 0.001))
    assert_true(popover_frame(800, 600, scale, tiny).has_prefix("{\"ok\":true"))
    let state = popover_state.val
    let tree = state.tree.unwrap()
    assert_true(state.primary.val.unwrap().bounds() == tree.node(8).unwrap().bounds())
    assert_true(state.secondary.val.unwrap().bounds() == tree.node(14).unwrap().bounds())
  }
  // This broader numeric envelope is outside the browser DPR subset. Its
  // source-snapped 14px line plus padding is below core Button's minimum.
  popover_reset()
  popover_state.val.parent.val = true
  assert_eq(popover_frame(800, 600, 0.0625, fixture_prefixes()),
    "{\"ok\":false,\"error\":\"unsupported_button_bounds\"}")
  assert_true(popover_state.val.frame is None)
  assert_true(popover_state.val.tree is None)
  assert_false(popover_pointer("down", 0, 0, 0))
  ignore(fixture_frame())
}

///|
test "popover source bars preserve GPUI green lightness one-quarter" {
  // Pinned gpui/src/color.rs: green() is HSL(1/3,1,0.25), not CSS lime.
  // The portable RGBA8 paint boundary rounds its 127.5 green channel to128
  // and source alpha0.25 to64; exact floating-alpha raster parity is unverified.
  let state = initial_state()
  let prepared = build_view(state, text_blocks(800, 1, fixture_prefixes()))
    .request_layout_with_device_scale(size(800, 600), 1).unwrap().prepaint().unwrap()
  let mut checked = 0
  for item in prepared.paint_snapshot(1).unwrap().items() {
    match item {
      @scene.QuadItem(id=23, color~, ..) => {
        assert_true(color == @primitives.Color::rgba(0, 128, 0, 64).unwrap())
        checked = checked + 1
      }
      _ => ()
    }
  }
  assert_eq(checked, 1)
}
