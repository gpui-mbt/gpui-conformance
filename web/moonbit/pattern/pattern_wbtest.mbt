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
test "invalid metrics and unsafe viewports fail closed" {
  assert_eq(pattern_frame_at_scale(600,600,[],1,1),"{\"ok\":false,\"error\":\"invalid_metrics\"}")
  for (w,h,dpr,scale) in [(0.0,600.0,1.0,1.0),(2049.0,600.0,1.0,1.0),(600.0,600.0,0.0,1.0),(600.0,600.0,2.0,2.0)] {
    assert_eq(pattern_frame_at_scale(w,h,[140.0,350.0],dpr,scale),"{\"ok\":false,\"error\":\"invalid_pattern_viewport\"}")
  }
}

///|
test "live clipping and DPR preserve authored content and mark qualification separately" {
  for dpr in [0.75,1.0,1.25,2.0,3.0] {
    let frame = prepare([140.0,350.0],dpr)
    assert_eq(frame.tree().node(1).unwrap().bounds().size().width(),600)
    for (w,h) in [(320.0,480.0),(800.0,700.0),(600.0,600.0)] {
      let scene = canonical_scene(frame,w,h,1,dpr)
      assert_eq(scene.viewport().size().width(),w)
      assert_eq(scene.viewport().size().height(),h)
      let output = present(scene,dpr,w,h)
      assert_true(output.contains("\"ok\":true"))
      assert_true(output.contains(if w == 600 && h == 600 && dpr == 1 { "\"comparison_profile_match\":true" } else { "\"comparison_profile_match\":false" }))
    }
  }
}

///|
test "fractional clipped live edges retain opaque transport and exact qualification stays unchanged" {
  for (w,h,scale) in [(1.0,1.0,0.25),(321.0,479.0,1.25),(801.0,701.0,0.75),(320.0,480.0,2.0)] {
    let scene = live_scene(prepare([140.0,350.0],scale),w,h,scale,scale)
    let tile = scene.rasterize_paint_run_webgl2_linear(0,scene.items().length()-2).unwrap().unwrap()
    let bytes = tile.rgba()
    for i = 3; i < bytes.length(); i = i + 4 { assert_eq(bytes[i],255) }
    assert_eq(scene.items()[0].id(),0)
  }
  let frame = prepare([140.0,350.0],1)
  assert_eq(live_scene(frame,600,600,1,1).canonical_json(),canonical_scene(frame,600,600,1,1).canonical_json())
}
