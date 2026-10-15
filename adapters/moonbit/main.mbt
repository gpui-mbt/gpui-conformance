///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value {
    Ok(value) => value
    Err(_) => abort("framework operation failed")
  }
}

///|
fn field(value : Json, key : String) -> Json {
  match value {
    Object(fields) => fields.get(key).unwrap()
    _ => abort("expected object")
  }
}

///|
fn optional(value : Json, key : String) -> Json? {
  match value {
    Object(fields) => fields.get(key)
    _ => None
  }
}

///|
fn array(value : Json) -> Array[Json] {
  match value {
    Array(values) => values
    _ => abort("expected array")
  }
}

///|
fn number(value : Json) -> Double {
  match value {
    Number(value, ..) => value
    _ => abort("expected number")
  }
}

///|
fn string(value : Json) -> String {
  match value {
    String(value) => value
    _ => abort("expected string")
  }
}

///|
fn boolean(value : Json) -> Bool {
  match value {
    True => true
    False => false
    _ => abort("expected bool")
  }
}

///|
fn object(fields : Array[(String, Json)]) -> Json {
  Json::object(Map::from_array(fields))
}

///|
fn bounds(rect : @primitives.Rect) -> Json {
  @json.to_json([
    rect.left(),
    rect.top(),
    rect.size().width(),
    rect.size().height(),
  ])
}

///|
fn rect(value : Json) -> @primitives.Rect {
  let v = array(value)
  checked(
    @primitives.Rect::new(
      number(v[0]),
      number(v[1]),
      number(v[2]),
      number(v[3]),
    ),
  )
}

///|
fn tree(s : Json) -> @element.Prepainted {
  let direction = if optional(s, "direction") == Some(@json.to_json("column")) {
    @layout.FlowDirection::column()
  } else {
    @layout.FlowDirection::row()
  }
  let justify = match optional(s, "justify") {
    Some(String("center")) => @layout.JustifyContent::center()
    Some(String("end")) => @layout.JustifyContent::end()
    _ => @layout.JustifyContent::start()
  }
  let align = match optional(s, "align") {
    Some(String("center")) => @layout.AlignItems::center()
    Some(String("end")) => @layout.AlignItems::end()
    _ => @layout.AlignItems::start()
  }
  let style = checked(
    @layout.FlexTreeStyle::new(direction)
    .with_justify(justify)
    .with_align(align)
    .with_gap(number(field(s, "gap"))),
  )
  let mut root = @element.Element::root(1, style).with_focusable(true)
  for i, child in array(field(s, "children")) {
    let dimensions = array(child)
    let width = number(dimensions[0])
    let height = number(dimensions[1])
    let item = @layout.FlexItem::new(
      (i + 2).to_uint64(),
      checked(
        @layout.Dimension::points(
          if direction is @layout.Column {
            height
          } else {
            width
          },
        ),
      ),
      checked(
        @layout.Dimension::points(
          if direction is @layout.Column {
            width
          } else {
            height
          },
        ),
      ),
      checked(@primitives.Size::new(width, height)),
    )
    let item = checked(
      item.with_flex(
        match optional(s, "grow") {
          Some(value) => number(array(value)[i])
          None => 0.0
        },
        match optional(s, "shrink") {
          Some(value) => number(array(value)[i])
          None => 1.0
        },
      ),
    )
    let item = checked(
      item.with_main_limits(
        match optional(s, "min_main") {
          Some(value) => number(array(value)[i])
          None => 0.0
        },
        match optional(s, "max_main") {
          Some(value) =>
            match array(value)[i] {
              Null => None
              limit => Some(number(limit))
            }
          None => None
        },
      ),
    )
    root = root.with_child(
      @element.Element::new(item).with_background(
        Some(checked(@primitives.Color::rgba(32, 64, 96, 255))),
      ).with_focusable(string(field(s, "kind")) == "focus"),
    )
  }
  checked(
    checked(
      root.request_layout(
        checked(
          @primitives.Size::new(
            number(field(s, "width")),
            number(field(s, "height")),
          ),
        ),
      ),
    ).prepaint(),
  )
}

