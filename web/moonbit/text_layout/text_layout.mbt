///|
fn color(red : Int, green : Int, blue : Int) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn fixed(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    id, @layout.Dimension::points(main).unwrap(),
    @layout.Dimension::points(cross).unwrap(), @primitives.Size::new(0.0, 0.0).unwrap(),
  ).with_flex(0.0, 0.0).unwrap())
}

///|
fn row(justify : @layout.JustifyContent) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::row()).with_justify(justify)
}

///|
fn text_layout_tree(widths : Array[Double]) -> @element.Prepainted {
  // Reproduce the upstream element tree. Positions come from gpui.mbt layout,
  // never from saved screenshots or fixed result coordinates.
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
    .with_gap(8.0).unwrap()
    .with_insets(@layout.Insets::all(16.0).unwrap(), @layout.Insets::zero())
  let line_ids : Array[UInt64] = [2, 3, 4, 5, 6, 7, 8, 9, 10]
  let text_ids : Array[UInt64] = [102, 103, 104, 105, 106, 107, 108, 109, 110]
  let mut root = @element.Element::root(1, column).with_background(Some(color(255, 255, 255)))
  for index = 0; index < 9; index = index + 1 {
    let alignment = if index % 3 == 0 { @layout.JustifyContent::start() }
      else if index % 3 == 1 { @layout.JustifyContent::center() }
      else { @layout.JustifyContent::end() }
    root = root.with_child(fixed(line_ids[index], 26.0, 768.0)
      .with_children_style(row(alignment))
      .with_child(fixed(text_ids[index], widths[index], 26.0)))
  }
  let inset = @layout.Insets::all(4.0).unwrap()
  let border = @layout.Insets::all(1.0).unwrap()
  let boxes = fixed(20, 36.0, 768.0)
    .with_children_style(row(@layout.JustifyContent::start()).with_gap(8.0).unwrap())
    .with_child(fixed(21, 400.0, 36.0).with_background(Some(color(255, 255, 255)))
      .with_children_style(row(@layout.JustifyContent::center()).with_insets(inset, border))
      .with_child(fixed(121, widths[9], 26.0)))
    // Pinned gpui.mbt has start/center/end only. A real flexible spacer gives
    // the two upstream justify_between children the same available free space.
    .with_child(@element.Element::new(@layout.FlexItem::new(23,
      @layout.Dimension::points(0.0).unwrap(), @layout.Dimension::points(36.0).unwrap(),
      @primitives.Size::new(0.0, 0.0).unwrap()).with_flex(1.0, 0.0).unwrap()))
    .with_child(fixed(22, 128.0, 36.0).with_background(Some(color(255, 255, 255)))
      .with_children_style(row(@layout.JustifyContent::end()).with_insets(inset, border))
      .with_child(fixed(122, widths[10], 26.0)))
  let mut styled = fixed(30, 26.0, 768.0).with_children_style(row(@layout.JustifyContent::start()))
  let run_ids : Array[UInt64] = [131, 132, 133, 134]
  for index = 0; index < 4; index = index + 1 {
    styled = styled.with_child(fixed(run_ids[index], widths[index + 11], 26.0))
  }
  root.with_child(boxes).with_child(styled)
    .request_layout(@primitives.Size::new(800.0, 600.0).unwrap()).unwrap()
    .prepaint().unwrap()
}

