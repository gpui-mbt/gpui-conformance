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
}
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    window: [f32; 2],
    scale_factor: f32,
    ancestor_origin: [f32; 2],
    ancestor_size: [f32; 2],
    ancestor_movement: [f32; 2],
    anchor: String,
    margin: f32,
    outer_size: [f32; 2],
    nested_size: [f32; 2],
    nested_position: [f32; 2],
    layers: Vec<Layer>,
    update_layer: String,
    update_priority: usize,
    remove_nested: String,
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
fn attachment(child: AnyElement, position: [f32; 2], margin: f32) -> Anchored {
    anchored()
        .anchor(Anchor::TopLeft)
        .position_mode(AnchoredPositionMode::Local)
        .position(point(px(position[0]), px(position[1])))
        .snap_to_window_with_margin(px(margin))
        .child(child)
}
fn outer_subtree(layer: &Layer, case: &Scenario, removed: bool, log: &SharedLog) -> AnyElement {
    let root_id = format!("{}.root", layer.id);
    let mut root = box_node(&root_id, case.outer_size).child(sentinel(
        &format!("{}.before", layer.id),
        [0., 0.],
        log,
    ));
    if !removed || layer.id != case.remove_nested {
        let nested_root = format!("{}.nested.root", layer.id);
        let nested_anchor = format!("{}.nested.anchor", layer.id);
        let nested_deferred = format!("{}.nested.deferred", layer.id);
        let child = observed(box_node(&nested_root, case.nested_size), &nested_root, log)
            .into_any_element();
        root = root.child(observed(
            deferred(observed(
                attachment(child, case.nested_position, case.margin),
                &nested_anchor,
                log,
            ))
            .with_priority(layer.nested_priority),
            &nested_deferred,
            log,
        ));
    }
    observed(
        root.child(sentinel(&format!("{}.after", layer.id), [16., 8.], log)),
        &root_id,
        log,
    )
    .into_any_element()
}
struct Probe {
    scenario: Scenario,
    removed: bool,
    updated: bool,
    moved: bool,
    log: SharedLog,
}
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let case = &self.scenario;
        let movement = if self.moved {
            case.ancestor_movement
        } else {
            [0., 0.]
        };
        let mut ancestor = div()
            .absolute()
            .left(px(case.ancestor_origin[0] + movement[0]))
            .top(px(case.ancestor_origin[1] + movement[1]))
            .w(px(case.ancestor_size[0]))
            .h(px(case.ancestor_size[1]))
            .child(sentinel("ordinary.before", [0., 0.], &self.log));
        // Structural iteration only. Upstream owns all discovery and paint scheduling.
        for layer in &case.layers {
            let priority = if self.updated && layer.id == case.update_layer {
                case.update_priority
            } else {
                layer.priority
            };
            let anchor_id = format!("{}.anchor", layer.id);
            let deferred_id = format!("{}.deferred", layer.id);
            let child = outer_subtree(layer, case, self.removed, &self.log);
            ancestor = ancestor.child(observed(
                deferred(observed(
                    attachment(child, layer.position, case.margin),
                    &anchor_id,
                    &self.log,
                ))
                .with_priority(priority),
                &deferred_id,
                &self.log,
            ));
        }
        observed(
            div().relative().size_full().child(observed(
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
    }));
    operation_start(&log, "initial", json!({"action": "open_window"}));
    let handle = app.open_window(
        size(px(scenario.window[0]), px(scenario.window[1])),
        |_, _| Probe {
            scenario: scenario.clone(),
            removed: false,
            updated: false,
            moved: false,
            log: log.clone(),
        },
    );
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    operation_end(&log, &mut cx);
    for stage in ["base", "updated", "removed", "restored", "moved"] {
        let input = match stage {
            "base" => json!({"action": "set_scale_factor", "scale_factor": scenario.scale_factor}),
            "updated" => {
                json!({"action": "set_parent_priority", "layer": scenario.update_layer, "priority": scenario.update_priority})
            }
            "removed" => json!({"action": "remove_nested_child", "layer": scenario.remove_nested}),
            "restored" => json!({"action": "restore_original_tree"}),
            _ => json!({"action": "move_ancestor", "delta": scenario.ancestor_movement}),
        };
        operation_start(&log, stage, input);
        if stage == "base" {
            cx.simulate_scale_factor_change(scenario.scale_factor);
        }
        handle.update(&mut cx, |probe, _, cx| {
            probe.updated = stage == "updated" || stage == "removed";
            probe.removed = stage == "removed";
            probe.moved = stage == "moved";
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
        return Err("usage: gpui-nested-deferred-diagnostic SCENARIOS_JSON RUN_TOKEN".into());
    }
    let input: Value = serde_json::from_slice(&std::fs::read(&arguments[1])?)?;
    if input["schema_version"] != 1 {
        return Err("unsupported schema".into());
    }
    let scenarios: Vec<Scenario> = serde_json::from_value(input["cases"].clone())?;
    if scenarios.iter().any(|case| case.anchor != "TopLeft") {
        return Err("only TopLeft anchors are qualified".into());
    }
    let cases = scenarios
        .iter()
        .map(observe)
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        serde_json::to_string(&json!({"schema_version": 1,
        "layer": "supplemental-headless-nested-deferred", "fixture": "font-free-two-level-nested-deferred",
        "text_system": "NoopTextSystem; no text used", "upstream_revision": UPSTREAM,
        "run_token": arguments[2], "input": input, "cases": cases}))?
    );
    Ok(())
}
