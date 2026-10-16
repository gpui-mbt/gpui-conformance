///| The calculation is the unchanged upstream 6k±1 brute-force test, not a sieve
/// or a saved result. All presets fit signed 32-bit arithmetic (sqrt(100M) = 10k).
fn is_prime(n : Int) -> Bool {
  if n < 2 { return false }
  if n < 4 { return true }
  if n % 2 == 0 || n % 3 == 0 { return false }
  let mut i = 5
  while i * i <= n {
    if n % i == 0 || n % (i + 2) == 0 { return false }
    i = i + 6
  }
  true
}

///|
#export_name("hello_web_count")
pub fn hello_web_count(start : Int, end : Int) -> Int {
  if start < 0 || end < start || end > 100000000 { return -1 }
  let mut count = 0
  for n = start; n < end; n = n + 1 {
    if is_prime(n) { count = count + 1 }
  }
  count
}

///|
fn number(n : Int) -> String {
  let text = n.to_string()
  let chars = text.to_array()
  let mut out = ""
  for i = 0; i < chars.length(); i = i + 1 {
    if i > 0 && (chars.length() - i) % 3 == 0 { out = out + "," }
    out = out + chars[i].to_string()
  }
  out
}

///|
priv struct State {
  mut selected : Int
  mut generation : Int
  mut started : Bool
  mut run_limit : Int
  mut done : Int
  mut total : Int
  mut elapsed : Int
  mut failed : Bool
  seen : Array[Bool]
  history : Array[String]
  threads : Int
}

///|
fn new_state(threads : Int) -> State {
  { selected: 0, generation: 0, started: false, run_limit: 10000000, done: 0, total: 0,
    elapsed: 0, failed: false, seen: Array::make(12, false), history: [], threads }
}

///|
let state : Ref[State] = Ref(new_state(2))
///|
let last_tree : Ref[@element.ElementTree?] = Ref(None)
///|
fn running(s : State) -> Bool { s.started && s.done < 12 && !s.failed }
///|
fn limit(s : State) -> Int { [10000000, 50000000, 100000000][s.selected] }
///|
fn quote(text : String) -> String { @json.to_json(text).stringify() }
///|
#export_name("hello_web_init")
pub fn hello_web_init(threads : Int) -> Unit {
  state.val = new_state(if threads < 2 { 2 } else if threads > 12 { 12 } else { threads })
  last_tree.val = None
}

///|
#export_name("hello_web_metadata")
pub fn hello_web_metadata() -> String {
  "{\"id\":\"hello_web\",\"width\":640,\"height\":560,\"font_family\":\"IBM Plex Sans\",\"font_size\":16,\"interactive\":true}"
}

///|
fn status(s : State) -> String {
  if s.failed { "Background worker failed. Reload to retry." }
  else if !s.started { "Select a range and press Count Primes to begin." }
  else if s.done == 12 {
    "Found \{number(s.total)} primes below \{number(s.run_limit)} in \{s.elapsed} ms"
  } else {
    "Searching up to \{number(s.run_limit)} … \{s.done}/12 chunks  (\{s.done * 100 / 12}%)"
  }
}

///|
fn texts(s : State) -> Array[String] {
  let result = ["Prime Sieve — GPUI Web",
    "Background threads: \{s.threads} · Chunks per run: 12", "Count primes below:",
    "10 M", "50 M", "100 M", if running(s) { "Running…" } else { "Count Primes" }, status(s)]
  if !s.history.is_empty() {
    result.push("History")
    for i = s.history.length() - 1; i >= 0; i = i - 1 { result.push(s.history[i]) }
  }
  result
}

///|
fn font_size(index : Int) -> Double {
  if index == 0 { 20.0 } else if index == 6 || index == 7 { 16.0 } else { 14.0 }
}
///|
fn line_height(index : Int) -> Double {
  if index == 0 { 32.0 } else if index == 6 || index == 7 { 26.0 } else { 23.0 }
}

///|
#export_name("hello_web_content")
pub fn hello_web_content() -> String {
  let s = state.val
  let runs = texts(s).mapi((index, text) => "{\"text\":\{quote(text)},\"font_size\":\{font_size(index)}}")
  "{\"runs\":[\{runs.join(",")}],\"selected\":\{s.selected},\"generation\":\{s.generation},\"running\":\{running(s)},\"failed\":\{s.failed},\"chunks_done\":\{s.done},\"total\":\{s.total},\"elapsed_ms\":\{s.elapsed},\"history\":\{@json.to_json(s.history).stringify()}}"
}

