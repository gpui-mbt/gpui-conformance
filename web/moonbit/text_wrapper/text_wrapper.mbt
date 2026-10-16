///|
// Port of zed@5a5fbe7 crates/gpui/examples/text_wrapper.rs. Font shaping and
// grapheme segmentation are host extensions; line decisions belong here.
fn fixture_text() -> String {
  "The longest word 你好世界这段是中文，こんにちはこの段落は日本語です in any of the major English language dictionaries is pneumonoultramicroscopicsilicovolcanoconiosis, a word that refers to a lung disease contracted from the inhalation of very fine silica particles, a url https://github.com/zed-industries/zed/pull/35724?query=foo&bar=2, specifically from a volcano; medically, it is the same as silicosis."
}

///|
fn fixture_texts() -> Array[String] {
  let text = fixture_text()
  [
    "longer text in flex 1",
    "short flex",
    "A short text in normal div",
    "ELLIPSIS: " + text,
    "ELLIPSIS 2 lines: " + text,
    "TRUNCATE: " + text,
    "TRUNCATE 3 lines: " + text,
    "NOWRAP: " + text,
    text,
  ]
}

///|
fn json_string(text : String) -> String {
  @json.to_json(text).stringify()
}

///|
#export_name("text_wrapper_metadata")
pub fn text_wrapper_metadata() -> String {
  let texts = fixture_texts()
  let mut runs = ""
  for i = 0; i < texts.length(); i = i + 1 {
    if i > 0 {
      runs = runs + ","
    }
    let size = if i < 3 { 16 } else { 20 }
    let line_height = if i < 3 { 26 } else { 32 }
    runs = runs +
      "{\"id\":\{i},\"text\":\{json_string(texts[i])},\"font_size\":\{size},\"line_height\":\{line_height},\"weight\":400,\"style\":\"normal\"}"
  }
  "{\"id\":\"text_wrapper\",\"width\":800,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":false,\"runs\":[\{runs}],\"metrics_contract\":\"graphemes,individual_advances,shaped_prefix_widths,ellipsis_widths_16_20,scale\",\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"grapheme_segmentation\"]}"
}

///|
// Match the pinned upstream LineWrapper::is_word_char at grapheme boundaries.
// Unlike native scalar/glyph iteration, a combined grapheme is never split.
fn is_word(grapheme : String) -> Bool {
  let chars = grapheme.to_array()
  if chars.is_empty() {
    return false
  }
  let c = chars[0]
  let n = c.to_int()
  c.is_ascii_alphabetic() ||
  c.is_ascii_digit() ||
  (n >= 0x00c0 && n <= 0x024f) ||
  (n >= 0x0400 && n <= 0x04ff) ||
  (n >= 0x1e00 && n <= 0x1eff) ||
  (n >= 0x0300 && n <= 0x036f) ||
  (n >= 0x0980 && n <= 0x09ff) ||
  "-_.'’‘$%@#^~,=:;!)]}\"”»…⋯".to_array().contains(c) ||
  n == 0x202f ||
  n == 0x00a0 ||
  n == 0x2011
}

///|
fn can_break_before(
  tokens : Array[String],
  i : Int32,
  seen_text : Bool,
) -> Bool {
  seen_text &&
  tokens[i] != " " &&
  (!is_word(tokens[i]) || (i > 0 && tokens[i - 1] == " "))
}

///|
fn trim_end_index(tokens : Array[String], end : Int32) -> Int32 {
  let mut result = end
  while result > 0 {
    let chars = tokens[result - 1].to_array()
    if !chars.is_empty() &&
      chars.all(c => c.is_whitespace() || c.is_ascii_punctuation()) {
      result = result - 1
    } else {
      break
    }
  }
  result
}

///|
fn joined(tokens : Array[String], start : Int32, end : Int32) -> String {
  let mut text = ""
  for i = start; i < end; i = i + 1 {
    text = text + tokens[i]
  }
  text
}

