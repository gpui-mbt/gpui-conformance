///|
let field_state : Ref[@text_field.TextField?] = { val: None }

///|
/// Gesture ownership stays beside the authoritative TextField. The browser
/// transports a single captured pointer; it never stores selection offsets.
let pointer_selecting : Ref[Bool] = { val: false }

///|
/// Uniform scalar widths are an explicit candidate layout proxy, not GPUI or
/// browser font-shaping evidence. TextField owns all document transactions.
fn measure(
  document : @text.TextDocument,
) -> Result[@text_layout.TextMeasurement, @text_field.TextFieldError] {
  let offsets = [0]
  let mut current = 0
  for scalar in document.text().iter() {
    current += if scalar.to_int() > 0xFFFF { 2 } else { 1 }
    offsets.push(current)
  }
  let carets : Array[@text_layout.CaretGeometry] = []
  for i = 0; i < offsets.length(); i = i + 1 {
    let x = i.to_double() * 12.0
    let rect = @primitives.Rect::new(x, 0.0, 0.0, 30.0).unwrap()
    carets.push(
      @text_layout.CaretGeometry::new(offsets[i], true, rect, rect).unwrap(),
    )
  }
  let bounds = @primitives.Rect::new(
    0.0, 0.0, (offsets.length() - 1).to_double() * 12.0, 30.0,
  ).unwrap()
  match @text_layout.TextMeasurement::new(
    document, bounds, bounds, 24.0, 1, 0, carets,
  ) {
    Ok(value) => Ok(value)
    Err(_) => Err(@text_field.MeasurementFailed)
  }
}

///|
fn admit(
  document : @text.TextDocument,
  measurement : @text_layout.TextMeasurement,
) -> Result[Unit, @text_field.TextFieldError] {
  if document != measurement.document() {
    return Err(@text_field.AdmissionFailed)
  }
  match @text_field.scene_text_run_geometry(measurement) {
    Ok(_) => Ok(())
    Err(_) => Err(@text_field.UnsupportedLayout)
  }
}

///|
fn hit(
  document : @text.TextDocument,
  point : @primitives.Point,
) -> Result[@text_layout.TextHit, @text_field.TextFieldError] {
  let measurement = match measure(document) {
    Ok(value) => value
    Err(error) => return Err(error)
  }
  let mut best = 0
  let mut distance = 1.0e300
  for caret in measurement.carets() {
    let x = caret.strong().left()
    let diff = if x < point.x() { point.x() - x } else { x - point.x() }
    if diff < distance {
      distance = diff
      best = caret.utf16_offset()
    }
  }
  match @text_layout.TextHit::new(document, best, 0, best, true, true) {
    Ok(value) => Ok(value)
    Err(_) => Err(@text_field.HitTestFailed)
  }
}

///|
fn initial_field() -> @text_field.TextField {
  let document = @text.TextDocument::new("").unwrap()
  @text_field.TextField::new(
    4UL, @primitives.Rect::new(8.0, 34.0, 284.0, 38.0).unwrap(),
    24.0, document, measure, admit,
  ).unwrap().with_focus(true).unwrap()
}

///|
fn current() -> @text_field.TextField {
  match field_state.val {
    Some(field) => field
    None => {
      let field = initial_field()
      field_state.val = Some(field)
      field
    }
  }
}

///|
#export_name("input_reset")
pub fn input_reset() -> Unit {
  pointer_selecting.val = false
  field_state.val = Some(initial_field())
}

///|
fn update(
  event : @primitives.InputEvent,
) -> Bool {
  match current().handle_input(event, measure, admit, hit) {
    Ok((field, _)) => {
      field_state.val = Some(field)
      true
    }
    Err(_) => false
  }
}

///|
#export_name("input_insert")
pub fn input_insert(text : String) -> Bool {
  update(@primitives.TextInput(text~))
}

