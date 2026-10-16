///|
// Source: tab_stop.rs, blob cc7c34a9979ce4027578ec2c358f503d944ee26f.
priv struct TabStopState {
  mut tree : @element.ElementTree?
  mut scale : Double?
  mut modality : @element.InputModality
  mut pointer : @primitives.Point?
  mut message : String
  mut pending_keyboard : @element.FocusOwner?
  pending_mouse : Array[Bool]
}

///|
fn initial_state() -> TabStopState {
  {
    tree: None,
    scale: None,
    modality: @element.Mouse,
    pointer: None,
    message: "Press `Tab`, `Shift-Tab` to switch focus.",
    pending_keyboard: None,
    pending_mouse: [false, false],
  }
}

///|
let tab_stop_state : Ref[TabStopState] = Ref(initial_state())

///|
fn card_ids() -> Array[UInt64] {
  [10, 11, 12, 13, 14]
}

///|
fn button_ids() -> Array[UInt64] {
  [20, 21]
}

///|
fn all_button_ids() -> Array[UInt64] {
  [20, 21, 101, 102, 103, 201, 202, 203]
}

///|
fn join_ids(first : Array[UInt64], second : Array[UInt64]) -> Array[UInt64] {
  let result : Array[UInt64] = []
  for id in first {
    result.push(id)
  }
  for id in second {
    result.push(id)
  }
  result
}

///|
fn text_ids() -> Array[UInt64] {
  [2, 50, 51, 52, 53, 54, 60, 61, 110, 111, 112, 210, 211, 212]
}

///|
fn texts(message : String) -> Array[String] {
  [
    message, "tab_index: 1", "tab_index: 2", "tab_index: 3", "tab_stop: false", "tab_index: 2",
    "Button 1", "Button 2", "Tab index [6, 1]", "Tab index [6, 2]", "Tab index [6, 3]",
    "Tab index [7, 1]", "Tab index [7, 2]", "Tab index [7, 3]",
  ]
}

///|
fn snap(value : Double, scale : Double) -> Double {
  (value * scale - 0.5).ceil() / scale
}

///|
fn line_height(font_size : Double, scale : Double) -> Double {
  snap(font_size * 1.618033988749895, scale)
}

///|
fn quote(value : String) -> String {
  @json.to_json(value).stringify()
}

///|
fn runs_json(state : TabStopState) -> String {
  let labels = texts(state.message)
  let ids = text_ids()
  let scale = state.scale.unwrap_or(1.0)
  let runs : Array[String] = []
  for index = 0; index < labels.length(); index = index + 1 {
    runs.push(
      "{\"id\":\{ids[index]},\"text\":\{quote(labels[index])},\"font_size\":16,\"font_weight\":400,\"line_height\":\{line_height(16, scale)}}",
    )
  }
  "[\{runs.join(",")}]"
}

///|
#export_name("tab_stop_metadata")
pub fn tab_stop_metadata() -> String {
  "{\"id\":\"tab_stop\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":true,\"runs\":\{runs_json(initial_state())},\"source_blob\":\"cc7c34a9979ce4027578ec2c358f503d944ee26f\",\"metrics_contract\":\"fourteen shaped widths in message, five source cards, two ordinary buttons, group1 children, group2 children order; session-fixed device scale\",\"conformance\":\"unverified\"}"
}

///|
#export_name("tab_stop_content")
pub fn tab_stop_content() -> String {
  let state = tab_stop_state.val
  "{\"message\":\{quote(state.message)},\"runs\":\{runs_json(state)}}"
}

///|
#export_name("tab_stop_reset")
pub fn tab_stop_reset() -> Unit {
  // Reset is the only operation that discards the authoritative tree lineage.
  tab_stop_state.val = initial_state()
}

