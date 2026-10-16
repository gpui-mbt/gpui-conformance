///|
// Source-derived port of unchanged scrollable.rs, blob c81795618875aecf06e06043bd1709c48630b58f.
// Layout, scroll limits, wheel routing, translation and hit clipping use the
// real element lifecycle. Browser font widths are the sole geometry input.
priv struct ScrollableState {
  mut outer : @primitives.Point
  mut inner : @primitives.Point
  mut pointer : @primitives.Point?
  mut hovered : Bool
  mut tree : @element.ElementTree?
  mut updates : Array[@element.ScrollViewport]
}

///|
fn initial_state() -> ScrollableState {
  {
    outer: point(0.0, 0.0),
    inner: point(0.0, 0.0),
    pointer: None,
    hovered: false,
    tree: None,
    updates: [],
  }
}

///|
let scrollable_state : Ref[ScrollableState] = Ref(initial_state())

///|
fn point(x : Double, y : Double) -> @primitives.Point {
  @primitives.Point::new(x, y).unwrap()
}

///|
fn color(red : Int32, green : Int32, blue : Int32) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn transparent() -> @primitives.Color {
  @primitives.Color::rgba(0, 0, 0, 0).unwrap()
}

///|
fn line_height() -> Double {
  // GPUI TextStyle::default uses relative(phi), with 16px rem/font size.
  16.0 * 1.618033988749895
}

///|
fn labels() -> Array[String] {
  [
    "Example for test 2 way scroll in nested layout", "Scroll Horizontal", "Scroll Vertical",
  ]
}

///|
fn quote(text : String) -> String {
  @json.to_json(text).stringify()
}

///|
#export_name("scrollable_metadata")
pub fn scrollable_metadata() -> String {
  let runs = labels().map(text => {
    "{\"text\":\{quote(text)},\"font_size\":16,\"line_height\":\{line_height()}}"
  })
  "{\"id\":\"scrollable\",\"width\":500,\"height\":500,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":\{line_height()},\"interactive\":true,\"runs\":[\{runs.join(",")}],\"source_blob\":\"c81795618875aecf06e06043bd1709c48630b58f\",\"metrics_contract\":\"three shaped label widths in heading,horizontal,vertical order; device scale\",\"conformance\":\"unverified\"}"
}

///|
#export_name("scrollable_reset")
pub fn scrollable_reset() -> Unit {
  scrollable_state.val = initial_state()
}

///|
fn column(padding : Double, border : Double) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  .with_align(@layout.AlignItems::stretch())
  .with_insets(
    @layout.Insets::all(padding).unwrap(),
    @layout.Insets::all(border).unwrap(),
  )
}

///|
fn node(
  id : UInt64,
  height : @layout.Dimension,
  width : @layout.Dimension,
) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      height,
      width,
      @primitives.Size::new(0.0, 0.0).unwrap(),
    )
    .with_flex(0.0, 0.0)
    .unwrap(),
  )
}

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn text_node(id : UInt64, width : Double) -> @element.Element {
  // Transparent markers preserve the actual inherited core clip chain for
  // replacement by scene text at exactly this laid-out/prepainted location.
  node(id, fixed(line_height()), fixed(width))
  .with_background(Some(transparent()))
  .with_pointer_events(false)
}

///|
fn scrollable_layout(
  s : ScrollableState,
  widths : Array[Double],
  scale : Double,
) -> @element.Prepainted {
  let green = node(5, fixed(150.0), fixed(2000.0))
    .with_children_style(column(16.0, 1.0))
    .with_background(Some(color(0, 128, 0)))
    .with_child(text_node(6, widths[1]))
  let horizontal = node(4, @layout.Dimension::auto(), @layout.Dimension::auto())
    .with_children_style(column(0.0, 0.0))
    .with_background(Some(transparent()))
    .with_scroll_offset(s.inner)
    .with_child(green)
  // With these two children a 20px column gap is precisely the source's mb5
  // on the horizontal viewport. It is not appended after the vertical label.
  let body = node(3, fixed(5000.0), @layout.Dimension::auto())
    .with_children_style(column(16.0, 1.0).with_gap(20.0).unwrap())
    .with_background(Some(color(0, 0, 255)))
    .with_child(horizontal)
    .with_child(text_node(8, widths[2]))
  @element.Element::root(1, column(16.0, 0.0))
  .with_background(Some(color(255, 255, 255)))
  .with_scroll_offset(s.outer)
  .with_child(text_node(2, widths[0]))
  .with_child(body)
  .request_layout_with_device_scale(
    @primitives.Size::new(500.0, 500.0).unwrap(),
    scale,
  )
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn pointer_hover(
  tree : @element.ElementTree,
  pointer : @primitives.Point?,
) -> Bool {
  match pointer {
    None => false
    Some(position) => tree.dispatch_pointer(position).bubble().contains(5)
  }
}

///|
#export_name("scrollable_pointer")
pub fn scrollable_pointer(x : Double, y : Double) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  let s = scrollable_state.val
  s.pointer = Some(position)
  // The source green div is anonymous: it has no retained hover_state, so a
  // pointer-only change does not notify. A subsequent real repaint computes
  // hover from the new pointer and current clipped core hitboxes.
  false
}

///|
#export_name("scrollable_leave")
pub fn scrollable_leave() -> Bool {
  let s = scrollable_state.val
  s.pointer = None
  false
}

