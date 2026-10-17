///|
// Source: focus_visible.rs, blob c5b3d5dfec3a189d088a621baff55eb55a121b6c.
priv struct FocusVisibleState {
  mut tree : @element.ElementTree?
  mut scale : Double?
  mut modality : @element.InputModality
  mut pointer : @primitives.Point?
  mut message : String
  mut pending_keyboard : @element.FocusOwner?
  pending_mouse : Array[Bool]
}

///|
fn initial_state() -> FocusVisibleState {
  {
    tree: None,
    scale: None,
    modality: @element.Mouse,
    pointer: None,
    message: "Try clicking vs tabbing! Click shows no border, Tab shows border.",
    pending_keyboard: None,
    pending_mouse: [false, false, false],
  }
}

///|
let focus_visible_state : Ref[FocusVisibleState] = Ref(initial_state())

///|
fn button_ids() -> Array[UInt64] {
  [12, 22, 32]
}

///|
fn text_ids() -> Array[UInt64] {
  [2, 4, 11, 13, 21, 23, 31, 33]
}

///|
fn texts(message : String) -> Array[String] {
  [
    "CSS focus-visible Demo", message, "1. Regular .focus() - always visible:", "Button with .focus() - always shows border when focused",
    "2. New .focus_visible() - only keyboard:", "Button with .focus_visible() - only shows border with keyboard",
    "3. Both .focus() (yellow) and .focus_visible() (green):", "Button with both .focus() and .focus_visible()",
  ]
}

///|
fn font_sizes() -> Array[Double] {
  [24, 16, 14, 16, 14, 16, 14, 16]
}

///|
fn font_weight(index : Int32) -> Int32 {
  if index == 0 || index == 2 || index == 4 || index == 6 {
    700
  } else {
    400
  }
}

///|
fn line_height(font_size : Double, scale : Double) -> Double {
  // TextLayout::layout uses Window::pixel_snap on phi * font size before
  // measuring the layout node. GPUI rounds exact halves toward zero.
  (font_size * 1.618033988749895 * scale - 0.5).ceil() / scale
}

///|
fn quote(value : String) -> String {
  @json.to_json(value).stringify()
}

///|
fn runs_json(state : FocusVisibleState) -> String {
  let labels = texts(state.message)
  let sizes = font_sizes()
  let ids = text_ids()
  let scale = state.scale.unwrap_or(1.0)
  let runs : Array[String] = []
  for index = 0; index < labels.length(); index = index + 1 {
    runs.push(
      "{\"id\":\{ids[index]},\"text\":\{quote(labels[index])},\"font_size\":\{sizes[index]},\"font_weight\":\{font_weight(index)},\"line_height\":\{line_height(sizes[index], scale)}}",
    )
  }
  "[\{runs.join(",")}]"
}

///|
#export_name("focus_visible_metadata")
pub fn focus_visible_metadata() -> String {
  "{\"id\":\"focus_visible\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":true,\"runs\":\{runs_json(initial_state())},\"source_blob\":\"c5b3d5dfec3a189d088a621baff55eb55a121b6c\",\"metrics_contract\":\"eight shaped widths in title,message,label1,button1,label2,button2,label3,button3 order; session-fixed device scale\",\"conformance\":\"unverified\"}"
}

///|
#export_name("focus_visible_content")
pub fn focus_visible_content() -> String {
  let state = focus_visible_state.val
  "{\"message\":\{quote(state.message)},\"runs\":\{runs_json(state)}}"
}

///|
#export_name("focus_visible_reset")
pub fn focus_visible_reset() -> Unit {
  // Reset is the only operation that discards the authoritative tree lineage.
  focus_visible_state.val = initial_state()
}

///|
fn color(red : Int32, green : Int32, blue : Int32) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn column(padding : Double, gap : Double) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  .with_align(@layout.AlignItems::stretch())
  .with_insets(@layout.Insets::all(padding).unwrap(), @layout.Insets::zero())
  .with_gap(gap)
  .unwrap()
}

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
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
      @primitives.Size::new(0, 0).unwrap(),
    )
    .with_flex(0, 0)
    .unwrap(),
  )
}

///|
fn text_node(
  id : UInt64,
  width : Double,
  font_size : Double,
  scale : Double,
) -> @element.Element {
  node(id, fixed(line_height(font_size, scale)), fixed(width))
  .with_background(Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()))
  .with_pointer_events(false)
}

