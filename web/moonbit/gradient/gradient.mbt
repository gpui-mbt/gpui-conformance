///|
// Source-authored structure, not final fixture rectangles. Geometry is produced
// by actual Element request_layout/prepaint, then canonical PaintCommands in the
// same traversal order. Gradient sampling and pixel presentation live in core.
let oklab : Ref[Bool] = Ref(false)

///|
let current_tree : Ref[@element.ElementTree?] = Ref(None)

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn rgba(r : Double, g : Double, b : Double, a : Double) -> @primitives.FloatColor {
  @primitives.FloatColor::rgba(r, g, b, a).unwrap()
}

///|
fn transparent() -> @primitives.Color {
  @primitives.Color::rgba(0, 0, 0, 0).unwrap()
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_align(@layout.AlignItems::stretch())
}

///|
fn row() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::row()).with_align(@layout.AlignItems::stretch())
}

///|
fn node(id : UInt64, main : Double, cross : @layout.Dimension, grow : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(id, fixed(main), cross, @primitives.Size::new(0, 0).unwrap())
    .with_flex(grow, if grow > 0 { 1 } else { 0 }).unwrap(),
  ).with_background(Some(transparent())).with_pointer_events(false)
}

///|
fn line_height(size : Double, scale : Double) -> Double {
  (size * 1.618033988749895 * scale - 0.5).ceil() / scale
}

///|
fn prepare(width : Double, height : Double, widths : Array[Double], scale : Double) -> @element.Prepainted {
  let auto = @layout.Dimension::auto()
  let method_width = widths[if oklab.val { 2 } else { 1 }]
  let title_height = line_height(16, scale)
  let method_height = line_height(14, scale)
  let header_height = title_height.max(method_height + 8)
  let title = node(100, widths[0], fixed(title_height), 0)
  let button = node(3, method_width + 24, fixed(method_height + 8), 0)
    .with_pointer_events(true)
    .with_children_style(column().with_insets(@layout.Insets::new(4,12,4,12).unwrap(), @layout.Insets::zero()))
    .with_child(node(101, method_height, fixed(method_width), 0))
  let header = node(2, header_height, auto, 0)
    .with_children_style(row().with_gap(8).unwrap().with_align(@layout.AlignItems::center()).with_justify(@layout.JustifyContent::space_between()))
    .with_child(title).with_child(button)
  let mut root = @element.Element::root(1,
    column().with_gap(12).unwrap().with_insets(@layout.Insets::all(16).unwrap(), @layout.Insets::zero()))
    .with_background(Some(@primitives.Color::rgba(255,255,255,255).unwrap()))
    .with_pointer_events(false).with_child(header)
  let mut solids = node(10, 0, auto, 1).with_children_style(row().with_gap(12).unwrap())
  for index = 0; index < 2; index = index + 1 {
    solids = solids.with_child(node(20 + index.to_uint64(), 0, auto, 1)
      .with_children_style(column().with_align(@layout.AlignItems::center()).with_justify(@layout.JustifyContent::center()))
      .with_child(node(102 + index.to_uint64(), title_height, fixed(widths[3]), 0)))
  }
  root = root.with_child(solids)
  for group = 0; group < 2; group = group + 1 {
    let mut strip = node(11 + group.to_uint64(), 0, auto, 1).with_children_style(row().with_gap(12).unwrap())
    for index = 0; index < 4; index = index + 1 {
      strip = strip.with_child(node(30 + (group * 4 + index).to_uint64(), 0, auto, 1))
    }
    root = root.with_child(strip)
  }
  root = root.with_child(node(38,0,auto,1)).with_child(node(39,0,auto,1))
  // Preserve the extra nested row in the original equal-stop example.
  root = root.with_child(node(13,0,auto,1).with_children_style(row().with_gap(12).unwrap())
    .with_child(node(14,0,auto,1).with_children_style(row().with_gap(12).unwrap()).with_child(node(40,0,auto,1)))
    .with_child(node(41,0,auto,1)))
  root = root.with_child(node(50,96,auto,0))
  root.request_layout_with_device_scale(@primitives.Size::new(width,height).unwrap(),scale).unwrap().prepaint().unwrap()
}

///|
fn gradient(index : Int) -> @scene.PaintFill {
  let red = rgba(1,0,0,1)
  let blue = rgba(0,0,1,1)
  let green = rgba(0,0.5,0,1)
  let yellow = rgba(1,1,0,1)
  let white = rgba(1,1,1,1)
  let (angle, start, stop0, end, stop1) = match index {
    0 => (45.0,red,0.0,blue,1.0)
    1 => (135.0,red,0.0,green,1.0)
    2 => (225.0,green,0.0,blue,1.0)
    3 => (315.0,green,0.0,yellow,1.0)
    4 => (0.0,red,0.0,white,1.0)
    5 => (90.0,blue,0.0,white,1.0)
    6 => (180.0,green,0.0,white,1.0)
    7 => (360.0,yellow,0.0,white,1.0)
    8 => (0.0,green,0.05,yellow,0.95)
    9 => (90.0,blue,0.05,red,0.95)
    10 => (90.0,blue,0.5,red,0.5)
    11 => (180.0,green,0.0,blue,0.5)
    _ => (180.0,red,0.0,blue,1.0)
  }
  @scene.Gradient(@scene.LinearGradient::new(angle,start,stop0,end,stop1,
    if oklab.val { @scene.Oklab } else { @scene.Srgb }).unwrap())
}

