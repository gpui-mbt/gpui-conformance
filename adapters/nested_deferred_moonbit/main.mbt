// Actual production layout and scene-command emission observations. No input claim.
// Extra unpainted positioning wrappers are explicit structural-only nodes.
// No fabricated per-node lifecycle callbacks or GPUI input emulation.

///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value {
    Ok(value) => value
    Err(_) => abort("production operation rejected fixture")
  }
}

///|
fn field(value : Json, key : String) -> Json {
  match value {
    Object(fields) => fields.get(key).unwrap()
    _ => abort("object required")
  }
}

///|
fn array(value : Json) -> Array[Json] {
  match value {
    Array(values) => values
    _ => abort("array required")
  }
}

///|
fn number(value : Json) -> Double {
  match value {
    Number(value, ..) => value
    _ => abort("number required")
  }
}

///|
fn string(value : Json) -> String {
  match value {
    String(value) => value
    _ => abort("string required")
  }
}

///|
fn object(fields : Array[(String, Json)]) -> Json {
  Json::object(Map::from_array(fields))
}

///|
fn size(w : Double, h : Double) -> @primitives.Size {
  checked(@primitives.Size::new(w, h))
}

///|
fn bounds(r : @primitives.Rect) -> Json {
  @json.to_json([r.left(), r.top(), r.size().width(), r.size().height()])
}

///|
fn row() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
}

///|
struct Probe {
  events : Array[Json]
  ids : Map[String, UInt64]
  names : Map[UInt64, String]
  mut operation : String
  mut frame : Int32
}

///|
fn Probe::record(self : Probe, event : Json) -> Unit {
  self.events.push(
    object([
      ("sequence", @json.to_json(self.events.length())),
      ("operation", @json.to_json(self.operation)),
      ("frame", @json.to_json(self.frame)),
      ("event", event),
    ]),
  )
}

///|
fn Probe::register(self : Probe, name : String) -> Unit {
  let id = (self.ids.length() + 1).to_uint64()
  self.ids[name] = id
  self.names[id] = name
}

///|
fn Probe::identifier(self : Probe, id : UInt64?) -> Json {
  match id {
    Some(id) => @json.to_json(self.names.get(id).unwrap())
    None => Json::null()
  }
}

///|
fn Probe::fixed(
  self : Probe,
  name : String,
  main : Double,
  cross : Double,
) -> @element.Element {
  let item = checked(
    @layout.FlexItem::new(
      self.ids.get(name).unwrap(),
      checked(@layout.Dimension::points(main)),
      checked(@layout.Dimension::points(cross)),
      size(0, 0),
    ).with_flex(0, 0),
  )
  @element.Element::new(item).with_pointer_events(false)
}

///|
fn painted(
  element : @element.Element,
  interactive : Bool,
  transparent : Bool,
) -> @element.Element {
  element
  .with_background(
    Some(
      checked(
        @primitives.Color::rgba(
          120,
          154,
          188,
          if transparent {
            0
          } else {
            255
          },
        ),
      ),
    ),
  )
  .with_pointer_events(interactive)
  .with_focusable(false)
}

///|
fn Probe::positioned(
  self : Probe,
  name : String,
  x : Double,
  y : Double,
  child : @element.Element,
) -> @element.Element {
  // A zero-extent ordinary box with authored padding locates an independently
  // positioned subtree. It neither measures nor positions an anchored popup.
  // The full box remains observable in the actual structural dispatch tree.
  self
  .fixed(name, 0, 0)
  .with_children_style(
    row().with_insets(
      checked(@layout.Insets::new(y, 0, 0, x)),
      @layout.Insets::zero(),
    ),
  )
  .with_child(child)
}

