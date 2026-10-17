//! Source-derived fixture. All delivery and state transitions run in actual GPUI.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};
const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Step {
    id: String,
    kind: String,
    point: [f32; 2],
    button: String,
}
#[derive(Default)]
struct Log {
    events: Vec<Value>,
    operation: String,
    frame: usize,
}
type SharedLog = Rc<RefCell<Log>>;
fn record(log: &SharedLog, event: Value) {
    let mut log = log.borrow_mut();
    let row = json!({"sequence": log.events.len(), "operation": log.operation,
        "frame": log.frame, "event": event});
    log.events.push(row);
}
fn bounds_value(bounds: Bounds<Pixels>) -> Value {
    json!([
        f32::from(bounds.origin.x),
        f32::from(bounds.origin.y),
        f32::from(bounds.size.width),
        f32::from(bounds.size.height)
    ])
}
struct Observed<E: Element> {
    inner: E,
    node: &'static str,
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
        if self.node == "host" {
            self.log.borrow_mut().frame += 1;
            record(
                &self.log,
                json!({"type":"frame_start", "scale":window.scale_factor()}),
            );
        }
        self.inner.request_layout(id, inspector, window, cx)
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
            json!({"type":"prepaint", "node":self.node, "bounds":bounds_value(bounds)}),
        );
        self.inner
            .prepaint(id, inspector, bounds, layout, window, cx)
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
            json!({"type":"paint", "node":self.node, "bounds":bounds_value(bounds)}),
        );
        self.inner
            .paint(id, inspector, bounds, layout, prepaint, window, cx);
        if self.node == "host" {
            record(&self.log, json!({"type":"host_paint_return"}));
        }
    }
}
fn observed(element: impl IntoElement, node: &'static str, log: &SharedLog) -> impl IntoElement {
    Observed {
        inner: element.into_element(),
        node,
        log: log.clone(),
    }
}
struct Probe {
    open: bool,
    secondary_open: bool,
    log: SharedLog,
}
impl Probe {
    fn callback(&self, name: &str, before: [bool; 2], button: Option<MouseButton>) {
        record(
            &self.log,
            json!({"type":"callback", "name":name, "before":before,
            "after":[self.open,self.secondary_open], "button":button.map(|button|format!("{button:?}"))}),
        );
    }
}
impl Render for Probe {
    fn render(&mut self, _window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        record(
            &self.log,
            json!({"type":"render", "state":[self.open,self.secondary_open],
            "parent_outside_registered":self.open && !self.secondary_open,
            "child_outside_registered":self.open && self.secondary_open}),
        );
        let child_button = div()
            .id("secondary-btn")
            .absolute()
            .left(px(16.))
            .top(px(16.))
            .w(px(64.))
            .h(px(24.))
            .bg(rgb(0x447744))
            .on_click(cx.listener(|this, _, _, cx| {
                let before = [this.open, this.secondary_open];
                this.secondary_open = true;
                this.callback("open_child", before, None);
                cx.notify();
            }))
            .when(self.secondary_open, |button| {
                button.child(
                    deferred(
                        anchored()
                            .anchor(Anchor::TopLeft)
                            .position(point(px(160.), px(130.)))
                            .snap_to_window_with_margin(px(8.))
                            .child(observed(
                                div()
                                    .w(px(100.))
                                    .h(px(60.))
                                    .bg(rgb(0xeeeeff))
                                    .on_mouse_down_out(cx.listener(
                                        |this, event: &MouseDownEvent, _, cx| {
                                            let before = [this.open, this.secondary_open];
                                            this.secondary_open = false;
                                            this.callback(
                                                "dismiss_child",
                                                before,
                                                Some(event.button),
                                            );
                                            cx.notify();
                                        },
                                    )),
                                "child",
                                &self.log,
                            )),
                    )
                    .priority(2),
                )
            });
        let parent = div()
            .relative()
            .w(px(180.))
            .h(px(110.))
            .bg(rgb(0xeeeeee))
            .when(!self.secondary_open, |parent| {
                parent.on_mouse_down_out(cx.listener(|this, event: &MouseDownEvent, _, cx| {
                    let before = [this.open, this.secondary_open];
                    this.open = false;
                    this.callback("dismiss_parent", before, Some(event.button));
                    cx.notify();
                }))
            })
            .child(observed(child_button, "child_trigger", &self.log));
        let trigger = div()
            .id("popover1")
            .absolute()
            .left(px(20.))
            .top(px(20.))
            .w(px(60.))
            .h(px(24.))
            .bg(rgb(0x444444))
            .on_click(cx.listener(|this, _, _, cx| {
                let before = [this.open, this.secondary_open];
                this.open = true;
                this.callback("open_parent", before, None);
                cx.notify();
            }))
            .when(self.open, |trigger| {
                trigger.child(
                    deferred(
                        anchored()
                            .anchor(Anchor::TopLeft)
                            .position(point(px(60.), px(70.)))
                            .snap_to_window_with_margin(px(8.))
                            .child(observed(parent, "parent", &self.log)),
                    )
                    .priority(1),
                )
            });
        observed(
            div()
                .relative()
                .size_full()
                .child(observed(trigger, "parent_trigger", &self.log)),
            "host",
            &self.log,
        )
    }
}
fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err("usage: gpui-popover-outside-diagnostic SCENARIOS_JSON RUN_TOKEN".into());
    }
    let input: Value = serde_json::from_slice(&std::fs::read(&arguments[1])?)?;
    if input["schema_version"] != 1 {
        return Err("unsupported schema".into());
    }
    let steps: Vec<Step> = serde_json::from_value(input["steps"].clone())?;
    for step in &steps {
        if !matches!(step.kind.as_str(), "down" | "up")
            || !matches!(step.button.as_str(), "left" | "right")
            || !step.point.iter().all(|v| v.is_finite())
        {
            return Err("unsupported pointer operation".into());
        }
    }
    let mut app = TestAppContext::single();
    let log = Rc::new(RefCell::new(Log {
        operation: "initial".into(),
        ..Default::default()
    }));
    record(
        &log,
        json!({"type":"operation_start","input":{"kind":"open_window"}}),
    );
    let handle = app.open_window(size(px(320.), px(240.)), |_, _| Probe {
        open: false,
        secondary_open: false,
        log: log.clone(),
    });
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    let state = handle.update(&mut cx, |probe, _, _| [probe.open, probe.secondary_open])?;
    record(&log, json!({"type":"operation_end","state":state}));
    for step in steps {
        log.borrow_mut().operation = step.id.clone();
        record(
            &log,
            json!({"type":"operation_start","input":{"kind":step.kind,"point":step.point,"button":step.button}}),
        );
        let position = point(px(step.point[0]), px(step.point[1]));
        let button = if step.button == "left" {
            MouseButton::Left
        } else {
            MouseButton::Right
        };
        if step.kind == "down" {
            cx.simulate_mouse_down(position, button, Modifiers::default());
        } else {
            cx.simulate_mouse_up(position, button, Modifiers::default());
        }
        cx.run_until_parked();
        let state = handle.update(&mut cx, |probe, _, _| [probe.open, probe.secondary_open])?;
        record(&log, json!({"type":"operation_end","state":state}));
    }
    println!(
        "{}",
        serde_json::to_string(&json!({"schema_version":1,
        "layer":"supplemental-headless-popover-outside", "fixture":"source-derived-font-free-two-level-popover",
        "upstream_revision":UPSTREAM,"run_token":arguments[2],"input":input,
        "events":log.borrow().events}))?
    );
    Ok(())
}
