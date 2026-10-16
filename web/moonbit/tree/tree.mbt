///|
fn tree_color(index : Int32) -> @primitives.Color {
  let (red, green, blue) = match index % 4 {
    0 => (255, 0, 0)
    1 => (0, 0, 255)
    2 => (0, 128, 0)
    _ => (255, 255, 0)
  }
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn tree_style() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  .with_align(@layout.AlignItems::stretch())
  .with_insets(@layout.Insets::all(2.0).unwrap(), @layout.Insets::zero())
}

///|
fn tree_node(index : Int32) -> @element.Element {
  // Upstream uses block layout. A single-child column with auto main size and
  // stretched cross size preserves that block flow without precomputed bounds.
  @element.Element::new(
    @layout.FlexItem::new(
      (index + 2).to_uint64(),
      @layout.Dimension::auto(),
      @layout.Dimension::auto(),
      @primitives.Size::new(0.0, 0.0).unwrap(),
    )
    .with_flex(0.0, 0.0)
    .unwrap(),
  )
  .with_children_style(tree_style())
  .with_background(Some(tree_color(index)))
}

///|
fn tree_layout(depth : Int32) -> @element.Prepainted {
  // GPUI stretches an auto-sized window root to the viewport before layout
  // (window.rs -> TaffyLayoutEngine::stretch_auto_size_to_fill). The colored
  // outer block is that root, not a shrink-wrapped child of a synthetic root.
  let mut root = @element.Element::root((depth + 2).to_uint64(), tree_style()).with_background(
    Some(tree_color(depth)),
  )
  // As in tree.rs, depth counts wrapping operations, not total colored nodes.
  if depth > 0 {
    let mut inner = tree_node(0)
    for index = 1; index < depth; index = index + 1 {
      inner = tree_node(index).with_child(inner)
    }
    root = root.with_child(inner)
  }
  root
  .request_layout(@primitives.Size::new(300.0, 300.0).unwrap())
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
#export_name("tree_metadata")
pub fn tree_metadata() -> String {
  "{\"id\":\"tree\",\"width\":300,\"height\":300,\"depth\":50,\"node_count\":51,\"padding\":2,\"interactive\":false}"
}

///|
#export_name("tree_frame")
pub fn tree_frame(scale : Double) -> String {
  if !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let snapshot = tree_layout(50).paint_snapshot(scale).unwrap()
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"host_extensions\":[]}"
}
