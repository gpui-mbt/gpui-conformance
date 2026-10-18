// Source-only paired probe of the production measured-leaf anchored lifecycle.
// The JS boundary validates/reads fixture inputs and encodes strings only.
// Text metrics are source-derived NoopTextSystem inputs, supplied by noop_metrics.mbt.
// No Rust owner/popup rectangles or observer line-height outputs are inputs.
// This is bounded synthetic-metric layout pairing, not glyph/screenshot parity.

extern "js" fn probe_validate_fixture() -> Unit =
  #| () => {
  #|   const input = JSON.parse(process.env.GPUI_SCENARIOS || "null");
  #|   if (!input || input.schema_version !== 1 || JSON.stringify(input.variants) !== JSON.stringify(["example_branch", "asymmetric_fractional"]) || !Array.isArray(input.steps) || input.steps.length !== 14) throw new Error("unsupported measured-anchor fixture");
  #|   if (typeof process.env.GPUI_RUN_TOKEN !== "string" || process.env.GPUI_RUN_TOKEN.length === 0) throw new Error("nonempty GPUI_RUN_TOKEN required");
  #|   if (Object.keys(input).sort().join(",") !== "schema_version,steps,variants") throw new Error("unknown fixture field");
  #|   const seen = new Set();
  #|   for (const step of input.steps) {
  #|     if (!step || typeof step.id !== "string" || !step.id || seen.has(step.id) || !Array.isArray(step.viewport) || step.viewport.length !== 2 || !step.viewport.every(v => Number.isFinite(v) && v > 0) || !Number.isFinite(step.scale) || step.scale <= 0 || typeof step.nested_open !== "boolean") throw new Error("invalid measured-anchor step");
  #|     if (Object.keys(step).sort().join(",") !== "id,nested_open,scale,viewport") throw new Error("unknown step field");
  #|     seen.add(step.id);
  #|   }
  #| }

extern "js" fn probe_fixture_json() -> String =
  #| () => JSON.stringify(JSON.parse(process.env.GPUI_SCENARIOS))

extern "js" fn probe_token_json() -> String =
  #| () => JSON.stringify(process.env.GPUI_RUN_TOKEN)

extern "js" fn probe_json_string(value : String) -> String =
  #| value => JSON.stringify(value)

extern "js" fn probe_step_count() -> Int =
  #| () => JSON.parse(process.env.GPUI_SCENARIOS).steps.length

extern "js" fn probe_step_id(index : Int) -> String =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].id

extern "js" fn probe_step_width(index : Int) -> Double =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].viewport[0]

extern "js" fn probe_step_height(index : Int) -> Double =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].viewport[1]

extern "js" fn probe_step_scale(index : Int) -> Double =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].scale

extern "js" fn probe_step_nested(index : Int) -> Bool =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].nested_open

const PROBE_PRIMARY : String = "Open Popover"
const PROBE_SECONDARY : String = "Child Popover"
const PROBE_FIRST : String = "This is first level Popover, we can use deferred to render it in a floating layer.\nClick outside to close."
const PROBE_SECOND : String = "This is second level Popover with nested deferred!"

fn probe_size(width : Double, height : Double) -> @primitives.Size {
  @primitives.Size::new(width, height).unwrap()
}

fn probe_rect_json(bounds : @primitives.Rect) -> String {
  "[\{bounds.left()},\{bounds.top()},\{bounds.size().width()},\{bounds.size().height()}]"
}

fn probe_size_json(size : @primitives.Size) -> String {
  "[\{size.width()},\{size.height()}]"
}

fn probe_insets_json(insets : @layout.Insets) -> String {
  // CSS order: top, right, bottom, left.
  "[\{insets.top()},\{insets.right()},\{insets.bottom()},\{insets.left()}]"
}

// Derive the available paragraph width from authored style inputs, not any
// observed owner, popup, line count or final bounds. Match production's
// nonnegative authored-length rule: nearest device pixel, ties toward zero.
fn probe_snap_authored(value : Double, scale : Double) -> Double {
  (value * scale - 0.5).ceil() / scale
}

fn probe_snap_border(value : Double, scale : Double) -> Double {
  let snapped = probe_snap_authored(value, scale)
  if value > 0.0 && snapped < 1.0 / scale { 1.0 / scale } else { snapped }
}

fn probe_parent_text_width(scale : Double) -> Double {
  probe_snap_authored(384, scale) -
  probe_snap_authored(12, scale) - probe_snap_authored(12, scale) -
  probe_snap_border(1, scale) - probe_snap_border(1, scale)
}

fn probe_button_insets(asymmetric : Bool) -> (@layout.Insets, @layout.Insets) {
  if asymmetric {
    (@layout.Insets::new(3.75, 17.5, 6.5, 11.25).unwrap(),
      @layout.Insets::new(0.75, 2.5, 1.5, 1.25).unwrap())
  } else {
    (@layout.Insets::new(4, 12, 4, 12).unwrap(), @layout.Insets::zero())
  }
}

