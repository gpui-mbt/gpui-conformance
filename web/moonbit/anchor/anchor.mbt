///|
// Unchanged source5a anchor.rs, blob b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b.
// Only shaped text widths enter from the host. Core grid/flex, anchored_after,
// deferred prepaint and hit testing own all geometry and hover admission.
let pointer : Ref[@primitives.Point?] = Ref(None)

///|
fn labels() -> Array[String] {
  [
    "TopLeft", "TopCenter", "TopRight", "LeftCenter", "Center", "RightCenter", "BottomLeft",
    "BottomCenter", "BottomRight",
  ]
}

///|
fn fixed(value : Double) -> @layout.Dimension {
  @layout.Dimension::points(value).unwrap()
}

///|
fn color(value : Int32) -> @primitives.Color {
  @primitives.Color::rgba(value, value, value, 255).unwrap()
}

///|
fn column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_align(
    @layout.AlignItems::start(),
  )
}

///|
fn node(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(
    @layout.FlexItem::new(
      id,
      fixed(main),
      fixed(cross),
      @primitives.Size::new(0, 0).unwrap(),
    )
    .with_flex(0, 0)
    .unwrap(),
  ).with_pointer_events(false)
}

///|
// Pinned text.rs request_layout uses Window.pixel_snap on the phi line height.
// Positive half ties go toward zero; return logical pixels at the actual DPR.
fn line_height(font_size : Double, scale : Double) -> Double {
  (font_size * 1.618033988749895 * scale - 0.5).ceil() / scale
}

///|
fn text_node(id : UInt64, height : Double, width : Double) -> @element.Element {
  node(id, height, width).with_background(
    Some(@primitives.Color::rgba(0, 0, 0, 0).unwrap()),
  )
}

///|
fn corner(index : Int32) -> @element.Anchor {
  match index {
    0 => @element.TopLeft
    1 => @element.TopCenter
    2 => @element.TopRight
    3 => @element.LeftCenter
    5 => @element.RightCenter
    6 => @element.BottomLeft
    7 => @element.BottomCenter
    _ => @element.BottomRight
  }
}

///|
fn resolved_position(index : Int32) -> @primitives.Point {
  // Exact source resolved_position, including its vertical other-side mapping.
  let x = match index {
    1 | 7 => 60.0
    2 | 3 | 8 => 120.0
    _ => 0.0
  }
  let y = match index {
    0 | 1 | 2 => 0.0
    3 | 5 => -32.5
    _ => -65.0
  }
  @primitives.Point::new(x, y).unwrap()
}

