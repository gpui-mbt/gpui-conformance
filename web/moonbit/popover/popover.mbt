///|
// Source5a popover.rs, blob 7678a6a3ed865d9874b72cb99b473a115591d35c.
// Host supplies actual-font prefix widths only. All line breaks, intrinsic
// dimensions, anchors, deferred order, hit testing and state live here.
// Canvas/Cosmic shaping, rounded borders and shadow kernels are NOT parity claims.
priv struct PopoverState {
  parent : Ref[Bool]
  child : Ref[Bool]
  primary : Ref[@button.Button?]
  secondary : Ref[@button.Button?]
  mut frame : @element.PointerOutsideFrame?
  mut tree : @element.ElementTree?
  mut metrics : Array[Array[Double]]
  mut viewport : (Double, Double, Double)?
}

///|
fn initial_state() -> PopoverState {
  { parent: Ref(false), child: Ref(false),
    primary: Ref(None), secondary: Ref(None),
    frame: None, tree: None, metrics: [], viewport: None }
}

///|
let popover_state : Ref[PopoverState] = Ref(initial_state())

///|
fn source_texts() -> Array[String] {
  ["Opened Popover", "Open Popover",
    "Here is an example text rendered, to ensure the Popover will float above this contents.",
    "Child Popover",
    "This is a default opened Popover, we can use deferred to render it in a floating layer.",
    "This is first level Popover, we can use deferred to render it in a floating layer.\nClick outside to close.",
    "This is second level Popover with nested deferred!"]
}

///|
fn source_segments() -> Array[String] {
  let texts = source_texts()
  [texts[0], texts[1], texts[2], texts[3], texts[4],
    "This is first level Popover, we can use deferred to render it in a floating layer.",
    "Click outside to close.", texts[6]]
}

///|
fn quote(text : String) -> String { @json.to_json(text).stringify() }

///|
#export_name("popover_metadata")
pub fn popover_metadata() -> String {
  let runs : Array[String] = []
  let texts = source_texts()
  for i = 0; i < texts.length(); i = i + 1 {
    let size = if i < 3 { 16 } else { 14 }
    runs.push("{\"text\":\{quote(texts[i])},\"font_size\":\{size},\"weight\":400,\"style\":\"normal\"}")
  }
  "{\"id\":\"popover\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":true,\"runs\":[\{runs.join(",")}],\"source_blob\":\"7678a6a3ed865d9874b72cb99b473a115591d35c\",\"metrics_contract\":\"eight LF-separated actual-font shaped-prefix arrays in source order; logical CSS pixels\",\"conformance\":\"unverified\"}"
}

///|
#export_name("popover_cancel")
pub fn popover_cancel() -> Unit {
  let state = popover_state.val
  state.primary.val = state.primary.val.map(button => button.cancel_press())
  state.secondary.val = state.secondary.val.map(button => button.cancel_press())
  state.frame = None
  state.tree = None
}

///|
#export_name("popover_reset")
pub fn popover_reset() -> Unit { popover_state.val = initial_state() }

///|
fn snap_authored(value : Double, scale : Double) -> Double {
  (value * scale - 0.5).ceil() / scale
}

///|
fn border_width(scale : Double) -> Double {
  let width = snap_authored(1, scale)
  if width < 1 / scale { 1 / scale } else { width }
}

///|
fn paragraph_width(scale : Double) -> Double {
  snap_authored(384, scale) - 2 * snap_authored(12, scale) - 2 * border_width(scale)
}

///|
fn line_height(font_size : Double, scale : Double) -> Double {
  // Source RelativeLength::phi = 1.618034; authored positive device snapping.
  // Portable arithmetic stays Double; binary32 shaping is an explicit boundary.
  snap_authored(font_size * 1.618034, scale)
}

///|
priv struct TextBlock {
  lines : Array[String]
  width : Double
  height : Double
  line_height : Double
  font_size : Double
  white : Bool
}

///|
fn join_chars(chars : Array[Char], start : Int, end : Int) -> String {
  let mut result = ""
  for i = start; i < end; i = i + 1 { result = result + chars[i].to_string() }
  result
}

