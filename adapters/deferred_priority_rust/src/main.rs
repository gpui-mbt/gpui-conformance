//! Public GPUI observations only: no priority sorter, hit tester or expected results.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};
const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Interaction {
    listener: String,
    propagation: String,
    occlude: bool,
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Layer {
    id: String,
    priority: usize,
    transparent: bool,
    interaction: Interaction,
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    window: [f32; 2],
    scale_factor: f32,
    position: [f32; 2],
    size: [f32; 2],
    probe_position: [f32; 2],
    ordinary_interaction: Interaction,
    layers: Vec<Layer>,
    update_layer: String,
    update_priority: usize,
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
            json!({"type": "paint", "node": self.node, "bounds": bounds_value(bounds),
            "content_mask": bounds_value(window.content_mask().bounds)}),
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

fn interactive(
    mut element: Stateful<Div>,
    node: &str,
    config: &Interaction,
    log: &SharedLog,
) -> Stateful<Div> {
    if config.occlude {
        element = element.occlude();
    }
    if config.listener == "bubble-left-mouse-down" {
        let log = log.clone();
        let node = node.to_owned();
        let config = config.clone();
        element = element.on_mouse_down(MouseButton::Left, move |event, _, cx| {
            record(
                &log,
                json!({"type": "mouse_down", "node": node,
                "position": point_value(event.position), "button": "Left", "phase": "Bubble",
                "listener": config.listener, "propagation": config.propagation,
                "occlude": config.occlude}),
            );
            if config.propagation == "stop" {
                cx.stop_propagation();
            }
        });
    }
    element
}
fn box_node(
    node: &str,
    dimensions: [f32; 2],
    transparent: bool,
    config: &Interaction,
    log: &SharedLog,
) -> Stateful<Div> {
    interactive(
        div()
            .id(node.to_owned())
            .relative()
            .w(px(dimensions[0]))
            .h(px(dimensions[1]))
            .bg(if transparent {
                rgba(0x00000000)
            } else {
                rgba(0x789abcff)
            }),
        node,
        config,
        log,
    )
}
fn subtree(layer: &Layer, case: &Scenario, log: &SharedLog) -> AnyElement {
    let root_id = format!("{}.root", layer.id);
    let mut root = box_node(
        &root_id,
        case.size,
        layer.transparent,
        &layer.interaction,
        log,
    );
    for (suffix, origin) in [("first", [0., 0.]), ("second", [24., 16.])] {
        let id = format!("{}.{}", layer.id, suffix);
        root = root.child(observed(
            box_node(&id, [80., 64.], layer.transparent, &layer.interaction, log)
                .absolute()
                .left(px(origin[0]))
                .top(px(origin[1])),
            &id,
            log,
        ));
    }
    observed(root, &root_id, log).into_any_element()
}
struct Probe {
    scenario: Scenario,
    removed: bool,
    updated: bool,
    log: SharedLog,
}
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let case = &self.scenario;
        let ordinary = |node: &str| {
            observed(
                box_node(
                    node,
                    case.size,
                    false,
                    &case.ordinary_interaction,
                    &self.log,
                )
                .absolute()
                .left(px(case.position[0]))
                .top(px(case.position[1])),
                node,
                &self.log,
            )
        };
        let mut host = div()
            .relative()
            .size_full()
            .child(ordinary("ordinary.before"));
        // Only structural iteration. All deferred ordering belongs to upstream GPUI.
        for layer in &case.layers {
            if self.removed && layer.id == case.update_layer {
                continue;
            }
            let priority = if self.updated && layer.id == case.update_layer {
                case.update_priority
            } else {
                layer.priority
            };
            let anchor_id = format!("{}.anchor", layer.id);
            let deferred_id = format!("{}.deferred", layer.id);
            let attachment = anchored()
                .anchor(Anchor::TopLeft)
                .position_mode(AnchoredPositionMode::Window)
                .position(point(px(case.position[0]), px(case.position[1])))
                .child(subtree(layer, case, &self.log));
            host = host.child(observed(
                deferred(observed(attachment, &anchor_id, &self.log)).with_priority(priority),
                &deferred_id,
                &self.log,
            ));
        }
        observed(host.child(ordinary("ordinary.after")), "$host", &self.log)
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
            removed: false,
            updated: false,
            log: log.clone(),
        },
    );
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    for stage in ["base", "updated", "removed", "restored"] {
        let input = match stage {
            "base" => json!({"action": "set_scale_factor", "scale_factor": scenario.scale_factor}),
            "updated" => {
                json!({"action": "set_priority", "layer": scenario.update_layer, "priority": scenario.update_priority})
            }
            "removed" => json!({"action": "remove_layer", "layer": scenario.update_layer}),
            _ => json!({"action": "restore_original_layers"}),
        };
        operation_start(&log, stage, input);
        if stage == "base" {
            cx.simulate_scale_factor_change(scenario.scale_factor);
        }
        handle.update(&mut cx, |probe, _, cx| {
            probe.updated = stage == "updated" || stage == "removed";
            probe.removed = stage == "removed";
            cx.notify();
        })?;
        cx.run_until_parked();
        operation_end(&log, &mut cx);
        operation_start(
            &log,
            &format!("{stage}.input"),
            json!({"action": "left_click", "position": scenario.probe_position}),
        );
        cx.simulate_click(
            point(
                px(scenario.probe_position[0]),
                px(scenario.probe_position[1]),
            ),
            Modifiers::none(),
        );
        cx.run_until_parked();
        operation_end(&log, &mut cx);
    }
    Ok(json!({"id": scenario.id, "events": log.borrow().events.clone()}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err("usage: gpui-deferred-priority-diagnostic SCENARIOS_JSON RUN_TOKEN".into());
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
        serde_json::to_string(&json!({"schema_version": 1,
        "layer": "supplemental-headless-deferred-priority", "fixture": "font-free-bounded-flat-deferred-priority",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": UPSTREAM,
        "run_token": arguments[2], "input": input, "cases": cases}))?
    );
    Ok(())
}
