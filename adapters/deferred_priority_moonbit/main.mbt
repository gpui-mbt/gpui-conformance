// Actual production layout, scene-command emission and dispatch observations.
// Extra unpainted positioning wrappers are explicit structural-only nodes.
// No fabricated per-node lifecycle callbacks or GPUI input emulation.
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
fn painted(element : @element.Element, interactive : Bool, transparent : Bool) -> @element.Element {
  element.with_background(Some(checked(@primitives.Color::rgba(120, 154, 188, if transparent { 0 } else { 255 }))))
    .with_pointer_events(interactive).with_focusable(false)
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
fn boolean(value : Json) -> Bool {
  match value { True => true; False => false; _ => abort("boolean required") }
}
///|
fn Probe::path(self : Probe, ids : Array[UInt64]) -> Json {
  @json.to_json(ids.map(id => self.names.get(id).unwrap()))
}
///|
fn Probe::build(self : Probe, scenario : Json, stage : String) -> @element.Element {
  let position = array(field(scenario, "position"))
  let dimensions = array(field(scenario, "size"))
  let x = number(position[0])
  let y = number(position[1])
  let w = number(dimensions[0])
  let h = number(dimensions[1])
  let before = self.positioned("$before_position", x, y,
    painted(self.fixed("ordinary.before", w, h), true, false))
  let after = self.positioned("$after_position", x, y,
    painted(self.fixed("ordinary.after", w, h), true, false))
  let mut owner = self.fixed("$attachments", 0, 0).with_children_style(column())
    .with_child(self.fixed("$reference", 0, 0))
  // Only structural iteration. Ordering belongs to the production core.
  for layer in array(field(scenario, "layers")) {
    let name = string(field(layer, "id"))
    if stage == "removed" && name == string(field(scenario, "update_layer")) { continue }
    let interaction = field(layer, "interaction")
    let interactive = string(field(interaction, "listener")) != "none"
    let transparent = boolean(field(layer, "transparent"))
    let first = self.fixed(name + ".$first_holder", 24, h).with_children_style(row())
      .with_child(painted(self.fixed(name + ".first", 80, 64), interactive, transparent))
    let second = self.fixed(name + ".$second_holder", 80, h).with_children_style(
      row().with_insets(checked(@layout.Insets::new(16, 0, 0, 0)), @layout.Insets::zero()))
      .with_child(painted(self.fixed(name + ".second", 80, 64), interactive, transparent))
    let subtree = painted(self.fixed(name + ".root", w, h), interactive, transparent)
      .with_children_style(row()).with_child(first).with_child(second)
    let priority = if (stage == "updated" || stage == "removed") && name == string(field(scenario, "update_layer")) {
      number(field(scenario, "update_priority")).to_int()
    } else { number(field(layer, "priority")).to_int() }
    let attachment = checked(@element.Element::anchored_after(self.ids.get(name + ".anchor").unwrap(),
      self.ids.get("$reference").unwrap(), subtree, @element.TopLeft, @element.Window,
      checked(@primitives.Point::new(x, y))))
    owner = owner.with_child(checked(attachment.deferred(priority=priority)))
  }
  @element.Element::root(self.ids.get("$host").unwrap(), row()).with_pointer_events(false)
    .with_child(before).with_child(owner).with_child(after)
}
///|
fn Probe::render(self : Probe, scenario : Json, stage : String, scale : Double) -> @element.Prepainted {
  self.frame += 1
  let window = array(field(scenario, "window"))
  self.record(object([("type", @json.to_json("frame_start")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  let root = self.build(scenario, stage)
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
    self.record(object([("type", @json.to_json("scene")), ("kind", @json.to_json(kind)),
      ("node", self.identifier(Some(command.id()))), ("id", @json.to_json(command.id().to_string())),
      ("bounds", match command.bounds() { Some(rect) => bounds(rect); None => Json::null() })]))
  }
  self.record(object([("type", @json.to_json("frame_end")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  frame
}
///|
fn Probe::route(self : Probe, tree : @element.ElementTree, position : Json, action : String) -> Unit {
  let at = array(position)
  let point = checked(@primitives.Point::new(number(at[0]), number(at[1])))
  let event = if action == "down" {
    @primitives.PointerButtonPressed(position=point, button=@primitives.Primary, modifiers=@primitives.Modifiers::none())
  } else { @primitives.PointerButtonReleased(position=point, button=@primitives.Primary, modifiers=@primitives.Modifiers::none()) }
  let route = tree.dispatch_input(event)
  let callbacks : Array[Json] = []
  let delivered = checked(tree.dispatch_input_with(event, (context, _) => {
    callbacks.push(object([("node", self.identifier(Some(context.current_target()))),
      ("id", @json.to_json(context.current_target().to_string())),
      ("phase", @json.to_json(match context.phase() { @element.Capture => "capture"; @element.Bubble => "bubble" }))]))
    Ok(())
  }))
  self.record(object([("type", @json.to_json("route")), ("action", @json.to_json(action)), ("position", position),
    ("hit_test", self.identifier(tree.hit_test(point))), ("target", self.identifier(route.target())),
    ("capture", self.path(route.capture())), ("bubble", self.path(route.bubble())),
    ("callback_capture", self.path(delivered.capture_visited())), ("callback_bubble", self.path(delivered.bubble_visited())),
    ("callbacks", @json.to_json(callbacks))]))
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
  for name in ["$host", "$before_position", "ordinary.before", "$attachments", "$reference", "$after_position", "ordinary.after"] { probe.register(name) }
  for layer in array(field(scenario, "layers")) {
    let prefix = string(field(layer, "id"))
    for suffix in ["anchor", "root", "$first_holder", "first", "$second_holder", "second"] { probe.register(prefix + "." + suffix) }
  }
  probe.start("initial", object([("action", @json.to_json("open_window"))]))
  probe.render(scenario, "base", 2) |> ignore
  probe.end(2)
  let scale = number(field(scenario, "scale_factor"))
  for stage in ["base", "updated", "removed", "restored"] {
    let input = match stage {
      "base" => object([("action", @json.to_json("set_scale_factor")), ("scale_factor", @json.to_json(scale))])
      "updated" => object([("action", @json.to_json("set_priority")), ("layer", field(scenario, "update_layer")), ("priority", field(scenario, "update_priority"))])
      "removed" => object([("action", @json.to_json("remove_layer")), ("layer", field(scenario, "update_layer"))])
      _ => object([("action", @json.to_json("restore_original_layers"))])
    }
    probe.start(stage, input)
    let frame = probe.render(scenario, stage, scale)
    probe.end(scale)
    probe.start(stage + ".input", object([("action", @json.to_json("left_click")), ("position", field(scenario, "probe_position"))]))
    probe.route(frame.tree(), field(scenario, "probe_position"), "down")
    probe.route(frame.tree(), field(scenario, "probe_position"), "up")
    probe.end(scale)
  }
  object([("id", field(scenario, "id")), ("events", @json.to_json(probe.events))])
}
///|
fn main {
  let input = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch { _ => abort("invalid scenarios") }
  println(object([("schema_version", @json.to_json(1)), ("layer", @json.to_json("compiled-moonbit-deferred-priority")),
    ("fixture", @json.to_json("font-free-flat-deferred-priority")), ("input", input),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("cases", @json.to_json(array(field(input, "cases")).map(observe)))]).stringify())
}