///|
fn start(s : State) -> String {
  if running(s) || s.failed { return "{\"action\":\"none\"}" }
  s.generation = s.generation + 1
  s.started = true
  s.run_limit = limit(s)
  s.done = 0
  s.total = 0
  s.elapsed = 0
  for i = 0; i < 12; i = i + 1 { s.seen[i] = false }
  let size = limit(s) / 12
  let chunks = Array::makei(12, i => "{\"index\":\{i},\"start\":\{i * size},\"end\":\{if i == 11 { limit(s) } else { (i + 1) * size }}}")
  "{\"action\":\"start\",\"generation\":\{s.generation},\"chunks\":[\{chunks.join(",")}]}"
}

///| Pointer coordinates are delivered by the host; actual target/bubbling comes
/// from the measured gpui.mbt ElementTree. No hardcoded browser hit rectangles.
#export_name("hello_web_click")
pub fn hello_web_click(x : Double, y : Double) -> String {
  if !(x >= 0.0 && x < 640.0 && y >= 0.0 && y < 560.0) { return "{\"action\":\"none\"}" }
  let s = state.val
  if running(s) || s.failed { return "{\"action\":\"none\"}" }
  match last_tree.val {
    None => "{\"action\":\"none\"}"
    Some(tree) => {
      let path = tree.dispatch_pointer(@primitives.Point::new(x, y).unwrap()).bubble()
      if path.contains(26) { return start(s) }
      for i = 0; i < 3; i = i + 1 {
        if path.contains((23 + i).to_uint64()) {
          s.selected = i
          return "{\"action\":\"select\"}"
        }
      }
      "{\"action\":\"none\"}"
    }
  }
}

///|
#export_name("hello_web_receive")
pub fn hello_web_receive(generation : Int, index : Int, count : Int, elapsed : Int) -> Bool {
  let s = state.val
  if !running(s) || generation != s.generation || index < 0 || index >= 12 || count < 0 || elapsed < 0 { return false }
  let size = limit(s) / 12
  let end = if index == 11 { limit(s) } else { (index + 1) * size }
  if s.seen[index] || count > end - index * size { return false }
  s.seen[index] = true
  s.done = s.done + 1
  s.total = s.total + count
  if s.done == 12 {
    s.elapsed = elapsed
    s.history.push("π(\{number(s.run_limit)}) = \{number(s.total)} (\{elapsed} ms, 12 chunks)")
  }
  true
}

///|
#export_name("hello_web_fail")
pub fn hello_web_fail(generation : Int) -> Unit {
  if state.val.generation == generation && running(state.val) { state.val.failed = true }
}

///|
fn color(hex : Int) -> @primitives.Color {
  @primitives.Color::rgba((hex >> 16) & 255, (hex >> 8) & 255, hex & 255, 255).unwrap()
}
///|
fn fixed(id : UInt64, main : Double, cross : Double) -> @element.Element {
  @element.Element::new(@layout.FlexItem::new(id,
    @layout.Dimension::points(main).unwrap(), @layout.Dimension::points(cross).unwrap(),
    @primitives.Size::new(0.0, 0.0).unwrap()).with_flex(0.0, 0.0).unwrap())
}
///|
fn column(gap : Double, padding : Double, center : Bool) -> @layout.FlexTreeStyle {
  @layout.FlexTreeStyle::new(@layout.FlowDirection::column()).with_gap(gap).unwrap()
    .with_insets(@layout.Insets::all(padding).unwrap(), @layout.Insets::zero())
    .with_align(if center { @layout.AlignItems::center() } else { @layout.AlignItems::start() })
}
///|
fn text_node(index : Int, width : Double) -> @element.Element {
  fixed((101 + index).to_uint64(), line_height(index), width).with_pointer_events(false)
}
///|
fn tree(s : State, widths : Array[Double]) -> @element.Prepainted {
  let row = @layout.FlexTreeStyle::new(@layout.FlowDirection::row()).with_gap(8.0).unwrap()
  let mut presets = fixed(22, 31.0, widths[3] + widths[4] + widths[5] + 88.0).with_children_style(row)
  for i = 0; i < 3; i = i + 1 {
    presets = presets.with_child(fixed((23 + i).to_uint64(), widths[i + 3] + 24.0, 31.0)
      .with_background(Some(color(if s.selected == i { 0x89b4fa } else { 0x45475a })))
      .with_children_style(column(0.0, 0.0, true).with_justify(@layout.JustifyContent::center()))
      .with_child(text_node(i + 3, widths[i + 3])))
  }
  let controls = fixed(20, 148.0, 500.0).with_background(Some(color(0x313244)))
    .with_children_style(column(12.0, 16.0, true))
    .with_child(text_node(2, widths[2])).with_child(presets)
    .with_child(fixed(26, 38.0, widths[6] + 32.0)
      .with_background(Some(color(if running(s) { 0x45475a } else { 0xa6e3a1 })))
      .with_children_style(column(0.0, 0.0, true).with_justify(@layout.JustifyContent::center()))
      .with_child(text_node(6, widths[6])))
  let mut status_box = fixed(30, if s.started { 100.0 } else { 58.0 }, 500.0)
    .with_background(Some(color(0x313244))).with_children_style(column(8.0, 16.0, false))
    .with_child(text_node(7, widths[7]))
  if s.started {
    let progress = fixed(31, 8.0, 468.0).with_background(Some(color(0x45475a)))
      .with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::row()))
      .with_child(fixed(32, 468.0 * s.done.to_double() / 12.0, 8.0)
        .with_background(Some(color(if s.done == 12 { 0xa6e3a1 } else { 0x89b4fa }))))
    let mut dots = fixed(33, 18.0, 164.0)
      .with_children_style(@layout.FlexTreeStyle::new(@layout.FlowDirection::row()).with_gap(4.0).unwrap()
        .with_insets(@layout.Insets::new(8.0, 0.0, 0.0, 0.0).unwrap(), @layout.Insets::zero()))
    for i = 0; i < 12; i = i + 1 {
      dots = dots.with_child(fixed((40 + i).to_uint64(), 10.0, 10.0)
        .with_background(Some(color(if i < s.done { 0xcba6f7 } else { 0x45475a }))))
    }
    status_box = status_box.with_child(progress).with_child(dots)
  }
  let mut root = @element.Element::root(1, column(16.0, 16.0, true)
    .with_justify(@layout.JustifyContent::center())).with_background(Some(color(0x1e1e2e)))
    .with_child(text_node(0, widths[0])).with_child(text_node(1, widths[1]))
    .with_child(controls).with_child(status_box)
  if !s.history.is_empty() {
    let mut history = fixed(60, 59.0 + 27.0 * s.history.length().to_double(), 500.0)
      .with_background(Some(color(0x313244))).with_children_style(column(8.0, 16.0, false))
      .with_child(text_node(8, widths[8]))
    let mut entries = fixed(61, 27.0 * s.history.length().to_double() - 4.0, 468.0)
      .with_children_style(column(4.0, 0.0, false))
    for i = 9; i < widths.length(); i = i + 1 { entries = entries.with_child(text_node(i, widths[i])) }
    history = history.with_child(entries)
    root = root.with_child(history)
  }
  root.request_layout(@primitives.Size::new(640.0, 560.0).unwrap()).unwrap().prepaint().unwrap()
}