///|
fn canonical_scene(frame : @element.Prepainted, scale : Double, viewport? : @primitives.Rect = frame.viewport_bounds()) -> @scene.SceneSnapshot {
  let bindings : Array[@element.ElementPaintBinding] = []
  for id in [20UL,21UL,30UL,31UL,32UL,33UL,34UL,35UL,36UL,37UL,38UL,39UL,40UL,41UL] {
    bindings.push(@element.ElementPaintBinding::new(id, fn(bounds) {
      let fill = if id == 20 { @scene.FloatSolid(rgba(1,0,0,1)) } else if id == 21 { @scene.FloatSolid(rgba(0,0,1,1)) } else { gradient((id-30).to_int()) }
      let radius = 12.0.min(bounds.size().width()/2).min(bounds.size().height()/2)
      Ok((@scene.PaintShape::rounded_quad(bounds,radius).unwrap(),fill,1.0))
    }))
  }
  bindings.push(@element.ElementPaintBinding::new(3,fn(bounds) {
    Ok((@scene.PaintShape::rounded_quad(bounds,0).unwrap(),@scene.FloatSolid(rgba(0,0,0,1)),1.0))
  }))
  bindings.push(@element.ElementPaintBinding::new(50,fn(bounds) {
    let x = bounds.size().width() * 0.1
    let w = bounds.size().width() * 0.8
    let y = bounds.top()
    // Exact upstream omission of bounds.origin.x; core uses actual tight/clipped
    // polygon bounds50, not the nominal80 allocation, for normalization.
    let points = [@primitives.Point::new(x,y+80).unwrap(),@primitives.Point::new(x+80,y+30).unwrap(),@primitives.Point::new(x+w-80,y+30).unwrap(),@primitives.Point::new(x+w,y+80).unwrap()]
    Ok((@scene.PaintShape::convex_polygon(points).unwrap(),gradient(12),1.0))
  }))
  let base = frame.paint_with_paints(bindings).unwrap().snapshot_v1(viewport,scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match item {
      @scene.QuadItem(id~,bounds~,transform~,opacity~,clip_chain_id~,..) if id >= 100 && id <= 103 => {
        let text = if id == 100 { "Gradient Examples" } else if id == 101 { if oklab.val { "Oklab" } else { "sRGB" } } else { "Solid Color" }
        let channel = if id == 100 { 0 } else { 255 }
        items.push(@scene.SceneItem::text_run(id,bounds,bounds.origin(),text,if id == 101 { 14 } else { 16 },@primitives.Color::rgba(channel,channel,channel,255).unwrap(),transform,opacity,clip_chain_id).unwrap())
      }
      _ => items.push(item)
    }
  }
  @scene.SceneSnapshot::new(base.viewport(),scale,base.resources(),base.clip_chains(),items).unwrap()
}

///|
#export_name("gradient_click")
pub fn gradient_click(x : Double, y : Double) -> Unit {
  match current_tree.val {
    Some(tree) => if tree.dispatch_pointer(@primitives.Point::new(x,y).unwrap()).target() == Some(3) { oklab.val = !oklab.val }
    None => ()
  }
}

///|
#export_name("gradient_reset")
pub fn gradient_reset() -> Unit {
  current_tree.val = None
  oklab.val = false
}

///|
fn valid_viewport(width : Double, height : Double, scale : Double) -> Bool {
  let w = (width * scale).ceil()
  let h = (height * scale).ceil()
  width >= 240 && width <= 2048 && height >= 300 && height <= 2048 &&
  scale >= 0.25 && scale <= 4 && w >= 1 && h >= 1 && w <= 2048 && h <= 2048 && w*h <= 1048576
}

///|
fn present(scene : @scene.SceneSnapshot) -> String {
  let operations : Array[String] = []
  for index = 0; index < scene.items().length(); index = index + 1 {
    let item = scene.items()[index]
    match item {
      @scene.TextItem(..) | @scene.TextRunItem(..) => operations.push("{\"kind\":\"legacy\",\"index\":\{index}}")
      _ => match scene.rasterize_item_tile_webgl2_linear(index).unwrap() {
        None => operations.push("{\"kind\":\"skip\",\"index\":\{index}}")
        Some(tile) => {
          let bytes = tile.rgba().map(value => value.to_string()).join(",")
          operations.push("{\"kind\":\"rgba\",\"index\":\{index},\"x\":\{tile.x()},\"y\":\{tile.y()},\"width\":\{tile.width()},\"height\":\{tile.height()},\"rgba\":[\{bytes}]}")
        }
      }
    }
  }
  "{\"ok\":true,\"conformance\":\"unverified\",\"snapshot\":\{scene.canonical_json()},\"decorations\":[],\"raster_transport\":\"ordered_core_webgl2_linear_straight_v1\",\"operations\":[\{operations.join(",")}]}"
}

