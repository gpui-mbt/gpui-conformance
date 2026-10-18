///|
// Unchanged drag_drop.rs, blob 8f038ef3308fee9b097e7289665c9fa47cd6945b.
// The real typed core owns admission, move-only activation and consumption.
priv struct DragInfo {
  ix : Int32
  color : @primitives.Color
  position : @primitives.Point
} derive(Eq)

///|
priv struct DragDropState {
  session : @element.DragSession[DragInfo]
  mut tree : @element.ElementTree?
  mut scale : Double?
  mut pointer : @primitives.Point?
  mut drop_on : DragInfo?
  mut drop_count : Int32
  mut last_outcome : String
  mut last_error : String?
}

///|
fn initial_state() -> DragDropState {
  {
    session: @element.DragSession::new(),
    tree: None,
    scale: None,
    pointer: None,
    drop_on: None,
    drop_count: 0,
    last_outcome: "unchanged",
    last_error: None,
  }
}

///|
let drag_drop_state : Ref[DragDropState] = Ref(initial_state())

///|
fn point(x : Double, y : Double) -> @primitives.Point {
  @primitives.Point::new(x, y).unwrap()
}

///|
fn color(r : Int32, g : Int32, b : Int32) -> @primitives.Color {
  @primitives.Color::rgba(r, g, b, 255).unwrap()
}

///|
fn transparent() -> @primitives.Color {
  @primitives.Color::rgba(0, 0, 0, 0).unwrap()
}

///|
fn colors() -> Array[@primitives.Color] {
  [color(0, 0, 255), color(255, 0, 0), color(0, 128, 0)]
}

///|
fn source_ids() -> Array[UInt64] {
  [10, 11, 12]
}

///|
fn labels() -> Array[String] {
  [
    "Drop & Drop", "Item (0)", "Item (1)", "Item (2)", "Drop items here", "Item 0",
    "Item 1", "Item 2",
  ]
}

///|
fn quote(value : String) -> String {
  @json.to_json(value).stringify()
}

///|
// GPUI metric rounding: exact half ties go toward zero, including negatives.
fn snap(value : Double, scale : Double) -> Double {
  if value < 0 {
    -(-value * scale - 0.5).ceil() / scale
  } else {
    (value * scale - 0.5).ceil() / scale
  }
}

///|
fn line_height(font_size : Double, scale : Double) -> Double {
  snap(font_size * 1.618033988749895, scale)
}

///|
#export_name("drag_drop_metadata")
pub fn drag_drop_metadata() -> String {
  let runs : Array[String] = []
  let texts = labels()
  for index = 0; index < texts.length(); index = index + 1 {
    let size = if index == 0 { 20 } else if index < 5 { 16 } else { 12 }
    runs.push(
      "{\"text\":\{quote(texts[index])},\"font_size\":\{size},\"weight\":400,\"line_height\":\{line_height(size.to_double(), 1)}}",
    )
  }
  "{\"id\":\"drag_drop\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":true,\"runs\":[\{runs.join(",")}],\"source_blob\":\"8f038ef3308fee9b097e7289665c9fa47cd6945b\",\"metrics_contract\":\"eight shaped widths: heading, three source labels, target, three previews; session-fixed device scale\",\"conformance\":\"unverified\"}"
}

///|
#export_name("drag_drop_reset")
pub fn drag_drop_reset() -> Unit {
  // Cancel before replacement: any old alias shares the cleared one-shot cell.
  ignore(drag_drop_state.val.session.cancel())
  drag_drop_state.val = initial_state()
}

///|
fn sources() -> Array[@element.DragSource[DragInfo]] {
  let result : Array[@element.DragSource[DragInfo]] = []
  for ix = 0; ix < 3; ix = ix + 1 {
    result.push(
      @element.DragSource::new(source_ids()[ix], {
        ix,
        color: colors()[ix],
        position: point(0, 0),
      }),
    )
  }
  result
}