///|
#export_name("hello_web_frame")
pub fn hello_web_frame(widths : Array[Double], scale : Double) -> String {
  let s = state.val
  let labels = texts(s)
  if widths.length() != labels.length() || !(scale > 0.0 && scale <= 4.0) { return "{\"ok\":false,\"error\":\"invalid_metrics\"}" }
  for width in widths { if !(width >= 0.0 && width <= 10000.0) { return "{\"ok\":false,\"error\":\"invalid_metrics\"}" } }
  let prepainted = tree(s, widths)
  let tree = prepainted.tree()
  last_tree.val = Some(tree)
  let base = prepainted.paint_snapshot(scale).unwrap()
  let items = base.items()
  for i = 0; i < labels.length(); i = i + 1 {
    let ink = if i == 0 || (i == 7 && s.started) { 0xcdd6f4 }
      else if i == 1 || i == 7 || i == 8 { 0x6c7086 }
      else if i == 2 { 0xf9e2af }
      else if i == 6 { if running(s) { 0x6c7086 } else { 0x1e1e2e } }
      else if i >= 3 && i <= 5 { if s.selected == i - 3 { 0x1e1e2e } else { 0xa6adc8 } }
      else { 0xa6adc8 }
    let id = (101 + i).to_uint64()
    items.push(@scene.SceneItem::text(id, tree.node(id).unwrap().bounds(), labels[i], font_size(i),
      color(ink), @scene.AffineTransform::identity(), 1.0, None).unwrap())
  }
  let snapshot = @scene.SceneSnapshot::new(base.viewport(), scale, [], [], items).unwrap()
  let rounded : Array[String] = []
  for node in tree.nodes() {
    let id = node.id()
    let radius = if id == 20 || id == 30 || id == 60 { 8.0 }
      else if id >= 23 && id <= 26 { 6.0 }
      else if id == 31 || id == 32 || (id >= 40 && id <= 51) { 2.0 }
      else { 0.0 }
    if radius > 0.0 && node.bounds().size().width() >= radius * 2.0 {
      rounded.push("{\"id\":\{id},\"radius\":\{radius}}")
    }
  }
  "{\"ok\":true,\"snapshot\":\{snapshot.canonical_json()},\"decorations\":[],\"rounded_fills\":[\{rounded.join(",")}],\"conformance\":\"unverified\",\"host_extensions\":[\"font_metrics\",\"rounded_fill\",\"browser_pointer_delivery\",\"web_worker_execution\"]}"
}
