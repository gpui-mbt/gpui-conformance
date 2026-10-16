///|
fn color(red : Int, green : Int, blue : Int) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn fixed(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      @layout.Dimension::points(main).unwrap(),
      @layout.Dimension::points(cross).unwrap(),
      @primitives.Size::new(0.0, 0.0).unwrap(),
    ).with_flex(0.0, 0.0).unwrap(),
  )
}

///|
fn hello_world_layout(text_width : Double) -> @element.Prepainted {
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
    .with_gap(12.0).unwrap()
    .with_justify(@layout.JustifyContent::center())
    .with_align(@layout.AlignItems::center())
    .with_insets(@layout.Insets::zero(), @layout.Insets::all(1.0).unwrap())
  let row_style = @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
    .with_gap(8.0).unwrap()
  let colors = [
    color(255, 0, 0), color(0, 128, 0), color(0, 0, 255),
    color(255, 255, 0), color(0, 0, 0), color(255, 255, 255),
  ]
  let ids : Array[UInt64] = [4, 5, 6, 7, 8, 9]
  let mut row = fixed(3, 32.0, 232.0).with_children_style(row_style)
  for index = 0; index < colors.length(); index = index + 1 {
    row = row.with_child(
      fixed(ids[index], 32.0, 32.0).with_background(Some(colors[index])),
    )
  }
  // Do not replace this tree with precomputed boxes: layout is the candidate under test.
  @element.Element::root(1, column)
    .with_background(Some(color(80, 80, 80)))
    .with_child(fixed(2, 32.0, text_width))
    .with_child(row)
    .request_layout(@primitives.Size::new(500.0, 500.0).unwrap()).unwrap()
    .prepaint().unwrap()
}

///|
#export_name("hello_world_metadata")
pub fn hello_world_metadata() -> String {
  "{\"id\":\"hello_world\",\"width\":500,\"height\":500,\"text\":\"Hello, World!\",\"font_family\":\"IBM Plex Sans\",\"font_size\":20,\"line_height\":32,\"interactive\":false}"
}

///|
#export_name("hello_world_frame")
pub fn hello_world_frame(text_width : Double, scale : Double) -> String {
  // NaN fails these ordered comparisons; no invalid host metric may reach unwrap.
  if !(text_width >= 0.0 && text_width <= 498.0 && scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let prepainted = hello_world_layout(text_width)
  let title_bounds = prepainted.tree().node(2).unwrap().bounds()
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  items.push(
    @scene.SceneItem::text(
      2, title_bounds, "Hello, World!", 20.0, color(255, 255, 255),
      @scene.AffineTransform::identity(), 1.0, None,
    ).unwrap(),
  )
  let snapshot = @scene.SceneSnapshot::new(
    base.viewport(), scale, [], [], items,
  ).unwrap()
  // The public scene format has no rounded/dashed borders. Keep the host extension
  // separate rather than claiming it is a native SceneSnapshot capability.
  let decorations = "[{\"id\":1,\"radius\":0,\"border\":\"#0000ff\",\"border_width\":1,\"border_style\":\"solid\",\"shadow\":true},{\"id\":4,\"radius\":6,\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"},{\"id\":5,\"radius\":6,\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"},{\"id\":6,\"radius\":6,\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"},{\"id\":7,\"radius\":6,\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"},{\"id\":8,\"radius\":6,\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"},{\"id\":9,\"radius\":6,\"border\":\"#000000\",\"border_width\":1,\"border_style\":\"dashed\"}]"
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":\{decorations},\"conformance\":\"unverified\",\"host_extensions\":[\"rounded_border\",\"dashed_border\",\"shadow\",\"font_metrics\"]}"
}
