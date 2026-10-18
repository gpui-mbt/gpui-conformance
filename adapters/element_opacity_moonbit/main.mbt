// JS reads authored inputs and quotes strings only. All layout, alpha scope,
// deferred traversal, clip stack and event routing execute production core.
extern "js" fn input_json() -> String =
  #| () => process.env.GPUI_SCENARIOS
extern "js" fn token_json() -> String =
  #| () => JSON.stringify(process.env.GPUI_RUN_TOKEN)
extern "js" fn quote(value : String) -> String =
  #| value => JSON.stringify(value)
extern "js" fn count() -> Int =
  #| () => JSON.parse(process.env.GPUI_SCENARIOS).cases.length
extern "js" fn name(i : Int) -> String =
  #| i => JSON.parse(process.env.GPUI_SCENARIOS).cases[i].id
extern "js" fn number(i : Int, key : String) -> Double =
  #| (i,key) => JSON.parse(process.env.GPUI_SCENARIOS).cases[i][key] ?? 1
extern "js" fn present(i : Int, key : String) -> Bool =
  #| (i,key) => JSON.parse(process.env.GPUI_SCENARIOS).cases[i][key] !== null
extern "js" fn flag(i : Int, key : String) -> Bool =
  #| (i,key) => JSON.parse(process.env.GPUI_SCENARIOS).cases[i][key]
extern "js" fn viewport(index : Int) -> Double =
  #| index => JSON.parse(process.env.GPUI_SCENARIOS).viewport[index]

