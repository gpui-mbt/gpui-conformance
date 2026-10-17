// Observe production attachment/layout/scene/hit/dispatch APIs. No expected or
// final popup rectangles enter this program. All geometry comes from the core.
///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value { Ok(value) => value; Err(_) => abort("production operation rejected fixture") }
}
///|
fn field(value : Json, key : String) -> Json {
  match value { Object(fields) => fields.get(key).unwrap(); _ => abort("object required") }
}
///|
fn array(value : Json) -> Array[Json] {
  match value { Array(values) => values; _ => abort("array required") }
}
///|
fn number(value : Json) -> Double {
  match value { Number(value, ..) => value; _ => abort("number required") }
}
///|
fn string(value : Json) -> String {
  match value { String(value) => value; _ => abort("string required") }
}
///|
fn object(fields : Array[(String, Json)]) -> Json { Json::object(Map::from_array(fields)) }
///|
fn size(w : Double, h : Double) -> @primitives.Size { checked(@primitives.Size::new(w, h)) }
///|
fn bounds(r : @primitives.Rect) -> Json { @json.to_json([r.left(), r.top(), r.size().width(), r.size().height()]) }
///|
fn row() -> @layout.FlexTreeStyle { @layout.FlexTreeStyle::new(@layout.FlowDirection::row()) }
///|
fn column() -> @layout.FlexTreeStyle { @layout.FlexTreeStyle::new(@layout.FlowDirection::column()) }
///|
fn anchor(name : String) -> @element.Anchor {
  match name {
    "TopLeft" => @element.TopLeft
    "TopCenter" => @element.TopCenter
    "TopRight" => @element.TopRight
    "LeftCenter" => @element.LeftCenter
    "RightCenter" => @element.RightCenter
    "BottomLeft" => @element.BottomLeft
    "BottomCenter" => @element.BottomCenter
    "BottomRight" => @element.BottomRight
    _ => abort("unknown anchor")
  }
}
///|
struct Probe {
  events : Array[Json]
  ids : Map[String, UInt64]
  names : Map[UInt64, String]
  mut operation : String
  mut frame : Int
}
///|
fn Probe::record(self : Probe, event : Json) -> Unit {
  self.events.push(object([
    ("sequence", @json.to_json(self.events.length())), ("operation", @json.to_json(self.operation)),
    ("frame", @json.to_json(self.frame)), ("event", event),
  ]))
}
///|
fn Probe::register(self : Probe, name : String) -> Unit {
  let id = (self.ids.length() + 1).to_uint64()
  self.ids[name] = id
  self.names[id] = name
}
///|
fn Probe::identifier(self : Probe, id : UInt64?) -> Json {
  match id { Some(id) => @json.to_json(self.names.get(id).unwrap()); None => Json::null() }
}
///|
fn Probe::fixed(self : Probe, name : String, main : Double, cross : Double) -> @element.Element {
  let item = checked(@layout.FlexItem::new(self.ids.get(name).unwrap(),
    checked(@layout.Dimension::points(main)), checked(@layout.Dimension::points(cross)), size(0, 0)).with_flex(0, 0))
  @element.Element::new(item).with_pointer_events(false)
}
///|
fn painted(element : @element.Element) -> @element.Element {
  element.with_background(Some(checked(@primitives.Color::rgba(120, 154, 188, 255))))
    .with_pointer_events(false).with_focusable(false)
}
///|
fn Probe::positioned(self : Probe, name : String, x : Double, y : Double, child : @element.Element) -> @element.Element {
  // A zero-extent ordinary box with authored padding locates an independently
  // positioned subtree. It neither measures nor positions an anchored popup.
  // The full box remains observable in the actual structural dispatch tree.
  self.fixed(name, 0, 0).with_children_style(
    row().with_insets(checked(@layout.Insets::new(y, 0, 0, x)), @layout.Insets::zero())
  ).with_child(child)
}
///|
fn Probe::build(self : Probe, scenario : Json) -> @element.Element {
  let origin = array(field(scenario, "parent_origin"))
  let parent_size = array(field(scenario, "parent_size"))
  let popup = field(scenario, "popup")
  let dimensions = array(field(popup, "size"))
  let position = array(field(popup, "position"))
  let mode = match string(field(popup, "position_mode")) {
    "Local" => @element.Local
    "Window" => @element.Window
    _ => abort("unknown position mode")
  }
  let leaf = painted(self.fixed("popup", number(dimensions[0]), number(dimensions[1])))
  let attached = checked(@element.Element::anchored_after(self.ids.get("anchor").unwrap(),
    self.ids.get("button").unwrap(), leaf, anchor(string(field(popup, "anchor"))), mode,
    checked(@primitives.Point::new(number(position[0]), number(position[1]))),
    margin=number(field(popup, "margin"))))
  let parent = self.fixed("parent", number(parent_size[0]), number(parent_size[1]))
    .with_children_style(column()).with_child(painted(self.fixed("button", 65, 120)))
    .with_child(checked(attached.deferred()))
  @element.Element::root(self.ids.get("$host").unwrap(), row()).with_pointer_events(false)
    .with_child(self.positioned("$parent_position", number(origin[0]), number(origin[1]), parent))
}
///|
fn Probe::render(self : Probe, scenario : Json, scale : Double) -> @element.Prepainted {
  self.frame += 1
  let window = array(field(scenario, "window"))
  self.record(object([("type", @json.to_json("frame_start")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  let root = self.build(scenario)
  self.record(object([("type", @json.to_json("request_start"))]))
  let requested = checked(root.request_layout_with_device_scale(size(number(window[0]), number(window[1])), scale))
  self.record(object([("type", @json.to_json("request_end"))]))
  self.record(object([("type", @json.to_json("prepaint_start"))]))
  let frame = checked(requested.prepaint())
  self.record(object([("type", @json.to_json("prepaint_end")), ("overflow", @json.to_json(frame.overflow()))]))
  for node in frame.tree().nodes() {
    self.record(object([("type", @json.to_json("node")), ("node", self.identifier(Some(node.id()))),
      ("id", @json.to_json(node.id().to_string())), ("parent", self.identifier(node.parent())), ("bounds", bounds(node.bounds())),
      ("pointer_events", @json.to_json(node.accepts_pointer_events())), ("focusable", @json.to_json(node.is_focusable()))]))
  }
  for command in frame.paint().commands() {
    let kind = match command.kind() { @scene.Quad => "quad"; @scene.ClipPush => "clip_push"; @scene.ClipPop => "clip_pop"; @scene.Paint => abort("unexpected non-quad paint") }
    self.record(object([("type", @json.to_json("scene")), ("kind", @json.to_json(kind)), ("node", self.identifier(Some(command.id()))),
      ("bounds", match command.bounds() { Some(rect) => bounds(rect); None => Json::null() })]))
  }
  // These noninteractive hit API observations are candidate-only smoke checks.
  // They establish neither paired pointer behavior nor interactive hit masks.
  for (side, x, y) in [("right", number(window[0]) + 1, number(window[1]) / 2),
                       ("bottom", number(window[0]) / 2, number(window[1]) + 1)] {
    let point = checked(@primitives.Point::new(x, y))
    self.record(object([("type", @json.to_json("viewport_hit")), ("side", @json.to_json(side)),
      ("position", @json.to_json([x, y])), ("target", self.identifier(frame.tree().hit_test(point)))]))
  }
  self.record(object([("type", @json.to_json("frame_end")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  frame
}
///|
fn Probe::start(self : Probe, operation : String, input : Json) -> Unit {
  self.operation = operation
  self.record(object([("type", @json.to_json("operation_start")), ("input", input)]))
}
///|
fn Probe::end(self : Probe, scale : Double) -> Unit {
  self.record(object([("type", @json.to_json("operation_end")), ("scale_factor", @json.to_json(scale))]))
}
///|
fn observe(scenario : Json) -> Json {
  let probe : Probe = { events: [], ids: Map::from_array([]), names: Map::from_array([]), operation: "initial", frame: 0 }
  for name in ["$host", "$parent_position", "parent", "button", "anchor", "popup"] { probe.register(name) }
  probe.start("initial", object([("action", @json.to_json("open_window"))]))
  probe.render(scenario, 2) |> ignore
  probe.end(2)
  let scale = number(field(scenario, "scale_factor"))
  probe.start("configured", object([("action", @json.to_json("set_scale_factor")), ("scale_factor", @json.to_json(scale))]))
  probe.render(scenario, scale) |> ignore
  probe.end(scale)
  object([("id", field(scenario, "id")), ("events", @json.to_json(probe.events))])
}
///|
fn main {
  let input = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch { _ => abort("invalid scenarios") }
  println(object([("schema_version", @json.to_json(1)), ("layer", @json.to_json("compiled-moonbit-anchor-margin")),
    ("fixture", @json.to_json("font-free-bounded-anchor-margin")), ("input", input),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("cases", @json.to_json(array(field(input, "cases")).map(observe)))]).stringify())
}
