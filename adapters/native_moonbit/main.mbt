///|
fn[T, E] checked(value : Result[T, E]) -> T {
  match value {
    Ok(value) => value
    Err(_) => {
      restore_foreground()
      abort("native framework operation failed")
    }
  }
}

///|
fn field(value : Json, key : String) -> Json {
  match value {
    Object(values) => values.get(key).unwrap()
    _ => abort("object")
  }
}

///|
fn array(value : Json) -> Array[Json] {
  match value {
    Array(value) => value
    _ => abort("array")
  }
}

///|
fn number(value : Json) -> Double {
  match value {
    Number(value, ..) => value
    _ => abort("number")
  }
}

///|
fn object(values : Array[(String, Json)]) -> Json {
  Json::object(Map::from_array(values))
}

///|
extern "C" fn preserve_foreground() -> Unit = "conformance_preserve_foreground"

///|
extern "C" fn restore_foreground() -> Unit = "conformance_restore_foreground"

///|
fn main {
  let s = @json.parse(@env.get_env_var("GPUI_SCENARIOS").unwrap()) catch {
    _ => abort("scenarios")
  }
  let cases = array(field(s, "cases"))
  let w = cases[0]
  let p = cases[1]
  preserve_foreground()
  let host = checked(@macos.Host::start())
  let window = checked(
    host.create_window(
      "GPUI conformance (self-closing)",
      number(field(w, "width")),
      number(field(w, "height")),
    ),
  )
  let (width, height, scale) = checked(host.window_metrics(window))
  let live_before = host.window_metrics(window) is Ok(_)
  let r = array(field(p, "rect"))
  let viewport = checked(@primitives.Rect::new(0, 0, width, height))
  let background = array(field(p, "background"))
  let color = if @env.get_env_var("GPUI_NEGATIVE_CONTROL") == Some("1") {
    @json.to_json([0, 0, 255, 255])
  } else {
    field(p, "color")
  }
  let channels = array(color)
  let scene = @scene.Scene::new([
    @scene.PaintCommand::quad(
      1,
      viewport,
      checked(
        @primitives.Color::rgba(
          number(background[0]).to_int(),
          number(background[1]).to_int(),
          number(background[2]).to_int(),
          number(background[3]).to_int(),
        ),
      ),
    ),
    @scene.PaintCommand::quad(
      2,
      checked(
        @primitives.Rect::new(
          number(r[0]),
          number(r[1]),
          number(r[2]),
          number(r[3]),
        ),
      ),
      checked(
        @primitives.Color::rgba(
          number(channels[0]).to_int(),
          number(channels[1]).to_int(),
          number(channels[2]).to_int(),
          number(channels[3]).to_int(),
        ),
      ),
    ),
  ])
  checked(host.present(window, checked(scene.snapshot_v1(viewport, scale))))
  let capture = checked(@testing.capture_frame(host, window))
  let samples = array(field(p, "points")).map(point => {
    let coords = array(point)
    let (red, green, blue, alpha) = checked(
      capture.pixel_rgba8(
        (number(coords[0]) * scale).to_int(),
        (number(coords[1]) * scale).to_int(),
      ),
    )
    @json.to_json([red, green, blue, alpha])
  })
  let size = array(field(w, "resize"))
  checked(host.set_size(window, number(size[0]), number(size[1])))
  for _ in 0..<8 {
    ignore(checked(host.next_event(timeout_ms=10)))
  }
  let (new_width, new_height, _) = checked(host.window_metrics(window))
  checked(host.destroy_window(window))
  let live_after = match host.window_metrics(window) {
    Err(error) if error.code() is @diagnostics.StaleHandle => false
    Err(_) => {
      restore_foreground()
      abort("unexpected post-destroy error")
    }
    Ok(_) => true
  }
  checked(host.stop())
  restore_foreground()
  let rows = [
    object([
      ("id", field(w, "id")),
      ("layer", @json.to_json("native-window")),
      ("status", @json.to_json("observed")),
      (
        "observation",
        object([
          ("initial", @json.to_json([0.0, 0.0, width, height])),
          ("resized", @json.to_json([0.0, 0.0, new_width, new_height])),
          ("live_before", @json.to_json(live_before)),
          ("live_after", @json.to_json(live_after)),
        ]),
      ),
    ]),
    object([
      ("id", field(p, "id")),
      ("layer", @json.to_json("native-gpu")),
      ("status", @json.to_json("observed")),
      (
        "observation",
        object([
          ("width", @json.to_json(capture.width())),
          ("height", @json.to_json(capture.height())),
          ("scale", @json.to_json(capture.scale())),
          ("samples", @json.to_json(samples)),
        ]),
      ),
    ]),
  ]
  let output = object([
    ("implementation", @json.to_json("moonbit")),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap())),
    ("cases", @json.to_json(rows)),
    (
      "frame",
      object([
        ("width", @json.to_json(capture.width())),
        ("height", @json.to_json(capture.height())),
        ("scale", @json.to_json(capture.scale())),
        (
          "rgba8",
          @json.to_json(
            capture.rgba8_top_left().to_array().map(byte => byte.to_int()),
          ),
        ),
      ]),
    ),
  ])
  println("GPUI_CONFORMANCE " + output.stringify())
}
