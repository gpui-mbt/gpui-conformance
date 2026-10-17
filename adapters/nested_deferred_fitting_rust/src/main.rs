//! Actual public GPUI callbacks only. No scheduling model or predicted rectangles.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};
const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Layer {
    id: String,
    priority: usize,
    nested_priority: usize,
    position: [f32; 2],
    nested_position: [f32; 2],
    nested_mode: String,
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    window: [f32; 2],
    ancestor_origin: [f32; 2],
    ancestor_size: [f32; 2],
    ancestor_movement: [f32; 2],
    reference_size: [f32; 2],
    updated_nested_reference_height: f32,
    anchor: String,
    margin: f32,
    outer_size: [f32; 2],
    nested_size: [f32; 2],
    layers: Vec<Layer>,
}
struct Log {
    events: Vec<Value>,
    operation: String,
    frame: usize,
    priorities: [usize; 4],
}
type SharedLog = Rc<RefCell<Log>>;
fn record(log: &SharedLog, mut event: Value) {
    let mut log = log.borrow_mut();
    if let Some(node) = event["node"].as_str().map(str::to_owned) {
        let group = if node.starts_with("a.nested.") {
            "a.nested"
        } else if node.starts_with("b.nested.") {
            "b.nested"
        } else if node.starts_with("a.") {
            "a"
        } else if node.starts_with("b.") {
            "b"
        } else {
            "ordinary"
        };
        let priority = match group {
            "a" => Some(log.priorities[0]),
            "a.nested" => Some(log.priorities[1]),
            "b" => Some(log.priorities[2]),
            "b.nested" => Some(log.priorities[3]),
            _ => None,
        };
        event["group"] = json!(group);
        event["priority"] = json!(priority);
    }
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
            json!({"type": "prepaint_end", "node": self.node, "bounds": bounds_value(bounds),
                "element_offset": point_value(window.element_offset()),
                "content_mask": bounds_value(window.content_mask().bounds)}),
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
        record(
            &self.log,
            json!({"type": "paint_end", "node": self.node,
            "bounds": bounds_value(bounds),
            "content_mask": bounds_value(window.content_mask().bounds)}),
        );
    }
}
fn observed<E: Element>(inner: E, node: &str, log: &SharedLog) -> Observed<E> {
    Observed {
        inner,
        node: node.into(),
        log: log.clone(),
    }
}

