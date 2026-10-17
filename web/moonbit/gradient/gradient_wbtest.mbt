///|
test "source ElementTree rows, core bounds and actual dispatch" {
  gradient_reset()
  let widths = [140.0,35.0,40.0,80.0]
  for (width,height) in [(960.0,600.0),(600.0,960.0),(733.0,515.0)] {
    let frame = prepare(width,height,widths,1)
    let tree = frame.tree()
    assert_eq(tree.node(1).unwrap().bounds().size().width(),width)
    assert_eq(tree.node(50).unwrap().bounds().size().height(),96)
    let button = tree.node(3).unwrap().bounds()
    current_tree.val = Some(tree)
    gradient_click(button.left()+2,button.top()+2)
    assert_true(oklab.val)
    gradient_click(button.left()+2,button.top()+2)
    assert_false(oklab.val)
    gradient_click(0,0)
    assert_false(oklab.val)
    let scene = canonical_scene(frame,1)
    let mut paint_count = 0
    for item in scene.items() {
      match item { @scene.PaintItem(..) => paint_count += 1; _ => () }
    }
    assert_eq(paint_count,16) //15 source colored shapes plus method button.
    let polygon = scene.sample_paint(50,@primitives.Point::new(width*0.5,tree.node(50).unwrap().bounds().top()+55).unwrap()).unwrap()
    assert_true(polygon is Some(_))
  }
}

///|
test "safe live profile separate from frozen comparison profile" {
  assert_true(valid_viewport(733,515,1.25))
  assert_true(valid_viewport(600,960,1))
  assert_false(valid_viewport(200,600,1))
  assert_false(valid_viewport(960,600,4))
  assert_false(valid_viewport(960,600,0))
  assert_eq(gradient_frame(200,600,[],1),"{\"ok\":false,\"error\":\"invalid_live_viewport\"}")
  assert_eq(gradient_frame(960,600,[],1),"{\"ok\":false,\"error\":\"invalid_metrics\"}")
}

///|
test "exact half green remains float through authored source" {
  assert_eq(rgba(0,0.5,0,0.5).green(),0.5)
  assert_eq(rgba(0,0.5,0,0.5).alpha(),0.5)
}
