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
priv struct StatusWrap {
  lines : Array[String]
  widths : Array[Double]
}

///|
// Canvas supplies prefix advances, while MoonBit chooses complete status lines.
// A remote-font failure may be longer than the upstream 836px content area.
fn wrap_status(status : String, prefixes : Array[Double]) -> StatusWrap {
  let characters = status.to_array()
  let starts = [0]
  let mut last = 0
  let mut candidate = 0
  for i = 0; i < characters.length(); i = i + 1 {
    if i > 0 && characters[i] != ' ' && characters[i - 1] == ' ' {
      candidate = i
    }
    if prefixes[i + 1] - prefixes[last] > 836.0 && i > last {
      last = if candidate > last { candidate } else { i }
      starts.push(last)
      candidate = last
    }
  }
  let lines = []
  let widths = []
  for i = 0; i < starts.length(); i = i + 1 {
    let end = if i + 1 < starts.length() { starts[i + 1] } else { characters.length() }
    let mut line = ""
    for j = starts[i]; j < end; j = j + 1 {
      line = line + characters[j].to_string()
    }
    lines.push(line)
    widths.push(prefixes[end] - prefixes[starts[i]])
  }
  { lines, widths }
}

///|
fn dynamic_fonts_layout(widths : Array[Double], wrapped : StatusWrap) -> @element.Prepainted {
  let heights = [36.0, 26.0, 52.0, 42.0, 26.0, 26.0, 26.0]
  let ids : Array[UInt64] = [2, 3, 4, 5, 6, 7, 8]
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
    .with_gap(16.0).unwrap()
    .with_insets(@layout.Insets::all(32.0).unwrap(), @layout.Insets::zero())
  let mut root = @element.Element::root(1, column)
    .with_background(Some(color(32, 32, 48)))
  for index = 0; index < ids.length(); index = index + 1 {
    if index == 4 {
      let mut status_element = fixed(
        ids[index], wrapped.lines.length().to_double() * 26.0, 836.0,
      ).with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::column()))
      for j = 0; j < wrapped.lines.length(); j = j + 1 {
        status_element = status_element.with_child(
          fixed((60 + j).to_uint64(), 26.0, wrapped.widths[j]),
        )
      }
      root = root.with_child(status_element)
    } else {
      root = root.with_child(fixed(ids[index], heights[index], widths[index]))
    }
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
pub fn dynamic_fonts_frame(
  widths : Array[Double], status : String, status_prefixes : Array[Double], scale : Double,
) -> String {
  if widths.length() != 7 || !(scale > 0.0 && scale <= 4.0) ||
    status_prefixes.length() != status.to_array().length() + 1 ||
    status_prefixes[0] != 0.0 {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  for index = 0; index < widths.length(); index = index + 1 {
    let limit = if index == 4 { 100000.0 } else { 2048.0 }
    if !(widths[index] >= 0.0 && widths[index] <= limit) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  for i = 1; i < status_prefixes.length(); i = i + 1 {
    if !(status_prefixes[i] >= status_prefixes[i - 1] &&
      status_prefixes[i] <= 100000.0) {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
  }
  if (status_prefixes[status_prefixes.length() - 1] - widths[4]).abs() > 0.000001 {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let wrapped = wrap_status(status, status_prefixes)
  let prepainted = dynamic_fonts_layout(widths, wrapped)
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
    if index == 4 {
      for j = 0; j < wrapped.lines.length(); j = j + 1 {
        let id = if j == 0 { 6.to_uint64() } else { (60 + j).to_uint64() }
        items.push(@scene.SceneItem::text(
          id, tree.node((60 + j).to_uint64()).unwrap().bounds(), wrapped.lines[j],
          16.0, color(255, 255, 255),
          @scene.AffineTransform::identity(), 1.0, None,
        ).unwrap())
      }
    } else {
      items.push(@scene.SceneItem::text(
        ids[index], tree.node(ids[index]).unwrap().bounds(), texts[index],
        sizes[index], color(255, 255, 255),
        @scene.AffineTransform::identity(), 1.0, None,
      ).unwrap())
    }
  }
  let snapshot = @scene.SceneSnapshot::new(
    base.viewport(), scale, [], [], items,
  ).unwrap()
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"status_lines\":\{@json.to_json(wrapped.lines).stringify()},\"decorations\":[],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"font_fallback\",\"missing_glyph_probe\",\"remote_font_fetch\",\"font_registration\"]}"
}
