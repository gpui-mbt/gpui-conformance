///|
extern "js" fn input() -> String =
  #| () => process.env.SCROLL_SCENARIOS

///|
fn field(v : Json, key : String) -> Json {
  match v {
    Object(fields) => fields.get(key).unwrap()
    _ => abort("object")
  }
}

///|
fn array(v : Json) -> Array[Json] {
  match v {
    Array(values) => values
    _ => abort("array")
  }
}

///|
fn number(v : Json) -> Double {
  match v {
    Number(n, ..) => n
    _ => abort("number")
  }
}

///|
fn object(v : Array[(String, Json)]) -> Json {
  Json::object(Map::from_array(v))
}

///|
fn point(x : Double, y : Double) -> @primitives.Point {
  @primitives.Point::new(x, y).unwrap()
}

///|
fn xy(p : @primitives.Point) -> Json {
  @json.to_json([p.x(), p.y()])
}

///|
fn rect(b : @primitives.Rect) -> Json {
  @json.to_json([b.left(), b.top(), b.size().width(), b.size().height()])
}

///|
fn block(id : UInt64, w : Double, h : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      @layout.Dimension::points(h).unwrap(),
      @layout.Dimension::points(w).unwrap(),
      @primitives.Size::new(0, 0).unwrap(),
    )
    .with_flex(0, 0)
    .unwrap(),
  ).with_children_style(
    @layout.FlexTreeStyle::new(@layout.FlowDirection::column()),
  )
}

///|
fn view(
  outer : @primitives.Point,
  inner : @primitives.Point,
) -> @element.Prepainted {
  @element.Element::root(
    1,
    @layout.FlexTreeStyle::new(@layout.FlowDirection::column()),
  )
  .with_pointer_events(false)
  .with_child(
    block(2, 160, 120)
    .with_scroll_offset(outer)
    .with_child(
      block(3, 320, 360)
      .with_child(
        block(4, 160, 60)
        .with_scroll_offset(inner)
        .with_child(block(5, 320, 60)),
      )
      .with_child(block(6, 320, 300)),
    ),
  )
  .request_layout(@primitives.Size::new(240, 180).unwrap())
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn main {
  let input = try! @json.parse(input())
  let cases : Array[Json] = []
  for case in array(field(input, "cases")) {
    let mut outer = point(0, 0)
    let mut inner = point(0, 0)
    let wheels = array(field(case, "wheels"))
    let frames : Array[Json] = []
    for step = -1; step < wheels.length(); step = step + 1 {
      if step >= 0 {
        let wheel = array(wheels[step])
        let tree = view(outer, inner).tree()
        // GPUI pixel deltas move content; core deltas advance the viewport.
        for
          update in tree
          .scroll_wheel(
            point(number(wheel[0]), number(wheel[1])),
            -number(wheel[2]),
            -number(wheel[3]),
          )
          .unwrap() {
          if update.id() == 2 {
            outer = update.offset()
          }
          if update.id() == 4 {
            inner = update.offset()
          }
        }
      }
      let tree = view(outer, inner).tree()
      let bounds : Array[Json] = []
      for id = 2; id <= 6; id = id + 1 {
        bounds.push(
          @json.to_json([
            @json.to_json(id),
            rect(tree.node(id.to_uint64()).unwrap().bounds()),
          ]),
        )
      }
      let targets = array(field(input, "points")).map(p => {
        let p = array(p)
        match
          tree.dispatch_pointer(point(number(p[0]), number(p[1]))).target() {
          Some(id) => @json.to_json(id.to_int())
          None => Json::null()
        }
      })
      let outside = tree.scroll_viewport(2).unwrap()
      let inside = tree.scroll_viewport(4).unwrap()
      // Core uses positive content offsets; upstream ScrollHandle exposes the
      // corresponding negative translation. This is representation only.
      frames.push(
        object([
          (
            "offsets",
            @json.to_json([
              xy(point(-outside.offset().x(), -outside.offset().y())),
              xy(point(-inside.offset().x(), -inside.offset().y())),
            ]),
          ),
          (
            "maximums",
            @json.to_json([xy(outside.max_offset()), xy(inside.max_offset())]),
          ),
          ("bounds", @json.to_json(bounds)),
          ("targets", @json.to_json(targets)),
        ]),
      )
    }
    cases.push(
      object([("id", field(case, "id")), ("frames", @json.to_json(frames))]),
    )
  }
  println(
    object([
      ("schema_version", @json.to_json(1)),
      ("backend", @json.to_json("moonbit")),
      ("input", input),
      ("cases", @json.to_json(cases)),
    ]).stringify(),
  )
}
