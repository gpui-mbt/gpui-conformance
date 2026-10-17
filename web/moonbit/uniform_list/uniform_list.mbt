///|
// Unchanged source5a uniform_list.rs port. Only font shaping and input transport
// are host services. Production UniformList owns measurement/ranges/IDs/offsets.
priv struct ListState {
  mut offset : Double
  mut tree : @element.ElementTree?
  click : @element.UniformListClickSession
  mut clicked : Int?
}

///|
fn initial_state() -> ListState {
  { offset: 0.0, tree: None, click: @element.UniformListClickSession::new(2), clicked: None }
}

///|
let list_state : Ref[ListState] = Ref(initial_state())

///|
fn line_height() -> Double { 16.0 * 1.618033988749895 }

///|
fn quote(text : String) -> String { @json.to_json(text).stringify() }

///|
fn label(index : Int) -> String { "Item \{index + 1}" }

///|
#export_name("uniform_list_metadata")
pub fn uniform_list_metadata() -> String {
  let runs : Array[String] = []
  for index = 0; index < 50; index = index + 1 {
    runs.push("{\"text\":\{quote(label(index))},\"font_size\":16}")
  }
  "{\"id\":\"uniform_list\",\"width\":300,\"height\":300,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":\{line_height()},\"runs\":[\{runs.join(",")}],\"source_blob\":\"4a2c4788b192d802ee3d51714c250e7c5a82db76\",\"metrics_contract\":\"50 unhinted shaped widths, prefix advances and glyph advances; source-authored 16phi line height; device scale\",\"conformance\":\"unverified\"}"
}

///|
#export_name("uniform_list_reset")
pub fn uniform_list_reset() -> Unit { list_state.val = initial_state() }

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
}

///|
fn intrinsic(id : UInt64, width : Double, height : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    id, @layout.Dimension::auto(), @layout.Dimension::auto(),
    @primitives.Size::new(width, height).unwrap(),
  ).with_flex(0.0, 0.0).unwrap())
}

///|
fn rect_json(bounds : @primitives.Rect) -> String {
  "{\"x\":\{bounds.left()},\"y\":\{bounds.top()},\"width\":\{bounds.size().width()},\"height\":\{bounds.size().height()}}"
}

///|
fn layout_list(
  state : ListState, widths : Array[Double], height : Double, scale : Double,
  calls : Array[String], anchors : Map[UInt64, Int],
) -> @element.Prepainted {
  let white = @primitives.Color::rgba(255, 255, 255, 255).unwrap()
  let transparent = @primitives.Color::rgba(0, 0, 0, 0).unwrap()
  let list = @element.UniformList::new(
    @layout.FlexItem::new(2, @layout.Dimension::points(300).unwrap(),
      @layout.Dimension::points(300).unwrap(), @primitives.Size::new(0, 0).unwrap())
      .with_flex(0, 0).unwrap(),
    50, @element.UniformListIdSpace::new(100, 2).unwrap(), range => {
      let rows : Array[@element.Element] = []
      let ids : Array[String] = []
      for index = range.start(); index < range.end(); index = index + 1 {
        let row_id = range.id(index, 0).unwrap()
        let anchor_id = range.id(index, 1).unwrap()
        anchors.set(anchor_id, index)
        ids.push("\{row_id}")
        rows.push(intrinsic(row_id, 0, 0)
          .with_children_style(column().with_align(@layout.AlignItems::stretch())
            .with_insets(@layout.Insets::new(0, 8, 0, 8).unwrap(), @layout.Insets::zero()))
          .with_child(intrinsic(anchor_id, widths[index], height)
            .with_background(Some(transparent)).with_pointer_events(false)))
      }
      calls.push("{\"start\":\{range.start()},\"end\":\{range.end()},\"created_ids\":[\{ids.join(",")}]}" )
      Ok(rows)
    },
  ).unwrap().with_scroll_offset(state.offset).unwrap().into_element()
  @element.Element::root(1, column()).with_background(Some(white)).with_child(list)
    .request_layout_with_device_scale(@primitives.Size::new(300, 300).unwrap(), scale)
    .unwrap().prepaint().unwrap()
}

///|
fn text_snapshot(
  prepainted : @element.Prepainted, scale : Double, anchors : Map[UInt64, Int],
  prefixes : Array[Array[Double]], advances : Array[Array[Double]],
) -> @scene.SceneSnapshot {
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match (item, anchors.get(item.id())) {
      (@scene.QuadItem(id~, bounds~, transform~, opacity~, clip_chain_id~, ..), Some(index)) => {
        // Shaping and rasterization are distinct in source5a. These ASCII glyph
        // origins derive only from explicit host-measured unhinted metrics.
        // Preserve the real core anchor bounds, transform, clips and row order.
        let characters = label(index).to_array()
        for slot = 0; slot < characters.length(); slot = slot + 1 {
          let origin = prefixes[index][slot + 1] - advances[index][slot]
          // Source window.rs:4850 rounds positive device X to four subpixel
          // variants, halves toward zero. This is glyph paint, not row layout.
          let paint_x = ((bounds.left() + origin) * scale * 4.0 - 0.5).ceil() / (scale * 4.0)
          items.push(@scene.SceneItem::text_run(id * 10 + slot.to_uint64(), bounds,
            @primitives.Point::new(paint_x, bounds.top()).unwrap(),
            characters[slot].to_string(), 16,
            @primitives.Color::rgba(0, 0, 0, 255).unwrap(), transform, opacity, clip_chain_id).unwrap())
        }
      }
      _ => items.push(item)
    }
  }
  @scene.SceneSnapshot::new(base.viewport(), scale, base.resources(), base.clip_chains(), items).unwrap()
}

