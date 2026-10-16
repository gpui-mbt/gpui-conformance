///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value { Ok(value) => value; Err(_) => abort("production core operation rejected fixture") }
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
fn applied(value : Json) -> Json {
  match value {
    Number(n, ..) => @json.to_json(Float::from_double(n).to_double())
    Array(values) => @json.to_json(values.map(applied))
    Object(fields) => {
      let result : Map[String, Json] = Map([])
      for key, value in fields { result[key] = applied(value) }
      Json::object(result)
    }
    _ => value
  }
}
///|
fn size(w : Double, h : Double) -> @primitives.Size { checked(@primitives.Size::new(w, h)) }
///|
fn point(v : Json) -> @primitives.Point {
  let v = array(v)
  checked(@primitives.Point::new(number(v[0]), number(v[1])))
}
///|
fn bounds(rect : @primitives.Rect) -> Json {
  @json.to_json([rect.left(), rect.top(), rect.size().width(), rect.size().height()])
}
///|
fn dimensions(s : @primitives.Size) -> Json { @json.to_json([s.width(), s.height()]) }
///|
fn column() -> @layout.FlexTreeStyle { @layout.FlexTreeStyle::new(@layout.FlowDirection::column()) }
///|
struct Probe {
  events : Array[Json]
  mut operation : String
  mut frame : Int
  mut factory : Int
  mut configuration : Json
  mut offset : Double
  session : @element.UniformListClickSession
  mut down : Json
  mut row_factory : Map[UInt64, Int]
}
///|
fn Probe::record(self : Probe, event : Json) -> Unit {
  self.events.push(object([
    ("sequence", @json.to_json(self.events.length())),
    ("operation", @json.to_json(self.operation)),
    ("frame", @json.to_json(self.frame)), ("event", event),
  ]))
}
///|
fn auto_item(id : UInt64, w : Double, h : Double) -> @layout.FlexItem {
  checked(@layout.FlexItem::new(id, @layout.Dimension::auto(), @layout.Dimension::auto(), size(w, h)).with_flex(0, 0))
}
///|
fn Probe::render(self : Probe) -> @element.Prepainted {
  self.frame += 1
  self.record(object([("type", @json.to_json("frame_start")), ("configuration", self.configuration), ("logical_layout_scale", @json.to_json(1))]))
  let box = array(field(self.configuration, "list"))
  let w = number(box[2])
  let h = number(box[3])
  let inner_height = number(field(self.configuration, "inner_height"))
  let item = checked(@layout.FlexItem::new(2, checked(@layout.Dimension::points(h)), checked(@layout.Dimension::points(w)), size(w, h)).with_flex(0, 0))
  self.row_factory = Map([])
  let list = checked(@element.UniformList::new(
    item, number(field(self.configuration, "count")).to_int(),
    checked(@element.UniformListIdSpace::new(1000, 2)),
    range => {
      self.factory += 1
      let call = self.factory
      self.record(object([("type", @json.to_json("factory")), ("factory_call", @json.to_json(call)), ("range", @json.to_json([range.start(), range.end()]))]))
      let rows : Array[@element.Element] = []
      for index = range.start(); index < range.end(); index = index + 1 {
        let row_id = checked(range.id(index, 0))
        let inner_id = checked(range.id(index, 1))
        self.row_factory[row_id] = call
        self.row_factory[inner_id] = call
        self.record(object([("type", @json.to_json("constructed")), ("item_id", @json.to_json(index)), ("row_id", @json.to_json(row_id.to_string())), ("inner_id", @json.to_json(inner_id.to_string())), ("factory_call", @json.to_json(call))]))
        // The leaf is the font-free source's explicit intrinsic input. The
        // auto row itself has zero intrinsic size and is measured recursively.
        let inner = @element.Element::new(auto_item(inner_id, w, inner_height))
          .with_background(Some(checked(@primitives.Color::rgba(0, 0, 0, 0))))
        let row = @element.Element::new(auto_item(row_id, 0, 0))
          .with_children_style(column()).with_child(inner)
          .with_background(Some(checked(@primitives.Color::rgba(0, 0, 0, 0))))
        rows.push(row)
      }
      Ok(rows)
    },
  ))
  let list = checked(list.with_scroll_offset(self.offset)).into_element()
  // Fixed single-child fixture: root padding is the core-supported way to
  // obtain the source's absolute (left,top) allocation, without rect injection.
  let style = column().with_insets(checked(@layout.Insets::new(number(box[1]), 0, 0, number(box[0]))), @layout.Insets::zero())
  let root = @element.Element::root(1, style)
    .with_scroll_offset(checked(@primitives.Point::new(0, 0)))
    .with_child(list)
  let window = array(field(self.configuration, "window"))
  let frame = checked(checked(root.request_layout(size(number(window[0]), number(window[1])))).prepaint())
  let tree = frame.tree()
  if self.session.reconcile(tree) { self.down = Json::null() }
  for node in tree.nodes() {
    self.record(object([
      ("type", @json.to_json("node")), ("id", @json.to_json(node.id().to_string())),
      ("parent", match node.parent() { Some(id) => @json.to_json(id.to_string()); None => Json::null() }),
      ("bounds", bounds(node.bounds())),
      ("factory_call", match self.row_factory.get(node.id()) { Some(call) => @json.to_json(call); None => Json::null() }),
    ]))
  }
  for command in frame.paint().commands() {
    let kind = match command.kind() { @scene.Quad => "quad"; @scene.ClipPush => "clip_push"; @scene.ClipPop => "clip_pop" }
    self.record(object([("type", @json.to_json("scene")), ("kind", @json.to_json(kind)), ("id", @json.to_json(command.id().to_string())), ("bounds", match command.bounds() { Some(rect) => bounds(rect); None => Json::null() })]))
  }
  self.offset = tree.uniform_list(2).unwrap().offset()
  self.record(object([("type", @json.to_json("frame_end")), ("state", state(tree))]))
  frame
}
///|
fn state(tree : @element.ElementTree) -> Json {
  let list = tree.uniform_list(2).unwrap()
  object([
    ("list_bounds", bounds(list.bounds())), ("item_count", @json.to_json(list.item_count())),
    ("measured_item_size", match list.measured_item_size() { Some(s) => dimensions(s); None => Json::null() }),
    ("content_size", dimensions(list.content_size())),
    ("offset", @json.to_json([0.0, list.offset()])), ("max_offset", @json.to_json([0.0, list.max_offset()])),
    ("visible_range", @json.to_json([list.visible_range().start(), list.visible_range().end()])),
    ("window_size", dimensions(tree.node(1).unwrap().bounds().size())),
  ])
}
///|
fn Probe::pointer(self : Probe, tree : @element.ElementTree, operation : Json) -> Unit {
  let at = field(operation, "position")
  let action = string(field(operation, "action"))
  let event = match action {
    "down" => @primitives.PointerButtonPressed(position=point(at), button=@primitives.Primary, modifiers=@primitives.Modifiers::none())
    "up" => @primitives.PointerButtonReleased(position=point(at), button=@primitives.Primary, modifiers=@primitives.Modifiers::none())
    _ => @primitives.PointerMoved(position=point(at))
  }
  let route = tree.dispatch_input(event)
  self.record(object([("type", @json.to_json("route")), ("capture", @json.to_json(route.capture().map(id => id.to_string()))), ("bubble", @json.to_json(route.bubble().map(id => id.to_string())))]))
  match self.session.dispatch(tree, event) {
    @element.Pressed(index~, id~) => {
      self.down = at
      self.record(object([("type", @json.to_json("pressed")), ("item_id", @json.to_json(index)), ("row_id", @json.to_json(id.to_string()))]))
    }
    @element.Cancelled => { self.down = Json::null(); self.record(object([("type", @json.to_json("cancelled"))])) }
    @element.Clicked(index~, id~) => {
      self.record(object([("type", @json.to_json("click")), ("item_id", @json.to_json(index)), ("row_id", @json.to_json(id.to_string())), ("factory_call", @json.to_json(self.row_factory.get(id).unwrap())), ("detail", object([("kind", @json.to_json("mouse")), ("down", self.down), ("up", at)]))]))
      self.down = Json::null()
    }
    @element.Unchanged => ()
  }
}
///|
fn observe(scenario : Json) -> Json {
  let probe : Probe = { events: [], operation: "initial", frame: 0, factory: 0, configuration: applied(field(scenario, "initial")), offset: 0, session: @element.UniformListClickSession::new(2), down: Json::null(), row_factory: Map([]) }
  probe.record(object([("type", @json.to_json("operation_start")), ("input", object([("id", @json.to_json("initial")), ("action", @json.to_json("open_window"))]))]))
  let mut frame = probe.render()
  probe.record(object([("type", @json.to_json("operation_end")), ("configuration", probe.configuration), ("state", state(frame.tree()))]))
  for original in array(field(scenario, "operations")) {
    let operation = applied(original)
    probe.operation = string(field(original, "id"))
    probe.record(object([("type", @json.to_json("operation_start")), ("input", original), ("applied_input", operation)]))
    let configuration = match probe.configuration { Object(fields) => fields.copy(); _ => abort("configuration") }
    match string(field(operation, "action")) {
      "set_scale_factor" => configuration["scale_factor"] = field(operation, "scale_factor")
      "set_offset" => probe.offset = number(field(operation, "y"))
      "set_count" => configuration["count"] = field(operation, "count")
      "set_inner_height" => configuration["inner_height"] = field(operation, "height")
      "resize_window" => configuration["window"] = field(operation, "size")
      "resize_list" => {
        let box = array(configuration["list"]).copy()
        box[3] = field(operation, "height")
        configuration["list"] = @json.to_json(box)
      }
      "wheel" => {
        let delta = array(field(operation, "delta"))
        // Only input-sign normalization: axis policy/routing/clamping are core.
        let updates = checked(frame.tree().scroll_wheel(point(field(operation, "position")), -number(delta[0]), -number(delta[1])))
        for update in updates {
          probe.record(object([("type", @json.to_json("wheel_update")), ("id", @json.to_json(update.id().to_string())), ("offset", @json.to_json([update.offset().x(), update.offset().y()]))]))
          if update.id() == 2 { probe.offset = update.offset().y() }
        }
      }
      "down" | "up" | "move" => probe.pointer(frame.tree(), operation)
      _ => abort("unknown operation")
    }
    probe.configuration = Json::object(configuration)
    frame = probe.render()
    probe.record(object([("type", @json.to_json("operation_end")), ("configuration", probe.configuration), ("state", state(frame.tree()))]))
  }
  object([("id", field(scenario, "id")), ("events", @json.to_json(probe.events))])
}
///|
fn main {
  let input = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch { _ => abort("invalid scenarios") }
  let output = object([
    ("schema_version", @json.to_json(1)), ("layer", @json.to_json("compiled-moonbit-uniform-list-semantics")),
    ("fixture", @json.to_json("font-free-nested-auto-height")), ("logical_layout_scale", @json.to_json(1)),
    ("platform_scale_claim", @json.to_json(false)), ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("input", input), ("cases", @json.to_json(array(field(input, "cases")).map(observe))),
  ])
  println(output.stringify())
}
