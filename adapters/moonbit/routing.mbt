///|
fn route_events(
  tree : @element.ElementTree,
  event : @primitives.InputEvent,
  stop : Json?,
) -> Json {
  let events : Array[Json] = []
  ignore(
    checked(
      tree.dispatch_input_with(event, (context, _) => {
        let phase = match context.phase() {
          @element.Capture => "capture"
          @element.Bubble => "bubble"
        }
        let entry = @json.to_json([
          @json.to_json(context.current_target().to_int()),
          @json.to_json(phase),
        ])
        events.push(entry)
        if stop == Some(entry) {
          context.stop_propagation()
        }
        Ok(())
      }),
    ),
  )
  @json.to_json(events)
}

///|
fn observe_routing(s : Json) -> Json {
  let mut element_tree = tree(s).tree()
  let stop = optional(s, "stop")
  let observation = if string(field(s, "kind")) == "route" {
    let events = array(field(s, "points")).map(p => {
      let coords = array(p)
      route_events(
        element_tree,
        @primitives.PointerButtonPressed(
          position=checked(
            @primitives.Point::new(number(coords[0]), number(coords[1])),
          ),
          button=@primitives.Primary,
          modifiers=@primitives.Modifiers::none(),
        ),
        stop,
      )
    })
    object([("events", @json.to_json(events))])
  } else {
    let steps : Array[Json] = []
    for desired in array(field(s, "focuses")) {
      element_tree = match desired {
        Null => element_tree.clear_focus()
        _ => checked(element_tree.with_focus(number(desired).to_uint64()))
      }
      let focused = match element_tree.focused() {
        Some(id) => @json.to_json(id.to_int())
        None => Json::null()
      }
      let key = @primitives.Character(string(field(s, "key")))
      let event = if string(field(s, "event")) == "up" {
        @primitives.KeyReleased(key~, modifiers=@primitives.Modifiers::none())
      } else {
        @primitives.KeyPressed(
          key~,
          modifiers=@primitives.Modifiers::none(),
          repeat=false,
        )
      }
      steps.push(
        object([
          ("focused", focused),
          ("events", route_events(element_tree, event, stop)),
        ]),
      )
    }
    object([("steps", @json.to_json(steps))])
  }
  object([
    ("id", field(s, "id")),
    ("layer", field(s, "layer")),
    ("status", @json.to_json("observed")),
    ("observation", observation),
  ])
}