fn probe_auto(id : UInt64, intrinsic : @primitives.Size) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(
    id, @layout.Dimension::auto(), @layout.Dimension::auto(), intrinsic,
  ).with_flex(0, 0).unwrap())
}

fn probe_column() -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
}

fn probe_background(element : @element.Element, black : Bool) -> @element.Element {
  let channel = if black { 0 } else { 255 }
  element.with_background(Some(
    @primitives.Color::rgba(channel, channel, channel, 255).unwrap(),
  ))
}

fn probe_button(id : UInt64, leaf_id : UInt64, intrinsic : @primitives.Size,
  asymmetric : Bool) -> @element.Element {
  let (padding, border) = probe_button_insets(asymmetric)
  probe_background(probe_auto(id, probe_size(0, 0)), true)
    .with_children_style(probe_column().with_insets(padding, border))
    .with_child(probe_auto(leaf_id, intrinsic).with_pointer_events(false))
}

fn probe_popup_style() -> @layout.FlexTreeStyle {
  probe_column()
    .with_insets(@layout.Insets::all(12).unwrap(), @layout.Insets::all(1).unwrap())
    .with_align(@layout.AlignItems::center())
    .with_justify(@layout.JustifyContent::center())
}

fn probe_anchor_mode() -> @element.AnchoredPositionMode {
  @element.Local // MUTATION_SITE_LOCAL_MODE
}

fn probe_attachment(id : UInt64, leaf_id : UInt64, popup : @element.Element,
  priority : Int) -> @element.Element {
  // MUTATION_SITE_WRONG_STATIC_ORIGIN is in production element/anchored.mbt:
  // requested measured-leaf origin -> parent.left()/parent.bottom().
  // Keep the measured constructor; replacing it with anchored_after would
  // merely reject the Auto/decorated owner rather than run a semantic control.
  @element.Element::anchored_after_measured_leaf(
    id, leaf_id, popup, @element.TopLeft, probe_anchor_mode(),
    @primitives.Point::new(0, 0).unwrap(), margin=8,
  ).unwrap().deferred(priority~).unwrap()
}

fn probe_view(asymmetric : Bool, nested : Bool,
  primary_metrics : @primitives.Size, parent_metrics : @primitives.Size,
  secondary_metrics : @primitives.Size, child_metrics : @primitives.Size,
) -> @element.Element {
  let mut secondary = probe_button(8, 9, secondary_metrics, asymmetric)
  if nested {
    let child = probe_background(probe_auto(11, probe_size(0, 0)), false)
      .with_children_style(probe_popup_style())
      .with_child(probe_auto(12, child_metrics).with_pointer_events(false))
    secondary = secondary.with_child(probe_attachment(10, 9, child, 2))
  }
  // mt_2 is a flow margin, not an anchor offset. This unpainted wrapper adds
  // only the authored top inset. Its independent bounds prove the 8px inset
  // separately from the parent's 12px gap; it emits no background quad.
  let secondary_margin = probe_auto(7, probe_size(0, 0))
    .with_pointer_events(false)
    .with_children_style(probe_column().with_insets(
      @layout.Insets::new(8, 0, 0, 0).unwrap(), @layout.Insets::zero(),
    )).with_child(secondary)
  // Every anchored popup is measured under the core's temporary Row root,
  // hence the fixed authored width is main, while its height remains Auto.
  let parent = probe_background(@element.Element::new(@layout.FlexItem::new(
    5, @layout.Dimension::points(384).unwrap(), @layout.Dimension::auto(),
    probe_size(0, 0),
  ).with_flex(0, 0).unwrap()), false)
    .with_children_style(probe_popup_style().with_gap(12).unwrap())
    .with_child(probe_auto(6, parent_metrics).with_pointer_events(false))
    .with_child(secondary_margin)
  let primary = probe_button(2, 3, primary_metrics, asymmetric)
    .with_child(probe_attachment(4, 3, parent, 1))
  probe_background(@element.Element::root(1,
    probe_column().with_gap(12).unwrap()
      .with_align(@layout.AlignItems::center())
      .with_justify(@layout.JustifyContent::center()),
  ), false).with_child(primary)
}

fn probe_node_name(id : UInt64) -> String {
  match id {
    1UL => "host"
    2UL => "primary"
    3UL => "primary_text"
    4UL => "primary_anchor_static"
    5UL => "parent"
    6UL => "parent_text"
    7UL => "secondary_margin"
    8UL => "secondary"
    9UL => "secondary_text"
    10UL => "secondary_anchor_static"
    11UL => "child"
    12UL => "child_text"
    _ => abort("unexpected production node identity")
  }
}

