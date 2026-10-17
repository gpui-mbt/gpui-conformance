// Source reconstruction against the public core pin. No previous draft byte
// identity or successful execution is claimed. The JS boundary reads inputs
// and encodes strings only; all layout, routing and gesture decisions are core.
extern "js" fn fixture_json() -> String =
  #| () => JSON.stringify(JSON.parse(process.env.GPUI_SCENARIOS))

extern "js" fn token_json() -> String =
  #| () => JSON.stringify(process.env.GPUI_RUN_TOKEN || "")

extern "js" fn step_count() -> Int =
  #| () => JSON.parse(process.env.GPUI_SCENARIOS).steps.length

extern "js" fn step_id_json(index : Int) -> String =
  #| i => JSON.stringify(JSON.parse(process.env.GPUI_SCENARIOS).steps[i].id)

extern "js" fn step_input_json(index : Int) -> String =
  #| i => { const {id, ...input} = JSON.parse(process.env.GPUI_SCENARIOS).steps[i]; return JSON.stringify(input); }

extern "js" fn step_kind(index : Int) -> String =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].kind

extern "js" fn step_button(index : Int) -> String =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].button

extern "js" fn step_x(index : Int) -> Double =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].point[0]

extern "js" fn step_y(index : Int) -> Double =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).steps[i].point[1]

struct App {
  parent : Ref[Bool]
  child : Ref[Bool]
  parent_button : Ref[@button.Button]
  child_button : Ref[@button.Button]
  dirty : Ref[Bool]
  callbacks : Array[String]
}

fn state(app : App) -> String {
  "[\{app.parent.val},\{app.child.val}]"
}

fn item(id : UInt64, main : Double, cross : Double) -> @layout.FlexItem {
  @layout.FlexItem::new(id, @layout.Dimension::points(main).unwrap(),
    @layout.Dimension::points(cross).unwrap(),
    @primitives.Size::new(0, 0).unwrap()).with_flex(0, 0).unwrap()
}

fn plain(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(item(id, main, cross)).with_pointer_events(false)
}

fn view(app : App) -> @element.Element {
  let column = @layout.FlexTreeStyle::new(@layout.FlowDirection::column())
  let row = @layout.FlexTreeStyle::new(@layout.FlowDirection::row())
  let trigger = @element.Element::new(item(2, 60, 24))
    .with_background(Some(@primitives.Color::rgba(68, 68, 68, 255).unwrap()))
  let shell = plain(6, 240, 320).with_children_style(
    row.with_insets(@layout.Insets::new(20, 0, 0, 20).unwrap(),
      @layout.Insets::zero()),
  ).with_child(trigger)
  let mut root = @element.Element::root(1, column).with_child(shell)
  if app.parent.val {
    // The ordinary child supplies insets without changing the zero-inset
    // anchored owner contract. Its bounds are never supplied as output boxes.
    let content = plain(7, 110, 180).with_children_style(
      row.with_insets(@layout.Insets::new(16, 0, 0, 16).unwrap(),
        @layout.Insets::zero()),
    ).with_child(@element.Element::new(item(4, 64, 24))
      .with_background(Some(@primitives.Color::rgba(68, 119, 68, 255).unwrap())))
    // A popup is measured by a row temporary root, hence width then height.
    let mut parent = @element.Element::new(item(3, 180, 110))
      .with_background(Some(@primitives.Color::rgba(238, 238, 238, 255).unwrap()))
      .with_children_style(column).with_child(content)
    if app.child.val {
      parent = parent.with_child(@element.Element::anchored_after(
        9, 7, @element.Element::new(item(5, 100, 60))
          .with_background(Some(@primitives.Color::rgba(238, 238, 255, 255).unwrap())),
        @element.TopLeft, @element.Window,
        @primitives.Point::new(160, 130).unwrap(), margin=8,
      ).unwrap().deferred(priority=2).unwrap())
    }
    root = root.with_child(@element.Element::anchored_after(
      8, 6, parent, @element.TopLeft, @element.Window,
      @primitives.Point::new(60, 70).unwrap(), margin=8,
    ).unwrap().deferred(priority=1).unwrap())
  }
  root
}

fn registry(app : App) -> Array[UInt64] {
  if app.child.val {
    [5UL] // MUTATION_SITE_WRONG_REGISTRY: replace [5UL] with [3UL, 5UL].
  } else if app.parent.val {
    [3UL]
  } else {
    []
  }
}

fn rect_json(bounds : @primitives.Rect) -> String {
  "[\{bounds.origin().x()},\{bounds.origin().y()},\{bounds.size().width()},\{bounds.size().height()}]"
}