///|
#export_name("input_key")
pub fn input_key(label : String, shift : Bool, control : Bool, meta : Bool) -> Bool {
  let key = match label {
    "ArrowLeft" => @primitives.ArrowLeft
    "ArrowRight" => @primitives.ArrowRight
    "Home" => @primitives.Home
    "End" => @primitives.End
    "Backspace" => @primitives.Backspace
    "Delete" => @primitives.Delete
    "Escape" => @primitives.Escape
    "Enter" => @primitives.Enter
    _ => @primitives.Character(label)
  }
  update(@primitives.KeyPressed(
    key~, modifiers=@primitives.Modifiers::new(
      shift~, control~, alt=false, meta~,
    ), repeat=false,
  ))
}

///|
#export_name("input_pointer")
pub fn input_pointer(x : Double, y : Double, shift : Bool) -> Bool {
  pointer_selecting.val = false
  let position = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  if !current().bounds().contains(position) || current().is_composing() {
    return false
  }
  let accepted = select_at(position, shift)
  pointer_selecting.val = accepted
  accepted
}

///|
fn select_at(position : @primitives.Point, shift : Bool) -> Bool {
  // The pinned TextField exposes click/Shift-click rather than a drag API.
  // Reuse that validated path to retain its anchor, scroll offset, UTF-16
  // cursor stops and edit history throughout the example-local gesture.
  update(
    @primitives.PointerButtonPressed(
      position~,
      button=@primitives.Primary,
      modifiers=@primitives.Modifiers::new(
        shift~,
        control=false,
        alt=false,
        meta=false,
      ),
    ),
  )
}

///|
#export_name("input_pointer_move")
pub fn input_pointer_move(x : Double, y : Double) -> Bool {
  if !pointer_selecting.val || current().is_composing() {
    return false
  }
  let point = match @primitives.Point::new(x, y) {
    Ok(value) => value
    Err(_) => return false
  }
  // A captured pointer can leave both field and canvas. Clamp to the field's
  // closed edges; TextField maps through its current horizontal scroll offset
  // and keeps the moving head visible without changing the original anchor.
  let bounds = current().bounds()
  let clamped = @primitives.Point::new(
    point.x().max(bounds.left()).min(bounds.right()),
    point.y().max(bounds.top()).min(bounds.bottom()),
  ).unwrap()
  select_at(clamped, true)
}

///|
#export_name("input_pointer_end")
pub fn input_pointer_end() -> Unit {
  pointer_selecting.val = false
}

///|
#export_name("input_selecting")
pub fn input_selecting() -> Bool {
  pointer_selecting.val
}

///|
#export_name("input_scroll_offset")
pub fn input_scroll_offset() -> Double {
  current().scroll_offset()
}

///|
#export_name("input_copy")
pub fn input_copy() -> String {
  current().selected_text()
}

///|
#export_name("input_cut")
pub fn input_cut() -> Bool {
  let field = current()
  if field.is_composing() {
    return false
  }
  match field.replace_selection("", measure, admit) {
    Ok(next) => { field_state.val = Some(next); true }
    Err(_) => false
  }
}

///|
#export_name("input_preedit")
pub fn input_preedit(preedit : String, anchor : Int, head : Int) -> Bool {
  let selection = match @text.TextSelection::new(anchor, head) {
    Ok(value) => value
    Err(_) => return false
  }
  match current().update_composition(preedit, selection, measure, admit) {
    Ok(next) => { field_state.val = Some(next); true }
    Err(_) => false
  }
}

///|
#export_name("input_finish")
pub fn input_finish(text : String, commit : Bool) -> Bool {
  let field = current()
  if !field.is_composing() {
    return if commit { input_insert(text) } else { true }
  }
  let result = if commit {
    field.commit_composition(text, measure, admit)
  } else {
    field.cancel_composition(measure, admit)
  }
  match result {
    Ok(next) => { field_state.val = Some(next); true }
    Err(_) => false
  }
}

///|
#export_name("input_text")
pub fn input_text() -> String { current().document().text() }

///|
#export_name("input_anchor")
pub fn input_anchor() -> Int { current().selection().anchor() }

///|
#export_name("input_head")
pub fn input_head() -> Int { current().selection().head() }

