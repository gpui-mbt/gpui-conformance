///|
// Source: unchanged zed@5a5fbe7 grid_layout.rs, blob 51f9b13e41fb7913c653d716da3e8ce05a96109d.
// Production core allocates the query and every grid/flex block. Font shaping,
// line wrapping and Canvas decoration rasterization are explicitly bounded
// paint adapters; no host-calculated grid rectangles enter the tree.
priv struct GridFrame {
  prepainted : @element.Prepainted
  measured : @primitives.Size
  callbacks : Int32
}

///|
fn quote(value : String) -> String {
  @json.to_json(value).stringify()
}

///|
fn color(red : Int32, green : Int32, blue : Int32) -> @primitives.Color {
  @primitives.Color::rgba(red, green, blue, 255).unwrap()
}

///|
fn labels(width : Double) -> Array[String] {
  let pixels = if width == width.floor() {
    "\{width.to_int()}"
  } else {
    "\{width}"
  }
  ["Header — \{pixels}px", "Table of contents", "Content", "AD :(", "Footer"]
}

///|
fn block_ids() -> Array[UInt64] {
  [10, 11, 12, 13, 14]
}

///|
fn block_names() -> Array[String] {
  ["header", "toc", "content", "ad", "footer"]
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_align(
    @layout.AlignItems::stretch(),
  )
}

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn block(element : @element.Element, index : Int32) -> @element.Element {
  let colors = [
    color(255, 255, 255),
    color(255, 0, 0),
    color(0, 128, 0),
    color(0, 0, 255),
    color(0, 0, 0),
  ]
  // Default GPUI Display::Block: items_center does not center this child.
  // The source has no padding. Border1 supplies the text's 1px inset.
  element
  .with_background(Some(colors[index]))
  .with_children_style(
    column().with_insets(
      @layout.Insets::zero(),
      @layout.Insets::all(1).unwrap(),
    ),
  )
  .with_child(
    @element.Element::new(
      @layout.FlexItem::new(
        100 + index.to_uint64(),
        fixed(26),
        @layout.Dimension::auto(),
        @primitives.Size::new(0, 0).unwrap(),
      )
      .with_flex(0, 0)
      .unwrap(),
    )
    .with_background(Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()))
    .with_pointer_events(false),
  )
}

///|
fn responsive_root(size : @primitives.Size) -> @element.Element {
  let auto = @layout.Dimension::auto()
  if size.width() < 400 {
    let heights = [48.0, 80.0, 2.0, 80.0, 48.0]
    let mut root = @element.Element::root(2, column().with_gap(4).unwrap()).with_background(
      Some(color(80, 80, 80)),
    )
    for index = 0; index < 5; index = index + 1 {
      // flex_1: basis zero with a border-box floor, and the source text's
      // automatic minimum. Fixed flex_none siblings never shrink.
      let item = @layout.FlexItem::new(
          block_ids()[index],
          fixed(heights[index]),
          auto,
          @primitives.Size::new(0, 0).unwrap(),
        )
        .with_flex(
          if index == 2 {
            1
          } else {
            0
          },
          if index == 2 {
            1
          } else {
            0
          },
        )
        .unwrap()
        .with_main_limits(if index == 2 { 28 } else { 0 }, None)
        .unwrap()
      root = root.with_child(block(@element.Element::new(item), index))
    }
    root
  } else {
    let mut root = @element.Element::grid_root(
      2,
      @layout.GridTreeStyle::new(5, 5).unwrap().with_gap(4).unwrap(),
    ).with_background(Some(color(80, 80, 80)))
    for index = 0; index < 5; index = index + 1 {
      let item = @layout.GridItem::new(
        block_ids()[index],
        auto,
        if index == 1 {
          fixed(224)
        } else {
          auto
        },
      )
      let item = match index {
        0 | 4 => item.full_columns()
        2 => item.with_span(3, 3).unwrap()
        3 => item.with_span(1, 3).unwrap()
        _ => item
      }
      root = root.with_child(block(@element.Element::grid_item(item), index))
    }
    root
  }
}