///|
fn color(red : Int32, green : Int32, blue : Int32) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn flow(
  direction : @layout.FlowDirection,
  padding : Double,
  gap : Double,
) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(direction)
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
  main : @layout.Dimension,
  cross : @layout.Dimension,
  min_main~ : Double = 0,
  grow~ : Double = 0,
  shrink~ : Double = 1,
) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(id, main, cross, @primitives.Size::new(0, 0).unwrap())
    .with_main_limits(min_main, None)
    .unwrap()
    .with_flex(grow, shrink)
    .unwrap(),
  )
}

///|
fn text_node(
  id : UInt64,
  width : Double,
  scale : Double,
  in_row~ : Bool = false,
) -> @element.Element {
  let height = line_height(16, scale)
  node(
    id,
    fixed(if in_row { width } else { height }),
    fixed(if in_row { height } else { width }),
    shrink=0,
  )
  .with_background(Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()))
  .with_pointer_events(false)
}

///|
fn border_width(state : TabStopState, id : UInt64) -> Double {
  if !card_ids().contains(id) && !all_button_ids().contains(id) {
    return 0
  }
  let focused = match state.tree {
    Some(tree) => tree.is_focused(id)
    None => false
  }
  if focused && id != 13 {
    3
  } else {
    1
  }
}

///|
fn centered(border : Double) -> @layout.FlexTreeStyle {
  flow(@layout.FlowDirection::row(), 0, 0)
  .with_insets(@layout.Insets::zero(), @layout.Insets::all(border).unwrap())
  .with_align(@layout.AlignItems::center())
  .with_justify(@layout.JustifyContent::center())
}

///|
fn button(
  id : UInt64,
  text_id : UInt64,
  index : Int32,
  width : Double,
  scale : Double,
  state : TabStopState,
  ordinary~ : Bool,
) -> @element.Element {
  let border = snap(border_width(state, id), scale)
  let height = snap(40, scale)
  // Taffy floors flex-basis:0 by padding+border. Block children do not flex.
  node(
    id,
    if ordinary {
      fixed(2 * border)
    } else {
      fixed(40)
    },
    if ordinary {
      fixed(40)
    } else {
      @layout.Dimension::auto()
    },
    min_main=if ordinary { width + 2 * border } else { height },
    grow=if ordinary { 1 } else { 0 },
    shrink=if ordinary { 1 } else { 0 },
  )
  .with_children_style(centered(border))
  .with_background(Some(color(0, 0, 0)))
  .with_focusable(true)
  .with_tab_index(index)
  .with_tab_stop(true)
  .with_child(text_node(text_id, width, scale, in_row=true))
}