///|
#export_name("uniform_list_frame")
pub fn uniform_list_frame(
  widths : Array[Double], prefixes : Array[Array[Double]],
  advances : Array[Array[Double]], scale : Double,
) -> String {
  if widths.length() != 50 || prefixes.length() != 50 || advances.length() != 50 || !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  for index = 0; index < 50; index = index + 1 {
    let width = widths[index]
    let length = label(index).to_array().length()
    if !(width > 0.0 && width <= 284.0) || prefixes[index].length() != length + 1 ||
      advances[index].length() != length || prefixes[index][0] != 0.0 || prefixes[index][length] != width {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  for index = 0; index < 50; index = index + 1 {
    for slot = 0; slot < advances[index].length(); slot = slot + 1 {
      let advance = advances[index][slot]
      let prefix = prefixes[index][slot + 1]
      if !(advance > 0.0 && advance <= 32.0) || !(prefix > prefixes[index][slot] && prefix <= 284.0) ||
        !(prefix - advance >= 0.0) {
        return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
      }
    }
  }
  let state = list_state.val
  let calls : Array[String] = []
  let anchors : Map[UInt64, Int] = Map([])
  let prepainted = layout_list(state, widths, line_height(), scale, calls, anchors)
  let tree = prepainted.tree()
  let list = tree.uniform_list(2).unwrap()
  state.offset = list.offset()
  state.tree = Some(tree)
  ignore(state.click.reconcile(tree))
  let snapshot = text_snapshot(prepainted, scale, anchors, prefixes, advances)
  let rows : Array[String] = []
  let range = list.visible_range()
  for index = range.start(); index < range.end(); index = index + 1 {
    let id = range.id(index, 0).unwrap()
    let bounds = tree.node(id).unwrap().bounds()
    rows.push("{\"index\":\{index},\"id\":\{id},\"text_anchor_id\":\{range.id(index, 1).unwrap()},\"bounds\":\{rect_json(bounds)}}")
  }
  let measured = list.measured_item_size().unwrap()
  let clicked = match state.clicked { Some(index) => "\{index}"; None => "null" }
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"cursor\":\"pointer\",\"host_extensions\":[\"font_metrics\",\"browser_pixel_wheel_delivery\",\"canvas_text_rasterization\"],\"uniform_list\":{\"offset\":\{list.offset()},\"max_offset\":\{list.max_offset()},\"content_height\":\{list.content_size().height()},\"measured_height\":\{measured.height()},\"measured_width\":\{measured.width()},\"bounds\":\{rect_json(list.bounds())},\"range\":[\{range.start()},\{range.end()}],\"rows\":[\{rows.join(",")}],\"factory_calls\":[\{calls.join(",")}],\"clicked_index\":\{clicked},\"evidence\":\"Actual production core output; not an observation of the Rust oracle\"}}"
}

///|
#export_name("uniform_list_wheel")
pub fn uniform_list_wheel(x : Double, y : Double, dx : Double, dy : Double) -> Bool {
  let position = match @primitives.Point::new(x, y) {
    Ok(position) => position
    Err(_) => return false
  }
  let state = list_state.val
  let tree = match state.tree { Some(tree) => tree; None => return false }
  let updates = match tree.scroll_wheel(position, dx, dy) {
    Ok(updates) => updates
    Err(_) => return false
  }
  for update in updates { if update.id() == 2 { state.offset = update.offset().y() } }
  (dx != 0.0 || dy != 0.0) && !updates.is_empty()
}

///|
#export_name("uniform_list_pointer")
pub fn uniform_list_pointer(kind : String, x : Double, y : Double, button : Int) -> Bool {
  if button != 0 { return false }
  let position = match @primitives.Point::new(x, y) {
    Ok(position) => position
    Err(_) => return false
  }
  let state = list_state.val
  let tree = match state.tree { Some(tree) => tree; None => return false }
  let modifiers = @primitives.Modifiers::new(shift=false, control=false, alt=false, meta=false)
  let event = match kind {
    "down" => @primitives.PointerButtonPressed(position~, button=@primitives.Primary, modifiers~)
    "up" => @primitives.PointerButtonReleased(position~, button=@primitives.Primary, modifiers~)
    _ => return false
  }
  match state.click.dispatch(tree, event) {
    @element.Clicked(index~, ..) => { state.clicked = Some(index); true }
    _ => false
  }
}