///|
fn word_char(c : Char) -> Bool {
  c.is_ascii_alphabetic() || c.is_ascii_digit() ||
    "-_.'$%@#^~,=:;!)]}\"".to_array().contains(c)
}

///|
fn wrap_segment(text : String, prefixes : Array[Double], budget : Double) -> Array[String] {
  let chars = text.to_array()
  let lines : Array[String] = []
  let mut start = 0
  let mut candidate = -1
  let mut seen = false
  for i = 0; i < chars.length(); i = i + 1 {
    let c = chars[i]
    if seen && c != ' ' && (!word_char(c) || (i > 0 && chars[i - 1] == ' ')) {
      candidate = i
    }
    if c != ' ' { seen = true }
    if budget > 0 && prefixes[i + 1] - prefixes[start] > budget && i > start {
      let end = if candidate > start { candidate } else { i }
      lines.push(join_chars(chars, start, end))
      start = end
      candidate = -1
    }
  }
  lines.push(join_chars(chars, start, chars.length()))
  lines
}

///|
fn text_block(indices : Array[Int], prefixes : Array[Array[Double]],
  budget : Double, font_size : Double, scale : Double, white : Bool,
) -> TextBlock {
  let texts = source_segments()
  let lines : Array[String] = []
  let mut width = 0.0
  for index in indices {
    for line in wrap_segment(texts[index], prefixes[index], budget) { lines.push(line) }
    let total = prefixes[index][prefixes[index].length() - 1]
    // Pinned WrappedLineLayout::width is min(unwrapped, wrap_width), not
    // maximum chosen line width. Do not feed observed popup bounds back here.
    let measured = if budget > 0 && total > budget { budget } else { total }
    if measured > width { width = measured }
  }
  let height = line_height(font_size, scale)
  { lines, width: width.ceil(), height: height * lines.length().to_double(),
    line_height: height, font_size, white }
}

///|
fn size(width : Double, height : Double) -> @primitives.Size {
  @primitives.Size::new(width, height).unwrap()
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
}

///|
fn auto(id : UInt64, width : Double, height : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(id,
    @layout.Dimension::auto(), @layout.Dimension::auto(), size(width, height),
  ).with_flex(0, 0).unwrap())
}

///|
fn color(channel : Int) -> @primitives.Color {
  @primitives.Color::rgba(channel, channel, channel, 255).unwrap()
}

///|
fn text_leaf(id : UInt64, block : TextBlock) -> @element.Element {
  auto(id, block.width, block.height).with_pointer_events(false)
    .with_background(Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()))
}

///|
fn trigger(id : UInt64, leaf : UInt64, block : TextBlock) -> @element.Element {
  auto(id, 0, 0).with_background(Some(color(0)))
    .with_children_style(column().with_insets(
      @layout.Insets::new(4, 12, 4, 12).unwrap(), @layout.Insets::zero()))
    .with_child(text_leaf(leaf, block))
}

///|
fn popup_style() -> @layout.FlexTreeStyle {
  column().with_insets(@layout.Insets::all(12).unwrap(), @layout.Insets::all(1).unwrap())
    .with_align(@layout.AlignItems::center()).with_justify(@layout.JustifyContent::center())
}

///|
fn popup(id : UInt64, fixed : Bool) -> @element.Element {
  let node = if fixed {
    @element.Element::new(@layout.FlexItem::new(id,
      @layout.Dimension::points(384).unwrap(), @layout.Dimension::auto(), size(0, 0),
    ).with_flex(0, 0).unwrap())
  } else { auto(id, 0, 0) }
  node.with_background(Some(color(255))).with_children_style(
    if fixed { popup_style().with_gap(12).unwrap() } else { popup_style() })
}

///|
fn attachment(id : UInt64, leaf : UInt64, content : @element.Element, priority : Int) -> @element.Element {
  @element.Element::anchored_after_measured_leaf(id, leaf, content,
    @element.TopLeft, @element.Local, @primitives.Point::new(0, 0).unwrap(), margin=8,
  ).unwrap().deferred(priority~).unwrap()
}

