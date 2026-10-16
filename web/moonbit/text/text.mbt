///|
// zed@5a5fbe7 text.rs: browser-host font metrics, scroll and pointer dispatch
// are explicit extensions; gpui.mbt owns the Element layout and SceneSnapshot.
fn text_families() -> Array[String] {
  [".ZedMono", ".SystemUIFont", "Menlo", "Monaco", "Courier New"]
}

///|
fn text_intro() -> Array[String] {
  ["CJK: 中文「日本語」한글",
   "Kana: が / か\u{3099}; Hangul: 각 / \u{1100}\u{1161}\u{11a8}",
   "Emoji: 😀 ❤️ ❤\u{fe0e} 👍🏽 🇯🇵 1\u{fe0f}\u{20e3} 👩‍💻 👨‍👩‍👧‍👦"]
}

///|
fn text_characters() -> Array[String] {
  ["1","2","3","4","5","6","7","8","9","0","A","B","C","D","E","F","G",
   "H","I","J","K","L","M","N","P","Q","R","S","T","U","V","W","X","Y",
   "Z","a","b","c","d","e","f","g","h","i","j","k","l","m","n","p","q",
   "r","s","t","u","v","w","x","y","z","ẞ","ſ","ß","ð","Þ","þ","α","β",
   "Γ","γ","Δ","δ","η","θ","ι","κ","Λ","λ","μ","ν","ξ","π","τ","υ","φ",
   "χ","ψ","∂","а","в","Ж","ж","З","з","К","к","л","м","Н","н","Р","р",
   "У","у","ф","ч","ь","ы","Э","э","Я","я","ij","öẋ",".,","⣝⣑","~","*",
   "_","^","\u{60}","'","(","{","«","#","&","@","$","¢","%","|","?","¶","µ",
   "❮","<=","!=","==","--","++","=>","->","🏀","🎊","😍","❤️","👍","👎"]
}

///|
fn specimen_text() -> String {
  "The quick brown fox jumps over the lazy dog"
}

///|
fn text_scales() -> Array[Double] {
  let mut value = 1.0 / (1.33 * 1.33)
  let result : Array[Double] = []
  for i = 0; i < 9; i = i + 1 {
    result.push(value)
    result.push(value)
    value = value * 1.33
  }
  result
}

///|
fn text_json(s : String) -> String { @json.to_json(s).stringify() }

///|
fn text_run(id : Int, s : String, size : Double) -> String {
  "{\"id\":\{id},\"text\":\{text_json(s)},\"font_size\":\{size},\"weight\":400,\"style\":\"normal\"}"
}

///|
#export_name("text_metadata")
pub fn text_metadata() -> String {
  let mut runs = ""
  let mut index = 0
  for s in text_families() {
    if index > 0 { runs = runs + "," }
    runs = runs + text_run(20 + index, s, 16.0)
    index = index + 1
  }
  for s in text_intro() {
    runs = runs + "," + text_run(110 + index - 5, s, 16.0)
    index = index + 1
  }
  for s in text_characters() {
    runs = runs + "," + text_run(500 + index - 8, s, 24.0)
    index = index + 1
  }
  for scale in text_scales() {
    runs = runs + "," + text_run(900 + index - 8 - text_characters().length(),
      specimen_text(), 16.0 * scale)
    index = index + 1
  }
  "{\"id\":\"text\",\"width\":920,\"height\":720,\"font_family\":\"Zed Mono\",\"font_size\":16,\"interactive\":true,\"runs\":[\{runs}],\"conformance\":\"unverified\"}"
}

///|
fn text_color(r : Int, g : Int, b : Int) -> @primitives.Color {
  @primitives.Color::rgba(r, g, b, 255).unwrap()
}

///|
fn text_box(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    id, @layout.Dimension::points(main).unwrap(),
    @layout.Dimension::points(cross).unwrap(),
    @primitives.Size::new(0.0, 0.0).unwrap(),
  ).with_flex(0.0, 0.0).unwrap())
}

///|
fn text_row() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
}

///|
fn text_col() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
}

///|
priv struct TextSpecimen {
  lines : Array[String]
  widths : Array[Double]
}