///|
fn focus_layout(widths : Array[Double], scale : Double) -> @element.Prepainted {
  let auto = @layout.Dimension::auto()
  let mut sections = node(5, auto, auto).with_children_style(column(0, 16))
  for index = 0; index < 3; index = index + 1 {
    let group_id = ((index + 1) * 10).to_uint64()
    let label = text_node(group_id + 1, widths[index * 2 + 2], 14, scale)
    let button = node(group_id + 2, fixed(64), auto)
      .with_children_style(
        column(0, 0)
        .with_align(@layout.AlignItems::center())
        .with_justify(@layout.JustifyContent::center()),
      )
      .with_background(Some(color(37, 99, 235)))
      .with_focusable(true)
      .with_tab_index(index + 1)
      .with_tab_stop(true)
      .with_child(text_node(group_id + 3, widths[index * 2 + 3], 16, scale))
    sections = sections.with_child(
      node(group_id, auto, auto)
      .with_children_style(column(0, 8))
      .with_child(label)
      .with_child(button),
    )
  }
  @element.Element::root(1, column(32, 24))
  .with_background(Some(color(243, 244, 246)))
  .with_focusable(true)
  .with_tab_index(0)
  .with_tab_stop(false)
  .with_child(text_node(2, widths[0], 24, scale))
  .with_child(
    node(3, auto, auto)
    .with_children_style(column(16, 0))
    .with_background(Some(color(219, 234, 254)))
    .with_child(text_node(4, widths[1], 16, scale)),
  )
  .with_child(sections)
  .request_layout_with_device_scale(
    @primitives.Size::new(800, 600).unwrap(),
    scale,
  )
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn focus_target(state : FocusVisibleState, target : UInt64) -> Bool {
  let tree = match state.tree {
    Some(tree) => tree
    None => return false
  }
  // Window::focus is a no-op for the same handle. Core with_focus deliberately
  // allocates a new acquisition, so never call it for an already focused node.
  if tree.is_focused(target) {
    return true
  }
  match tree.with_focus(target) {
    Ok(focused) => {
      state.tree = Some(focused)
      true
    }
    Err(_) => false
  }
}

///|
fn hovered(state : FocusVisibleState, id : UInt64) -> Bool {
  if !state.modality.allows_hover() {
    return false
  }
  match (state.tree, state.pointer) {
    (Some(tree), Some(position)) =>
      tree.dispatch_pointer(position).bubble().contains(id)
    _ => false
  }
}

///|
fn ring(state : FocusVisibleState, id : UInt64) -> String? {
  let tree = match state.tree {
    Some(tree) => tree
    None => return None
  }
  // Source refinement order is .focus(), then .focus_visible().
  if (id == 22 || id == 32) && tree.is_focus_visible(id, state.modality) {
    Some("#10b981")
  } else if (id == 12 || id == 32) && tree.is_focused(id) {
    Some("#fbbf24")
  } else {
    None
  }
}

///|
fn click(state : FocusVisibleState, id : UInt64) -> Unit {
  match id {
    12 => state.message = "Clicked button 1 - focus border is visible!"
    22 => state.message = "Clicked button 2 - no border! Try Tab instead."
    32 => state.message = "Clicked button 3 - yellow border. Tab shows green!"
    _ => ()
  }
}

///|
fn pointer_button(button : Int32) -> @primitives.MouseButton? {
  match button {
    0 => Some(@primitives.Primary)
    1 => Some(@primitives.Middle)
    2 => Some(@primitives.Secondary)
    3 => Some(@primitives.Back)
    4 => Some(@primitives.Forward)
    _ => None
  }
}

///|
#export_name("focus_visible_pointer")
pub fn focus_visible_pointer(
  kind : String,
  x : Double,
  y : Double,
  button : Int32,
  shift : Bool,
  control : Bool,
  alt : Bool,
  meta : Bool,
) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  let modifiers = @primitives.Modifiers::new(shift~, control~, alt~, meta~)
  let event = match kind {
    "move" => @primitives.PointerMoved(position~)
    "down" | "up" => {
      let button = match pointer_button(button) {
        Some(button) => button
        None => return false
      }
      if kind == "down" {
        @primitives.PointerButtonPressed(position~, button~, modifiers~)
      } else {
        @primitives.PointerButtonReleased(position~, button~, modifiers~)
      }
    }
    _ => return false
  }
  let state = focus_visible_state.val
  let tree = match state.tree {
    Some(tree) => tree
    None => return false
  }
  state.modality = state.modality.after_input(event)
  state.pointer = Some(position)
  let path = tree.dispatch_input(event).bubble()
  let ids = button_ids()
  if kind == "down" {
    for id in path {
      if tree.node(id).unwrap().is_focusable() {
        if !focus_target(state, id) {
          return false
        }
        break
      }
    }
    // Source click listeners retain primary presses only. A secondary press
    // can focus, but neither creates nor clears an existing primary press.
    if button == 0 {
      for index = 0; index < ids.length(); index = index + 1 {
        if path.contains(ids[index]) {
          state.pending_mouse[index] = true
        }
      }
    }
  } else if kind == "up" {
    for index = 0; index < ids.length(); index = index + 1 {
      let pending = state.pending_mouse[index]
      state.pending_mouse[index] = false
      // Upstream checks the recorded down button, not up/down identity.
      if pending && hovered(state, ids[index]) {
        click(state, ids[index])
      }
    }
  }
  true
}