///|
fn targets() -> Array[@element.DropTarget[DragInfo]] {
  [@element.DropTarget::new(30)]
}

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn node(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      fixed(main),
      fixed(cross),
      @primitives.Size::new(0, 0).unwrap(),
    )
    .with_flex(0, 0)
    .unwrap(),
  )
}

///|
fn centered(
  direction : @layout.FlowDirection,
  border : Double,
) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(direction)
  .with_align(@layout.AlignItems::center())
  .with_justify(@layout.JustifyContent::center())
  .with_insets(@layout.Insets::zero(), @layout.Insets::all(border).unwrap())
}

///|
fn text_node(
  id : UInt64,
  width : Double,
  size : Double,
  scale : Double,
  in_row~ : Bool = true,
) -> @element.Element {
  let height = line_height(size, scale)
  node(
    id,
    if in_row {
      width
    } else {
      height
    },
    if in_row {
      height
    } else {
      width
    },
  )
  .with_background(Some(transparent()))
  .with_pointer_events(false)
}

///|
fn drag_layout(widths : Array[Double], scale : Double) -> @element.Prepainted {
  let mut row = node(4, 128, 800)
    .with_children_style(
      centered(@layout.FlowDirection::row(), 0).with_gap(16).unwrap(),
    )
    .with_pointer_events(false)
  for ix = 0; ix < 3; ix = ix + 1 {
    row = row.with_child(
      node(source_ids()[ix], 128, 128)
      .with_children_style(
        centered(@layout.FlowDirection::row(), snap(2, scale)),
      )
      .with_background(Some(transparent()))
      .with_child(text_node(20 + ix.to_uint64(), widths[ix + 1], 16, scale)),
    )
  }
  // Anonymous mb_10 lowers to a non-hit wrapper with a 40px bottom inset.
  // There is still only one root gap between this wrapper and the target.
  let margin_row = node(3, 168, 800)
    .with_children_style(
      @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_insets(
        @layout.Insets::new(0, 0, 40, 0).unwrap(),
        @layout.Insets::zero(),
      ),
    )
    .with_pointer_events(false)
    .with_child(row)
  let target = node(30, 128, 512)
    .with_children_style(centered(@layout.FlowDirection::row(), snap(3, scale)))
    .with_background(Some(transparent()))
    .with_child(text_node(31, widths[4], 16, scale))
  @element.Element::root(
    1,
    centered(@layout.FlowDirection::column(), 0).with_gap(20).unwrap(),
  )
  .with_background(Some(color(255, 255, 255)))
  .with_child(text_node(2, widths[0], 20, scale, in_row=false))
  .with_child(margin_row)
  .with_child(target)
  .request_layout_with_device_scale(
    @primitives.Size::new(800, 600).unwrap(),
    scale,
  )
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn active(state : DragDropState) -> Bool {
  state.session.snapshot() is @element.Active(..)
}

///|
fn hovered(state : DragDropState, id : UInt64) -> Bool {
  if active(state) {
    return false
  }
  match (state.tree, state.pointer) {
    (Some(tree), Some(position)) =>
      tree.dispatch_pointer(position).bubble().contains(id)
    _ => false
  }
}

///|
fn cursor(state : DragDropState) -> String {
  if active(state) {
    return "move"
  }
  for id in source_ids() {
    if hovered(state, id) {
      return "move"
    }
  }
  "default"
}

///|
fn error_name(error : @element.DragDispatchError) -> String {
  match error {
    @element.DuplicateSourceBinding(id) => "duplicate_source_binding:\{id}"
    @element.DuplicateTargetBinding(id) => "duplicate_target_binding:\{id}"
    @element.UnknownSourceBinding(id) => "unknown_source_binding:\{id}"
    @element.UnknownTargetBinding(id) => "unknown_target_binding:\{id}"
    @element.CursorOffsetOverflow(id) => "cursor_offset_overflow:\{id}"
    @element.ReentrantDispatch => "reentrant_dispatch"
  }
}

///|
fn dispatch(
  state : DragDropState,
  tree : @element.ElementTree,
  event : @primitives.InputEvent,
  current_sources : Array[@element.DragSource[DragInfo]],
  current_targets : Array[@element.DropTarget[DragInfo]],
) -> String {
  match state.session.dispatch(tree, event, current_sources, current_targets) {
    Err(error) => {
      // Core Err is atomic, even for release. This application's explicit
      // error policy cancels and reports; it never pretends the event passed.
      let message = error_name(error)
      let cancelled = state.session.cancel()
      state.last_error = Some(message)
      state.last_outcome = "error"
      "{\"ok\":false,\"error\":\{quote(message)},\"cancelled\":\{cancelled},\"cursor\":\{quote(cursor(state))}}"
    }
    Ok(outcome) => {
      state.last_error = None
      state.last_outcome = match outcome {
        @element.Unchanged => "unchanged"
        @element.Admitted => "admitted"
        @element.Activated => "activated"
        @element.Moved => "moved"
        @element.Cancelled => "cancelled"
        @element.Rejected(_) => "rejected"
        @element.Dropped(target, payload) =>
          // Apply the typed one-shot result after core has consumed it.
          if target == 30 {
            state.drop_on = Some(payload)
            state.drop_count = state.drop_count + 1
            "dropped"
          } else {
            "dropped_unhandled_target"
          }
      }
      "{\"ok\":true,\"changed\":\{outcome.state_changed()},\"stopped\":\{outcome.was_stopped()},\"outcome\":\{quote(state.last_outcome)},\"cursor\":\{quote(cursor(state))}}"
    }
  }
}

///|
fn invalid_input(message : String) -> String {
  drag_drop_state.val.last_error = Some(message)
  "{\"ok\":false,\"error\":\{quote(message)},\"cancelled\":false,\"cursor\":\{quote(cursor(drag_drop_state.val))}}"
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
#export_name("drag_drop_pointer")
pub fn drag_drop_pointer(
  kind : String,
  x : Double,
  y : Double,
  button : Int32,
  shift : Bool,
  control : Bool,
  alt : Bool,
  meta : Bool,
) -> String {
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return invalid_input("invalid_pointer")
  }
  let modifiers = @primitives.Modifiers::new(shift~, control~, alt~, meta~)
  let event = match kind {
    "move" => @primitives.PointerMoved(position~)
    "down" | "up" => {
      let button = match pointer_button(button) {
        Some(value) => value
        None => return invalid_input("invalid_button")
      }
      if kind == "down" {
        @primitives.PointerButtonPressed(position~, button~, modifiers~)
      } else {
        @primitives.PointerButtonReleased(position~, button~, modifiers~)
      }
    }
    _ => return invalid_input("invalid_pointer_kind")
  }
  let state = drag_drop_state.val
  let tree = match state.tree {
    Some(value) => value
    None => return invalid_input("layout_required")
  }
  state.pointer = Some(position)
  dispatch(state, tree, event, sources(), targets())
}

///|
#export_name("drag_drop_leave")
pub fn drag_drop_leave() -> String {
  let state = drag_drop_state.val
  state.pointer = None
  // The source has no Escape/leave cancellation handler.
  "{\"ok\":true,\"changed\":true,\"stopped\":false,\"outcome\":\"leave\",\"cursor\":\{quote(cursor(state))}}"
}

///|
fn preview_value(state : DragDropState) -> DragInfo? {
  match state.session.snapshot() {
    @element.Active(cursor_offset~, payload~, ..) =>
      Some({ ix: payload.ix, color: payload.color, position: cursor_offset, })
    _ => None
  }
}

///|
fn preview_origin(
  position : @primitives.Point,
  value : DragInfo,
  scale : Double,
) -> @primitives.Point {
  // Signed visible-overflow Block lowering. These are two independent snaps;
  // cancellation into pointer-(60,25) is wrong for fractional inputs.
  point(
    snap(position.x() - value.position.x(), scale) +
    snap(value.position.x() - 60, scale),
    snap(position.y() - value.position.y(), scale) +
    snap(value.position.y() - 25, scale),
  )
}

///|
fn append_preview(
  items : Array[@scene.SceneItem],
  state : DragDropState,
  widths : Array[Double],
  scale : Double,
) -> Unit {
  match (state.session.snapshot(), preview_value(state)) {
    (@element.Active(position~, ..), Some(value)) => {
      let origin = preview_origin(position, value, scale)
      let preview = @element.Element::root(
          90,
          centered(@layout.FlowDirection::row(), 0),
        )
        .with_background(Some(value.color))
        .with_pointer_events(false)
        .with_child(text_node(91, widths[5 + value.ix], 12, scale))
        .request_layout_with_device_scale(
          @primitives.Size::new(120, 50).unwrap(),
          scale,
        )
        .unwrap()
        .prepaint()
        .unwrap()
        .paint_snapshot(scale)
        .unwrap()
      for item in preview.items() {
        let bounds = match item {
          @scene.QuadItem(bounds~, ..) => bounds
          _ => continue
        }
        let absolute = @primitives.Rect::new(
          bounds.left() + origin.x(),
          bounds.top() + origin.y(),
          bounds.size().width(),
          bounds.size().height(),
        ).unwrap()
        if item.id() == 90 {
          items.push(
            @scene.SceneItem::quad(
              90,
              absolute,
              value.color,
              @scene.AffineTransform::identity(),
              0.5,
              None,
            ).unwrap(),
          )
        } else {
          items.push(
            @scene.SceneItem::text(
              91,
              absolute,
              labels()[5 + value.ix],
              12,
              color(255, 255, 255),
              @scene.AffineTransform::identity(),
              1,
              None,
            ).unwrap(),
          )
        }
      }
    }
    _ => ()
  }
}

///|
fn snapshot(
  prepainted : @element.Prepainted,
  state : DragDropState,
  widths : Array[Double],
  scale : Double,
) -> @scene.SceneSnapshot {
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match item {
      @scene.QuadItem(id~, bounds~, clip_chain_id~, ..) =>
        if id == 2 || (id >= 20 && id <= 22) || id == 31 {
          let index = if id == 2 {
            0
          } else if id == 31 {
            4
          } else {
            (id - 19).to_int()
          }
          let ink = if index >= 1 && index <= 3 {
            colors()[index - 1]
          } else {
            color(51, 51, 51)
          }
          items.push(
            @scene.SceneItem::text(
              id,
              bounds,
              labels()[index],
              if id == 2 {
                20
              } else {
                16
              },
              ink,
              @scene.AffineTransform::identity(),
              1,
              clip_chain_id,
            ).unwrap(),
          )
          if id != 2 {
            let owner = if id == 31 { 30UL } else { id - 10 }
            let bounds = prepainted.tree().node(owner).unwrap().bounds()
            // Full-bounds transparent quad AFTER this label retains the Rust
            // ordering rectangle and an opaque border independent of the fill.
            items.push(
              @scene.SceneItem::quad(
                owner + 1000,
                bounds,
                transparent(),
                @scene.AffineTransform::identity(),
                1,
                clip_chain_id,
              ).unwrap(),
            )
          }
        } else if source_ids().contains(id) || id == 30 {
          let fill = if id == 30 {
            match state.drop_on {
              Some(value) => Some((value.color, 0.5))
              None => None
            }
          } else if hovered(state, id) {
            Some((colors()[(id - 10).to_int()], 0.2))
          } else {
            None
          }
          match fill {
            Some((ink, opacity)) =>
              items.push(
                @scene.SceneItem::quad(
                  id,
                  bounds,
                  ink,
                  @scene.AffineTransform::identity(),
                  opacity,
                  clip_chain_id,
                ).unwrap(),
              )
            None => ()
          }
        } else {
          items.push(item)
        }
      _ => items.push(item)
    }
  }
  append_preview(items, state, widths, scale)
  @scene.SceneSnapshot::new(
    base.viewport(),
    scale,
    base.resources(),
    base.clip_chains(),
    items,
  ).unwrap()
}