///|
// The fixed upstream specimen is ASCII. Match text_wrapper's word-boundary
// wrapping from measured shaped-prefix positions, retaining all spaces/text.
// This is an example-local adapter, not a general gpui.mbt text layout API.
fn wrap_specimen(prefixes : Array[Double]) -> TextSpecimen {
  let characters = specimen_text().to_array()
  let starts = [0]
  let mut last = 0
  let mut candidate = 0
  for i = 0; i < characters.length(); i = i + 1 {
    if i > 0 && characters[i] != ' ' && characters[i - 1] == ' ' {
      candidate = i
    }
    if prefixes[i + 1] - prefixes[last] > 900.0 && i > last {
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
fn specimen_line_id(specimen : Int, line : Int) -> UInt64 {
  (1000 + specimen * 100 + line).to_uint64()
}

///|
// Upstream cells have a 62px basis, default flex shrink and an automatic
// minimum measured from their text. Let gpui.mbt resolve the 20-column row.
fn character_cell(index : Int, width : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    (300 + index).to_uint64(), @layout.Dimension::points(62.0).unwrap(),
    @layout.Dimension::points(62.0).unwrap(),
    @primitives.Size::new(0.0, 0.0).unwrap(),
  ).with_flex(0.0, 1.0).unwrap().with_main_limits(width.ceil(), None).unwrap())
}

///|
fn text_tree(widths : Array[Double], runs : Array[TextSpecimen], font_index : Int) -> @element.Prepainted {
  let chars = text_characters()
  let scales = text_scales()
  let white = text_color(255,255,255)
  let header = text_box(2,52.0,920.0).with_background(Some(white))
    .with_children_style(text_row().with_insets(
      @layout.Insets::all(12.0).unwrap(), @layout.Insets::zero()))
    .with_child(text_box(3,widths[font_index] + 24.0,28.0)
      .with_background(Some(text_color(0,0,0)))
      .with_children_style(text_row()
        .with_justify(@layout.JustifyContent::center())
        .with_align(@layout.AlignItems::center()))
      .with_child(text_box(4,widths[font_index],22.0)))
  let mut intro = text_box(101,96.0,920.0)
    .with_children_style(text_col().with_insets(
      @layout.Insets::all(12.0).unwrap(), @layout.Insets::zero()))
  for i = 0; i < 3; i = i + 1 {
    intro = intro.with_child(text_box((110+i).to_uint64(),24.0,widths[5+i]))
  }
  let rows = (chars.length() + 19) / 20
  let mut grid = text_box(200,(rows * 70 + 24).to_double(),920.0)
    .with_children_style(text_col().with_gap(8.0).unwrap().with_insets(
      @layout.Insets::all(16.0).unwrap(), @layout.Insets::zero()))
  for r = 0; r < rows; r = r + 1 {
    let mut line = text_box((210+r).to_uint64(),62.0,888.0)
      .with_children_style(text_row())
    for c = 0; c < 20; c = c + 1 {
      let i = r*20+c
      if i < chars.length() {
        line = line.with_child(character_cell(i,widths[8+i])
          .with_background(Some(white))
          .with_children_style(text_row()
            .with_justify(@layout.JustifyContent::center())
            .with_align(@layout.AlignItems::center()))
          .with_child(text_box((500+i).to_uint64(),widths[8+i],24.0)))
      } else {
        // The final upstream row fills its unused columns with flex_1 divs.
        line = line.with_child(@element.Element::new(@layout.FlexItem::new(
          (300+i).to_uint64(), @layout.Dimension::points(0.0).unwrap(),
          @layout.Dimension::points(62.0).unwrap(),
          @primitives.Size::new(0.0,0.0).unwrap(),
        ).with_flex(1.0,1.0).unwrap()))
      }
    }
    grid = grid.with_child(line)
  }
  let mut total_height = 0.0
  for i = 0; i < scales.length(); i = i + 1 {
    total_height = total_height + runs[i].lines.length().to_double() * 16.0 * scales[i] * 1.3 + 20.0
  }
  let mut specimens = text_box(700,total_height,920.0).with_children_style(text_col())
  for i = 0; i < scales.length(); i = i + 1 {
    let line_height = 16.0 * scales[i] * 1.3
    let h = runs[i].lines.length().to_double() * line_height + 20.0
    let bg = if i % 2 == 0 { white } else { text_color(0,0,0) }
    let mut specimen = text_box((800+i).to_uint64(),h,920.0)
      .with_background(Some(bg))
      .with_children_style(text_col().with_insets(
        @layout.Insets::all(10.0).unwrap(), @layout.Insets::zero()))
    for j = 0; j < runs[i].lines.length(); j = j + 1 {
      specimen = specimen.with_child(text_box(specimen_line_id(i,j),
        line_height,runs[i].widths[j]))
    }
    specimens = specimens.with_child(specimen)
  }
  @element.Element::root(1,text_col()).with_background(Some(white))
    .with_child(header)
    .with_child(text_box(100,668.0,920.0).with_children_style(text_col())
      .with_child(intro).with_child(grid).with_child(specimens))
    .request_layout(@primitives.Size::new(920.0,720.0).unwrap()).unwrap()
    .prepaint().unwrap()
}

///|
#export_name("text_frame")
pub fn text_frame(
  widths : Array[Double], prefixes : Array[Array[Double]],
  scroll : Double, font_index : Int, scale : Double,
) -> String {
  let chars = text_characters()
  let scales = text_scales()
  if widths.length() != 8+chars.length()+scales.length() ||
    prefixes.length() != scales.length() ||
    font_index < 0 || font_index >= 5 ||
    !(scroll >= 0.0 && scroll <= 100000.0 && scale > 0.0 && scale <= 4.0) {
    return "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
  }
  for w in widths {
    if !(w >= 0.0 && w <= 10000.0) {
      return "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
    }
  }
  let runs = []
  for i = 0; i < scales.length(); i = i + 1 {
    let prefix = prefixes[i]
    if prefix.length() != specimen_text().length() + 1 || prefix[0] != 0.0 {
      return "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
    }
    for j = 1; j < prefix.length(); j = j + 1 {
      if !(prefix[j] >= prefix[j-1] && prefix[j] <= 10000.0) {
        return "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
      }
    }
    if (prefix[prefix.length()-1] - widths[8+chars.length()+i]).abs() > 0.000001 {
      return "{\"ok\":false,\"error\":\"invalid_text_inputs\"}"
    }
    runs.push(wrap_specimen(prefix))
  }
  let painted = text_tree(widths,runs,font_index)
  let tree = painted.tree()
  let base = painted.paint_snapshot(scale).unwrap()
  let items = base.items()
  let black = text_color(0,0,0)
  let white = text_color(255,255,255)
  items.push(@scene.SceneItem::text(4,tree.node(4).unwrap().bounds(),
    text_families()[font_index],16.0,white,
    @scene.AffineTransform::identity(),1.0,None).unwrap())
  let intro = text_intro()
  for i = 0; i < intro.length(); i = i + 1 {
    let id = (110+i).to_uint64()
    items.push(@scene.SceneItem::text(id,tree.node(id).unwrap().bounds(),
      intro[i],16.0,black,@scene.AffineTransform::identity(),1.0,None).unwrap())
  }
  for i = 0; i < chars.length(); i = i + 1 {
    let id = (500+i).to_uint64()
    items.push(@scene.SceneItem::text(id,tree.node(id).unwrap().bounds(),
      chars[i],24.0,black,@scene.AffineTransform::identity(),1.0,None).unwrap())
  }
  let mut diagnostics = ""
  for i = 0; i < scales.length(); i = i + 1 {
    let ink = if i % 2 == 0 { black } else { white }
    let ids = []
    for j = 0; j < runs[i].lines.length(); j = j + 1 {
      let id = specimen_line_id(i,j)
      ids.push(id.to_int())
      items.push(@scene.SceneItem::text(id,tree.node(id).unwrap().bounds(),
        runs[i].lines[j],16.0*scales[i],
        ink,@scene.AffineTransform::identity(),1.0,None).unwrap())
    }
    if i > 0 { diagnostics = diagnostics + "," }
    diagnostics = diagnostics +
      "{\"index\":\{i},\"box_id\":\{800+i},\"line_ids\":\{@json.to_json(ids).stringify()},\"lines\":\{@json.to_json(runs[i].lines).stringify()},\"content_width\":900}"
  }
  let snapshot = @scene.SceneSnapshot::new(base.viewport(),scale,[],[],items).unwrap()
  let button = tree.node(3).unwrap().bounds()
  let last = tree.node(817).unwrap().bounds()
  let max_scroll = (last.top()+last.size().height()-720.0).max(0.0)
  let scroll = scroll.min(max_scroll)
  "{\"ok\":true,\"specimens\":[\{diagnostics}],\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"conformance\":\"unverified\",\"font_index\":\{font_index},\"scroll\":{\"first_id\":100,\"top\":52,\"height\":668,\"y\":\{scroll},\"max\":\{max_scroll}},\"font_button\":{\"x\":\{button.left()},\"y\":\{button.top()},\"width\":\{button.size().width()},\"height\":\{button.size().height()}},\"host_extensions\":[\"font_metrics\",\"font_fallback\",\"scroll_viewport\",\"pointer_dispatch\"]}"
}
