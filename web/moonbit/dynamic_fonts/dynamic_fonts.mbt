///|
fn color(red : Int, green : Int, blue : Int) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn fixed(id : UInt64, height : Double, width : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      @layout.Dimension::points(height).unwrap(),
      @layout.Dimension::points(width).unwrap(),
      @primitives.Size::new(0.0, 0.0).unwrap(),
    ).with_flex(0.0, 0.0).unwrap(),
  )
}

///|
fn dynamic_fonts_layout(widths : Array[Double]) -> @element.Prepainted {
  let heights = [36.0, 26.0, 52.0, 42.0, 26.0, 26.0, 26.0]
  let ids : Array[UInt64] = [2, 3, 4, 5, 6, 7, 8]
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
    .with_gap(16.0).unwrap()
    .with_insets(@layout.Insets::all(32.0).unwrap(), @layout.Insets::zero())
  let mut root = @element.Element::root(1, column)
    .with_background(Some(color(32, 32, 48)))
  for index = 0; index < ids.length(); index = index + 1 {
    root = root.with_child(fixed(ids[index], heights[index], widths[index]))
  }
  root.request_layout(@primitives.Size::new(900.0, 500.0).unwrap()).unwrap()
    .prepaint().unwrap()
}

///|
#export_name("dynamic_fonts_metadata")
pub fn dynamic_fonts_metadata() -> String {
  "{\"id\":\"dynamic_fonts\",\"width\":900,\"height\":500,\"font_family\":\"IBM Plex Sans\",\"font_fallback\":\"Noto Sans Devanagari\",\"font_size\":16,\"interactive\":false,\"runs\":[{\"text\":\"On-demand font loading\",\"font_size\":24},{\"text\":\"Only IBM Plex Sans is bundled. Missing Devanagari triggers the font download.\",\"font_size\":16},{\"text\":\"नमस्ते 😀 दुनिया 👨‍👩‍👧‍👦 नमस्ते ❤️\",\"font_size\":40},{\"text\":\"Emoji still uses Canvas: 😀 👨‍👩‍👧‍👦\",\"font_size\":32},{\"text\":\"Waiting for a missing Devanagari glyph…\",\"font_size\":16},{\"text\":\"Source: Google Fonts CDN · Noto Sans Devanagari · SIL Open Font License\",\"font_size\":16},{\"text\":\"Use the browser Network panel to throttle or block the font request, then reload.\",\"font_size\":16}]}"
}

///|
#export_name("dynamic_fonts_frame")
pub fn dynamic_fonts_frame(widths : Array[Double], status : String, scale : Double) -> String {
  if widths.length() != 7 || !(scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  for width in widths {
    if !(width >= 0.0 && width <= 2048.0) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  let prepainted = dynamic_fonts_layout(widths)
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  let tree = prepainted.tree()
  let ids : Array[UInt64] = [2, 3, 4, 5, 6, 7, 8]
  let texts = [
    "On-demand font loading",
    "Only IBM Plex Sans is bundled. Missing Devanagari triggers the font download.",
    "नमस्ते 😀 दुनिया 👨‍👩‍👧‍👦 नमस्ते ❤️",
    "Emoji still uses Canvas: 😀 👨‍👩‍👧‍👦",
    status,
    "Source: Google Fonts CDN · Noto Sans Devanagari · SIL Open Font License",
    "Use the browser Network panel to throttle or block the font request, then reload.",
  ]
  let sizes = [24.0, 16.0, 40.0, 32.0, 16.0, 16.0, 16.0]
  for index = 0; index < ids.length(); index = index + 1 {
    items.push(@scene.SceneItem::text(
      ids[index], tree.node(ids[index]).unwrap().bounds(), texts[index],
      sizes[index], color(255, 255, 255),
      @scene.AffineTransform::identity(), 1.0, None,
    ).unwrap())
  }
  let snapshot = @scene.SceneSnapshot::new(
    base.viewport(), scale, [], [], items,
  ).unwrap()
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"font_fallback\",\"missing_glyph_probe\",\"remote_font_fetch\",\"font_registration\"]}"
}