///|
#export_name("scrollable_wheel")
pub fn scrollable_wheel(
  x : Double,
  y : Double,
  dx : Double,
  dy : Double,
) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  let s = scrollable_state.val
  let tree = match s.tree {
    Some(value) => value
    None => return false
  }
  let updates = match tree.scroll_wheel(position, dx, dy) {
    Ok(value) => value
    Err(_) => return false
  }
  s.pointer = Some(position)
  s.updates = updates
  for update in updates {
    if update.id() == 1 {
      s.outer = update.offset()
    }
    if update.id() == 4 {
      s.inner = update.offset()
    }
  }
  // Upstream adds raw deltas and notifies before the next prepaint clamps.
  // A nonzero wheel at a limit therefore still repaints; a zero wheel does not.
  (dx != 0.0 || dy != 0.0) && !updates.is_empty()
}

///|
fn append_border(
  items : Array[@scene.SceneItem],
  id : UInt64,
  bounds : @primitives.Rect,
  ink : @primitives.Color,
  clip : Int32?,
  scale : Double,
) -> Unit {
  // Border geometry derives from prepainted element bounds and the source's
  // one-pixel border. Non-overlapping strips avoid corner alpha accumulation.
  let x = bounds.left()
  let y = bounds.top()
  let w = bounds.size().width()
  let h = bounds.size().height()
  if w == 0.0 || h == 0.0 {
    return
  }
  // GPUI window::snap_stroke rounds half toward zero and retains at least one
  // physical pixel for a nonzero stroke. This is painting, not layout input.
  let thickness = (scale - 0.5).ceil().max(1.0) / scale
  if thickness * 2.0 >= w || thickness * 2.0 >= h {
    items.push(
      @scene.SceneItem::quad(
        id * 10 + 1,
        bounds,
        ink,
        @scene.AffineTransform::identity(),
        1.0,
        clip,
      ).unwrap(),
    )
    return
  }
  let strips = [
    @primitives.Rect::new(x, y, w, thickness).unwrap(),
    @primitives.Rect::new(x, y + h - thickness, w, thickness).unwrap(),
    @primitives.Rect::new(x, y + thickness, thickness, h - 2.0 * thickness).unwrap(),
    @primitives.Rect::new(
      x + w - thickness,
      y + thickness,
      thickness,
      h - 2.0 * thickness,
    ).unwrap(),
  ]
  for i = 0; i < strips.length(); i = i + 1 {
    items.push(
      @scene.SceneItem::quad(
        id * 10 + (i + 1).to_uint64(),
        strips[i],
        ink,
        @scene.AffineTransform::identity(),
        1.0,
        clip,
      ).unwrap(),
    )
  }
}

///|
fn scrollable_snapshot(
  prepainted : @element.Prepainted,
  scale : Double,
  hovered : Bool,
) -> @scene.SceneSnapshot {
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  let texts = labels()
  let black = color(0, 0, 0)
  for item in base.items() {
    match item {
      @scene.QuadItem(id~, bounds~, color~, clip_chain_id~, ..) =>
        if id == 2 || id == 6 || id == 8 {
          let index = if id == 2 { 0 } else if id == 6 { 1 } else { 2 }
          items.push(
            @scene.SceneItem::text(
              id,
              bounds,
              texts[index],
              16.0,
              black,
              @scene.AffineTransform::identity(),
              1.0,
              clip_chain_id,
            ).unwrap(),
          )
        } else if id == 3 || id == 5 {
          let opacity = if id == 3 { 0.05 } else if hovered { 0.2 } else { 0.1 }
          items.push(
            @scene.SceneItem::quad(
              id,
              bounds,
              color,
              @scene.AffineTransform::identity(),
              opacity,
              clip_chain_id,
            ).unwrap(),
          )
          append_border(items, id, bounds, color, clip_chain_id, scale)
        } else {
          items.push(item)
        }
      _ => items.push(item)
    }
  }
  @scene.SceneSnapshot::new(
    base.viewport(),
    scale,
    base.resources(),
    base.clip_chains(),
    items,
  ).unwrap()
}

///|
fn viewport_json(viewport : @element.ScrollViewport) -> String {
  let bounds = viewport.bounds()
  let offset = viewport.offset()
  let maximum = viewport.max_offset()
  "{\"id\":\{viewport.id()},\"bounds\":{\"x\":\{bounds.left()},\"y\":\{bounds.top()},\"width\":\{bounds.size().width()},\"height\":\{bounds.size().height()}},\"offset\":{\"x\":\{offset.x()},\"y\":\{offset.y()}},\"max_offset\":{\"x\":\{maximum.x()},\"y\":\{maximum.y()}}}"
}

///|
#export_name("scrollable_frame")
pub fn scrollable_frame(widths : Array[Double], scale : Double) -> String {
  if widths.length() != 3 || !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  // This source's three short labels fit on one line. General text wrapping is
  // outside this bounded port; invalid metrics never silently truncate a label.
  let available = [468.0, 1966.0, 434.0]
  for i = 0; i < widths.length(); i = i + 1 {
    if !(widths[i] > 0.0 && widths[i] <= available[i]) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  let s = scrollable_state.val
  let prepainted = scrollable_layout(s, widths, scale)
  let tree = prepainted.tree()
  let outer = tree.scroll_viewport(1).unwrap()
  let inner = tree.scroll_viewport(4).unwrap()
  s.outer = outer.offset()
  s.inner = inner.offset()
  s.tree = Some(tree)
  s.hovered = pointer_hover(tree, s.pointer)
  let snapshot = scrollable_snapshot(prepainted, scale, s.hovered)
  let updates = s.updates.map(viewport_json)
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"browser_pointer_delivery\",\"browser_pixel_wheel_delivery\"],\"scrollable\":{\"hovered\":\{s.hovered},\"viewports\":[\{viewport_json(outer)},\{viewport_json(inner)}],\"updates\":[\{updates.join(",")}],\"offset_convention\":\"positive content offsets from actual MoonBit core\",\"evidence\":\"source-derived; Rust browser comparison pending\"}}"
}