fn rect(b : @primitives.Rect) -> String {
  "[\{b.left()},\{b.top()},\{b.size().width()},\{b.size().height()}]"
}
fn block(id : UInt64, w : Double, h : Double, r : Int, g : Int, b : Int) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(id,
    @layout.Dimension::points(w).unwrap(), @layout.Dimension::points(h).unwrap(),
    @primitives.Size::new(0, 0).unwrap()).with_flex(0, 0).unwrap())
    .with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::column()))
    .with_background(Some(@primitives.Color::rgba(r, g, b, 255).unwrap()))
}
fn opacity(e : @element.Element, i : Int, key : String) -> @element.Element {
  if present(i, key) { e.with_opacity(number(i, key)).unwrap() } else { e }
}
fn view(i : Int) -> @element.Element {
  let grandchild = opacity(block(4, 40, 40, 0, 0, 255), i, "grandchild")
  // Anchored popups measure under the production temporary row root;
  // ordinary children use the column owner's main/cross dimensions.
  let child_main = if flag(i, "deferred") { 120.0 } else { 100.0 }
  let child_cross = if flag(i, "deferred") { 100.0 } else { 120.0 }
  let mut child = opacity(block(3, child_main, child_cross, 0, 255, 0), i, "child").with_child(grandchild)
  if flag(i, "nested") {
    let popup = block(7, 20, 20, 255, 255, 0).with_opacity(0.25).unwrap()
    child = child.with_child(@element.Element::anchored_after(
      9, 4, popup, @element.TopLeft, @element.Window,
      @primitives.Point::new(60, 50).unwrap(), margin=0,
    ).unwrap().deferred(priority=2).unwrap())
  }
  let mut parent = opacity(block(2, 100, 80, 255, 0, 0), i, "parent")
  if flag(i, "clip") {
    parent = parent.with_scroll_offset(@primitives.Point::new(0, 0).unwrap())
  }
  if flag(i, "deferred") {
    let leaf = block(8, 40, 40, 0, 0, 0).with_background(None).with_pointer_events(false)
    parent = parent.with_child(leaf).with_child(@element.Element::anchored_after(
      6, 8, child, @element.TopLeft, @element.Window,
      @primitives.Point::new(20, 20).unwrap(), margin=0,
    ).unwrap().deferred(priority=1).unwrap())
  } else { parent = parent.with_child(child) }
  @element.Element::root(1, @layout.FlexTreeStyle::new(@layout.FlowDirection::row()))
    .with_pointer_events(false).with_child(parent).with_child(block(5, 40, 80, 255, 0, 255))
}
fn main {
  let cases : Array[String] = []
  for i = 0; i < count(); i = i + 1 {
    let frame = view(i).request_layout(@primitives.Size::new(viewport(0), viewport(1)).unwrap()).unwrap().prepaint().unwrap()
    let alpha = number(i, "alpha") / 255.0
    let binding = number(i, "binding")
    let scene = frame.paint_with_paints([@element.ElementPaintBinding::new(4, bounds => {
      Ok((@scene.PaintShape::rounded_quad(bounds, 0).unwrap(),
        @scene.FloatSolid(@primitives.FloatColor::rgba(0, 0, 1, alpha).unwrap()), binding))
    })]).unwrap()
    scene.validate().unwrap()
    let stack : Array[@primitives.Rect] = []
    let quads : Array[String] = []
    let raw : Array[String] = []
    for command in scene.commands() {
      match command {
        @scene.ClipPushCommand(bounds~, ..) => stack.push(bounds)
        @scene.ClipPopCommand(..) => { let _ = stack.pop().unwrap() }
        _ => {
          let (bounds, r, g, b, a, opacity) = match command {
            @scene.QuadCommand(bounds~, color~, ..) =>
              (bounds, color.red().to_double()/255, color.green().to_double()/255,
                color.blue().to_double()/255, color.alpha().to_double()/255, 1.0)
            @scene.OpacityQuadCommand(bounds~, color~, opacity~, ..) =>
              (bounds, color.red().to_double()/255, color.green().to_double()/255,
                color.blue().to_double()/255, color.alpha().to_double()/255, opacity)
            @scene.PaintCommand(shape~, fill~, opacity~, ..) => {
              let color = match fill { @scene.FloatSolid(color) => color; _ => abort("non-solid fixture paint") }
              (shape.bounds(), color.red(), color.green(), color.blue(), color.alpha(), opacity)
            }
            _ => abort("unexpected command")
          }
          let mut clip = Some(@primitives.Rect::new(0, 0, viewport(0), viewport(1)).unwrap())
          for next in stack { match clip { Some(current) => clip = current.intersection(next); None => () } }
          raw.push("{\"id\":\{command.id()},\"alpha\":\{a},\"opacity\":\{opacity}}")
          // Observable scene normalization only: GPUI culls fully transparent
          // solids and nonintersecting masks. Keep raw command alpha separately.
          match clip {
            Some(mask) => if a * opacity > 0 && bounds.intersection(mask) is Some(_) {
              quads.push("{\"bounds\":\{rect(bounds)},\"clip\":\{rect(mask)},\"rgba\":[\{r},\{g},\{b},\{a * opacity}]}")
            }
            None => ()
          }
        }
      }
    }
    if stack.length() != 0 { abort("unbalanced clips") }
    let bounds : Array[String] = []
    let ids = [2UL, 3UL, 4UL, 5UL]
    if flag(i, "nested") { ids.push(7UL) }
    for id in ids {
      bounds.push("{\"id\":\{id},\"bounds\":\{rect(frame.tree().node(id).unwrap().bounds())}}")
    }
    let p = if flag(i, "deferred") { 25.0 } else { 10.0 }
    let targets : Array[UInt64] = []
    frame.tree().dispatch_input_with(@primitives.PointerButtonPressed(
      position=@primitives.Point::new(p, p).unwrap(), button=@primitives.Primary,
      modifiers=@primitives.Modifiers::none(),
    ), (context, _) => {
      if context.phase() == @element.Bubble && context.current_target() != 1UL {
        targets.push(context.current_target())
      }
      Ok(())
    }).unwrap() |> ignore
    let target = if targets.length() == 0 { "null" } else { "\{targets[0]}" }
    cases.push("{\"id\":\{quote(name(i))},\"quads\":[\{quads.join(",")}],\"bounds\":[\{bounds.join(",")}],\"target\":\{target},\"raw_alpha\":[\{raw.join(",")}]}" )
  }
  println("{\"schema_version\":1,\"backend\":\"moonbit-core\",\"run_token\":\{token_json()},\"input\":\{input_json()},\"cases\":[\{cases.join(",")}]}" )
}
