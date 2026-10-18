///|
// Source structure: immutable pattern.rs, blob 7d2e98d16e24dc23dc307296a3b35c18e624d9e3.
// ElementTree owns intrinsic sizing and device-grid layout; core owns all paint.
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn rgba(r : Double, g : Double, b : Double, a : Double) -> @primitives.FloatColor {
  @primitives.FloatColor::rgba(r,g,b,a).unwrap()
}

///|
fn rect(x : Double,y : Double,w : Double,h : Double) -> @primitives.Rect {
  @primitives.Rect::new(x,y,w,h).unwrap()
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_align(@layout.AlignItems::stretch())
}

///|
fn node(id : UInt64, height : @layout.Dimension, width : @layout.Dimension) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(id,height,width,@primitives.Size::new(0,0).unwrap()).with_flex(0,0).unwrap())
    .with_background(Some(@primitives.Color::rgba(0,0,0,0).unwrap())).with_pointer_events(false)
}

///|
fn line_height(scale : Double) -> Double {
  (20.0 * 1.618033988749895 * scale - 0.5).ceil() / scale
}

///|
fn prepare(widths : Array[Double], scale : Double) -> @element.Prepainted {
  let auto = @layout.Dimension::auto()
  let border = (1.0 * scale).round() / scale
  let label = fn(id : UInt64, width : Double) {
    node(id,fixed(line_height(scale)),fixed(width))
  }
  let bordered = fn(id : UInt64) {
    node(id,auto,auto).with_children_style(column().with_insets(@layout.Insets::zero(),@layout.Insets::all(border).unwrap()))
  }
  let mut small = bordered(10)
  for index = 0; index < 4; index = index + 1 {
    small = small.with_child(node(20 + index.to_uint64(),fixed(18),fixed(54)))
  }
  let mut large = bordered(11).with_child(label(101,widths[1]))
  for index = 0; index < 4; index = index + 1 {
    large = large.with_child(node(30 + index.to_uint64(),fixed(if index == 3 { 26 } else { 56 }),fixed(256)))
  }
  let root = @element.Element::root(1,column().with_gap(12).unwrap().with_align(@layout.AlignItems::center()).with_justify(@layout.JustifyContent::center()))
    .with_background(Some(@primitives.Color::rgba(255,255,255,255).unwrap())).with_pointer_events(false)
    .with_child(label(100,widths[0])).with_child(small).with_child(large)
    .with_child(node(40,fixed(40),fixed(240))).with_child(node(41,fixed(40),fixed(240)))
  // Upstream explicitly .size(px(600.0)); viewport resizing must not stretch it.
  root.request_layout_with_device_scale(@primitives.Size::new(600,600).unwrap(),scale).unwrap().prepaint().unwrap()
}

///|
fn stripe_fill(id : UInt64) -> @scene.PaintFill {
  let color = match id { 31 => rgba(0,0.5,0,1); 32 => rgba(0,0,1,1); 33 => rgba(1,1,0,1); _ => rgba(1,0,0,1) }
  let width = if id < 30 { 4.5 } else { 56.0 / 6.0 }
  let interval = if id == 23 { 9.0 } else { width }
  @scene.Slash(@scene.SlashPattern::new(color,width,interval).unwrap())
}