///|
// Upstream truncate_line first bypasses scalar-advance truncation when the
// honestly shaped full line fits. Otherwise the affix budget is strict (<),
// overflow is floor(sum advances) > budget, and punctuation is trimmed.
fn single_truncation_end(
  tokens : Array[String],
  advances : Array[Double],
  shaped_width : Double,
  budget : Double,
  affix_width : Double,
) -> Int32? {
  if shaped_width <= budget {
    return None
  }
  let mut width = 0.0
  let mut end = 0
  for i = 0; i < tokens.length(); i = i + 1 {
    if width + affix_width < budget {
      end = i
    }
    width = width + advances[i]
    if width.floor() > budget {
      return Some(trim_end_index(tokens, end))
    }
  }
  None
}

///|
// Match the pinned upstream wrapped truncation for this fixture's paragraphs
// (no explicit newlines or leading indentation). Native uses scalar advances;
// the port uses indivisible measured graphemes, an explicit boundary extension.
fn wrapped_truncation_end(
  tokens : Array[String],
  advances : Array[Double],
  budget : Double,
  max_lines : Int32,
  affix_width : Double,
) -> Int32? {
  let mut width = 0.0
  let mut line = 0
  let mut seen = false
  let mut candidate = 0
  let mut candidate_width = 0.0
  let mut last_wrap = 0
  let mut end = 0
  for i = 0; i < tokens.length(); i = i + 1 {
    if can_break_before(tokens, i, seen) {
      candidate = i
      candidate_width = width
    }
    if tokens[i] != " " {
      seen = true
    }
    width = width + advances[i]
    if line < max_lines - 1 {
      if width > budget && i > last_wrap {
        if candidate > last_wrap {
          last_wrap = candidate
          width = width - candidate_width
          candidate = 0
        } else {
          last_wrap = i
          width = advances[i]
        }
        line = line + 1
        end = last_wrap
      }
    } else {
      if width + affix_width <= budget {
        end = i + 1
      }
      if width > budget {
        return Some(trim_end_index(tokens, end))
      }
    }
  }
  None
}

///|
// Pinned LineLayout::compute_wrap_boundaries chooses the last word candidate
// before overflow, falling back to the current glyph. Prefix positions are the
// host's measured shaping proxy. Preserve trailing spaces as upstream does.
fn wrap_starts(
  tokens : Array[String],
  prefixes : Array[Double],
  budget : Double,
  max_lines : Int32,
) -> Array[Int32] {
  let starts = [0]
  let mut seen = false
  let mut candidate : Int32? = None
  let mut last = 0
  for i = 0; i < tokens.length(); i = i + 1 {
    if can_break_before(tokens, i, seen) {
      candidate = Some(i)
    }
    if tokens[i] != " " {
      seen = true
    }
    if prefixes[i + 1] - prefixes[last] > budget && i > last {
      if max_lines > 0 && starts.length() >= max_lines {
        break
      }
      last = match candidate {
        Some(index) => index
        None => i
      }
      starts.push(last)
      candidate = None
    }
  }
  starts
}

///|
priv struct WrappedRun {
  lines : Array[String]
  widths : Array[Double]
  truncated : Bool
  clamped : Bool
}

