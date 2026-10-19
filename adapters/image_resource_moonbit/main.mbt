// JavaScript supplies only the fresh execution token. All geometry, image-fit,
// inherited alpha, clipping and painter ordering are production core output.
extern "js" fn token_json() -> String =
  #| () => JSON.stringify(process.env.GPUI_RUN_TOKEN)

fn block(id : UInt64, w : Double, h : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(id,
    @layout.Dimension::points(w).unwrap(), @layout.Dimension::points(h).unwrap(),
    @primitives.Size::new(0, 0).unwrap()).with_flex(0, 0).unwrap())
    .with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::row()))
}
fn main {
  let icon = @scene.SceneResource::image(1, @scene.ImageData::new(
    "77453d98d46494b3b34b94aa863b686ea299e0190030a5c7ca5377b238332522", 512, 512, 1).unwrap())
  let portrait = @scene.SceneResource::image(2, @scene.ImageData::new(
    "5ee1c4f5612fcc49c0bf14d1a4b774f9ba7ae4249ceec93869c9f9ba68493f0f", 100, 200, 1).unwrap())
  let cases : Array[String] = []
  for i = 0; i < 4; i = i + 1 {
    let name = if i == 0 { "original_png_nested" } else if i == 1 { "original_png_clipped" } else if i == 2 { "portrait_contain" } else { "painter_order" }
    let root = @element.Element::root(1, @layout.FlexTreeStyle::new(@layout.FlowDirection::row()))
    let (view, bindings) = if i == 2 {
      (root.with_child(block(2, 100, 100).with_scroll_offset(@primitives.Point::new(0, 0).unwrap())
        .with_child(block(3, 100, 100))),
       [@element.ElementImageBinding::new(3, portrait, 0, @scene.Contain, 1).unwrap()])
    } else {
      let red = if i == 3 { Some(@primitives.Color::rgba(255, 0, 0, 255).unwrap()) } else { None }
      let blue = if i == 3 { Some(@primitives.Color::rgba(0, 0, 255, 255).unwrap()) } else { None }
      (root.with_child(block(2, if i == 1 { 20 } else { 32 }, 32).with_background(red).with_opacity(0.5).unwrap()
          .with_scroll_offset(@primitives.Point::new(0, 0).unwrap())
          .with_child(block(3, 32, 32).with_opacity(0.5).unwrap().with_child(block(4, 32, 32))))
        .with_child(block(5, 32, 32).with_background(blue).with_child(block(6, 32, 32))),
       [@element.ElementImageBinding::new(4, icon, 0, @scene.Contain, 1).unwrap(),
        @element.ElementImageBinding::new(6, icon, 0, @scene.Contain, 1).unwrap()])
    }
    let frame = view.request_layout(@primitives.Size::new(160, 120).unwrap()).unwrap().prepaint().unwrap()
    let snapshot = frame.paint_with_images(bindings).unwrap()
      .snapshot_v1(@primitives.Rect::new(0, 0, 160, 120).unwrap(), 1).unwrap().canonical_json()
    cases.push("{\"case\":\"\{name}\",\"frame\":{\"ok\":true,\"conformance\":\"unverified\",\"decorations\":[],\"snapshot\":\{snapshot}}}")
  }
  println("{\"schema_version\":1,\"backend\":\"actual-moonbit-core\",\"run_token\":\{token_json()},\"cases\":[\{cases.join(\",\")}]}")
}