///|
fn prepare(width : Double, height : Double, scale : Double) -> GridFrame {
  let measured : Ref[@primitives.Size?] = Ref(None)
  let callbacks = Ref(0)
  let root = @element.Element::container_query_root(1, size => {
    measured.val = Some(size)
    callbacks.val += 1
    Ok(responsive_root(size))
  })
  let request = root
    .request_layout_with_device_scale(
      @primitives.Size::new(width, height).unwrap(),
      scale,
    )
    .unwrap()
  let prepainted = request.prepaint().unwrap()
  { prepainted, measured: measured.val.unwrap(), callbacks: callbacks.val, }
}

///|
fn valid_viewport(width : Double, height : Double, scale : Double) -> Bool {
  // Live resource limits, independent of the frozen comparison profile.
  // Minimum dimensions keep the bounded dashed-border/shadow adapters valid.
  // Match the host's rounded Canvas backing-store allocation exactly.
  let pixels_w = (width * scale + 0.5).floor()
  let pixels_h = (height * scale + 0.5).floor()
  width >= 16 &&
  width <= 16384 &&
  height >= 32 &&
  height <= 16384 &&
  scale >= 0.25 &&
  scale <= 8 &&
  pixels_w >= 1 &&
  pixels_w <= 16384 &&
  pixels_h >= 1 &&
  pixels_h <= 16384 &&
  pixels_w * pixels_h <= 33554432
}

///|
fn comparison_profile_match(
  width : Double,
  height : Double,
  scale : Double,
) -> Bool {
  (width == 399 || width == 400 || width == 401 || width == 500) &&
  height == 500 &&
  scale == 1
}

///|
#export_name("grid_layout_metadata")
pub fn grid_layout_metadata() -> String {
  "{\"id\":\"grid_layout\",\"width\":500,\"height\":500,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"line_height\":26,\"interactive\":true,\"viewport_mode\":\"responsive\",\"viewport_profile\":{\"widths\":[399,400,401,500],\"height\":500,\"device_scale\":1},\"source_blob\":\"51f9b13e41fb7913c653d716da3e8ce05a96109d\",\"source_sha256\":\"c82663a8c48340464f70f96dfa60135f4cd3b48670882b7bc23a9ca787fb261e\",\"metrics_contract\":\"five shaped per-character prefix arrays in source order, live viewport width/height, device scale; content preflight performs its own core layout\",\"conformance\":\"unverified\"}"
}

///|
#export_name("grid_layout_content")
pub fn grid_layout_content(
  width : Double,
  height : Double,
  scale : Double,
) -> String {
  if !valid_viewport(width, height, scale) {
    return "{\"ok\":false,\"error\":\"invalid_live_viewport\"}"
  }
  // Use the actual query allocation to format Pixels, including device snapping.
  // The host measures these strings; it does not choose the responsive branch.
  let frame = prepare(width, height, scale)
  let runs = labels(frame.measured.width()).map(text => {
    "{\"text\":\{quote(text)},\"font_size\":16}"
  })
  "{\"ok\":true,\"runs\":[\{runs.join(",")}],\"layout_passes\":1,\"query_callbacks\":\{frame.callbacks}}"
}

///|
fn wrapped_starts(
  text : String,
  prefixes : Array[Double],
  budget : Double,
) -> Array[Int32] {
  let chars = text.to_array()
  let starts = [0]
  let mut candidate : Int32? = None
  let mut last = 0
  for index = 0; index < chars.length(); index = index + 1 {
    // Bounded ASCII plus source em dash. Preserve the trailing spaces, as
    // GPUI LineLayout::compute_wrap_boundaries does. Shaping remains a proxy.
    if index > 0 &&
      chars[index] != ' ' &&
      (chars[index - 1] == ' ' || chars[index] == '—') {
      candidate = Some(index)
    }
    if prefixes[index + 1] - prefixes[last] > budget && index > last {
      last = match candidate {
        Some(next) if next > last => next
        _ => index
      }
      starts.push(last)
      candidate = None
    }
  }
  starts
}

///|
fn substring(text : String, start : Int32, end : Int32) -> String {
  let chars = text.to_array()
  let mut result = ""
  for index = start; index < end; index = index + 1 {
    result += chars[index].to_string()
  }
  result
}