///|
#export_name("focus_visible_leave")
pub fn focus_visible_leave() -> Bool {
  let state = focus_visible_state.val
  if state.tree is None {
    return false
  }
  state.pointer = None
  true
}

///|
fn key(label : String) -> @primitives.Key {
  match label {
    "Tab" => @primitives.Tab
    "Enter" => @primitives.Enter
    " " | "Space" => @primitives.Space
    "Escape" => @primitives.Escape
    "ArrowLeft" => @primitives.ArrowLeft
    "ArrowRight" => @primitives.ArrowRight
    "ArrowUp" => @primitives.ArrowUp
    "ArrowDown" => @primitives.ArrowDown
    "Home" => @primitives.Home
    "End" => @primitives.End
    "PageUp" => @primitives.PageUp
    "PageDown" => @primitives.PageDown
    "Backspace" => @primitives.Backspace
    "Delete" => @primitives.Delete
    _ => @primitives.Character(label)
  }
}

///|
#export_name("focus_visible_key")
pub fn focus_visible_key(
  label : String,
  down : Bool,
  shift : Bool,
  control : Bool,
  alt : Bool,
  meta : Bool,
  repeat : Bool,
) -> Bool {
  if label.length() == 0 || label.length() > 128 {
    return false
  }
  let state = focus_visible_state.val
  let tree = match state.tree {
    Some(tree) => tree
    None => return false
  }
  let key = key(label)
  let modifiers = @primitives.Modifiers::new(shift~, control~, alt~, meta~)
  let event = if down {
    @primitives.KeyPressed(key~, modifiers~, repeat~)
  } else {
    @primitives.KeyReleased(key~, modifiers~)
  }
  state.modality = state.modality.after_input(event)
  let path = tree.dispatch_input(event).bubble()
  let activation = (key == @primitives.Enter || key == @primitives.Space) &&
    modifiers.is_empty()
  if down &&
    key == @primitives.Tab &&
    !control &&
    !alt &&
    !meta &&
    path.contains(1) {
    let next = if shift { tree.focus_prev() } else { tree.focus_next() }
    match next {
      Ok(focused) => state.tree = Some(focused)
      Err(_) => return false
    }
    state.pending_keyboard = None
    state.message = if shift {
      "Pressed Shift-Tab - focus-visible border should appear!"
    } else {
      "Pressed Tab - focus-visible border should appear!"
    }
  } else {
    let target = match tree.focused() {
      Some(id) => id
      None => return true
    }
    if button_ids().contains(target) && path.contains(target) {
      if down {
        state.pending_keyboard = if activation {
          tree.focus_owner()
        } else {
          None
        }
      } else {
        let pending = state.pending_keyboard
        state.pending_keyboard = None
        // Acquisition equality prevents focus-away/back ABA and intentionally
        // permits Space-down / Enter-up, as the source generation marker does.
        if activation && pending is Some(_) && pending == tree.focus_owner() {
          click(state, target)
        }
      }
    }
  }
  true
}

///|
#export_name("focus_visible_wheel")
pub fn focus_visible_wheel(
  x : Double,
  y : Double,
  dx : Double,
  dy : Double,
) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  let delta = match @primitives.Point::new(dx, dy) {
    Ok(value) => value
    Err(_) => return false
  }
  let state = focus_visible_state.val
  let tree = match state.tree {
    Some(tree) => tree
    None => return false
  }
  let event = @primitives.Scroll(
    position~,
    delta~,
    modifiers=@primitives.Modifiers::none(),
  )
  state.modality = state.modality.after_input(event)
  // There is no scrollable in this source. Routing is still core-owned, and
  // wheel cannot synthesize mouse modality or a click.
  ignore(tree.dispatch_input(event))
  true
}