///|
fn point_json(value : @primitives.Point) -> String {
  "{\"x\":\{value.x()},\"y\":\{value.y()}}"
}

///|
fn payload_json(value : DragInfo) -> String {
  "{\"ix\":\{value.ix},\"position\":\{point_json(value.position)},\"color\":{\"red\":\{value.color.red()},\"green\":\{value.color.green()},\"blue\":\{value.color.blue()}}}"
}

///|
fn state_json(state : DragDropState) -> String {
  let session = match state.session.snapshot() {
    @element.Idle => "{\"phase\":\"idle\"}"
    @element.Pending(source~, origin~) =>
      "{\"phase\":\"pending\",\"source\":\{source},\"origin\":\{point_json(origin)}}"
    @element.Active(source~, origin~, position~, cursor_offset~, payload~) =>
      "{\"phase\":\"active\",\"source\":\{source},\"origin\":\{point_json(origin)},\"position\":\{point_json(position)},\"cursor_offset\":\{point_json(cursor_offset)},\"payload\":\{payload_json(payload)}}"
  }
  let drop = match state.drop_on {
    Some(value) => payload_json(value)
    None => "null"
  }
  let preview = match preview_value(state) {
    Some(value) => payload_json(value)
    None => "null"
  }
  let error = match state.last_error {
    Some(value) => quote(value)
    None => "null"
  }
  "{\"session\":\{session},\"drop_on\":\{drop},\"preview_value\":\{preview},\"drop_count\":\{state.drop_count},\"last_outcome\":\{quote(state.last_outcome)},\"last_error\":\{error},\"evidence\":\"actual candidate diagnostic state; not a Rust oracle\"}"
}