///|
fn observe(s : Json) -> Json {
  let kind = string(field(s, "kind"))
  if kind == "focus" || kind == "route" { return observe_routing(s) }
  let row : Map[String, Json] = Map::from_array([
    ("id", field(s, "id")),
    ("layer", field(s, "layer")),
    ("status", @json.to_json("observed")),
  ])
  match kind {
    "scene" => {
      let snapshot = checked(tree(s).paint_snapshot(1))
      let quads = snapshot
        .items()
        .map(item => {
          match item {
            @scene.QuadItem(bounds=quad_bounds, color~, ..) =>
              object([
                ("bounds", bounds(quad_bounds)),
                (
                  "rgba",
                  @json.to_json([
                    color.red(),
                    color.green(),
                    color.blue(),
                    color.alpha(),
                  ]),
                ),
              ])
            _ => abort("fixture emitted a non-quad")
          }
        })
      row["observation"] = object([("quads", @json.to_json(quads))])
    }
    "window" | "pixels" => {
      row["status"] = @json.to_json("unverified")
      row["reason"] = @json.to_json(
        "Native macOS fixture requires coordinated foreground execution; not executed",
      )
    }
    "ime" => {
      row["status"] = @json.to_json("unsupported")
      row["reason"] = @json.to_json(
        "IME composition is outside this first slice",
      )
    }
    "clip" => {
      let viewport = checked(
        @primitives.Rect::new(
          0,
          0,
          number(field(s, "width")),
          number(field(s, "height")),
        ),
      )
      let clips = array(field(s, "clips"))
      // Generate and validate a real scene snapshot; clip chains are retained.
      let scene = @scene.Scene::new([
        @scene.PaintCommand::clip_push(1, rect(clips[0])),
        @scene.PaintCommand::clip_push(2, rect(clips[1])),
        @scene.PaintCommand::quad(
          3,
          viewport,
          checked(@primitives.Color::rgba(32, 64, 96, 255)),
        ),
        @scene.PaintCommand::clip_pop(2),
        @scene.PaintCommand::clip_pop(1),
      ])
      let snapshot = checked(scene.snapshot_v1(viewport, 1))
      let mut clip = viewport
      for r in snapshot.clip_chains()[0].rects() {
        clip = clip.intersection(r).unwrap()
      }
      row["observation"] = object([("effective_clip", bounds(clip))])
    }
    "layout" => {
      let painted = tree(s)
      // Execute the complete request-layout/prepaint/paint-snapshot path.
      ignore(checked(painted.paint_snapshot(1)))
      let output = painted.tree().nodes().map(node => bounds(node.bounds()))
      if @env.get_env_var("GPUI_NEGATIVE_CONTROL") == Some("1") {
        let first = array(output[1])
        first[2] = @json.to_json(number(first[2]) + 1)
        output[1] = Json::array(first)
      }
      row["observation"] = object([("bounds", @json.to_json(output))])
    }
    "pointer" => {
      let element_tree = tree(s).tree()
      let targets = array(field(s, "points")).map(p => {
        let coords = array(p)
        let plan = element_tree.dispatch_input(
          @primitives.PointerButtonPressed(
            position=checked(
              @primitives.Point::new(number(coords[0]), number(coords[1])),
            ),
            button=@primitives.Primary,
            modifiers=@primitives.Modifiers::none(),
          ),
        )
        match plan.target() {
          Some(id) if id > 1 => @json.to_json(id.to_int())
          _ => Json::null()
        }
      })
      row["observation"] = object([("targets", @json.to_json(targets))])
    }
    "key" => {
      let element_tree = checked(tree(s).tree().with_focus(1))
      let keys : Array[Json] = []
      for k in array(field(s, "keys")) {
        let v = array(k)
        let event = @primitives.KeyPressed(
          key=@primitives.Character(string(v[0])),
          modifiers=@primitives.Modifiers::new(
            shift=boolean(v[1]),
            control=boolean(v[2]),
            alt=boolean(v[3]),
            meta=boolean(v[4]),
          ),
          repeat=boolean(v[5]),
        )
        ignore(
          checked(
            element_tree.dispatch_input_with(event, (context, event) => {
              if context.phase() is @element.Bubble {
                match event {
                  @primitives.KeyPressed(
                    key=@primitives.Character(key),
                    modifiers~,
                    repeat~
                  ) =>
                    keys.push(
                      @json.to_json([
                        @json.to_json(key),
                        @json.to_json(modifiers.shift()),
                        @json.to_json(modifiers.control()),
                        @json.to_json(modifiers.alt()),
                        @json.to_json(modifiers.meta()),
                        @json.to_json(repeat),
                      ]),
                    )
                  _ => ()
                }
              }
              Ok(())
            }),
          ),
        )
      }
      row["observation"] = object([("keys", @json.to_json(keys))])
    }
    _ => abort("unknown scenario kind")
  }
  Json::object(row)
}

///|
fn main {
  let raw = @env.get_env_var("GPUI_SCENARIOS").unwrap()
  let scenarios = @json.parse(raw) catch { _ => abort("invalid scenarios") }
  let cases = array(field(scenarios, "cases")).map(observe)
  let output = object([
    ("implementation", @json.to_json("moonbit")),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("cases", @json.to_json(cases)),
  ])
  println("GPUI_CONFORMANCE " + output.stringify())
}