///|
#export_name("text_layout_metadata")
pub fn text_layout_metadata() -> String {
  "{\"id\":\"text_layout\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":false,\"runs\":[{\"id\":102,\"text\":\"Text left\",\"weight\":400,\"style\":\"normal\"},{\"id\":103,\"text\":\"Text center\",\"weight\":400,\"style\":\"normal\"},{\"id\":104,\"text\":\"Text right\",\"weight\":400,\"style\":\"normal\"},{\"id\":105,\"text\":\"Text left (underline)\",\"weight\":400,\"style\":\"normal\"},{\"id\":106,\"text\":\"Text center (underline)\",\"weight\":400,\"style\":\"normal\"},{\"id\":107,\"text\":\"Text right (underline)\",\"weight\":400,\"style\":\"normal\"},{\"id\":108,\"text\":\"Text left (line_through)\",\"weight\":400,\"style\":\"normal\"},{\"id\":109,\"text\":\"Text center (line_through)\",\"weight\":400,\"style\":\"normal\"},{\"id\":110,\"text\":\"Text right (line_through)\",\"weight\":400,\"style\":\"normal\"},{\"id\":121,\"text\":\"A long non-wrapping text align center\",\"weight\":400,\"style\":\"normal\"},{\"id\":122,\"text\":\"100%\",\"weight\":400,\"style\":\"normal\"},{\"id\":131,\"text\":\"A\",\"weight\":800,\"style\":\"normal\"},{\"id\":132,\"text\":\"B\",\"weight\":400,\"style\":\"normal\"},{\"id\":133,\"text\":\"C\",\"weight\":400,\"style\":\"italic\"},{\"id\":134,\"text\":\"D\",\"weight\":400,\"style\":\"normal\"}]}"
}

///|
#export_name("text_layout_frame")
pub fn text_layout_frame(widths : Array[Double], scale : Double) -> String {
  if widths.length() != 15 || !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  for width in widths {
    if !(width >= 0.0 && width <= 768.0) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  let prepainted = text_layout_tree(widths)
  let tree = prepainted.tree()
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  let ids : Array[UInt64] = [102, 103, 104, 105, 106, 107, 108, 109, 110, 121, 122, 131, 132, 133, 134]
  let texts = ["Text left", "Text center", "Text right", "Text left (underline)", "Text center (underline)", "Text right (underline)", "Text left (line_through)", "Text center (line_through)", "Text right (line_through)", "A long non-wrapping text align center", "100%", "A", "B", "C", "D"]
  let clips = [
    @scene.ClipChain::new(21, [tree.node(21).unwrap().bounds()]),
    @scene.ClipChain::new(22, [tree.node(22).unwrap().bounds()]),
  ]
  for index = 0; index < ids.length(); index = index + 1 {
    let clip = if index == 9 { Some(21) } else if index == 10 { Some(22) } else { None }
    items.push(@scene.SceneItem::text(ids[index], tree.node(ids[index]).unwrap().bounds(),
      texts[index], 16.0, color(0, 0, 0), @scene.AffineTransform::identity(), 1.0, clip).unwrap())
  }
  let snapshot = @scene.SceneSnapshot::new(base.viewport(), scale, [], clips, items).unwrap()
  let decorations = "[{\"id\":21,\"radius\":0,\"border\":\"#0000ff\",\"border_width\":1,\"border_style\":\"solid\"},{\"id\":22,\"radius\":0,\"border\":\"#0000ff\",\"border_width\":1,\"border_style\":\"solid\"}]"
  let styles = "[{\"id\":102,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":103,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":104,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":105,\"weight\":400,\"style\":\"normal\",\"decoration\":\"underline\"},{\"id\":106,\"weight\":400,\"style\":\"normal\",\"decoration\":\"underline\"},{\"id\":107,\"weight\":400,\"style\":\"normal\",\"decoration\":\"underline\"},{\"id\":108,\"weight\":400,\"style\":\"normal\",\"decoration\":\"line_through\"},{\"id\":109,\"weight\":400,\"style\":\"normal\",\"decoration\":\"line_through\"},{\"id\":110,\"weight\":400,\"style\":\"normal\",\"decoration\":\"line_through\"},{\"id\":121,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":122,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":131,\"weight\":800,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":132,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"},{\"id\":133,\"weight\":400,\"style\":\"italic\",\"decoration\":\"none\"},{\"id\":134,\"weight\":400,\"style\":\"normal\",\"decoration\":\"none\"}]"
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":\{decorations},\"text_styles\":\{styles},\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"font_style\",\"text_decoration\"]}"
}
