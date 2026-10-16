///|
fn[T] lab_required(value : Result[T, @diagnostics.FrameworkError]) -> T {
  match value {
    Ok(result) => result
    Err(error) => abort("\{error.operation()}: \{error.code().label()}")
  }
}

///|
fn lab_field(value : Json, key : String) -> Json {
  match value {
    Object(values) => values.get(key).unwrap()
    _ => abort("expected object")
  }
}

///|
fn lab_array(value : Json) -> Array[Json] {
  match value {
    Array(values) => values
    _ => abort("expected array")
  }
}

///|
fn lab_number(value : Json) -> Double {
  match value {
    Number(number, ..) => number
    _ => abort("expected number")
  }
}

///|
fn lab_rect(x : Double, y : Double, width : Double, height : Double) -> @primitives.Rect {
  match @primitives.Rect::new(x, y, width, height) {
    Ok(rect) => rect
    Err(_) => abort("invalid rectangle")
  }
}

///|
fn lab_color(value : Json) -> @primitives.Color {
  let channels = lab_array(value)
  match @primitives.Color::rgba(
    lab_number(channels[0]).to_int(),
    lab_number(channels[1]).to_int(),
    lab_number(channels[2]).to_int(),
    lab_number(channels[3]).to_int(),
  ) {
    Ok(color) => color
    Err(_) => abort("invalid fixture color")
  }
}

///|
fn lab_scene(pixels : Json, width : Double, height : Double, scale : Double) -> @scene.SceneSnapshot {
  let viewport = lab_rect(0.0, 0.0, width, height)
  let rect = lab_array(lab_field(pixels, "rect"))
  let foreground = if @env.get_env_var("GPUI_NEGATIVE_CONTROL") == Some("1") {
    @json.to_json([0, 0, 255, 255])
  } else {
    lab_field(pixels, "color")
  }
  let scene = @scene.Scene::new([
    @scene.PaintCommand::quad(1, viewport, lab_color(lab_field(pixels, "background"))),
    @scene.PaintCommand::quad(
      2,
      lab_rect(lab_number(rect[0]), lab_number(rect[1]), lab_number(rect[2]), lab_number(rect[3])),
      lab_color(foreground),
    ),
  ])
  match scene.snapshot_v1(viewport, scale) {
    Ok(snapshot) => snapshot
    Err(_) => abort("invalid scene snapshot")
  }
}

///|
fn lab_emit(event : String, width : Double, height : Double, scale : Double) -> Unit {
  let record = Json::object(Map::from_array([
    ("protocol", @json.to_json(1)),
    ("implementation", @json.to_json("moonbit")),
    ("run_token", @json.to_json(@env.get_env_var("GPUI_RUN_TOKEN").unwrap_or(""))),
    ("event", @json.to_json(event)),
    ("width", @json.to_json(width)),
    ("height", @json.to_json(height)),
    ("scale", @json.to_json(scale)),
  ]))
  println("GPUI_NATIVE_LAB " + record.stringify())
}

///|
fn main {
  let raw = @env.get_env_var("GPUI_SCENARIOS").unwrap()
  let scenarios = @json.parse(raw) catch {
    _ => abort("invalid shared scenarios")
  }
  let cases = lab_array(lab_field(scenarios, "cases"))
  let window_case = cases[0]
  let pixels = cases[1]
  let mut width = lab_number(lab_field(window_case, "width"))
  let mut height = lab_number(lab_field(window_case, "height"))
  let mut scale = 1.0
  let mut dirty = true
  let mut first_frame = false

  lab_emit("starting", width, height, scale)
  let host = lab_required(@native.Host::start())
  lab_emit("host_started", width, height, scale)
  let window = lab_required(
    host.create_window(width.to_int(), height.to_int(), "GPUI native lab — MoonBit"),
  )
  lab_emit("opened", width, height, scale)
  while host.state() == @native.Running {
    match host.next_event(timeout_ms=16) {
      Err(error) => {
        println("\{error.operation()}: \{error.code().label()}")
        ignore(host.request_exit())
      }
      Ok(Some(event)) => {
        scale = event.scale()
        match event.kind() {
          @platform.Resized(width=w, height=h) => {
            width = w
            height = h
            dirty = true
            lab_emit("resized", width, height, scale)
          }
          @platform.ScaleChanged => dirty = true
          @platform.FrameCompleted => {
            if !first_frame {
              first_frame = true
              lab_emit("frame_ready", width, height, scale)
            }
          }
          @platform.CloseRequested => {
            lab_emit("close_requested", width, height, scale)
            ignore(host.request_exit())
          }
          @platform.Input(@primitives.KeyPressed(key=@primitives.Escape, ..)) =>
            ignore(host.request_exit())
          _ => ()
        }
      }
      Ok(None) => ()
    }
    if dirty && width > 0.0 && height > 0.0 && host.state() == @native.Running {
      match host.present(window, lab_scene(pixels, width, height, scale)) {
        Ok(_) => dirty = false
        Err(error) =>
          if error.code() is @diagnostics.Busy {
            ()
          } else {
            println("\{error.operation()}: \{error.code().label()}")
            ignore(host.request_exit())
          }
      }
    }
  }
  lab_required(host.destroy_window(window))
  lab_required(host.stop())
  lab_emit("closed", width, height, scale)
}