///|
fn tab_layout(
  widths : Array[Double],
  scale : Double,
  state : TabStopState,
) -> @element.Prepainted {
  let auto = @layout.Dimension::auto()
  let height = snap(40, scale)
  let line = line_height(16, scale)
  let mut root = @element.Element::root(
      1,
      flow(@layout.FlowDirection::column(), 16, 12),
    )
    .with_background(Some(color(255, 255, 255)))
    .with_focusable(true)
    .with_tab_index(0)
    .with_tab_stop(false)
    .with_child(text_node(2, widths[0], scale))
  let indices = [1, 2, 3, 0, 2]
  for index = 0; index < 5; index = index + 1 {
    let id = card_ids()[index]
    let border = snap(border_width(state, id), scale)
    let minimum = if line + 2 * border < height {
      line + 2 * border
    } else {
      height
    }
    // Taffy uses inner flex basis for scaled shrink, while gpui.mbt uses
    // outer basis. Lower that source rule explicitly, never observed y tables.
    let shrink = if height > 2 * border {
      (height - 2 * border) / height
    } else {
      0
    }
    root = root.with_child(
      node(id, fixed(40), auto, min_main=minimum, shrink~)
      .with_children_style(centered(border))
      .with_background(Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()))
      .with_focusable(true)
      .with_tab_index(indices[index])
      .with_tab_stop(index != 3)
      .with_child(
        text_node(text_ids()[index + 1], widths[index + 1], scale, in_row=true),
      ),
    )
  }
  root = root.with_child(
    node(30, auto, auto, min_main=height)
    .with_children_style(
      flow(@layout.FlowDirection::row(), 0, 12).with_align(
        @layout.AlignItems::center(),
      ),
    )
    .with_child(button(20, 60, 4, widths[6], scale, state, ordinary=true))
    .with_child(button(21, 61, 5, widths[7], scale, state, ordinary=true)),
  )
  for group = 0; group < 2; group = group + 1 {
    let id = ((group + 1) * 100).to_uint64()
    let group_index = group + 6
    // Bounded lowering of these source Block groups: three definite-height,
    // full-width blocks, no margins/gap and no flex growth or child shrink.
    let mut container = node(id, auto, auto, min_main=height * 3)
      .with_children_style(flow(@layout.FlowDirection::column(), 0, 0))
      .with_focusable(true)
      .with_tab_index(group_index)
      .with_tab_group_index(Some(group_index))
      .with_tab_stop(false)
    for child = 0; child < 3; child = child + 1 {
      let run = 8 + group * 3 + child
      container = container.with_child(
        button(
          id + (child + 1).to_uint64(),
          id + (child + 10).to_uint64(),
          child + 1,
          widths[run],
          scale,
          state,
          ordinary=false,
        ),
      )
    }
    root = root.with_child(container)
  }
  root
  .request_layout_with_device_scale(
    @primitives.Size::new(800, 600).unwrap(),
    scale,
  )
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn focus_target(state : TabStopState, target : UInt64) -> Bool {
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
fn hovered(state : TabStopState, id : UInt64) -> Bool {
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
fn click(state : TabStopState, id : UInt64) -> Unit {
  match id {
    20 => state.message = "You have clicked Button 1."
    21 => state.message = "You have clicked Button 2."
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
#export_name("tab_stop_pointer")
pub fn tab_stop_pointer(
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
  let state = tab_stop_state.val
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
#export_name("tab_stop_leave")
pub fn tab_stop_leave() -> Bool {
  let state = tab_stop_state.val
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
#export_name("tab_stop_key")
pub fn tab_stop_key(
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
  let state = tab_stop_state.val
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
      "You have pressed `Shift-Tab`."
    } else {
      "You have pressed `Tab`."
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
#export_name("tab_stop_wheel")
pub fn tab_stop_wheel(x : Double, y : Double, dx : Double, dy : Double) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  let delta = match @primitives.Point::new(dx, dy) {
    Ok(value) => value
    Err(_) => return false
  }
  let state = tab_stop_state.val
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
  state : TabStopState,
  scale : Double,
) -> @scene.SceneSnapshot {
  let base = prepainted.paint_snapshot(scale).unwrap()
  let labels = texts(state.message)
  let ids = text_ids()
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
          items.push(
            @scene.SceneItem::text(
              id,
              bounds,
              labels[text_index],
              16,
              if text_index >= 6 {
                color(255, 255, 255)
              } else {
                color(0, 0, 0)
              },
              @scene.AffineTransform::identity(),
              if id == 53 {
                0.4
              } else {
                1
              },
              clip_chain_id,
            ).unwrap(),
          )
        } else if id == 13 {
          items.push(
            @scene.SceneItem::quad(
              id,
              bounds,
              @primitives.Color::rgba(0, 0, 0, 0).unwrap(),
              @scene.AffineTransform::identity(),
              0.4,
              clip_chain_id,
            ).unwrap(),
          )
        } else {
          if card_ids().contains(id) && hovered(state, id) {
            // Separate background opacity from the subsequent solid border.
            items.push(
              @scene.SceneItem::quad(
                id + 4000,
                bounds,
                color(0, 0, 0),
                @scene.AffineTransform::identity(),
                0.1,
                clip_chain_id,
              ).unwrap(),
            )
          }
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
fn state_json(state : TabStopState) -> String {
  let tree = state.tree.unwrap()
  let nodes : Array[String] = []
  for id in join_ids(join_ids(card_ids(), all_button_ids()), [100, 200]) {
    let node = tree.node(id).unwrap()
    let group = match node.tab_group_index() {
      Some(value) => value.to_string()
      None => "null"
    }
    nodes.push(
      "{\"id\":\{id},\"tab_index\":\{node.tab_index()},\"tab_group_index\":\{group},\"tab_stop\":\{node.is_tab_stop()},\"focused\":\{tree.is_focused(id)},\"hovered\":\{id != 13 && card_ids().contains(id) && hovered(state, id)},\"border_width\":\{border_width(state, id)}}",
    )
  }
  let focused = match tree.focused() {
    Some(id) => id.to_string()
    None => "null"
  }
  let pending = match state.pending_keyboard {
    Some(owner) => owner.id().to_string()
    None => "null"
  }
  "{\"focused_id\":\{focused},\"root_focused\":\{tree.is_focused(1)},\"modality\":\{quote(if state.modality == @element.Keyboard { "keyboard" } else { "mouse" })},\"message\":\{quote(state.message)},\"pending_keyboard_id\":\{pending},\"pending_keyboard_current\":\{state.pending_keyboard is Some(_) && state.pending_keyboard == tree.focus_owner()},\"nodes\":[\{nodes.join(",")}],\"evidence\":\"source-derived candidate; paired unchanged-Rust browser comparison pending\"}"
}

///|
#export_name("tab_stop_frame")
pub fn tab_stop_frame(widths : Array[Double], scale : Double) -> String {
  if widths.length() != 14 || !(scale > 0 && scale <= 4) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  // All source strings are a single line. Bound the measured profile instead
  // of inventing wrapping, changed labels or viewport fitting.
  let available = [
    768.0, 762, 762, 762, 762, 762, 370, 370, 762, 762, 762, 762, 762, 762,
  ]
  for index = 0; index < widths.length(); index = index + 1 {
    if !(widths[index] > 0 && widths[index] <= available[index]) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  let state = tab_stop_state.val
  match state.scale {
    Some(previous) =>
      if previous != scale {
        return "{\"ok\":false,\"error\":\"scale_changed_requires_reset\"}"
      }
    None => ()
  }
  if snap(40, scale) < 8 || line_height(16, scale) <= 0 || snap(1, scale) <= 0 {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let prepainted = tab_layout(widths, scale, state)
  let paint_tree = prepainted.tree()
  for id in join_ids(join_ids(text_ids(), card_ids()), all_button_ids()) {
    let bounds = paint_tree.node(id).unwrap().bounds()
    if bounds.size().width() <= 0 || bounds.size().height() <= 0 {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  match state.tree {
    None => {
      state.tree = Some(paint_tree.with_focus(1).unwrap())
      state.scale = Some(scale)
    }
    Some(tree) =>
      match tree.with_layout_bounds(prepainted) {
        Ok(refreshed) => state.tree = Some(refreshed)
        Err(_) => return "{\"ok\":false,\"error\":\"incompatible_layout\"}"
      }
  }
  // Keep the live lineage and acquisition; import only compatible layout
  // bounds. Fresh paint trees never receive retained focus owners.
  let scene = snapshot(prepainted, state, scale)
  let decorations : Array[String] = []
  for id in join_ids(card_ids(), all_button_ids()) {
    let width = border_width(state, id)
    decorations.push(
      "{\"id\":\{id},\"radius\":0,\"border_width\":\{width},\"border\":\{quote(if width == 3 { "#0000ff" } else { "#000000" })},\"border_style\":\"solid\"}",
    )
  }
  let shadows : Array[String] = []
  for id in all_button_ids() {
    shadows.push("{\"id\":\{id},\"kind\":\"shadow_sm\"}")
  }
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"shadows\":[\{shadows.join(",")}],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"source_border_box_flex_lowering\",\"bounded_block_groups_lowering\",\"solid_3px_focus_borders\",\"canvas_shadow_sm_approximation\",\"browser_input_delivery\"],\"tab_stop\":\{state_json(state)}}"
}