fn render(app : App) -> (@element.PointerOutsideFrame, String) {
  let prepared = view(app).request_layout_with_device_scale(
    @primitives.Size::new(320, 240).unwrap(), 2,
  ).unwrap().prepaint().unwrap()
  // Execute actual production deferred scene emission. This is not a claim
  // that the portable engine emits the Rust host-return phase chronology.
  let scene = prepared.paint()
  scene.validate().unwrap()
  let tree = prepared.tree()
  app.parent_button.val = app.parent_button.val.with_bounds(
    tree.node(2).unwrap().bounds(),
  ).unwrap()
  if app.parent.val {
    app.child_button.val = app.child_button.val.with_bounds(
      tree.node(4).unwrap().bounds(),
    ).unwrap()
  } else {
    app.child_button.val = app.child_button.val.cancel_press()
  }
  let bounds : Array[String] = []
  for (id, name) in [(1UL, "host"), (2UL, "parent_trigger"),
    (3UL, "parent"), (4UL, "child_trigger"), (5UL, "child")] {
    match tree.node(id) {
      Some(node) => bounds.push("\"\{name}\":\{rect_json(node.bounds())}")
      None => ()
    }
  }
  let ids = registry(app)
  let names : Array[String] = []
  for id in ids {
    names.push(if id == 3UL { "\"parent\"" } else { "\"child\"" })
  }
  let record = "{\"state\":\{state(app)},\"registrations\":[\{names.join(",")}],\"bounds\":{\{bounds.join(",")}},\"scale\":2}"
  app.dirty.val = false
  (@element.PointerOutsideFrame::new(tree, ids).unwrap(), record)
}

fn record_callback(app : App, name : String, before : String, button : String) -> Unit {
  app.callbacks.push("{\"name\":\"\{name}\",\"before\":\{before},\"after\":\{state(app)},\"button\":\{button}}")
  if before != state(app) { app.dirty.val = true }
}

// Observe the callback's delivered payload, never relabel it from the fixture.
// Releases are represented honestly so a broken release-dispatch control can
// reach semantic comparison and be rejected for its extra callback.
fn delivered_button(event : @primitives.InputEvent) -> String {
  let button = match event {
    @primitives.PointerButtonPressed(button~, ..) => button
    @primitives.PointerButtonReleased(button~, ..) => button
    _ => abort("Outside callback delivered a non-button event")
  }
  match button {
    @primitives.Primary => "left"
    @primitives.Secondary => "right"
    @primitives.Middle => "middle"
    @primitives.Back => "back"
    @primitives.Forward => "forward"
  }
}

fn dispatch(app : App, frame : @element.PointerOutsideFrame,
  event : @primitives.InputEvent, _fixture_button_name : String) -> Unit {
  frame.dispatch_input_with(event, (context, delivered_event) => {
    let button_name = delivered_button(delivered_event)
    let before = state(app)
    if context.current_target() == 5UL {
      app.child.val = false
      record_callback(app, "dismiss_child", before, "\"\{button_name}\"")
    } else if context.current_target() == 3UL {
      app.parent.val = false
      app.child.val = false
      record_callback(app, "dismiss_parent", before, "\"\{button_name}\"")
    }
    Ok(())
  }, (context, routed_event) => {
    if context.phase() == @element.Bubble {
      let target = context.current_target()
      if target == 2UL || target == 4UL {
        let model = if target == 2UL { app.parent_button } else { app.child_button }
        let pressed = model.val.is_pressed()
        let (next, effect) = model.val.handle_input(routed_event)
        model.val = next
        if pressed != next.is_pressed() { app.dirty.val = true }
        if effect.effect() == @button.Activated {
          let before = state(app)
          if target == 2UL {
            app.parent.val = true
            record_callback(app, "open_parent", before, "null")
          } else {
            app.child.val = true
            record_callback(app, "open_child", before, "null")
          }
        }
      }
    }
    Ok(())
  }).unwrap() |> ignore
}

fn main {
  let app : App = {
    parent: Ref(false), child: Ref(false), dirty: Ref(true), callbacks: [],
    parent_button: Ref(@button.Button::new(2,
      @primitives.Rect::new(0, 0, 60, 24).unwrap(), "parent").unwrap()),
    child_button: Ref(@button.Button::new(4,
      @primitives.Rect::new(0, 0, 64, 24).unwrap(), "child").unwrap()),
  }
  let (initial_frame, initial_record) = render(app)
  let mut frame = initial_frame
  let operations = ["{\"operation\":\"initial\",\"input\":{\"kind\":\"open_window\"},\"state\":\{state(app)},\"callbacks\":[],\"frame\":\{initial_record}}"]
  for index = 0; index < step_count(); index = index + 1 {
    app.callbacks.clear()
    let button_name = step_button(index)
    let button = match button_name {
      "left" => @primitives.Primary
      "right" => @primitives.Secondary
      _ => abort("Unsupported fixture button")
    }
    let position = @primitives.Point::new(step_x(index), step_y(index)).unwrap()
    let modifiers = @primitives.Modifiers::none()
    let event = match step_kind(index) {
      "down" => @primitives.PointerButtonPressed(position~, button~, modifiers~)
      "up" => @primitives.PointerButtonReleased(position~, button~, modifiers~)
      _ => abort("Unsupported fixture input")
    }
    dispatch(app, frame, event, button_name)
    // MUTATION_SITE_SAME_EVENT_CASCADE: inserting a render and redispatch here
    // wrongly allows the newly registered parent to see the child's down.
    let frame_field = if app.dirty.val {
      let (next, record) = render(app)
      frame = next
      ",\"frame\":\{record}"
    } else { "" }
    operations.push("{\"operation\":\{step_id_json(index)},\"input\":\{step_input_json(index)},\"state\":\{state(app)},\"callbacks\":[\{app.callbacks.join(",")}]\{frame_field}}")
  }
  println("{\"schema_version\":1,\"layer\":\"compiled-moonbit-popover-outside\",\"input\":\{fixture_json()},\"run_token\":\{token_json()},\"operations\":[\{operations.join(",")}]} ")
}
