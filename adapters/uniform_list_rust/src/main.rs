use gpui::{prelude::*, *};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{cell::RefCell, error::Error, rc::Rc};

const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Configuration {
    window: [f32; 2],
    list: [f32; 4],
    count: usize,
    inner_height: f32,
}

#[derive(Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct Scenario {
    id: String,
    initial: Configuration,
    operations: Vec<Operation>,
}

#[derive(Clone, Deserialize, Serialize)]
struct Operation {
    id: String,
    #[serde(flatten)]
    action: Action,
}

#[derive(Clone, Copy, Deserialize, Serialize)]
#[serde(tag = "action", rename_all = "snake_case")]
enum Action {
    SetOffset { y: f32 },
    SetCount { count: usize },
    SetInnerHeight { height: f32 },
    ResizeList { height: f32 },
    ResizeWindow { size: [f32; 2] },
    Wheel { position: [f32; 2], delta: [f32; 2] },
    Move { position: [f32; 2], held: bool },
    Down { position: [f32; 2] },
    Up { position: [f32; 2] },
}

struct Log {
    events: Vec<Value>,
    operation: String,
    frame: usize,
    factory: usize,
    configuration: Configuration,
}

type SharedLog = Rc<RefCell<Log>>;

fn record(log: &SharedLog, event: Value) {
    let mut log = log.borrow_mut();
    let sequence = log.events.len();
    let frame = log.frame;
    let operation = log.operation.clone();
    log.events.push(json!({
        "sequence": sequence, "operation": operation, "frame": frame, "event": event
    }));
}

fn point_value(value: Point<Pixels>) -> Value {
    json!([f32::from(value.x), f32::from(value.y)])
}

fn size_value(value: Size<Pixels>) -> Value {
    json!([f32::from(value.width), f32::from(value.height)])
}

fn bounds_value(value: Bounds<Pixels>) -> Value {
    json!([
        f32::from(value.origin.x),
        f32::from(value.origin.y),
        f32::from(value.size.width),
        f32::from(value.size.height)
    ])
}

fn position(value: [f32; 2]) -> Point<Pixels> {
    point(px(value[0]), px(value[1]))
}

fn scroll_value(handle: &UniformListScrollHandle) -> Value {
    let state = handle.0.borrow();
    json!({
        "offset": point_value(state.base_handle.offset()),
        "max_offset": point_value(state.base_handle.max_offset()),
        "last_item_size": state.last_item_size.map(|value| json!({
            "item": size_value(value.item), "contents": size_value(value.contents)
        }))
    })
}

// Delegate the element lifecycle unchanged; the observer never computes a row's layout or hitbox.
struct Observed<E: Element> {
    inner: E,
    kind: &'static str,
    item: Option<usize>,
    factory: Option<usize>,
    log: SharedLog,
    root_scroll: Option<UniformListScrollHandle>,
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
        if self.root_scroll.is_some() {
            self.log.borrow_mut().frame += 1;
            let configuration = self.log.borrow().configuration.clone();
            record(
                &self.log,
                json!({"type": "frame_start", "configuration": configuration}),
            );
        }
        record(
            &self.log,
            json!({"type": "request_layout", "kind": self.kind,
            "item_id": self.item, "factory_call": self.factory}),
        );
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
            json!({"type": "prepaint", "kind": self.kind,
            "item_id": self.item, "factory_call": self.factory,
            "bounds": bounds_value(bounds), "content_mask": bounds_value(window.content_mask().bounds)}),
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
        self.inner
            .paint(id, inspector, bounds, layout, prepaint, window, cx);
        if let Some(handle) = &self.root_scroll {
            record(
                &self.log,
                json!({"type": "frame_end", "scroll": scroll_value(handle),
                "window_size": size_value(window.viewport_size()), "scale_factor": window.scale_factor()}),
            );
        }
    }
}

fn observed<E: Element>(
    inner: E,
    kind: &'static str,
    item: Option<usize>,
    factory: Option<usize>,
    log: &SharedLog,
) -> Observed<E> {
    Observed {
        inner,
        kind,
        item,
        factory,
        log: log.clone(),
        root_scroll: None,
    }
}

struct Probe {
    log: SharedLog,
    scroll: UniformListScrollHandle,
}

impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        record(&self.log, json!({"type": "view_render"}));
        let configuration = self.log.borrow().configuration.clone();
        let log = self.log.clone();
        let inner_height = configuration.inner_height;
        let list = uniform_list("diagnostic-list", configuration.count, move |range, _, _| {
            let factory = {
                let mut log = log.borrow_mut();
                log.factory += 1;
                log.factory
            };
            record(&log, json!({"type": "factory", "factory_call": factory,
                "range": [range.start, range.end]}));
            range.map(|item| {
                record(&log, json!({"type": "constructed", "item_id": item, "factory_call": factory}));
                let click_log = log.clone();
                let child = observed(div().w_full().h(px(inner_height)), "inner", Some(item), Some(factory), &log);
                let row = div().id(item).w_full().child(child).on_click(move |event, _, _| {
                    let detail = match event {
                        ClickEvent::Mouse(mouse) => json!({"kind": "mouse",
                            "down": point_value(mouse.down.position), "up": point_value(mouse.up.position)}),
                        ClickEvent::Keyboard(_) => json!({"kind": "keyboard"}),
                        ClickEvent::Touch(_) => json!({"kind": "touch"}),
                    };
                    record(&click_log, json!({"type": "click", "item_id": item,
                        "factory_call": factory, "detail": detail}));
                });
                observed(row, "row", Some(item), Some(factory), &log)
            }).collect::<Vec<_>>()
        })
        .track_scroll(&self.scroll)
        .debug_selector(|| "diagnostic-list".into())
        .absolute().left(px(configuration.list[0])).top(px(configuration.list[1]))
        .w(px(configuration.list[2])).h(px(configuration.list[3]));
        let root = div()
            .id("diagnostic-root")
            .relative()
            .size_full()
            .child(observed(list, "list", None, None, &self.log));
        let mut root = observed(root, "root", None, None, &self.log);
        root.root_scroll = Some(self.scroll.clone());
        root
    }
}