///|
fn paint(
  frame : GridFrame,
  prefixes : Array[Array[Double]],
  scale : Double,
) -> @scene.SceneSnapshot {
  let base = frame.prepainted.paint_snapshot(scale).unwrap()
  let texts = labels(frame.measured.width())
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match item {
      @scene.QuadItem(id~, bounds~, transform~, opacity~, clip_chain_id~, ..) if id >=
        100 &&
        id < 105 => {
        let index = (id - 100).to_int()
        let text = texts[index]
        let starts = wrapped_starts(
          text,
          prefixes[index],
          bounds.size().width(),
        )
        for line = 0; line < starts.length(); line = line + 1 {
          let end = if line + 1 < starts.length() {
            starts[line + 1]
          } else {
            text.to_array().length()
          }
          let top = bounds.top() + line.to_double() * bounds.size().height()
          let line_bounds = @primitives.Rect::new(
            bounds.left(),
            top,
            bounds.size().width(),
            bounds.size().height(),
          ).unwrap()
          items.push(
            @scene.SceneItem::text_run(
              1000 + index.to_uint64() * 100 + line.to_uint64(),
              line_bounds,
              @primitives.Point::new(bounds.left(), top).unwrap(),
              substring(text, starts[line], end),
              16,
              if index >= 3 {
                color(255, 255, 255)
              } else {
                color(0, 0, 0)
              },
              transform,
              opacity,
              clip_chain_id,
            ).unwrap(),
          )
        }
      }
      _ => items.push(item)
    }
  }
  @scene.SceneSnapshot::new(
    base.viewport(),
    scale,
    base.resources(),
    base.clip_chains(),
    items,
  ).unwrap()
}

///|
fn rect_json(bounds : @primitives.Rect) -> String {
  "{\"x\":\{bounds.left()},\"y\":\{bounds.top()},\"width\":\{bounds.size().width()},\"height\":\{bounds.size().height()}}"
}

///|
#export_name("grid_layout_frame")
pub fn grid_layout_frame(
  width : Double,
  height : Double,
  prefixes : Array[Array[Double]],
  scale : Double,
) -> String {
  if !valid_viewport(width, height, scale) {
    return "{\"ok\":false,\"error\":\"invalid_live_viewport\"}"
  }
  let frame = prepare(width, height, scale)
  let texts = labels(frame.measured.width())
  if prefixes.length() != 5 {
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  for index = 0; index < 5; index = index + 1 {
    let prefix = prefixes[index]
    if prefix.length() != texts[index].to_array().length() + 1 || prefix[0] != 0 {
      return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
    }
    for slot = 1; slot < prefix.length(); slot = slot + 1 {
      if !(prefix[slot] > prefix[slot - 1] && prefix[slot] <= 4096) {
        return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
      }
    }
  }
  let scene = paint(frame, prefixes, scale)
  let blocks : Array[String] = []
  let decorations : Array[String] = []
  for index = 0; index < 5; index = index + 1 {
    let id = block_ids()[index]
    let bounds = frame.prepainted.tree().node(id).unwrap().bounds()
    // GPUI clamps authored rounded_md=6 to the physical border box.
    let radius = (bounds.size().width() / 2)
      .min(bounds.size().height() / 2)
      .min(6)
    blocks.push(
      "{\"id\":\{id},\"name\":\{quote(block_names()[index])},\"bounds\":\{rect_json(bounds)}}",
    )
    decorations.push(
      "{\"id\":\{id},\"radius\":\{radius},\"border\":\"#ffffff\",\"border_width\":1,\"border_style\":\"dashed\"}",
    )
  }
  let mode = if frame.measured.width() < 400 { "stack" } else { "grid" }
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"shadows\":[{\"id\":2,\"kind\":\"shadow_lg\"}],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"bounded_source_word_wrap\",\"canvas_rounded_dashed_border\",\"canvas_shadow_lg_approximation\",\"browser_viewport_resize\"],\"grid_layout\":{\"comparison_profile_match\":\{comparison_profile_match(width, height, scale)},\"mode\":\{quote(mode)},\"query_size\":{\"width\":\{frame.measured.width()},\"height\":\{frame.measured.height()}},\"frame_query_callbacks\":\{frame.callbacks},\"frame_layout_passes\":1,\"blocks\":[\{blocks.join(",")}],\"evidence\":\"Actual candidate core output; not a Rust observation or callback-count parity; content preflight and frame each request a fresh layout\"}}"
}
