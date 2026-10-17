//! Separately authored margin-only actual GPUI probe. No expected geometry or solver.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};

const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Popup {
    anchor: String,
    position: [f32; 2],
    position_mode: String,
    size: [f32; 2],
    margin: f32,
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    window: [f32; 2],
    parent_origin: [f32; 2],
    parent_size: [f32; 2],
    scale_factor: f32,
    popup: Popup,
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
    log.events.push(
        json!({"sequence": sequence, "operation": operation, "frame": frame, "event": event}),
    );
}
fn bounds_value(bounds: Bounds<Pixels>) -> Value {
    json!([
        f32::from(bounds.origin.x),
        f32::from(bounds.origin.y),
        f32::from(bounds.size.width),
        f32::from(bounds.size.height)
    ])
}
fn point_value(point: Point<Pixels>) -> Value {
    json!([f32::from(point.x), f32::from(point.y)])
}

// Original states and returns are delegated unchanged. Bounds are observations,
// including the absolute anchored element's genuine block static-position origin.
struct Observed<E: Element> {
    inner: E,
    node: String,
    log: SharedLog,
}
impl<E: Element> IntoElement for Observed<E> {
    type Element = Self;
    fn into_element(self) -> Self {
        self
    }
}
impl<E: Element> Element for Observed<E> {
    type RequestLayoutState = E::RequestLayoutState;
    type PrepaintState = E::PrepaintState;
    fn id(&self) -> Option<ElementId> {
        self.inner.id()
    }
    fn source_location(&self) -> Option<&'static std::panic::Location<'static>> {
        self.inner.source_location()
    }
    fn request_layout(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector: Option<&InspectorElementId>,
        window: &mut Window,
        cx: &mut App,
    ) -> (LayoutId, Self::RequestLayoutState) {
        if self.node == "$host" {
            self.log.borrow_mut().frame += 1;
            record(
                &self.log,
                json!({"type": "frame_start", "scale_factor": window.scale_factor(),
                "window_size": [f32::from(window.viewport_size().width), f32::from(window.viewport_size().height)],
                "client_inset": window.client_inset().map(f32::from)}),
            );
        }
        record(
            &self.log,
            json!({"type": "request_layout", "node": self.node}),
        );
        let result = self.inner.request_layout(id, inspector, window, cx);
        record(
            &self.log,
            json!({"type": "request_layout_end", "node": self.node}),
        );
        result
    }
    fn prepaint(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        layout: &mut Self::RequestLayoutState,
        window: &mut Window,
        cx: &mut App,
    ) -> Self::PrepaintState {
        record(
            &self.log,
            json!({"type": "prepaint", "node": self.node,
            "bounds": bounds_value(bounds), "content_mask": bounds_value(window.content_mask().bounds),
            "element_offset": point_value(window.element_offset())}),
        );
        let result = self
            .inner
            .prepaint(id, inspector, bounds, layout, window, cx);
        record(
            &self.log,
            json!({"type": "prepaint_end", "node": self.node}),
        );
        result
    }
    fn paint(
        &mut self,
        id: Option<&GlobalElementId>,
        inspector: Option<&InspectorElementId>,
        bounds: Bounds<Pixels>,
        layout: &mut Self::RequestLayoutState,
        prepaint: &mut Self::PrepaintState,
        window: &mut Window,
        cx: &mut App,
    ) {
        record(
            &self.log,
            json!({"type": "paint", "node": self.node, "bounds": bounds_value(bounds)}),
        );
        self.inner
            .paint(id, inspector, bounds, layout, prepaint, window, cx);
        record(&self.log, json!({"type": "paint_end", "node": self.node}));
    }
}
fn observed<E: Element>(inner: E, node: &str, log: &SharedLog) -> Observed<E> {
    Observed {
        inner,
        node: node.into(),
        log: log.clone(),
    }
}
fn anchor(value: &str) -> Anchor {
    match value {
        "TopLeft" => Anchor::TopLeft,
        "TopCenter" => Anchor::TopCenter,
        "TopRight" => Anchor::TopRight,
        "LeftCenter" => Anchor::LeftCenter,
        "RightCenter" => Anchor::RightCenter,
        "BottomLeft" => Anchor::BottomLeft,
        "BottomCenter" => Anchor::BottomCenter,
        "BottomRight" => Anchor::BottomRight,
        _ => panic!("unsupported anchor"),
    }
}
fn leaf(identifier: &str, dimensions: [f32; 2], log: &SharedLog) -> AnyElement {
    observed(
        div()
            .w(px(dimensions[0]))
            .h(px(dimensions[1]))
            .bg(rgb(0x789abc)),
        identifier,
        log,
    )
    .into_any_element()
}
struct Probe {
    scenario: Scenario,
    log: SharedLog,
}
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let case = &self.scenario;
        let popup = &case.popup;
        // Ordinary Block static placement is observed, never replaced by expected bounds.
        let anchored_element = anchored()
            .anchor(anchor(&popup.anchor))
            .position(point(px(popup.position[0]), px(popup.position[1])))
            .position_mode(if popup.position_mode == "Local" {
                AnchoredPositionMode::Local
            } else {
                AnchoredPositionMode::Window
            })
            .snap_to_window_with_margin(px(popup.margin))
            .child(leaf("popup", popup.size, &self.log));
        let parent = div()
            .relative()
            .w(px(case.parent_size[0]))
            .h(px(case.parent_size[1]))
            .child(leaf("button", [120., 65.], &self.log))
            .child(observed(
                deferred(observed(anchored_element, "anchor", &self.log)).with_priority(0),
                "deferred",
                &self.log,
            ));
        let host = div().relative().size_full().child(
            div()
                .absolute()
                .left(px(case.parent_origin[0]))
                .top(px(case.parent_origin[1]))
                .w(px(case.parent_size[0]))
                .h(px(case.parent_size[1]))
                .child(observed(parent, "parent", &self.log)),
        );
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
    let log = Rc::new(RefCell::new(Log {
        events: vec![],
        operation: "initial".into(),
        frame: 0,
    }));
    operation_start(&log, "initial", json!({"action": "open_window"}));
    let handle = app.open_window(
        size(px(scenario.window[0]), px(scenario.window[1])),
        |_, _| Probe {
            scenario: scenario.clone(),
            log: log.clone(),
        },
    );
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    operation_start(
        &log,
        "configured",
        json!({
            "action": "set_scale_factor", "scale_factor": scenario.scale_factor,
        }),
    );
    cx.simulate_scale_factor_change(scenario.scale_factor);
    handle.update(&mut cx, |_, _, cx| cx.notify())?;
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    Ok(json!({"id": scenario.id, "events": log.borrow().events.clone()}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err("usage: gpui-anchor-margin-diagnostic SCENARIOS_JSON RUN_TOKEN".into());
    }
    let input: Value = serde_json::from_slice(&std::fs::read(&arguments[1])?)?;
    if input["schema_version"] != 1 {
        return Err("unsupported schema".into());
    }
    let scenarios: Vec<Scenario> = serde_json::from_value(input["cases"].clone())?;
    let cases = scenarios
        .iter()
        .map(observe)
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema_version": 1, "layer": "supplemental-headless-anchor-margin",
            "fixture": "font-free-bounded-anchor-margin",
            "text_system": "NoopTextSystem; no text used", "upstream_revision": UPSTREAM,
            "run_token": arguments[2], "input": input, "cases": cases,
        }))?
    );
    Ok(())
}