///|
fn prepare_run(
  tokens : Array[String],
  advances : Array[Double],
  prefixes : Array[Double],
  budget : Double,
  index : Int32,
  ellipsis_width : Double,
) -> WrappedRun {
  let affix = if index <= 4 { "…" } else { "" }
  let affix_width = if affix == "" { 0.0 } else { ellipsis_width }
  let clamp = if index == 4 { 2 } else if index == 6 { 3 } else { 0 }
  let nowrap = index == 3 || index == 7
  let end = if index == 7 || index == 8 {
    None
  } else if clamp > 0 {
    wrapped_truncation_end(tokens, advances, budget, clamp, affix_width)
  } else {
    single_truncation_end(
      tokens,
      advances,
      prefixes[tokens.length()],
      budget,
      affix_width,
    )
  }
  let shortened = []
  let shortened_prefix = [0.0]
  let end_index = match end {
    Some(value) => value
    None => tokens.length()
  }
  for i = 0; i < end_index; i = i + 1 {
    shortened.push(tokens[i])
    shortened_prefix.push(prefixes[i + 1])
  }
  if end is Some(_) && affix != "" {
    shortened.push(affix)
    shortened_prefix.push(prefixes[end_index] + affix_width)
  }
  let starts = if nowrap {
    [0]
  } else {
    wrap_starts(shortened, shortened_prefix, budget, clamp)
  }
  let lines = []
  let widths = []
  for i = 0; i < starts.length(); i = i + 1 {
    let stop = if i + 1 < starts.length() {
      starts[i + 1]
    } else {
      shortened.length()
    }
    lines.push(joined(shortened, starts[i], stop))
    widths.push((shortened_prefix[stop] - shortened_prefix[starts[i]]).max(0.0))
  }
  {
    lines,
    widths,
    truncated: end is Some(_),
    clamped: clamp > 0 && end is Some(_),
  }
}

///|
fn color(red : Int32, green : Int32, blue : Int32) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn box(
  id : UInt64,
  main : Double,
  cross : Double,
  shrink : Double,
) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      @layout.Dimension::points(main).unwrap(),
      @layout.Dimension::points(cross).unwrap(),
      @primitives.Size::new(0.0, 0.0).unwrap(),
    )
    .with_flex(0.0, shrink)
    .unwrap(),
  )
}

///|
// Pinned upstream style.rs defaults to overflow Visible/min-size auto. Taffy
// 0.13 flexbox.rs measures MinContent for Visible, while Hidden has content min
// zero (with a border-box floor). GPUI text.rs does not constrain wrapping or
// truncation during its MinContent probe and ceil()s the measured text width.
// Adapt these three fixture items to explicit limits, then let gpui.mbt perform
// the real clamp/freeze/redistribute flex resolution. Broader intrinsic sizing
// is not implemented here; no screenshot/native result coordinates are used.
fn small_box(
  index : Int32,
  prefixes : Array[Array[Double]],
) -> @element.Element {
  let width = if index == 2 {
    784.0
  } else {
    prefixes[index][prefixes[index].length() - 1].ceil() + 2.0
  }
  let minimum = if index == 2 { 2.0 } else { width }
  @element.Element::new(
    @layout.FlexItem::new(
      (11 + index).to_uint64(),
      @layout.Dimension::points(width).unwrap(),
      @layout.Dimension::points(28.0).unwrap(),
      @primitives.Size::new(0.0, 0.0).unwrap(),
    )
    .with_flex(0.0, 1.0)
    .unwrap()
    .with_main_limits(minimum, None)
    .unwrap(),
  )
}

///|
fn small_row(prefixes : Array[Array[Double]]) -> @element.Element {
  let row = @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
    .with_gap(8.0)
    .unwrap()
  let border = @layout.Insets::all(1.0).unwrap()
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_insets(
    @layout.Insets::zero(),
    border,
  )
  let mut element = box(10, 28.0, 784.0, 0.0).with_children_style(row)
  for i = 0; i < 3; i = i + 1 {
    element = element.with_child(
      small_box(i, prefixes)
      .with_background(Some(color(255, 255, 255)))
      .with_children_style(column),
    )
  }
  element
}

///|
fn content_budgets(prefixes : Array[Array[Double]]) -> Array[Double] {
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_insets(
    @layout.Insets::all(8.0).unwrap(),
    @layout.Insets::zero(),
  )
  let tree = @element.Element::root(1, column)
    .with_child(small_row(prefixes))
    .request_layout(@primitives.Size::new(800.0, 600.0).unwrap())
    .unwrap()
    .prepaint()
    .unwrap()
    .tree()
  let budgets = []
  for i = 0; i < 3; i = i + 1 {
    budgets.push(
      (tree.node((11 + i).to_uint64()).unwrap().bounds().size().width() - 2.0).max(
        0.0,
      ),
    )
  }
  for i = 3; i < 9; i = i + 1 {
    budgets.push(if i == 8 { 784.0 } else { 782.0 })
  }
  budgets
}