///|
fn prepare(
  width : Double,
  height : Double,
  widths : Array[Double],
  hovered : Int32,
  scale : Double,
) -> @element.Prepainted {
  let root_style = column()
    .with_align(@layout.AlignItems::center())
    .with_justify(@layout.JustifyContent::center())
    .with_gap(16)
    .unwrap()
    .with_insets(@layout.Insets::all(40).unwrap(), @layout.Insets::zero())
  let mut root = @element.Element::root(1, root_style)
    .with_background(Some(color(255)))
    .with_pointer_events(false)
    .with_child(text_node(2, line_height(16, scale), widths[0]))
  // Source size_128 is 512px. The vertical flex item may shrink to the source
  // grid intrinsic minimum; the fixed cross width deliberately overflows 480.
  let mut grid = @element.Element::new(
      @layout.FlexItem::new(
        3,
        fixed(512),
        fixed(512),
        @primitives.Size::new(0, 0).unwrap(),
      )
      .with_main_limits(3 * 65 + 2 * 24, None)
      .unwrap(),
    )
    .with_pointer_events(false)
    .with_grid_children_style(
      @layout.GridTreeStyle::new(3, 3).unwrap().with_gap(24).unwrap(),
    )
  for index = 0; index < 9; index = index + 1 {
    let id : UInt64 = 10 + index.to_uint64()
    let mut wrapper = @element.Element::grid_item(
        @layout.GridItem::new(
          30 + index.to_uint64(),
          @layout.Dimension::auto(),
          @layout.Dimension::auto(),
        ),
      )
      .with_pointer_events(false)
      .with_children_style(column())
    let mut button = node(id, 65, 120)
      .with_background(Some(color(if hovered == index { 0 } else { 255 })))
      .with_pointer_events(index != 4)
      .with_children_style(
        column()
        .with_align(@layout.AlignItems::center())
        .with_justify(@layout.JustifyContent::center())
        .with_insets(
          @layout.Insets::zero(),
          @layout.Insets::all(if index == 4 { 0 } else { 1 }).unwrap(),
        ),
      )
    if index != 4 {
      button = button.with_child(
        text_node(
          100 + index.to_uint64(),
          line_height(16, scale),
          widths[index + 1],
        ),
      )
    }
    wrapper = wrapper.with_child(button)
    if hovered == index && index != 4 {
      // Popup width is its measured text plus source padding, floored by min_w.
      // Its subtree is measured afresh by core anchored layout before snapping.
      let popup = node(
          200,
          (widths[index + 10] + 2 * 8).max(100),
          line_height(14, scale) + 2 * 2,
        )
        .with_background(Some(@primitives.Color::rgba(0, 0, 0, 191).unwrap()))
        .with_children_style(
          column().with_insets(
            @layout.Insets::new(2, 8, 2, 8).unwrap(),
            @layout.Insets::zero(),
          ),
        )
        .with_child(text_node(201, line_height(14, scale), widths[index + 10]))
      wrapper = wrapper.with_child(
        @element.Element::anchored_after(
          202,
          id,
          popup,
          corner(index),
          @element.Local,
          resolved_position(index),
        )
        .unwrap()
        .deferred()
        .unwrap(),
      )
    }
    grid = grid.with_child(wrapper)
  }
  root = root.with_child(grid)
  root
  .request_layout_with_device_scale(
    @primitives.Size::new(width, height).unwrap(),
    scale,
  )
  .unwrap()
  .prepaint()
  .unwrap()
}

///|
fn valid_viewport(width : Double, height : Double, scale : Double) -> Bool {
  // Resource domain, not the frozen comparison profile. Four logical pixels
  // guarantee one backing pixel at minimum DPR. Fixed buttons may be clipped.
  // The 4096 width cap also keeps sourceShadowPaintCommands' offscreen caster
  // outside the viewport; wider centered anchors can expose its opaque fill.
  let pixels_w = (width * scale + 0.5).floor()
  let pixels_h = (height * scale + 0.5).floor()
  width >= 4 &&
  width <= 4096 &&
  height >= 4 &&
  height <= 16384 &&
  scale >= 0.25 &&
  scale <= 4 &&
  pixels_w >= 1 &&
  pixels_w <= 16384 &&
  pixels_h >= 1 &&
  pixels_h <= 16384 &&
  pixels_w * pixels_h <= 33554432
}

///|
#export_name("anchor_metadata")
pub fn anchor_metadata() -> String {
  let runs = ["{\"text\":\"Popover with Anchor\",\"font_size\":16}"]
  for size in [16, 14] {
    for label in labels() {
      runs.push(
        "{\"text\":\{@json.to_json(label).stringify()},\"font_size\":\{size}}",
      )
    }
  }
  "{\"id\":\"anchor\",\"width\":750,\"height\":600,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"interactive\":true,\"runs\":[\{runs.join(",")}],\"viewport_mode\":\"responsive\",\"viewport_profile\":{\"widths\":[750,480],\"height\":600,\"device_scale\":1},\"source_blob\":\"b4b280b714a61cea2cd3f3a8ffd82a8f0000eb6b\",\"conformance\":\"unverified\"}"
}