fn box_node(node: &str, dimensions: [f32; 2]) -> Stateful<Div> {
    div()
        .block()
        .id(node.to_owned())
        .relative()
        .w(px(dimensions[0]))
        .h(px(dimensions[1]))
        .bg(rgba(0x789abcff))
}
fn sentinel(node: &str, position: [f32; 2], log: &SharedLog) -> AnyElement {
    observed(
        box_node(node, [12., 12.])
            .absolute()
            .left(px(position[0]))
            .top(px(position[1])),
        node,
        log,
    )
    .into_any_element()
}
fn attachment(
    child: AnyElement,
    position: [f32; 2],
    mode: AnchoredPositionMode,
    margin: f32,
) -> Anchored {
    anchored()
        .anchor(Anchor::TopLeft)
        .position_mode(mode)
        .position(point(px(position[0]), px(position[1])))
        .snap_to_window_with_margin(px(margin))
        .child(child)
}
fn outer_subtree(
    layer: &Layer,
    case: &Scenario,
    priority: usize,
    reference_height: f32,
    log: &SharedLog,
) -> AnyElement {
    let root_id = format!("{}.root", layer.id);
    let reference_id = format!("{}.reference", layer.id);
    let nested_root = format!("{}.nested.root", layer.id);
    let nested_anchor = format!("{}.nested.anchor", layer.id);
    let nested_deferred = format!("{}.nested.deferred", layer.id);
    let child =
        observed(box_node(&nested_root, case.nested_size), &nested_root, log).into_any_element();
    let mode = if layer.nested_mode == "Window" {
        AnchoredPositionMode::Window
    } else {
        AnchoredPositionMode::Local
    };
    let root = box_node(&root_id, case.outer_size)
        .child(sentinel(&format!("{}.before", layer.id), [0., 0.], log))
        // Genuine ordinary flow layout establishes the nested anchor's static reference.
        .child(observed(
            box_node(&reference_id, [case.reference_size[0], reference_height]),
            &reference_id,
            log,
        ))
        .child(observed(
            deferred(observed(
                attachment(child, layer.nested_position, mode, case.margin),
                &nested_anchor,
                log,
            ))
            .with_priority(priority),
            &nested_deferred,
            log,
        ))
        .child(sentinel(&format!("{}.after", layer.id), [16., 8.], log));
    observed(root, &root_id, log).into_any_element()
}
struct Probe {
    scenario: Scenario,
    stage: String,
    log: SharedLog,
}
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let case = &self.scenario;
        let movement = if self.stage == "moved" {
            case.ancestor_movement
        } else {
            [0., 0.]
        };
        let reference_height = if self.stage == "reference-height" {
            case.updated_nested_reference_height
        } else {
            case.reference_size[1]
        };
        let priorities = match self.stage.as_str() {
            "child-lower" => [2, 0, 3, 1],
            "all-equal" => [1, 1, 1, 1],
            _ => [
                case.layers[0].priority,
                case.layers[0].nested_priority,
                case.layers[1].priority,
                case.layers[1].nested_priority,
            ],
        };
        self.log.borrow_mut().priorities = priorities;
        let mut ancestor = div()
            .block()
            .absolute()
            .left(px(case.ancestor_origin[0] + movement[0]))
            .top(px(case.ancestor_origin[1] + movement[1]))
            .w(px(case.ancestor_size[0]))
            .h(px(case.ancestor_size[1]))
            .child(sentinel("ordinary.before", [0., 0.], &self.log))
            .child(observed(
                box_node("ordinary.reference", case.reference_size),
                "ordinary.reference",
                &self.log,
            ));
        // Structural iteration only. Upstream owns scheduling, fitting and all rounding.
        for (ix, layer) in case.layers.iter().enumerate() {
            let anchor_id = format!("{}.anchor", layer.id);
            let deferred_id = format!("{}.deferred", layer.id);
            let child = outer_subtree(
                layer,
                case,
                priorities[ix * 2 + 1],
                reference_height,
                &self.log,
            );
            ancestor = ancestor.child(observed(
                deferred(observed(
                    attachment(
                        child,
                        layer.position,
                        AnchoredPositionMode::Local,
                        case.margin,
                    ),
                    &anchor_id,
                    &self.log,
                ))
                .with_priority(priorities[ix * 2]),
                &deferred_id,
                &self.log,
            ));
        }
        observed(
            div().block().relative().size_full().child(observed(
                ancestor.child(sentinel("ordinary.after", [8., 8.], &self.log)),
                "$ancestor",
                &self.log,
            )),
            "$host",
            &self.log,
        )
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
        priorities: [2, 3, 1, 3],
    }));
    operation_start(&log, "initial", json!({"action": "open_window"}));
    let handle = app.open_window(
        size(px(scenario.window[0]), px(scenario.window[1])),
        |_, _| Probe {
            scenario: scenario.clone(),
            stage: "initial".into(),
            log: log.clone(),
        },
    );
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    for stage in [
        "scale1",
        "scale1.25",
        "child-lower",
        "all-equal",
        "moved",
        "reference-height",
        "restored",
    ] {
        let input = match stage {
            "scale1" => json!({"action": "set_scale_factor", "scale_factor": 1}),
            "scale1.25" => json!({"action": "set_scale_factor", "scale_factor": 1.25}),
            "child-lower" => json!({"action": "set_priorities", "priorities": [2, 0, 3, 1]}),
            "all-equal" => json!({"action": "set_priorities", "priorities": [1, 1, 1, 1]}),
            "moved" => {
                json!({"action": "restore_priorities_and_move_ancestor", "delta": scenario.ancestor_movement})
            }
            "reference-height" => {
                json!({"action": "restore_ancestor_and_set_nested_reference_height", "height": scenario.updated_nested_reference_height})
            }
            _ => json!({"action": "restore_original_state"}),
        };
        operation_start(&log, stage, input);
        if stage == "scale1" {
            cx.simulate_scale_factor_change(1.);
        }
        if stage == "scale1.25" {
            cx.simulate_scale_factor_change(1.25);
        }
        handle.update(&mut cx, |probe, _, cx| {
            probe.stage = stage.into();
            cx.notify();
        })?;
        cx.run_until_parked();
        operation_end(&log, &mut cx);
    }
    Ok(json!({"id": scenario.id, "events": log.borrow().events.clone()}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err(
            "usage: gpui-nested-deferred-fitting-diagnostic SCENARIOS_JSON RUN_TOKEN".into(),
        );
    }
    let input: Value = serde_json::from_slice(&std::fs::read(&arguments[1])?)?;
    if input["schema_version"] != 1 {
        return Err("unsupported schema".into());
    }
    let scenarios: Vec<Scenario> = serde_json::from_value(input["cases"].clone())?;
    if scenarios.iter().any(|case| {
        case.anchor != "TopLeft"
            || case.layers.len() != 2
            || case
                .layers
                .iter()
                .any(|layer| layer.nested_mode != "Local" && layer.nested_mode != "Window")
    }) {
        return Err("only TopLeft anchors are qualified".into());
    }
    let cases = scenarios
        .iter()
        .map(observe)
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        serde_json::to_string(&json!({"schema_version": 1,
        "layer": "supplemental-headless-nested-deferred-fitting", "fixture": "font-free-two-level-nested-deferred-fitting-rounding",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": UPSTREAM,
        "run_token": arguments[2], "input": input, "cases": cases}))?
    );
    Ok(())
}
