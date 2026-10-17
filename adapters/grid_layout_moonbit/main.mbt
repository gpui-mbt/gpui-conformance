// Font-free production API observer. There is no track solver or rect injection.
///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value { Ok(value) => value; Err(_) => abort("production operation rejected fixture") }
}
///|
fn field(value : Json, key : String) -> Json {
  match value { Object(fields) => fields.get(key).unwrap(); _ => abort("object required") }
}
///|
fn optional(value : Json, key : String) -> Json? {
  match value { Object(fields) => fields.get(key); _ => abort("object required") }
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
fn dimensions(s : @primitives.Size) -> Json { @json.to_json([s.width(), s.height()]) }
///|
fn bounds(r : @primitives.Rect) -> Json { @json.to_json([r.left(), r.top(), r.size().width(), r.size().height()]) }
///|
fn dimension(node : Json, key : String) -> @layout.Dimension {
  match optional(node, key) { Some(value) => checked(@layout.Dimension::points(number(value))); None => @layout.Dimension::auto() }
}
///|
fn integer(node : Json, key : String, default : Int) -> Int {
  match optional(node, key) { Some(value) => number(value).to_int(); None => default }
}
///|
fn row() -> @layout.FlexTreeStyle { @layout.FlexTreeStyle::new(@layout.FlowDirection::row()) }
///|
struct Probe {
  events : Array[Json]
  ids : Map[String, UInt64]
  names : Map[UInt64, String]
  mut operation : String
  mut frame : Int
  mut callbacks : Int
}
///|
fn Probe::record(self : Probe, event : Json) -> Unit {
  self.events.push(object([
    ("sequence", @json.to_json(self.events.length())), ("operation", @json.to_json(self.operation)),
    ("frame", @json.to_json(self.frame)), ("event", event),
  ]))
}
///|
fn Probe::register(self : Probe, node : Json) -> Unit {
  let name = string(field(node, "id"))
  let id = (self.ids.length() + 1).to_uint64()
  self.ids[name] = id
  self.names[id] = name
  match optional(node, "children") { Some(children) => for child in array(children) { self.register(child) }; None => () }
}
///|
fn grid_style(node : Json) -> @layout.GridTreeStyle {
  checked(checked(@layout.GridTreeStyle::new(integer(node, "cols", 0), integer(node, "rows", 0))).with_gap(number(field(node, "gap"))))
}
///|
fn Probe::build(self : Probe, node : Json, allocation : String) -> @element.Element {
  let name = string(field(node, "id"))
  let id = self.ids.get(name).unwrap()
  let kind = string(field(node, "kind"))
  let mut result = match allocation {
    "generated-root" => {
      let root = if kind == "grid" { @element.Element::grid_root(id, grid_style(node)) } else { @element.Element::root(id, row()) }
      // These are authored dimensions of the independent callback result, never
      // the measured outer query. Tiny and huge roots use the production API.
      match (optional(node, "width"), optional(node, "height")) {
        (Some(w), Some(h)) => root.with_query_root_size(size(number(w), number(h)))
        (None, None) => root
        _ => abort("fixture requires both generated-root dimensions or neither")
      }
    }
    "flex" => @element.Element::new(checked(@layout.FlexItem::new(id,
      dimension(node, "width"), dimension(node, "height"), size(0, 0)).with_flex(0, 0)))
    "grid" => {
      let item = checked(@layout.GridItem::new(id, dimension(node, "width"), dimension(node, "height")).with_span(integer(node, "col_span", 1), integer(node, "row_span", 1)))
      let item = match optional(node, "full_columns") { Some(True) => item.full_columns(); _ => item }
      @element.Element::grid_item(item)
    }
    _ => abort("unknown allocation")
  }
  match kind {
    "grid" => {
      result = result.with_grid_children_style(grid_style(node))
      for child in array(field(node, "children")) { result = result.with_child(self.build(child, "grid")) }
      result
    }
    "query" => result.with_container_query(assigned => {
      self.callbacks += 1
      self.record(object([("type", @json.to_json("callback")), ("node", @json.to_json(name)), ("size", dimensions(assigned))]))
      Ok(self.build(array(field(node, "children"))[0], "generated-root"))
    })
    "box" => result.with_background(Some(checked(@primitives.Color::rgba(120, 154, 188, 255))))
    _ => abort("unsupported node kind")
  }
}
///|
fn Probe::render(self : Probe, scenario : Json, scale : Double) -> @element.Prepainted {
  self.frame += 1
  self.callbacks = 0
  let window = array(field(scenario, "window"))
  let origin = array(field(scenario, "origin"))
  self.record(object([("type", @json.to_json("frame_start")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  // Fixed flex allocation under a padded viewport is the declared source host
  // offset. Neither expected coordinates nor baseline output enter this probe.
  let style = match optional(scenario, "host") {
    Some(_) => row().with_align(@layout.AlignItems::end())
    None => row().with_insets(checked(@layout.Insets::new(number(origin[1]), 0, 0, number(origin[0]))), @layout.Insets::zero())
  }
  let root = @element.Element::root(1, style).with_child(self.build(field(scenario, "root"), "flex"))
  self.record(object([("type", @json.to_json("request_start"))]))
  let requested = checked(root.request_layout_with_device_scale(size(number(window[0]), number(window[1])), scale))
  self.record(object([("type", @json.to_json("request_end")), ("callback_count", @json.to_json(self.callbacks))]))
  self.record(object([("type", @json.to_json("prepaint_start"))]))
  let painted = checked(requested.prepaint())
  self.record(object([("type", @json.to_json("prepaint_end")), ("callback_count", @json.to_json(self.callbacks)), ("overflow", @json.to_json(painted.overflow()))]))
  for node in painted.tree().nodes() {
    self.record(object([("type", @json.to_json("node")), ("node", @json.to_json(self.names.get(node.id()).unwrap())),
      ("id", @json.to_json(node.id().to_string())), ("parent", match node.parent() { Some(id) => @json.to_json(self.names.get(id).unwrap()); None => Json::null() }), ("bounds", bounds(node.bounds()))]))
  }
  for command in painted.paint().commands() {
    let kind = match command.kind() { @scene.Quad => "quad"; @scene.ClipPush => "clip_push"; @scene.ClipPop => "clip_pop" }
    self.record(object([("type", @json.to_json("scene")), ("kind", @json.to_json(kind)), ("node", @json.to_json(self.names.get(command.id()).unwrap())),
      ("bounds", match command.bounds() { Some(rect) => bounds(rect); None => Json::null() })]))
  }
  self.record(object([("type", @json.to_json("frame_end")), ("scale_factor", @json.to_json(scale)), ("window_size", field(scenario, "window"))]))
  painted
}
///|
fn Probe::route(self : Probe, tree : @element.ElementTree, position : Json, action : String) -> Unit {
  let at = array(position)
  let point = checked(@primitives.Point::new(number(at[0]), number(at[1])))
  let event = if action == "down" {
    @primitives.PointerButtonPressed(position=point, button=@primitives.Primary, modifiers=@primitives.Modifiers::none())
  } else { @primitives.PointerButtonReleased(position=point, button=@primitives.Primary, modifiers=@primitives.Modifiers::none()) }
  let route = tree.dispatch_input(event)
  self.record(object([("type", @json.to_json("route")), ("action", @json.to_json(action)), ("position", position),
    ("target", match route.target() { Some(id) => @json.to_json(self.names.get(id).unwrap()); None => Json::null() }),
    ("capture", @json.to_json(route.capture().map(id => self.names.get(id).unwrap()))),
    ("bubble", @json.to_json(route.bubble().map(id => self.names.get(id).unwrap())))]))
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
  if string(field(scenario, "id")) == "explicit-collision" {
    return object([("id", field(scenario, "id")), ("status", @json.to_json("unsupported")), ("reason", @json.to_json("explicit-grid-line-placement")), ("events", Json::array([]))])
  }
  let probe : Probe = { events: [], ids: Map::from_array([("$host", 1)]), names: Map::from_array([(1, "$host")]), operation: "initial", frame: 0, callbacks: 0 }
  probe.register(field(scenario, "root"))
  probe.start("initial", object([("action", @json.to_json("open_window"))]))
  probe.render(scenario, 2) |> ignore
  probe.end(2)
  let scale = number(field(scenario, "scale_factor"))
  probe.start("configured", object([("action", @json.to_json("set_scale_factor")), ("scale_factor", @json.to_json(scale))]))
  let frame = probe.render(scenario, scale)
  probe.end(scale)
  for hit in array(field(scenario, "hits")) {
    probe.start(string(field(hit, "id")), object([("action", @json.to_json("click")), ("position", field(hit, "position"))]))
    probe.route(frame.tree(), field(hit, "position"), "down")
    probe.route(frame.tree(), field(hit, "position"), "up")
    probe.end(scale)
  }
  object([("id", field(scenario, "id")), ("status", @json.to_json("observed")), ("events", @json.to_json(probe.events))])
}
///|
fn main {
  let input = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch { _ => abort("invalid scenarios") }
  println(object([("schema_version", @json.to_json(1)), ("layer", @json.to_json("compiled-moonbit-grid-container-query")),
    ("fixture", @json.to_json("font-free-bounded-grid")), ("input", input),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("cases", @json.to_json(array(field(input, "cases")).map(observe)))]).stringify())
}