///|
#export_name("input_marked_start")
pub fn input_marked_start() -> Int {
  match current().marked_range() {
    Some(marked) => marked.start()
    None => -1
  }
}

///|
#export_name("input_marked_end")
pub fn input_marked_end() -> Int {
  match current().marked_range() {
    Some(marked) => marked.end()
    None => -1
  }
}

///|
#export_name("input_composing")
pub fn input_composing() -> Bool { current().is_composing() }

///|
#export_name("input_can_undo")
pub fn input_can_undo() -> Bool { current().can_undo() }

///|
#export_name("input_can_redo")
pub fn input_can_redo() -> Bool { current().can_redo() }

///|
fn color(r : Int, g : Int, b : Int) -> @primitives.Color {
  @primitives.Color::rgba(r, g, b, 255).unwrap()
}

///|
fn fixed(id : UInt64, height : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    id, @layout.Dimension::points(height).unwrap(),
    @layout.Dimension::points(300.0).unwrap(),
    @primitives.Size::new(0.0, 0.0).unwrap(),
  ).with_flex(0.0, 0.0).unwrap())
}

///|
#export_name("input_metadata")
pub fn input_metadata() -> String {
  "{\"id\":\"input\",\"width\":300,\"height\":300,\"font_family\":\"IBM Plex Sans\",\"font_size\":24,\"interactive\":true}"
}

///|
#export_name("input_frame")
pub fn input_frame(scale : Double) -> String {
  if !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_scale\"}"
  }
  let field = current()
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  let prepainted = @element.Element::root(1, column)
    .with_background(Some(color(170, 170, 170)))
    .with_child(fixed(2, 30.0).with_background(Some(color(255, 255, 255))))
    .with_child(fixed(3, 46.0))
    .request_layout(@primitives.Size::new(300.0, 300.0).unwrap())
    .unwrap().prepaint().unwrap()
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  let (clip, paint) = field.paint_items(100UL, 7).unwrap()
  for item in paint { items.push(item) }
  items.push(@scene.SceneItem::text(
    210UL, @primitives.Rect::new(5.0, 0.0, 196.0, 28.0).unwrap(),
    "Keyboard Browser", 16.0, color(0, 0, 0),
    @scene.AffineTransform::identity(), 1.0, None,
  ).unwrap())
  items.push(@scene.SceneItem::quad(
    211UL, @primitives.Rect::new(244.0, 2.0, 50.0, 26.0).unwrap(),
    color(255, 255, 0), @scene.AffineTransform::identity(), 1.0, None,
  ).unwrap())
  items.push(@scene.SceneItem::text(
    212UL, @primitives.Rect::new(251.0, 2.0, 44.0, 26.0).unwrap(),
    "Reset", 16.0, color(0, 0, 0),
    @scene.AffineTransform::identity(), 1.0, None,
  ).unwrap())
  if field.document().text() == "" {
    items.push(@scene.SceneItem::text(
      213UL, @primitives.Rect::new(12.0, 38.0, 266.0, 30.0).unwrap(),
      "Type here...", 24.0, color(190, 190, 190),
      @scene.AffineTransform::identity(), 1.0, Some(7),
    ).unwrap())
  }
  match field.marked_range() {
    Some(marked) => {
      let start = field.measurement().caret_at(marked.start()).unwrap().strong()
      let end = field.measurement().caret_at(marked.end()).unwrap().strong()
      let rect = @primitives.Rect::new(
        field.content_bounds().left() - field.scroll_offset() + start.left(),
        field.content_bounds().top() + 28.0, end.left() - start.left(), 1.0,
      ).unwrap()
      items.push(@scene.SceneItem::quad(
        214UL, rect, color(20, 24, 30),
        @scene.AffineTransform::identity(), 1.0, Some(7),
      ).unwrap())
    }
    None => ()
  }
  let snapshot = @scene.SceneSnapshot::new(
    base.viewport(), scale, [], [clip], items,
  ).unwrap()
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"host_extensions\":[\"browser_ime_delivery\",\"browser_clipboard\",\"scalar_advance_proxy\",\"browser_keyboard_layout_label\"]}"
}
