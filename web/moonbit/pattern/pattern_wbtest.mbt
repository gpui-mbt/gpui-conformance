///|
test "source structure uses intrinsic group width and eight authored stripe sizes" {
  let frame = prepare([140.0,350.0],1)
  let tree = frame.tree()
  assert_eq(tree.node(1).unwrap().bounds().left(),0)
  assert_eq(tree.node(1).unwrap().bounds().top(),0)
  assert_eq(tree.node(1).unwrap().bounds().size().width(),600)
  assert_eq(tree.node(1).unwrap().bounds().size().height(),600)
  assert_eq(tree.node(10).unwrap().bounds().size().width(),56)
  assert_eq(tree.node(10).unwrap().bounds().size().height(),74)
  assert_eq(tree.node(11).unwrap().bounds().size().width(),352)
  for id in [20UL,21UL,22UL,23UL] {
    assert_eq(tree.node(id).unwrap().bounds().size().width(),54)
  assert_eq(tree.node(id).unwrap().bounds().size().height(),18)
  }
  for id in [30UL,31UL,32UL] {
    assert_eq(tree.node(id).unwrap().bounds().size().width(),256)
  assert_eq(tree.node(id).unwrap().bounds().size().height(),56)
  }
  assert_eq(tree.node(33).unwrap().bounds().size().width(),256)
  assert_eq(tree.node(33).unwrap().bounds().size().height(),26)
  for id in [40UL,41UL] {
    assert_eq(tree.node(id).unwrap().bounds().size().width(),240)
  assert_eq(tree.node(id).unwrap().bounds().size().height(),40)
  }
  // Different measured text changes intrinsic width, never the authored stripe sizes.
  let wider = prepare([140.0,400.0],1).tree()
  assert_eq(wider.node(11).unwrap().bounds().size().width(),402)
  assert_eq(wider.node(30).unwrap().bounds().size().width(),256)
}

///|
test "canonical core scene preserves eight slash paints plus real controls" {
  let frame = prepare([140.0,350.0],1)
  let scene = canonical_scene(frame,600,600,1,1)
  let mut slash_count = 0
  let mut label_count = 0
  for item in scene.items() {
    match item {
      @scene.PaintItem(fill~,id~,..) => match fill {
        @scene.Slash(pattern) => {
        slash_count += 1
        if id < 30 {
          assert_eq(pattern.width(),4.5)
          assert_eq(pattern.interval(),if id == 23 { 9.0 } else { 4.5 })
        } else {
          assert_eq(pattern.width(),56.0/6.0)
          assert_eq(pattern.interval(),56.0/6.0)
        }
      }
        _ => ()
      }
      @scene.TextRunItem(..) => label_count += 1
      _ => ()
    }
  }
  assert_eq(slash_count,8)
  assert_eq(label_count,2)
  assert_eq(scene.items()[scene.items().length()-2].id(),100)
  assert_eq(scene.items()[scene.items().length()-1].id(),101)
  let solid = frame.tree().node(40).unwrap().bounds()
  let color = scene.sample_paint(40,@primitives.Point::new(solid.left()+10,solid.top()+10).unwrap()).unwrap().unwrap()
  assert_eq(color.red(),1)
  assert_eq(color.green(),0)
}

///|
test "source labels have no geometric overlap with source-later stripes" {
  let tree = prepare([140.0,350.0],1).tree()
  let title = tree.node(100).unwrap().bounds()
  assert_true(title.bottom() <= tree.node(10).unwrap().bounds().top())
  let label = tree.node(101).unwrap().bounds()
  assert_true(label.bottom() <= tree.node(30).unwrap().bounds().top())
  // Host independently checks actual glyph ink plus an antialias margin.
}

///|
test "invalid metrics and unsupported profiles fail closed" {
  assert_eq(pattern_frame_at_scale(600,600,[],1,1),"{\"ok\":false,\"error\":\"invalid_metrics\"}")
  assert_eq(pattern_frame_at_scale(600,600,[140.0,350.0],2,1),"{\"ok\":false,\"error\":\"unsupported_pattern_profile\"}")
  assert_eq(pattern_frame_at_scale(800,600,[140.0,350.0],1,1),"{\"ok\":false,\"error\":\"unsupported_pattern_profile\"}")
}