///|
fn canonical_scene(frame : @element.Prepainted, width : Double, height : Double, scale : Double, device_scale : Double) -> @scene.SceneSnapshot {
  let bindings : Array[@element.ElementPaintBinding] = []
  for id in [20UL,21UL,22UL,23UL,30UL,31UL,32UL,33UL,11UL,40UL,41UL] {
    bindings.push(@element.ElementPaintBinding::new(id,fn(bounds) {
      let fill = if id == 11 { @scene.FloatSolid(rgba(0,0.5,0,0.16)) }
        else if id == 40 { @scene.FloatSolid(rgba(1,0,0,1)) }
        else if id == 41 { @scene.Gradient(@scene.LinearGradient::new(45,rgba(1,0,0,1),0,rgba(0,0,1,1),1,@scene.Srgb).unwrap()) }
        else { stripe_fill(id) }
      Ok((@scene.PaintShape::rounded_quad(bounds,0).unwrap(),fill,1.0))
    }))
  }
  let base = frame.paint_with_paints(bindings).unwrap().snapshot_v1(rect(0,0,width,height),scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  let labels : Array[@scene.SceneItem] = []
  let border = (device_scale).round() / device_scale
  for item in base.items() {
    match item {
      @scene.QuadItem(id~,bounds~,transform~,opacity~,clip_chain_id~,..) if id == 100 || id == 101 => {
        labels.push(@scene.SceneItem::text_run(id,bounds,bounds.origin(),if id == 100 { "Pattern Example" } else { "Elements the same height should align" },20,@primitives.Color::rgba(0,0,0,255).unwrap(),transform,opacity,clip_chain_id).unwrap())
      }
      _ => {
        items.push(item)
        let id = item.id()
        if id == 10 || id == 11 || id == 40 || id == 41 {
          let bounds = frame.tree().node(id).unwrap().bounds()
          let blue = @primitives.Color::rgba(0,0,255,255).unwrap()
          for (index, edge) in [
            (0,rect(bounds.left(),bounds.top(),bounds.size().width(),border)),
            (1,rect(bounds.left(),bounds.bottom()-border,bounds.size().width(),border)),
            (2,rect(bounds.left(),bounds.top()+border,border,bounds.size().height()-2*border)),
            (3,rect(bounds.right()-border,bounds.top()+border,border,bounds.size().height()-2*border))
          ] {
            items.push(@scene.SceneItem::quad(1000 + id*4 + index.to_uint64(),edge,blue,@scene.AffineTransform::identity(),1,None).unwrap())
          }
        }
      }
    }
  }
  // Non-overlapping label normalization permits one opaque linear core paint run.
  // The host checks actual glyph ink against every later colored region before
  // presentation. Source labels and source tree order are retained in metadata.
  for label in labels { items.push(label) }
  @scene.SceneSnapshot::new(base.viewport(),scale,base.resources(),base.clip_chains(),items).unwrap()
}

///|
fn live_scene(frame : @element.Prepainted, width : Double, height : Double, scale : Double, device_scale : Double) -> @scene.SceneSnapshot {
  let raster_width = (width * scale).ceil() / scale
  let raster_height = (height * scale).ceil() / scale
  let scene = canonical_scene(frame,raster_width,raster_height,scale,device_scale)
  if width == 600 && height == 600 && scale == 1 && device_scale == 1 {
    return scene
  }
  // Nonqualified preview: an explicit white canvas backing, matching the page
  // background. Pixel-aligned coverage keeps clipped fractional edge pixels
  // opaque without relaxing the ordered transport's opaque-run invariant.
  // The original fixed-size root and all source geometry remain unchanged.
  let items : Array[@scene.SceneItem] = [@scene.SceneItem::quad(0,rect(0,0,raster_width,raster_height),@primitives.Color::rgba(255,255,255,255).unwrap(),@scene.AffineTransform::identity(),1,None).unwrap()]
  for item in scene.items() { items.push(item) }
  @scene.SceneSnapshot::new(scene.viewport(),scale,scene.resources(),scene.clip_chains(),items).unwrap()
}

///|
fn present(scene : @scene.SceneSnapshot, device_scale : Double, width : Double, height : Double) -> String {
  let count = scene.items().length()-2
  let tile = scene.rasterize_paint_run_webgl2_linear(0,count).unwrap().unwrap()
  let bytes = tile.rgba().map(value => value.to_string()).join(",")
  "{\"ok\":true,\"conformance\":\"unverified\",\"snapshot\":\{scene.canonical_json()},\"decorations\":[],\"raster_transport\":\"ordered_core_webgl2_linear_straight_v1\",\"operations\":[{\"kind\":\"rgba_run\",\"index\":0,\"count\":\{count},\"x\":\{tile.x()},\"y\":\{tile.y()},\"width\":\{tile.width()},\"height\":\{tile.height()},\"rgba\":[\{bytes}]},{\"kind\":\"legacy\",\"index\":\{count}},{\"kind\":\"legacy\",\"index\":\{count+1}}],\"pattern\":{\"comparison_profile_match\":\{width == 600 && height == 600 && scene.scale() == 1 && device_scale == 1},\"text_order\":\"disjoint_ink_checked_labels_last\",\"source_label_ids\":[100,101]},\"unverified\":[\"Canvas_vs_Cosmic_text\",\"shadow_kernel\",\"full_image\",\"native\"]}"
}

///|
#export_name("pattern_metadata")
pub fn pattern_metadata() -> String {
  "{\"id\":\"pattern\",\"width\":600,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":20,\"source_blob\":\"7d2e98d16e24dc23dc307296a3b35c18e624d9e3\",\"runs\":[{\"text\":\"Pattern Example\",\"font_size\":20},{\"text\":\"Elements the same height should align\",\"font_size\":20}],\"conformance\":\"unverified\"}"
}

///|
#export_name("pattern_frame_at_scale")
pub fn pattern_frame_at_scale(width : Double,height : Double,widths : Array[Double],device_scale : Double,scale : Double) -> String {
  // Live rendering is separate from the frozen numerical comparison profile.
  // Preserve upstream's fixed 600x600 content, clipping to the actual viewport.
  if !(width >= 1 && width <= 2048 && height >= 1 && height <= 2048 &&
    device_scale >= 0.25 && device_scale <= 64 && scale >= 0.25 && scale <= 4) ||
    (width * scale).ceil() > 2048 || (height * scale).ceil() > 2048 ||
    (width * scale).ceil() * (height * scale).ceil() > 1048576 ||
    ((width * scale).ceil() / scale * scale).ceil() != (width * scale).ceil() ||
    ((height * scale).ceil() / scale * scale).ceil() != (height * scale).ceil() {
    return "{\"ok\":false,\"error\":\"invalid_pattern_viewport\"}"
  }
  if widths.length() != 2 || widths.any(value => !(value > 0 && value < 590)) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  present(live_scene(prepare(widths,device_scale),width,height,scale,device_scale),device_scale,width,height)
}
