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
fn dimension(value : Json) -> @layout.Dimension {
  match value {
    Null => @layout.Dimension::auto()
    _ => checked(@layout.Dimension::points(number(value)))
  }
}

///|
fn dimension_fallback(value : Json) -> Double {
  match value {
    Null => 0.0
    _ => number(value)
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
fn tree(s : Json) -> @element.Prepainted {
  let direction = match optional(s, "direction") {
    Some(String("column")) => @layout.FlowDirection::column()
    Some(String("column_reverse")) => @layout.FlowDirection::column_reverse()
    Some(String("row_reverse")) => @layout.FlowDirection::row_reverse()
    _ => @layout.FlowDirection::row()
  }
  let is_column = optional(s, "direction") == Some(@json.to_json("column")) ||
    optional(s, "direction") == Some(@json.to_json("column_reverse"))
  let justify = match optional(s, "justify") {
    Some(String("center")) => @layout.JustifyContent::center()
    Some(String("end")) => @layout.JustifyContent::end()
    Some(String("space-between")) => @layout.JustifyContent::space_between()
    Some(String("space-around")) => @layout.JustifyContent::space_around()
    Some(String("space-evenly")) => @layout.JustifyContent::space_evenly()
    _ => @layout.JustifyContent::start()
  }
  let align = match optional(s, "align") {
    Some(String("center")) => @layout.AlignItems::center()
    Some(String("end")) => @layout.AlignItems::end()
    Some(String("stretch")) => @layout.AlignItems::stretch()
    _ => @layout.AlignItems::start()
  }
  let align_content = match optional(s, "align_content") {
    Some(String("space-between")) => @layout.AlignContent::space_between()
    Some(String("space-around")) => @layout.AlignContent::space_around()
    Some(String("space-evenly")) => @layout.AlignContent::space_evenly()
    Some(String("start")) => @layout.AlignContent::start()
    Some(String("center")) => @layout.AlignContent::center()
    Some(String("end")) => @layout.AlignContent::end()
    _ => @layout.AlignContent::stretch()
  }
  let wrap = match optional(s, "wrap") {
    Some(String("wrap")) => @layout.FlexWrap::wrap()
    Some(String("wrap_reverse")) => @layout.FlexWrap::wrap_reverse()
    _ => @layout.FlexWrap::no_wrap()
  }
  let style = checked(
    @layout.FlexTreeStyle::new(direction)
    .with_wrap(wrap)
    .with_justify(justify)
    .with_align(align)
    .with_align_content(align_content)
    .with_gap(number(field(s, "gap"))),
  )
  let style = match optional(s, "padding") {
    Some(p) => {
      let p = array(p)
      style.with_insets(
        checked(
          @layout.Insets::new(
            number(p[0]),
            number(p[1]),
            number(p[2]),
            number(p[3]),
          ),
        ),
        @layout.Insets::zero(),
      )
    }
    None => style
  }
  let style = match optional(s, "gap_x") {
    Some(v) => checked(style.with_gap_x(number(v)))
    None => style
  }
  let style = match optional(s, "gap_y") {
    Some(v) => checked(style.with_gap_y(number(v)))
    None => style
  }
  let mut root = @element.Element::root(1, style)
  for i, child in array(field(s, "children")) {
    let dimensions = array(child)
    let width = dimension_fallback(dimensions[0])
    let height = dimension_fallback(dimensions[1])
    let item = @layout.FlexItem::new(
      (i + 2).to_uint64(),
      if is_column {
        dimension(dimensions[1])
      } else {
        dimension(dimensions[0])
      },
      if is_column {
        dimension(dimensions[0])
      } else {
        dimension(dimensions[1])
      },
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
    let item = checked(
      item.with_cross_limits(
        match optional(s, "min_cross") {
          Some(value) => number(array(value)[i])
          None => 0.0
        },
        match optional(s, "max_cross") {
          Some(value) =>
            match array(value)[i] {
              Null => None
              limit => Some(number(limit))
            }
          None => None
        },
      ),
    )
    let item = item.with_align_self(
      match optional(s, "align_self") {
        Some(value) =>
          match array(value)[i] {
            String("start") => @layout.AlignSelf::start()
            String("end") => @layout.AlignSelf::end()
            String("center") => @layout.AlignSelf::center()
            String("stretch") => @layout.AlignSelf::stretch()
            String("flex_start") => @layout.AlignSelf::flex_start()
            String("flex_end") => @layout.AlignSelf::flex_end()
            String("auto") => @layout.AlignSelf::auto()
            _ => abort("unsupported align_self")
          }
        None => @layout.AlignSelf::auto()
      },
    )
    root = root.with_child(
      @element.Element::new(item).with_background(
        Some(checked(@primitives.Color::rgba(32, 64, 96, 255))),
      ),
    )
  }
  let viewport = checked(
    @primitives.Size::new(number(field(s, "width")), number(field(s, "height"))),
  )
  let requested = match optional(s, "device_scale_factor") {
    Some(scale) =>
      checked(root.request_layout_with_device_scale(viewport, number(scale)))
    None => checked(root.request_layout(viewport))
  }
  checked(requested.prepaint())
}

///|
fn observe(s : Json) -> Json {
  if string(field(s, "kind")) != "layout" {
    abort("layout-only probe")
  }
  let painted = tree(s)
  ignore(
    checked(painted.paint_snapshot(number(field(s, "device_scale_factor")))),
  )
  let output = painted.tree().nodes().map(node => bounds(node.bounds()))
  if @env.get_env_var("GPUI_NEGATIVE_CONTROL") == Some("1") {
    let first = array(output[1])
    first[2] = @json.to_json(number(first[2]) + 1)
    output[1] = Json::array(first)
  }
  object([
    ("id", field(s, "id")),
    ("layer", @json.to_json("headless-layout")),
    ("status", @json.to_json("observed")),
    ("observation", object([("bounds", @json.to_json(output))])),
  ])
}

///|
fn main {
  let raw = @env.get_env_var("GPUI_SCENARIOS").unwrap()
  let scenarios = @json.parse(raw) catch { _ => abort("invalid scenarios") }
  let cases = array(field(scenarios, "cases")).map(observe)
  let output = object([
    ("implementation", @json.to_json("moonbit")),
    ("cases", @json.to_json(cases)),
  ])
  println("GPUI_CONFORMANCE " + output.stringify())
}