///|
#export_name("anchor_pointer")
pub fn anchor_pointer(x : Double, y : Double, inside : Bool) -> Unit {
  pointer.val = if inside {
    @primitives.Point::new(x, y).to_option()
  } else {
    None
  }
}

///|
#export_name("anchor_reset")
pub fn anchor_reset() -> Unit {
  pointer.val = None
}

///|
#export_name("anchor_frame")
pub fn anchor_frame(
  width : Double,
  height : Double,
  widths : Array[Double],
  scale : Double,
) -> String {
  if !valid_viewport(width, height, scale) {
    anchor_reset()
    return "{\"ok\":false,\"error\":\"invalid_live_viewport\"}"
  }
  if widths.length() != 19 || widths.any(value => !(value > 0 && value <= 1000)) {
    anchor_reset()
    return "{\"ok\":false,\"error\":\"invalid_metrics\"}"
  }
  // Real core hit testing on current live geometry; popup has no pointer hitbox.
  let idle = prepare(width, height, widths, -1, scale)
  let hovered = match pointer.val {
    Some(point) if point.x() >= 0 &&
      point.x() < width &&
      point.y() >= 0 &&
      point.y() < height =>
      match idle.tree().hit_test(point) {
        Some(id) if id >= 10 && id <= 18 && id != 14 => (id - 10).to_int()
        _ => -1
      }
    _ => -1
  }
  let frame = if hovered < 0 {
    idle
  } else {
    prepare(width, height, widths, hovered, scale)
  }
  let base = frame.paint_snapshot(scale).unwrap()
  let items : Array[@scene.SceneItem] = []
  for item in base.items() {
    match item {
      @scene.QuadItem(id~, bounds~, transform~, opacity~, clip_chain_id~, ..) if id ==
        2 ||
        (id >= 100 && id <= 108) ||
        id == 201 => {
        let text = if id == 2 {
          "Popover with Anchor"
        } else if id == 201 {
          labels()[hovered]
        } else {
          labels()[(id - 100).to_int()]
        }
        items.push(
          @scene.SceneItem::text_run(
            id,
            bounds,
            bounds.origin(),
            text,
            if id == 201 {
              14
            } else {
              16
            },
            color(
              if id == 201 ||
                (id >= 100 && id <= 108 && (id - 100).to_int() == hovered) {
                255
              } else {
                0
              },
            ),
            transform,
            opacity,
            clip_chain_id,
          ).unwrap(),
        )
      }
      _ => items.push(item)
    }
  }
  let scene = @scene.SceneSnapshot::new(
    base.viewport(),
    scale,
    base.resources(),
    base.clip_chains(),
    items,
  ).unwrap()
  let decorations : Array[String] = []
  for index = 0; index < 9; index = index + 1 {
    if index != 4 {
      decorations.push(
        "{\"id\":\{10 + index},\"radius\":8,\"border\":\"#000000\",\"border_width\":1,\"border_style\":\"solid\"}",
      )
    }
  }
  let shadows = if hovered >= 0 {
    "[{\"id\":200,\"kind\":\"shadow_sm\"}]"
  } else {
    "[]"
  }
  let fills = if hovered >= 0 { "[{\"id\":200,\"radius\":2}]" } else { "[]" }
  "{\"ok\":true,\"snapshot\":\{scene.canonical_json()},\"decorations\":[\{decorations.join(",")}],\"rounded_fills\":\{fills},\"shadows\":\{shadows},\"conformance\":\"unverified\",\"anchor\":{\"hovered\":\{hovered},\"layout_passes\":\{if hovered >= 0 { 2 } else { 1 }},\"comparison_profile_match\":\{(width == 750 || width == 480) && height == 600 && scale == 1}},\"host_extensions\":[\"browser_font_metrics\",\"canvas_rounded_border\",\"canvas_shadow_sm_approximation\",\"browser_pointer_viewport_transport\"],\"unverified\":[\"full_image\",\"text_raster\",\"shadow_kernel\",\"native\",\"callback_counts\"]}"
}