///|
fn build_view(state : PopoverState, blocks : Map[UInt64, TextBlock]) -> @element.Element {
  let default_popup = popup(6, true).with_child(text_leaf(7, blocks.get(7).unwrap()))
  let opened = trigger(3, 4, blocks.get(4).unwrap())
    .with_child(attachment(5, 4, default_popup, 0))
  let mut primary = trigger(8, 9, blocks.get(9).unwrap())
  if state.parent.val {
    let mut secondary = trigger(14, 15, blocks.get(15).unwrap())
    if state.child.val {
      let child = popup(17, false).with_child(text_leaf(18, blocks.get(18).unwrap()))
      secondary = secondary.with_child(attachment(16, 15, child, 2))
    }
    // mt_2 is independently authored flow space, not the parent gap_3.
    let margin = auto(13, 0, 0).with_pointer_events(false)
      .with_children_style(column().with_insets(
        @layout.Insets::new(8, 0, 0, 0).unwrap(), @layout.Insets::zero()))
      .with_child(secondary)
    let parent = popup(11, true).with_child(text_leaf(12, blocks.get(12).unwrap()))
      .with_child(margin)
    primary = primary.with_child(attachment(10, 9, parent, 1))
  }
  let row = auto(2, 0, 0).with_pointer_events(false)
    .with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::row()).with_gap(16).unwrap())
    .with_child(opened).with_child(primary)
  let mut root = @element.Element::root(1, column().with_gap(12).unwrap()
    .with_align(@layout.AlignItems::center()).with_justify(@layout.JustifyContent::center()))
    .with_background(Some(color(255))).with_child(row)
    .with_child(text_leaf(19, blocks.get(19).unwrap()))
  for (id, red, green, blue) in [(20UL, 255, 0, 0), (21UL, 255, 255, 0),
    (22UL, 0, 0, 255), (23UL, 0, 128, 0)] {
    root = root.with_child(auto(id, 480, 8).with_pointer_events(false)
      .with_background(Some(@primitives.Color::rgba(red, green, blue, 64).unwrap())))
  }
  root
}

///|
fn valid_inputs(width : Double, height : Double, scale : Double, prefixes : Array[Array[Double]]) -> Bool {
  if !(width >= 1 && width <= 8192 && height >= 1 && height <= 8192 && scale >= 0.0625 && scale <= 8) {
    return false
  }
  if snap_authored(width, scale) <= 0 || snap_authored(height, scale) <= 0 { return false }
  let texts = source_segments()
  if prefixes.length() != texts.length() { return false }
  for i = 0; i < texts.length(); i = i + 1 {
    let values = prefixes[i]
    if values.length() != texts[i].to_array().length() + 1 || values[0] != 0 { return false }
    for j = 1; j < values.length(); j = j + 1 {
      if !(values[j] > values[j - 1] && values[j] <= 16384) { return false }
    }
  }
  true
}

///|
fn rect_json(bounds : @primitives.Rect) -> String {
  "{\"x\":\{bounds.left()},\"y\":\{bounds.top()},\"width\":\{bounds.size().width()},\"height\":\{bounds.size().height()}}"
}

///|
fn paint_text(prepared : @element.Prepainted, blocks : Map[UInt64, TextBlock], scale : Double) -> @scene.SceneSnapshot {
  let base = prepared.paint_snapshot(scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match (item, blocks.get(item.id())) {
      (@scene.QuadItem(id~, bounds~, transform~, opacity~, clip_chain_id~, ..), Some(block)) => {
        for i = 0; i < block.lines.length(); i = i + 1 {
          let y = bounds.top() + i.to_double() * block.line_height
          let line_bounds = @primitives.Rect::new(bounds.left(), y, bounds.size().width(), block.line_height).unwrap()
          items.push(@scene.SceneItem::text_run(id * 1024 + i.to_uint64(), line_bounds,
            @primitives.Point::new(bounds.left(), y).unwrap(), block.lines[i], block.font_size,
            color(if block.white { 255 } else { 0 }), transform, opacity, clip_chain_id).unwrap())
        }
      }
      _ => items.push(item)
    }
  }
  @scene.SceneSnapshot::new(base.viewport(), scale, base.resources(), base.clip_chains(), items).unwrap()
}