///|
fn Probe::build(
  self : Probe,
  scenario : Json,
  stage : String,
) -> @element.Element {
  let origin = array(field(scenario, "ancestor_origin"))
  let movement = array(field(scenario, "ancestor_movement"))
  let dx = if stage == "moved" { number(movement[0]) } else { 0 }
  let x = number(origin[0]) + dx
  let dy = if stage == "moved" { number(movement[1]) } else { 0 }
  let y = number(origin[1]) + dy
  let dimensions = array(field(scenario, "ancestor_size"))
  let outer = array(field(scenario, "outer_size"))
  let nested = array(field(scenario, "nested_size"))
  let nested_position = array(field(scenario, "nested_position"))
  let before = self.positioned(
    "$before_position",
    0,
    0,
    painted(self.fixed("ordinary.before", 12, 12), false, false),
  )
  let after = self.positioned(
    "$after_position",
    8,
    8,
    painted(self.fixed("ordinary.after", 12, 12), false, false),
  )
  let mut owner = self
    .fixed("$attachments", 0, 0)
    .with_children_style(column())
    .with_child(self.fixed("$reference", 0, 0))
  // Structural construction only: core owns discovery, measurement, offsets,
  // global deferred scheduling and actual scene-command emission.
  for layer in array(field(scenario, "layers")) {
    let name = string(field(layer, "id"))
    let reference = self
      .fixed(name + ".$reference", 0, 0)
      .with_children_style(row())
      .with_child(
        self.positioned(
          name + ".$before_position",
          0,
          0,
          painted(self.fixed(name + ".before", 12, 12), false, false),
        ),
      )
      .with_child(
        self.positioned(
          name + ".$after_position",
          16,
          8,
          painted(self.fixed(name + ".after", 12, 12), false, false),
        ),
      )
    let mut subtree = painted(
        self.fixed(name + ".root", number(outer[0]), number(outer[1])),
        false,
        false,
      )
      .with_children_style(column())
      .with_child(reference)
    if !(stage == "removed" && name == string(field(scenario, "remove_nested"))) {
      let content = painted(
        self.fixed(name + ".nested.root", number(nested[0]), number(nested[1])),
        false,
        false,
      )
      let attachment = checked(
        @element.Element::anchored_after(
          self.ids.get(name + ".nested.anchor").unwrap(),
          self.ids.get(name + ".$reference").unwrap(),
          content,
          @element.TopLeft,
          @element.Local,
          checked(
            @primitives.Point::new(
              number(nested_position[0]),
              number(nested_position[1]),
            ),
          ),
          margin=number(field(scenario, "margin")),
        ),
      )
      subtree = subtree.with_child(
        checked(
          attachment.deferred(
            priority=number(field(layer, "nested_priority")).to_int(),
          ),
        ),
      )
    }
    let priority = if (stage == "updated" || stage == "removed") &&
      name == string(field(scenario, "update_layer")) {
      number(field(scenario, "update_priority")).to_int()
    } else {
      number(field(layer, "priority")).to_int()
    }
    let position = array(field(layer, "position"))
    let attachment = checked(
      @element.Element::anchored_after(
        self.ids.get(name + ".anchor").unwrap(),
        self.ids.get("$reference").unwrap(),
        subtree,
        @element.TopLeft,
        @element.Local,
        checked(
          @primitives.Point::new(number(position[0]), number(position[1])),
        ),
        margin=number(field(scenario, "margin")),
      ),
    )
    owner = owner.with_child(checked(attachment.deferred(priority~)))
  }
  let ancestor = self
    .fixed("$ancestor", number(dimensions[0]), number(dimensions[1]))
    .with_children_style(row())
    .with_child(before)
    .with_child(owner)
    .with_child(after)
  @element.Element::root(self.ids.get("$host").unwrap(), row())
  .with_pointer_events(false)
  .with_child(self.positioned("$ancestor_position", x, y, ancestor))
}

