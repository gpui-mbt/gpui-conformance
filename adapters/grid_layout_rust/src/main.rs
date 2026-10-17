//! Font-free supplemental semantics, not the unchanged grid_layout example.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};

const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Node {
    id: String,
    kind: String,
    width: Option<f32>,
    height: Option<f32>,
    cols: Option<u16>,
    rows: Option<u16>,
    gap: Option<f32>,
    col_span: Option<u16>,
    row_span: Option<u16>,
    col_start: Option<i16>,
    col_end: Option<i16>,
    row_start: Option<i16>,
    row_end: Option<i16>,
    #[serde(default)]
    full_columns: bool,
    #[serde(default)]
    children: Vec<Node>,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Hit {
    id: String,
    position: [f32; 2],
}

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Host {
    layout: String,
    align_items: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    window: [f32; 2],
    origin: [f32; 2],
    scale_factor: f32,
    root: Node,
    host: Option<Host>,
    hits: Vec<Hit>,
}

struct Log {
    events: Vec<Value>,
    operation: String,
    frame: usize,
}
type SharedLog = Rc<RefCell<Log>>;

fn record(log: &SharedLog, event: Value) {
    let mut log = log.borrow_mut();
    let sequence = log.events.len();
    let frame = log.frame;
    let operation = log.operation.clone();
    log.events.push(json!({"sequence": sequence, "operation": operation,
        "frame": frame, "event": event}));
}
fn bounds_value(bounds: Bounds<Pixels>) -> Value {
    json!([f32::from(bounds.origin.x), f32::from(bounds.origin.y),
        f32::from(bounds.size.width), f32::from(bounds.size.height)])
}
fn size_value(size: Size<Pixels>) -> Value {
    json!([f32::from(size.width), f32::from(size.height)])
}
fn point_value(point: Point<Pixels>) -> Value {
    json!([f32::from(point.x), f32::from(point.y)])
}

// This wrapper delegates every lifecycle call and returns the original states.
// It does not place children, compute tracks, hit-test, or manufacture bounds.
struct Observed<E: Element> {
    inner: E,
    node: String,
    log: SharedLog,
}
impl<E: Element> IntoElement for Observed<E> {
    type Element = Self;
    fn into_element(self) -> Self { self }
}
impl<E: Element> Element for Observed<E> {
    type RequestLayoutState = E::RequestLayoutState;
    type PrepaintState = E::PrepaintState;
    fn id(&self) -> Option<ElementId> { self.inner.id() }
    fn source_location(&self) -> Option<&'static std::panic::Location<'static>> {
        self.inner.source_location()
    }
    fn request_layout(&mut self, id: Option<&GlobalElementId>, inspector: Option<&InspectorElementId>,
        window: &mut Window, cx: &mut App) -> (LayoutId, Self::RequestLayoutState) {
        if self.node == "$host" {
            self.log.borrow_mut().frame += 1;
            record(&self.log, json!({"type": "frame_start", "scale_factor": window.scale_factor(),
                "window_size": size_value(window.viewport_size())}));
        }
        record(&self.log, json!({"type": "request_layout", "node": self.node}));
        let result = self.inner.request_layout(id, inspector, window, cx);
        record(&self.log, json!({"type": "request_layout_end", "node": self.node}));
        result
    }
    fn prepaint(&mut self, id: Option<&GlobalElementId>, inspector: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>, layout: &mut Self::RequestLayoutState,
        window: &mut Window, cx: &mut App) -> Self::PrepaintState {
        record(&self.log, json!({"type": "prepaint", "node": self.node,
            "bounds": bounds_value(bounds), "content_mask": bounds_value(window.content_mask().bounds)}));
        let result = self.inner.prepaint(id, inspector, bounds, layout, window, cx);
        record(&self.log, json!({"type": "prepaint_end", "node": self.node}));
        result
    }
    fn paint(&mut self, id: Option<&GlobalElementId>, inspector: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>, layout: &mut Self::RequestLayoutState,
        prepaint: &mut Self::PrepaintState, window: &mut Window, cx: &mut App) {
        record(&self.log, json!({"type": "paint", "node": self.node, "bounds": bounds_value(bounds)}));
        self.inner.paint(id, inspector, bounds, layout, prepaint, window, cx);
        record(&self.log, json!({"type": "paint_end", "node": self.node}));
        if self.node == "$host" {
            record(&self.log, json!({"type": "frame_end", "scale_factor": window.scale_factor(),
                "window_size": size_value(window.viewport_size())}));
        }
    }
}
fn observed<E: Element>(inner: E, node: &str, log: &SharedLog) -> Observed<E> {
    Observed { inner, node: node.into(), log: log.clone() }
}

// Declarative GPUI builders only. No alternative layout implementation lives here.
fn styled<E: Styled>(mut element: E, node: &Node) -> E {
    element = element.size_full();
    if let Some(value) = node.width { element = element.w(px(value)); }
    if let Some(value) = node.height { element = element.h(px(value)); }
    if let Some(value) = node.col_span { element = element.col_span(value); }
    if let Some(value) = node.row_span { element = element.row_span(value); }
    if node.full_columns { element = element.col_span_full(); }
    if let Some(value) = node.col_start { element = element.col_start(value); }
    if let Some(value) = node.col_end { element = element.col_end(value); }
    if let Some(value) = node.row_start { element = element.row_start(value); }
    if let Some(value) = node.row_end { element = element.row_end(value); }
    element
}
fn build_node(node: &Node, log: &SharedLog) -> AnyElement {
    match node.kind.as_str() {
        "grid" => {
            let mut grid = styled(div().grid().grid_cols(node.cols.unwrap())
                .grid_rows(node.rows.unwrap()).gap(px(node.gap.unwrap())), node);
            for child in &node.children { grid = grid.child(build_node(child, log)); }
            observed(grid, &node.id, log).into_any_element()
        }
        "query" => {
            let child = node.children[0].clone();
            let callback_log = log.clone();
            let identifier = node.id.clone();
            let query = container_query(move |assigned, _, _| {
                record(&callback_log, json!({"type": "callback", "node": identifier,
                    "size": size_value(assigned)}));
                build_node(&child, &callback_log)
            });
            observed(styled(query, node), &node.id, log).into_any_element()
        }
        "box" => {
            let click_log = log.clone();
            let identifier = node.id.clone();
            let leaf = styled(div().id(node.id.clone()).bg(rgb(0x789abc)).occlude(), node)
                .on_click(move |event, _, cx| {
                    let detail = match event {
                        ClickEvent::Mouse(mouse) => json!({"kind": "mouse",
                            "down": point_value(mouse.down.position), "up": point_value(mouse.up.position)}),
                        ClickEvent::Keyboard(_) => json!({"kind": "keyboard"}),
                        ClickEvent::Touch(_) => json!({"kind": "touch"}),
                    };
                    record(&click_log, json!({"type": "click", "node": identifier, "detail": detail}));
                    cx.stop_propagation();
                });
            observed(leaf, &node.id, log).into_any_element()
        }
        _ => panic!("unsupported node kind"),
    }
}
struct Probe { root: Node, origin: [f32; 2], host: Option<Host>, log: SharedLog }
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        // Ordinary authored positioning, or a real flex-end host for the negative-origin regression.
        let host = if let Some(host) = &self.host {
            assert_eq!(host.layout, "flex-row");
            assert_eq!(host.align_items, "end");
            div().flex().flex_row().items_end().size_full().child(build_node(&self.root, &self.log))
        } else { div().relative().size_full().child(div().absolute()
            .left(px(self.origin[0])).top(px(self.origin[1]))
            .w(px(self.root.width.unwrap())).h(px(self.root.height.unwrap()))
            .child(build_node(&self.root, &self.log))) };
        observed(host, "$host", &self.log)
    }
}
fn operation_start(log: &SharedLog, id: &str, input: Value) {
    log.borrow_mut().operation = id.into();
    record(log, json!({"type": "operation_start", "input": input}));
}
fn operation_end(log: &SharedLog, cx: &mut VisualTestContext) {
    let scale = cx.update(|window, _| window.scale_factor());
    record(log, json!({"type": "operation_end", "scale_factor": scale}));
}
fn observe(scenario: &Scenario) -> Result<Value, Box<dyn Error>> {
    let mut app = TestAppContext::single();
    let log = Rc::new(RefCell::new(Log { events: vec![], operation: "initial".into(), frame: 0 }));
    operation_start(&log, "initial", json!({"action": "open_window"}));
    let handle = app.open_window(size(px(scenario.window[0]), px(scenario.window[1])), |_, _| Probe {
        root: scenario.root.clone(), origin: scenario.origin, host: scenario.host.clone(), log: log.clone(),
    });
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    operation_start(&log, "configured", json!({"action": "set_scale_factor", "scale_factor": scenario.scale_factor}));
    cx.simulate_scale_factor_change(scenario.scale_factor);
    handle.update(&mut cx, |_, _, cx| cx.notify())?;
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    for hit in &scenario.hits {
        operation_start(&log, &hit.id, json!({"action": "click", "position": hit.position}));
        cx.simulate_click(point(px(hit.position[0]), px(hit.position[1])), Modifiers::none());
        cx.run_until_parked();
        operation_end(&log, &mut cx);
    }
    let events = log.borrow().events.clone();
    Ok(json!({"id": scenario.id, "events": events}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let args = std::env::args().collect::<Vec<_>>();
    if args.len() != 3 { return Err("usage: gpui-grid-layout-diagnostic SCENARIOS_JSON RUN_TOKEN".into()); }
    let input: Value = serde_json::from_slice(&std::fs::read(&args[1])?)?;
    if input["schema_version"] != 1 { return Err("unsupported schema".into()); }
    let scenarios: Vec<Scenario> = serde_json::from_value(input["cases"].clone())?;
    let cases = scenarios.iter().map(observe).collect::<Result<Vec<_>, _>>()?;
    println!("{}", serde_json::to_string(&json!({"schema_version": 1,
        "layer": "supplemental-headless-grid-container-query", "fixture": "font-free-bounded-grid",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": UPSTREAM,
        "run_token": args[2], "input": input, "cases": cases}))?);
    Ok(())
}