///|
fn line_id(run : Int32, line : Int32) -> UInt64 {
  (1100 + run * 100 + line).to_uint64()
}

///|
fn add_lines(
  source : @element.Element,
  run : WrappedRun,
  index : Int32,
) -> @element.Element {
  let mut element = source
  let height = if index < 3 { 26.0 } else { 32.0 }
  for i = 0; i < run.lines.length(); i = i + 1 {
    element = element.with_child(
      box(line_id(index, i), height, run.widths[i], 0.0),
    )
  }
  element
}

///|
fn text_wrapper_tree(
  prefixes : Array[Array[Double]],
  runs : Array[WrappedRun],
) -> @element.Prepainted {
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  let page = column
    .with_gap(8.0)
    .unwrap()
    .with_insets(@layout.Insets::all(8.0).unwrap(), @layout.Insets::zero())
  // Rebuild the same flex allocation with measured line elements as descendants.
  let border_column = column.with_insets(
    @layout.Insets::zero(),
    @layout.Insets::all(1.0).unwrap(),
  )
  let mut row = box(10, 28.0, 784.0, 0.0).with_children_style(
    @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
    .with_gap(8.0)
    .unwrap(),
  )
  for i = 0; i < 3; i = i + 1 {
    row = row.with_child(
      add_lines(
        small_box(i, prefixes)
        .with_background(Some(color(255, 255, 255)))
        .with_children_style(border_column),
        runs[i],
        i,
      ),
    )
  }
  let mut root = @element.Element::root(1, page)
    .with_background(Some(color(255, 255, 255)))
    .with_child(row)
  for i = 3; i < 9; i = i + 1 {
    let bordered = i != 8
    let height = runs[i].lines.length().to_double() * 32.0 +
      (if bordered { 2.0 } else { 0.0 })
    let mut element = box(
      (17 + i).to_uint64(),
      height,
      784.0,
      if bordered {
        0.0
      } else {
        1.0
      },
    ).with_children_style(if bordered { border_column } else { column })
    if bordered {
      element = element.with_background(Some(color(255, 255, 255)))
    }
    root = root.with_child(add_lines(element, runs[i], i))
  }
  root
  .request_layout(@primitives.Size::new(800.0, 600.0).unwrap())
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn valid_metrics(
  graphemes : Array[Array[String]],
  advances : Array[Array[Double]],
  prefixes : Array[Array[Double]],
  ellipsis_widths : Array[Double],
  scale : Double,
) -> Bool {
  if graphemes.length() != 9 ||
    advances.length() != 9 ||
    prefixes.length() != 9 ||
    ellipsis_widths.length() != 2 ||
    !(scale > 0.0 && scale <= 4.0) {
    return false
  }
  for width in ellipsis_widths {
    if !(width > 0.0 && width <= 100.0) {
      return false
    }
  }
  let texts = fixture_texts()
  for i = 0; i < 9; i = i + 1 {
    let n = graphemes[i].length()
    if n == 0 ||
      n > 4096 ||
      advances[i].length() != n ||
      prefixes[i].length() != n + 1 ||
      prefixes[i][0] != 0.0 {
      return false
    }
    if joined(graphemes[i], 0, n) != texts[i] {
      return false
    }
    for j = 0; j < n; j = j + 1 {
      if graphemes[i][j] == "" ||
        !(advances[i][j] >= 0.0 && advances[i][j] <= 100000.0) ||
        !(prefixes[i][j + 1] >= 0.0 && prefixes[i][j + 1] <= 100000.0) ||
        prefixes[i][j + 1] + 0.000001 < prefixes[i][j] {
        return false
      }
    }
  }
  true
}

///|
#export_name("text_wrapper_frame")
pub fn text_wrapper_frame(
  graphemes : Array[Array[String]],
  advances : Array[Array[Double]],
  prefixes : Array[Array[Double]],
  ellipsis_widths : Array[Double],
  scale : Double,
) -> String {
  if !valid_metrics(graphemes, advances, prefixes, ellipsis_widths, scale) {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  let budgets = content_budgets(prefixes)
  let runs = []
  for i = 0; i < 9; i = i + 1 {
    runs.push(
      prepare_run(
        graphemes[i],
        advances[i],
        prefixes[i],
        budgets[i],
        i,
        ellipsis_widths[if i < 3 { 0 } else { 1 }],
      ),
    )
  }
  let prepainted = text_wrapper_tree(prefixes, runs)
  let tree = prepainted.tree()
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  let clips = []
  let mut diagnostics = ""
  let texts = fixture_texts()
  for i = 0; i < 9; i = i + 1 {
    let box_id = if i < 3 { 11 + i } else { 17 + i }
    let bounds = tree.node(box_id.to_uint64()).unwrap().bounds()
    let clipped = i == 2 || (i >= 3 && i <= 7)
    if clipped {
      let inner = @primitives.Rect::new(
        bounds.left() + 1.0,
        bounds.top() + 1.0,
        (bounds.size().width() - 2.0).max(0.0),
        (bounds.size().height() - 2.0).max(0.0),
      ).unwrap()
      clips.push(@scene.ClipChain::new(box_id, [inner]))
    }
    for j = 0; j < runs[i].lines.length(); j = j + 1 {
      let id = line_id(i, j)
      items.push(
        @scene.SceneItem::text(
          id,
          tree.node(id).unwrap().bounds(),
          runs[i].lines[j],
          if i < 3 {
            16.0
          } else {
            20.0
          },
          color(0, 0, 0),
          @scene.AffineTransform::identity(),
          1.0,
          if clipped {
            Some(box_id)
          } else {
            None
          },
        ).unwrap(),
      )
    }
    if i > 0 {
      diagnostics = diagnostics + ","
    }
    let run = runs[i]
    let mode = if i < 3 {
      "flex_ellipsis"
    } else if i == 3 {
      "single_ellipsis"
    } else if i == 4 {
      "ellipsis_2_lines"
    } else if i == 5 {
      "single_truncate"
    } else if i == 6 {
      "truncate_3_lines"
    } else if i == 7 {
      "nowrap"
    } else {
      "wrap"
    }
    diagnostics = diagnostics +
      "{\"run_index\":\{i},\"box_id\":\{box_id},\"mode\":\{json_string(mode)},\"line_count\":\{run.lines.length()},\"clipped\":\{clipped},\"original_text\":\{json_string(texts[i])},\"lines\":\{@json.to_json(run.lines).stringify()},\"truncated\":\{run.truncated},\"clamped\":\{run.clamped},\"content_width\":\{budgets[i]},\"box_bounds\":{\"x\":\{bounds.left()},\"y\":\{bounds.top()},\"width\":\{bounds.size().width()},\"height\":\{bounds.size().height()}}}"
  }
  let snapshot = @scene.SceneSnapshot::new(
    base.viewport(),
    scale,
    [],
    clips,
    items,
  ).unwrap()
  let mut decorations = ""
  for i = 0; i < 8; i = i + 1 {
    if i > 0 {
      decorations = decorations + ","
    }
    let id = if i < 3 { 11 + i } else { 17 + i }
    let border = if i < 3 {
      "#ff0000"
    } else if i < 5 {
      "#0000ff"
    } else if i < 7 {
      "#008000"
    } else {
      "#000000"
    }
    decorations = decorations +
      "{\"id\":\{id},\"radius\":0,\"border\":\{json_string(border)},\"border_width\":1,\"border_style\":\"solid\"}"
  }
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[\{decorations}],\"text_styles\":[],\"runs\":[\{diagnostics}],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"grapheme_segmentation\"],\"boundary\":\"Canvas shaped-prefix positions approximate native glyph advances; grapheme-safe boundaries differ from native scalar/glyph iteration; bidi, ligatures, fallback, broader intrinsic sizing and native pixel parity are unverified\"}"
}