///|
fn Probe::render(
  self : Probe,
  scenario : Json,
  stage : String,
  scale : Double,
) -> @element.Prepainted {
  self.frame += 1
  let window = array(field(scenario, "window"))
  self.record(
    object([
      ("type", @json.to_json("frame_start")),
      ("scale_factor", @json.to_json(scale)),
      ("window_size", field(scenario, "window")),
    ]),
  )
  let root = self.build(scenario, stage)
  self.record(object([("type", @json.to_json("request_start"))]))
  let requested = checked(
    root.request_layout_with_device_scale(
      size(number(window[0]), number(window[1])),
      scale,
    ),
  )
  self.record(object([("type", @json.to_json("request_end"))]))
  self.record(object([("type", @json.to_json("prepaint_start"))]))
  let frame = checked(requested.prepaint())
  self.record(
    object([
      ("type", @json.to_json("prepaint_end")),
      ("overflow", @json.to_json(frame.overflow())),
    ]),
  )
  for node in frame.tree().nodes() {
    self.record(
      object([
        ("type", @json.to_json("node")),
        ("node", self.identifier(Some(node.id()))),
        ("id", @json.to_json(node.id().to_string())),
        ("parent", self.identifier(node.parent())),
        ("bounds", bounds(node.bounds())),
        ("pointer_events", @json.to_json(node.accepts_pointer_events())),
        ("focusable", @json.to_json(node.is_focusable())),
      ]),
    )
  }
  for command in frame.paint().commands() {
    let kind = match command.kind() {
      @scene.Quad => "quad"
      @scene.ClipPush => "clip_push"
      @scene.ClipPop => "clip_pop"
      @scene.Paint => abort("unexpected non-quad paint")
    }
    self.record(
      object([
        ("type", @json.to_json("scene")),
        ("kind", @json.to_json(kind)),
        ("node", self.identifier(Some(command.id()))),
        ("id", @json.to_json(command.id().to_string())),
        (
          "bounds",
          match command.bounds() {
            Some(rect) => bounds(rect)
            None => Json::null()
          },
        ),
      ]),
    )
  }
  self.record(
    object([
      ("type", @json.to_json("frame_end")),
      ("scale_factor", @json.to_json(scale)),
      ("window_size", field(scenario, "window")),
    ]),
  )
  frame
}

///|
fn Probe::start(self : Probe, operation : String, input : Json) -> Unit {
  self.operation = operation
  self.record(
    object([("type", @json.to_json("operation_start")), ("input", input)]),
  )
}

///|
fn Probe::end(self : Probe, scale : Double) -> Unit {
  self.record(
    object([
      ("type", @json.to_json("operation_end")),
      ("scale_factor", @json.to_json(scale)),
    ]),
  )
}

///|
fn observe(scenario : Json) -> Json {
  let probe : Probe = {
    events: [],
    ids: Map::from_array([]),
    names: Map::from_array([]),
    operation: "initial",
    frame: 0,
  }
  for
    name in [
      "$host", "$ancestor_position", "$ancestor", "$before_position", "ordinary.before",
      "$attachments", "$reference",
    ] {
    probe.register(name)
  }
  for layer in array(field(scenario, "layers")) {
    let prefix = string(field(layer, "id"))
    for
      suffix in [
        "anchor", "root", "$reference", "$before_position", "before", "$after_position",
        "after", "nested.anchor", "nested.root",
      ] {
      probe.register(prefix + "." + suffix)
    }
  }
  for name in ["$after_position", "ordinary.after"] {
    probe.register(name)
  }
  probe.start("initial", object([("action", @json.to_json("open_window"))]))
  probe.render(scenario, "base", 2) |> ignore
  probe.end(2)
  let scale = number(field(scenario, "scale_factor"))
  for stage in ["base", "updated", "removed", "restored", "moved"] {
    let input = match stage {
      "base" =>
        object([
          ("action", @json.to_json("set_scale_factor")),
          ("scale_factor", @json.to_json(scale)),
        ])
      "updated" =>
        object([
          ("action", @json.to_json("set_parent_priority")),
          ("layer", field(scenario, "update_layer")),
          ("priority", field(scenario, "update_priority")),
        ])
      "removed" =>
        object([
          ("action", @json.to_json("remove_nested_child")),
          ("layer", field(scenario, "remove_nested")),
        ])
      "restored" => object([("action", @json.to_json("restore_original_tree"))])
      _ =>
        object([
          ("action", @json.to_json("move_ancestor")),
          ("delta", field(scenario, "ancestor_movement")),
        ])
    }
    probe.start(stage, input)
    probe.render(scenario, stage, scale) |> ignore
    probe.end(scale)
  }
  object([
    ("id", field(scenario, "id")),
    ("events", @json.to_json(probe.events)),
  ])
}

///|
fn main {
  let input = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch {
    _ => abort("invalid scenarios")
  }
  println(
    object([
      ("schema_version", @json.to_json(1)),
      ("layer", @json.to_json("compiled-moonbit-nested-deferred")),
      ("fixture", @json.to_json("font-free-two-level-nested-deferred")),
      ("input", input),
      ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
      ("cases", @json.to_json(array(field(input, "cases")).map(observe))),
    ]).stringify(),
  )
}