///|
fn snapshot(
  prepainted : @element.Prepainted,
  state : FocusVisibleState,
  scale : Double,
) -> @scene.SceneSnapshot {
  let base = prepainted.paint_snapshot(scale).unwrap()
  let labels = texts(state.message)
  let ids = text_ids()
  let sizes = font_sizes()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match item {
      @scene.QuadItem(id~, bounds~, clip_chain_id~, ..) => {
        let mut text_index = -1
        for index = 0; index < ids.length(); index = index + 1 {
          if id == ids[index] {
            text_index = index
          }
        }
        if text_index >= 0 {
          let ink = if text_index == 0 {
            color(17, 24, 39)
          } else if text_index == 1 {
            color(30, 58, 138)
          } else if text_index % 2 == 0 {
            color(55, 65, 81)
          } else {
            color(255, 255, 255)
          }
          items.push(
            @scene.SceneItem::text(
              id,
              bounds,
              labels[text_index],
              sizes[text_index],
              ink,
              @scene.AffineTransform::identity(),
              1,
              clip_chain_id,
            ).unwrap(),
          )
        } else if button_ids().contains(id) && hovered(state, id) {
          items.push(
            @scene.SceneItem::quad(
              id,
              bounds,
              color(29, 78, 216),
              @scene.AffineTransform::identity(),
              1,
              clip_chain_id,
            ).unwrap(),
          )
        } else {
          items.push(item)
        }
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
fn state_json(state : FocusVisibleState) -> String {
  let tree = state.tree.unwrap()
  let buttons : Array[String] = []
  let ids = button_ids()
  for index = 0; index < ids.length(); index = index + 1 {
    let id = ids[index]
    let border = match ring(state, id) {
      Some(value) => quote(value)
      None => "null"
    }
    buttons.push(
      "{\"id\":\{id},\"index\":\{index + 1},\"focused\":\{tree.is_focused(id)},\"focus_visible\":\{tree.is_focus_visible(id, state.modality)},\"hovered\":\{hovered(state, id)},\"ring_color\":\{border},\"pending_primary\":\{state.pending_mouse[index]}}",
    )
  }
  let focused = match tree.focused() {
    Some(id) => id.to_string()
    None => "null"
  }
  let modality = if state.modality == @element.Keyboard {
    "keyboard"
  } else {
    "mouse"
  }
  let pending = match state.pending_keyboard {
    Some(owner) => owner.id().to_string()
    None => "null"
  }
  "{\"focused_id\":\{focused},\"root_focused\":\{tree.is_focused(1)},\"modality\":\{quote(modality)},\"message\":\{quote(state.message)},\"pending_keyboard_id\":\{pending},\"pending_keyboard_current\":\{state.pending_keyboard is Some(_) && state.pending_keyboard == tree.focus_owner()},\"buttons\":[\{buttons.join(",")}],\"evidence\":\"source-derived candidate; unchanged-Rust browser comparison pending\"}"
}

///|
#export_name("focus_visible_frame")
pub fn focus_visible_frame(widths : Array[Double], scale : Double) -> String {
  if widths.length() != 8 || !(scale > 0 && scale <= 4) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  // Every source string fits a single line. Reserve a possible 4px border on
  // either side of each button; wrapped text is outside this bounded profile.
  let available = [736.0, 704.0, 736.0, 728.0, 736.0, 728.0, 736.0, 728.0]
  for index = 0; index < widths.length(); index = index + 1 {
    if !(widths[index] > 0 && widths[index] <= available[index]) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  let state = focus_visible_state.val
  match state.scale {
    Some(previous) =>
      if previous != scale {
        return "{\"ok\":false,\"error\":\"scale_changed_requires_reset\"}"
      }
    None => ()
  }
  let prepainted = focus_layout(widths, scale)
  // Extremely small finite device scales can collapse measured lineboxes or
  // rounded panels. Reject those dimensions before retaining any input state.
  let paint_tree = prepainted.tree()
  for id in text_ids() {
    let bounds = paint_tree.node(id).unwrap().bounds()
    if bounds.size().width() <= 0 || bounds.size().height() <= 0 {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  for id in [3UL, 12UL, 22UL, 32UL] {
    let bounds = paint_tree.node(id).unwrap().bounds()
    if bounds.size().width() < 12 || bounds.size().height() < 12 {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  if state.tree is None {
    state.tree = Some(prepainted.tree().with_focus(1).unwrap())
    state.scale = Some(scale)
  }
  // Paint trees have fresh lineage. Never restore an old owner into them or
  // replace the input tree during redraw: only the eight text widths change.
  let scene = snapshot(prepainted, state, scale)
  let decorations : Array[String] = []
  for id in button_ids() {
    match ring(state, id) {
      Some(border) =>
        decorations.push(
          "{\"id\":\{id},\"radius\":6,\"border_width\":4,\"border\":\{quote(border)},\"border_style\":\"solid\"}",
        )
      None => ()
    }
  }
  let styles : Array[String] = []
  let ids = text_ids()
  for index = 0; index < ids.length(); index = index + 1 {
    styles.push(
      "{\"id\":\{ids[index]},\"weight\":\{font_weight(index)},\"style\":\"normal\",\"decoration\":\"none\"}",
    )
  }
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"rounded_fills\":[{\"id\":3,\"radius\":6},{\"id\":12,\"radius\":6},{\"id\":22,\"radius\":6},{\"id\":32,\"radius\":6}],\"text_styles\":[\{styles.join(",")}],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"font_weight_700_closest_bundled_face\",\"rounded_fills\",\"solid_4px_focus_borders\",\"browser_input_delivery\"],\"focus_visible\":\{state_json(state)}}"
}