fn probe_effective_clip_json(stack : Array[(UInt64, @primitives.Rect)],
  viewport : @primitives.Rect) -> String {
  let mut clip : @primitives.Rect? = Some(viewport)
  for (_, bounds) in stack {
    match clip {
      None => ()
      Some(current) => clip = current.intersection(bounds)
    }
  }
  match clip {
    None => "null"
    Some(bounds) => probe_rect_json(bounds)
  }
}

fn probe_clip_stack_json(stack : Array[(UInt64, @primitives.Rect)]) -> String {
  let names : Array[String] = []
  for (id, _) in stack { names.push(probe_json_string(probe_node_name(id))) }
  "[\{names.join(",")}]"
}

fn probe_paint_json(scene : @scene.Scene, viewport : @primitives.Rect) -> (String, String) {
  let stack : Array[(UInt64, @primitives.Rect)] = []
  let commands : Array[String] = []
  let traversal : Array[String] = []
  for command in scene.commands() {
    let before = stack.length()
    let node = probe_json_string(probe_node_name(command.id()))
    let (kind, bounds) = match command {
      @scene.QuadCommand(bounds~, ..) => ("quad", probe_rect_json(bounds))
      @scene.ClipPushCommand(id~, bounds~) => {
        stack.push((id, bounds))
        ("clip_push", probe_rect_json(bounds))
      }
      @scene.ClipPopCommand(id~) => {
        let (opened, _) = stack.pop().unwrap()
        if opened != id { abort("unbalanced production scene clip identity") }
        ("clip_pop", "null")
      }
      @scene.PaintCommand(..) => abort("unexpected custom paint in background probe")
    }
    let clip = probe_effective_clip_json(stack, viewport)
    if kind == "quad" {
      traversal.push("{\"node\":\{node},\"bounds\":\{bounds},\"clip\":\{clip}}")
    }
    commands.push("{\"kind\":\{probe_json_string(kind)},\"node\":\{node},\"bounds\":\{bounds},\"clip\":\{clip},\"clip_depth_before\":\{before},\"clip_depth_after\":\{stack.length()},\"clip_stack_after\":\{probe_clip_stack_json(stack)}}")
  }
  if stack.length() != 0 { abort("unclosed production scene clips") }
  ("[\{traversal.join(",")} ]", "[\{commands.join(",")} ]")
}

fn probe_text_input(node : String, text : String, font_size : Double,
  available_width : Double, metrics_scale : Double, actual_scale : Double, intrinsic : @primitives.Size,
) -> String {
  let metrics_metadata = measured_text_metadata(text, font_size, available_width, metrics_scale, actual_scale)
  "{\"node\":\{probe_json_string(node)},\"text\":\{probe_json_string(text)},\"font_family\":\".SystemUIFont\",\"font_size\":\{font_size},\"available_width\":\{available_width},\"metrics_scale\":\{metrics_scale},\"actual_scale\":\{actual_scale},\"intrinsic\":\{probe_size_json(intrinsic)},\"metrics_metadata\":\{metrics_metadata}}"
}