///|
fn text_blocks(width : Double, scale : Double, prefixes : Array[Array[Double]]) -> Map[UInt64, TextBlock] {
  let budget = paragraph_width(scale)
  let blocks : Map[UInt64, TextBlock] = Map([])
  for (id, index, font, white) in [(4UL, 0, 16.0, true), (9UL, 1, 16.0, true),
    (15UL, 3, 14.0, true), (18UL, 7, 14.0, false)] {
    blocks.set(id, text_block([index], prefixes, 0, font, scale, white))
  }
  blocks.set(7, text_block([4], prefixes, budget, 14, scale, false))
  blocks.set(12, text_block([5, 6], prefixes, budget, 14, scale, false))
  blocks.set(19, text_block([2], prefixes, snap_authored(width, scale), 16, scale, false))
  blocks
}

///|
fn measured_button(previous : @button.Button?, id : UInt64,
  bounds : @primitives.Rect, label : String,
) -> Result[@button.Button, @button.ButtonError] {
  match previous {
    Some(button) => button.with_bounds(bounds)
    None => @button.Button::new(id, bounds, label)
  }
}

///|
#export_name("popover_frame")
pub fn popover_frame(width : Double, height : Double, scale : Double, prefixes : Array[Array[Double]]) -> String {
  let state = popover_state.val
  if !valid_inputs(width, height, scale, prefixes) {
    popover_cancel()
    state.viewport = None
    return "{\"ok\":false,\"error\":\"invalid_metrics_or_viewport\"}"
  }
  let viewport = (width, height, scale)
  if state.viewport != Some(viewport) || state.metrics != prefixes { popover_cancel() }
  state.metrics = prefixes.map(values => values.map(value => value))
  state.viewport = Some(viewport)
  let blocks = text_blocks(width, scale, prefixes)
  let prepared = build_view(state, blocks).request_layout_with_device_scale(size(width, height), scale)
    .unwrap().prepaint().unwrap()
  let tree = prepared.tree()
  // The bounded core Button requires >=24px dimensions. Construct lazily
  // from actual source layout, never from dummy/observed/hard-coded geometry.
  // Unsupported numeric inputs fail closed rather than enlarging the hit area.
  let primary = match measured_button(state.primary.val, 8, tree.node(8).unwrap().bounds(), "Open Popover") {
    Ok(button) => button
    Err(_) => {
      popover_cancel()
      return "{\"ok\":false,\"error\":\"unsupported_button_bounds\"}"
    }
  }
  let secondary = if state.parent.val {
    match measured_button(state.secondary.val, 14, tree.node(14).unwrap().bounds(), "Child Popover") {
      Ok(button) => Some(button)
      Err(_) => {
        popover_cancel()
        return "{\"ok\":false,\"error\":\"unsupported_button_bounds\"}"
      }
    }
  } else { None }
  state.primary.val = Some(primary)
  state.secondary.val = secondary
  state.tree = Some(tree)
  let registrations : Array[UInt64] = if state.child.val { [17UL] } else if state.parent.val { [11UL] } else { [] }
  state.frame = Some(@element.PointerOutsideFrame::new(tree, registrations).unwrap())
  let scene = paint_text(prepared, blocks, scale)
  let decorations : Array[String] = []
  let fills : Array[String] = []
  let shadows : Array[String] = []
  let bounds : Array[String] = []
  let lines : Array[String] = []
  for id in [6UL, 11UL, 17UL] {
    if tree.node(id) is Some(_) {
      let blue = id == 17UL
      decorations.push("{\"id\":\{id},\"radius\":6,\"border\":\{quote(if blue { "#0000ff" } else { "#000000" })},\"border_source\":\"device_snapped_1px\",\"border_width\":\{border_width(scale)},\"border_opacity\":\{if blue { 1.0 } else { 0.1 }},\"border_style\":\"solid\"}")
      fills.push("{\"id\":\{id},\"radius\":6}")
      shadows.push("{\"id\":\{id},\"kind\":\"shadow_lg\"}")
    }
  }
  for id = 1UL; id <= 23UL; id = id + 1 {
    match tree.node(id) {
      None => ()
      Some(node) => {
        bounds.push("\{quote(id.to_string())}:\{rect_json(node.bounds())}")
        match blocks.get(id) {
          None => ()
          Some(block) => {
            let text_lines = block.lines.map(quote)
            lines.push("\{quote(id.to_string())}:[\{text_lines.join(",")}]")
          }
        }
      }
    }
  }
  let registration_json = registrations.map(id => id.to_string()).join(",")
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"rounded_fills\":[\{fills.join(",")}],\"shadows\":[\{shadows.join(",")}],\"conformance\":\"unverified\",\"popover\":{\"parent_open\":\{state.parent.val},\"child_open\":\{state.child.val},\"bounds\":{\{bounds.join(",")}},\"lines\":{\{lines.join(",")}},\"registrations\":[\{registration_json}],\"comparison_profile_match\":false},\"host_extensions\":[\"actual_font_prefix_metrics\",\"canvas_text_rasterization\",\"canvas_rounded_border\",\"canvas_shadow_lg_approximation\"],\"unverified\":[\"Canvas_vs_Cosmic_shaping\",\"prefix_subtraction_wrapping\",\"full_image\",\"shadow_kernel\",\"native\"]}"
}

///|
#export_name("popover_pointer")
pub fn popover_pointer(kind : String, x : Double, y : Double, button : Int) -> Bool {
  let state = popover_state.val
  let frame = match state.frame { Some(frame) => frame; None => return false }
  let position = match @primitives.Point::new(x, y) { Ok(point) => point; Err(_) => return false }
  let pointer_button = match button {
    0 => @primitives.Primary
    1 => @primitives.Middle
    2 => @primitives.Secondary
    3 => @primitives.Back
    4 => @primitives.Forward
    _ => return false
  }
  let modifiers = @primitives.Modifiers::none()
  let event = match kind {
    "down" => @primitives.PointerButtonPressed(position~, button=pointer_button, modifiers~)
    "up" => @primitives.PointerButtonReleased(position~, button=pointer_button, modifiers~)
    _ => return false
  }
  let changed = Ref(false)
  frame.dispatch_input_with(event, (context, _) => {
    if context.current_target() == 17UL {
      state.child.val = false
      changed.val = true
    } else if context.current_target() == 11UL {
      state.parent.val = false
      state.child.val = false
      changed.val = true
    }
    Ok(())
  }, (context, routed_event) => {
    if context.phase() == @element.Bubble {
      let target = context.current_target()
      if target == 8UL || target == 14UL {
        let button = if target == 8UL { state.primary } else { state.secondary }
        match button.val {
          None => ()
          Some(current) => {
            let before = current.is_pressed()
            let (next, effect) = current.handle_input(routed_event)
            button.val = Some(next)
            if before != next.is_pressed() { changed.val = true }
            if effect.effect() == @button.Activated {
              if target == 8UL { state.parent.val = true } else { state.child.val = true }
              changed.val = true
            }
          }
        }
      }
    }
    Ok(())
  }).unwrap() |> ignore
  // Release outside a trigger must end its gesture even when it was not a
  // routed target. Cancellation never invents an activation.
  if kind == "up" && button == 0 {
    if state.primary.val.map(button => button.is_pressed()).unwrap_or(false) ||
      state.secondary.val.map(button => button.is_pressed()).unwrap_or(false) { changed.val = true }
    state.primary.val = state.primary.val.map(button => button.cancel_press())
    state.secondary.val = state.secondary.val.map(button => button.cancel_press())
  }
  // The immutable registry used above is never rebuilt/redispatched mid-event.
  if changed.val { state.frame = None }
  changed.val
}