///|
#export_name("gradient_metadata")
pub fn gradient_metadata() -> String {
  "{\"id\":\"gradient\",\"width\":960,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"source_blob\":\"df1398fff58b637abf0c0b31934f6ad523d84a21\",\"runs\":[{\"text\":\"Gradient Examples\",\"font_size\":16},{\"text\":\"sRGB\",\"font_size\":14},{\"text\":\"Oklab\",\"font_size\":14},{\"text\":\"Solid Color\",\"font_size\":16}],\"conformance\":\"unverified\"}"
}

///|
#export_name("gradient_frame")
pub fn gradient_frame(width : Double, height : Double, widths : Array[Double], scale : Double) -> String {
  gradient_frame_at_scale(width,height,widths,scale,scale)
}

///|
#export_name("gradient_frame_at_scale")
pub fn gradient_frame_at_scale(width : Double, height : Double, widths : Array[Double], device_scale : Double, scale : Double) -> String {
  if !(device_scale >= 0.25 && device_scale <= 64) { current_tree.val = None; return "{\"ok\":false,\"error\":\"invalid_device_scale\"}" }
  if !valid_viewport(width,height,scale) { current_tree.val = None; return "{\"ok\":false,\"error\":\"invalid_live_viewport\"}" }
  if widths.length() != 4 || widths.any(value => !(value > 0 && value < 1000)) { current_tree.val = None; return "{\"ok\":false,\"error\":\"invalid_metrics\"}" }
  let frame = prepare(width,height,widths,device_scale)
  current_tree.val = Some(frame.tree())
  let scene = canonical_scene(frame,scale,viewport=rect(0,0,width,height))
  let json = present(scene)
  // This metadata is diagnostic only. The independent comparator reads PNGs.
  json.unsafe_substring(start=0,end=json.length()-1).to_string() + ",\"gradient\":{\"color_space\":\"\{if oklab.val { "Oklab" } else { "sRGB" }}\",\"comparison_profile_match\":\{device_scale == 1 && scale == 1 && ((width == 960 && height == 600) || (width == 600 && height == 960))}}}"
}

///|
fn rect(x : Double,y : Double,w : Double,h : Double) -> @primitives.Rect {
  @primitives.Rect::new(x,y,w,h).unwrap()
}

///|
#export_name("gradient_policy_frame")
pub fn gradient_policy_frame() -> String {
  // Separately authored, frozen policy probes. Never part of gradient.rs.
  let commands : Array[@scene.PaintCommand] = [@scene.PaintCommand::quad(1,rect(0,0,960,600),@primitives.Color::rgba(255,255,255,255).unwrap())]
  let equal = @scene.Gradient(@scene.LinearGradient::new(90,rgba(1,0,0,1),0.5,rgba(0,0,1,1),0.5,@scene.Srgb).unwrap())
  for (id, bounds, fill) in [(2UL,rect(20,20,161,20),equal),(3UL,rect(20,60,161,20),@scene.FloatSolid(rgba(0,0.5,0,1))),(4UL,rect(20,100,161,20),@scene.FloatSolid(rgba(0,0.5,0,0.5)))] {
    commands.push(@scene.PaintCommand::paint(id,@scene.PaintShape::rounded_quad(bounds,0).unwrap(),fill,1).unwrap())
  }
  commands.push(@scene.PaintCommand::clip_push(5,rect(0,185,300,35)))
  let polygon = @scene.PaintShape::convex_polygon([@primitives.Point::new(20,220).unwrap(),@primitives.Point::new(100,170).unwrap(),@primitives.Point::new(180,170).unwrap(),@primitives.Point::new(260,220).unwrap()]).unwrap()
  commands.push(@scene.PaintCommand::paint(6,polygon,@scene.Gradient(@scene.LinearGradient::new(180,rgba(1,0,0,1),0,rgba(0,0,1,1),1,@scene.Srgb).unwrap()),1).unwrap())
  commands.push(@scene.PaintCommand::clip_pop(5))
  let scene = @scene.Scene::new(commands).snapshot_v1(rect(0,0,960,600),1).unwrap()
  let tile = scene.rasterize_paint_run_webgl2_linear(0,scene.items().length()).unwrap().unwrap()
  let bytes = tile.rgba().map(value => value.to_string()).join(",")
  let json = "{\"ok\":true,\"conformance\":\"unverified\",\"snapshot\":\{scene.canonical_json()},\"decorations\":[],\"raster_transport\":\"ordered_core_webgl2_linear_straight_v1\",\"operations\":[{\"kind\":\"rgba_run\",\"index\":0,\"count\":\{scene.items().length()},\"x\":\{tile.x()},\"y\":\{tile.y()},\"width\":\{tile.width()},\"height\":\{tile.height()},\"rgba\":[\{bytes}]}]}"
  json.unsafe_substring(start=0,end=json.length()-1).to_string() + ",\"gradient\":{\"color_space\":\"sRGB\",\"comparison_profile_match\":false,\"authored_policy_probe\":true}}"
}