fn probe_operation(index : Int, asymmetric : Bool) -> String {
  let width = probe_step_width(index)
  let height = probe_step_height(index)
  let scale = probe_step_scale(index)
  let nested = probe_step_nested(index)
  let paragraph_width = probe_parent_text_width(scale)
  // The used value is recorded, and each state always makes a fresh request.
  let metrics_scale = scale // MUTATION_SITE_METRICS_SCALE
  let primary_metrics = measured_text(PROBE_PRIMARY, 16, 0, metrics_scale, scale)
  let parent_metrics = measured_text(PROBE_FIRST, 14, paragraph_width, metrics_scale, scale)
  let secondary_metrics = measured_text(PROBE_SECONDARY, 14, 0, metrics_scale, scale)
  let child_metrics = if nested {
    measured_text(PROBE_SECOND, 14, 0, metrics_scale, scale)
  } else {
    probe_size(0, 0)
  }
  let frame = probe_view(asymmetric, nested, primary_metrics, parent_metrics,
      secondary_metrics, child_metrics)
    .request_layout_with_device_scale(probe_size(width, height), scale)
    .unwrap().prepaint().unwrap()
  let scene = frame.paint()
  scene.validate().unwrap()
  let tree = frame.tree()
  // The logical viewport is retained separately from snapped root bounds.
  // viewport_bounds() is the snapshot root rectangle and can be snapped.
  let logical_size = frame.viewport()
  let viewport = @primitives.Rect::new(
    0, 0, logical_size.width(), logical_size.height(),
  ).unwrap()
  let bounds : Array[String] = []
  for id in [1UL, 2UL, 3UL, 4UL, 5UL, 6UL, 7UL, 8UL, 9UL, 10UL, 11UL, 12UL] {
    match tree.node(id) {
      None => ()
      Some(node) => bounds.push("\{probe_json_string(probe_node_name(id))}:\{probe_rect_json(node.bounds())}")
    }
  }
  let attachments : Array[String] = []
  for (id, reference, popup) in [(4UL, 3UL, 5UL), (10UL, 9UL, 11UL)] {
    match tree.node(id) {
      None => ()
      Some(node) => {
        let origin = node.bounds().origin()
        attachments.push("{\"node\":\{probe_json_string(probe_node_name(id))},\"reference\":\{probe_json_string(probe_node_name(reference))},\"popup\":\{probe_json_string(probe_node_name(popup))},\"static_origin\":[\{origin.x()},\{origin.y()}]}")
      }
    }
  }
  let input_geometry : Array[String] = []
  let geometry_ids = [2UL, 8UL, if nested { 11UL } else { 5UL }]
  for id in geometry_ids {
    let node = tree.node(id).unwrap()
    if !node.accepts_pointer_events() {
      abort("corresponding core input node does not accept pointer events")
    }
    // The core has no upstream Div hitbox object. This separately labelled
    // correspondence uses actual core outer bounds and logical scene viewport.
    input_geometry.push("{\"node\":\{probe_json_string(probe_node_name(id))},\"bounds\":\{probe_rect_json(node.bounds())},\"content_mask\":\{probe_rect_json(viewport)}}")
  }
  let (paint_traversal, paint_commands) = probe_paint_json(scene, viewport)
  let (button_padding, button_border) = probe_button_insets(asymmetric)
  let mode = match probe_anchor_mode() {
    @element.Local => "Local"
    @element.Window => "Window"
  }
  let text_inputs = [
    probe_text_input("primary_text", PROBE_PRIMARY, 16, 0, metrics_scale, scale, primary_metrics),
    probe_text_input("parent_text", PROBE_FIRST, 14, paragraph_width, metrics_scale, scale, parent_metrics),
    probe_text_input("secondary_text", PROBE_SECONDARY, 14, 0, metrics_scale, scale, secondary_metrics),
  ]
  if nested {
    text_inputs.push(probe_text_input("child_text", PROBE_SECOND, 14, 0, metrics_scale, scale, child_metrics))
  }
  let source_inputs = "{\"text\":[\{text_inputs.join(",")}],\"text_backend\":\"source-derived-upstream-NoopTextSystem\",\"unbounded_available_width\":0,\"rem_size\":16,\"line_height_multiplier\":1.618034,\"button_padding\":\{probe_insets_json(button_padding)},\"button_border\":\{probe_insets_json(button_border)},\"inset_order\":\"top,right,bottom,left\",\"parent_width\":384,\"parent_padding\":[12,12,12,12],\"parent_border\":[1,1,1,1],\"parent_gap\":12,\"parent_text_available_width\":\{paragraph_width},\"secondary_margin_top\":8,\"secondary_margin_representation\":\"unpainted-flow-wrapper-top-inset\",\"child_padding\":[12,12,12,12],\"child_border\":[1,1,1,1],\"host_alignment\":\"center,center\",\"anchor\":\"TopLeft\",\"anchor_mode\":\{probe_json_string(mode)},\"anchor_position\":[0,0],\"anchor_margin\":8,\"deferred_priorities\":[1,2]}"
  "{\"id\":\{probe_json_string(probe_step_id(index))},\"viewport\":[\{width},\{height}],\"scale\":\{scale},\"nested_open\":\{nested},\"source_inputs\":\{source_inputs},\"bounds\":{\{bounds.join(",")}},\"attachments\":[\{attachments.join(",")}],\"corresponding_core_input_geometry\":[\{input_geometry.join(",")}],\"paint_traversal\":\{paint_traversal},\"paint_commands\":\{paint_commands},\"logical_viewport_mask\":\{probe_rect_json(viewport)},\"scene_valid\":true}"
}

fn main {
  probe_validate_fixture()
  let variants : Array[String] = []
  for (variant, asymmetric) in [("example_branch", false), ("asymmetric_fractional", true)] {
    let operations : Array[String] = []
    for index = 0; index < probe_step_count(); index = index + 1 {
      operations.push(probe_operation(index, asymmetric))
    }
    variants.push("{\"variant\":\{probe_json_string(variant)},\"operations\":[\{operations.join(",")} ]}")
  }
  println("{\"schema_version\":1,\"layer\":\"source-derived-measured-anchor-pair\",\"backend\":\"moonbit-core\",\"text_backend\":\"source-derived-upstream-NoopTextSystem\",\"run_token\":\{probe_token_json()},\"input\":\{probe_fixture_json()},\"paint_qualification\":\"actual-production-background-quad-traversal-and-clips; measured text leaves have no glyph paints\",\"variants\":[\{variants.join(",")} ]}")
}