fn snapshot(log: &SharedLog, scroll: &UniformListScrollHandle, cx: &mut VisualTestContext) {
    let list_bounds = cx.debug_bounds("diagnostic-list").map(bounds_value);
    let configuration = log.borrow().configuration.clone();
    record(
        log,
        json!({"type": "operation_end", "configuration": configuration,
        "scroll": scroll_value(scroll), "list_bounds": list_bounds}),
    );
}

fn observe(scenario: &Scenario) -> Result<Value, Box<dyn Error>> {
    let mut app = TestAppContext::single();
    let log = Rc::new(RefCell::new(Log {
        events: Vec::new(),
        operation: "initial".into(),
        frame: 0,
        factory: 0,
        configuration: scenario.initial.clone(),
    }));
    let scroll = UniformListScrollHandle::new();
    record(
        &log,
        json!({"type": "operation_start", "input": {"id": "initial", "action": "open_window"}}),
    );
    let handle = app.open_window(
        size(
            px(scenario.initial.window[0]),
            px(scenario.initial.window[1]),
        ),
        |_, _| Probe {
            log: log.clone(),
            scroll: scroll.clone(),
        },
    );
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    snapshot(&log, &scroll, &mut cx);
    for operation in &scenario.operations {
        log.borrow_mut().operation = operation.id.clone();
        record(&log, json!({"type": "operation_start", "input": operation}));
        match operation.action {
            Action::SetOffset { y } => {
                scroll
                    .0
                    .borrow()
                    .base_handle
                    .set_offset(point(px(0.), px(-y)));
                handle.update(&mut cx, |_, _, cx| cx.notify())?;
            }
            Action::SetCount { count } => {
                handle.update(&mut cx, |view, _, cx| {
                    view.log.borrow_mut().configuration.count = count;
                    cx.notify();
                })?;
            }
            Action::SetInnerHeight { height } => {
                handle.update(&mut cx, |view, _, cx| {
                    view.log.borrow_mut().configuration.inner_height = height;
                    cx.notify();
                })?;
            }
            Action::ResizeList { height } => {
                handle.update(&mut cx, |view, _, cx| {
                    view.log.borrow_mut().configuration.list[3] = height;
                    cx.notify();
                })?;
            }
            Action::ResizeWindow { size: dimensions } => {
                log.borrow_mut().configuration.window = dimensions;
                cx.simulate_resize(size(px(dimensions[0]), px(dimensions[1])));
            }
            Action::Wheel {
                position: at,
                delta,
            } => cx.simulate_event(ScrollWheelEvent {
                position: position(at),
                delta: ScrollDelta::Pixels(position(delta)),
                modifiers: Modifiers::none(),
                touch_phase: TouchPhase::Moved,
            }),
            Action::Move { position: at, held } => cx.simulate_mouse_move(
                position(at),
                held.then_some(MouseButton::Left),
                Modifiers::none(),
            ),
            Action::Down { position: at } => {
                cx.simulate_mouse_down(position(at), MouseButton::Left, Modifiers::none())
            }
            Action::Up { position: at } => {
                cx.simulate_mouse_up(position(at), MouseButton::Left, Modifiers::none())
            }
        }
        cx.run_until_parked();
        snapshot(&log, &scroll, &mut cx);
    }
    let events = log.borrow().events.clone();
    Ok(json!({"id": scenario.id, "events": events}))
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() != 3 {
        return Err("usage: gpui-uniform-list-diagnostic SCENARIOS_JSON RUN_TOKEN".into());
    }
    let raw_input: Value = serde_json::from_slice(&std::fs::read(&arguments[1])?)?;
    if raw_input["schema_version"] != 1 {
        return Err("unsupported input schema".into());
    }
    let scenarios: Vec<Scenario> = serde_json::from_value(raw_input["cases"].clone())?;
    let observations = scenarios
        .iter()
        .map(observe)
        .collect::<Result<Vec<_>, _>>()?;
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema_version": 1, "layer": "supplemental-headless-core-semantics",
            "fixture": "font-free-nested-auto-height", "text_system": "NoopTextSystem; no text used",
            "upstream_revision": UPSTREAM, "run_token": arguments[2],
            "input": raw_input, "cases": observations
        }))?
    );
    Ok(())
}