///|
#export_name("drag_drop_state")
pub fn drag_drop_diagnostics() -> String {
  state_json(drag_drop_state.val)
}

///|
#export_name("drag_drop_frame")
pub fn drag_drop_frame(widths : Array[Double], scale : Double) -> String {
  if widths.length() != 8 || !(scale > 0 && scale <= 4) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let available = [800.0, 124, 124, 124, 506, 120, 120, 120]
  for index = 0; index < widths.length(); index = index + 1 {
    if !(widths[index] > 0 && widths[index] <= available[index]) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  if line_height(12, scale) <= 0 || snap(2, scale) <= 0 {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let state = drag_drop_state.val
  match state.scale {
    Some(previous) if previous != scale =>
      return "{\"ok\":false,\"error\":\"scale_changed_requires_reset\"}"
    _ => ()
  }
  let prepainted = drag_layout(widths, scale)
  // Numeric IDs and current bindings, not focus acquisitions, retain this
  // drag over rerenders. No preview node is ever installed into this tree.
  state.tree = Some(prepainted.tree())
  state.scale = Some(scale)
  let scene = snapshot(prepainted, state, widths, scale)
  let decorations : Array[String] = []
  let hex = ["#0000ff", "#ff0000", "#008000"]
  for ix = 0; ix < 3; ix = ix + 1 {
    decorations.push(
      "{\"id\":\{source_ids()[ix] + 1000},\"radius\":0,\"border_width\":2,\"border\":\{quote(hex[ix])},\"border_style\":\"solid\"}",
    )
  }
  let target_color = match state.drop_on {
    Some(value) => hex[value.ix]
    None => "#000000"
  }
  decorations.push(
    "{\"id\":1030,\"radius\":0,\"border_width\":3,\"border\":\{quote(target_color)},\"border_style\":\"solid\"}",
  )
  let shadows = if active(state) {
    "[{\"id\":90,\"kind\":\"shadow_md\",\"element_opacity\":1}]"
  } else {
    "[]"
  }
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"shadows\":\{shadows},\"cursor\":\{quote(cursor(state))},\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"row_bottom_margin_lowering\",\"signed_preview_block_lowering\",\"solid_2px_3px_borders\",\"canvas_shadow_md_approximation\",\"browser_mouse_delivery\"],\"drag_drop\":\{state_json(state)}}"
}
