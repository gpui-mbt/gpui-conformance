//! Original bounded event/focus probes using actual GPUI listener dispatch.
use super::{Trace, n};
use gpui::{prelude::*, *};
use serde_json::{Value, json};
use std::{cell::RefCell, rc::Rc};

fn record(trace: &Trace, id: usize, phase: &str, stop: &Value, cx: &mut App) {
    trace.borrow_mut().push(json!([id, phase]));
    if *stop == json!([id, phase]) {
        cx.stop_propagation();
    }
}

fn node(id: usize, focus: &FocusHandle, trace: Trace, stop: &Value) -> Stateful<Div> {
    let capture = trace.clone();
    let bubble = trace.clone();
    let key_capture = trace.clone();
    let key_bubble = trace.clone();
    let up_capture = trace.clone();
    let stops = [
        stop.clone(),
        stop.clone(),
        stop.clone(),
        stop.clone(),
        stop.clone(),
        stop.clone(),
    ];
    let [s0, s1, s2, s3, s4, s5] = stops;
    div()
        .id(id)
        .track_focus(focus)
        .capture_any_mouse_down(move |_, _, cx| record(&capture, id, "capture", &s0, cx))
        .on_mouse_down(MouseButton::Left, move |_, _, cx| {
            record(&bubble, id, "bubble", &s1, cx)
        })
        .capture_key_down(move |_, _, cx| record(&key_capture, id, "capture", &s2, cx))
        .on_key_down(move |_, _, cx| record(&key_bubble, id, "bubble", &s3, cx))
        .capture_key_up(move |_, _, cx| record(&up_capture, id, "capture", &s4, cx))
        .on_key_up(move |_, _, cx| record(&trace, id, "bubble", &s5, cx))
}

struct RoutingView {
    scenario: Value,
    trace: Trace,
    focus: Vec<FocusHandle>,
}
impl Render for RoutingView {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let mut root = node(
            1,
            &self.focus[0],
            self.trace.clone(),
            &self.scenario["stop"],
        )
        .flex()
        .flex_row()
        .items_start()
        .w_full()
        .h_full()
        .gap(px(n(&self.scenario["gap"])));
        for (i, dimensions) in self.scenario["children"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            root = root.child(
                node(
                    i + 2,
                    &self.focus[i + 1],
                    self.trace.clone(),
                    &self.scenario["stop"],
                )
                .w(px(n(&dimensions[0])))
                .h(px(n(&dimensions[1])))
                .min_w(px(0.))
                .flex_shrink(1.),
            );
        }
        root
    }
}

pub fn observe(s: &Value) -> Value {
    let mut app = TestAppContext::single();
    let trace: Trace = Rc::new(RefCell::new(Vec::new()));
    let handles = Rc::new(RefCell::new(Vec::<FocusHandle>::new()));
    let copy = handles.clone();
    let handle = app.open_window(size(px(n(&s["width"])), px(n(&s["height"]))), |_, cx| {
        let focus: Vec<_> = (0..3).map(|_| cx.focus_handle()).collect();
        *copy.borrow_mut() = focus.clone();
        RoutingView {
            scenario: s.clone(),
            trace: trace.clone(),
            focus,
        }
    });
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    let observation = if s["kind"] == "route" {
        let mut events = Vec::new();
        for p in s["points"].as_array().unwrap() {
            trace.borrow_mut().clear();
            cx.simulate_mouse_down(
                point(px(n(&p[0])), px(n(&p[1]))),
                MouseButton::Left,
                Modifiers::default(),
            );
            events.push(json!(*trace.borrow()));
        }
        json!({"events":events})
    } else {
        let mut steps = Vec::new();
        for desired in s["focuses"].as_array().unwrap() {
            cx.update(|window, app| {
                if desired.is_null() {
                    window.blur(app);
                } else {
                    window.focus(
                        &handles.borrow()[desired.as_u64().unwrap() as usize - 1],
                        app,
                    );
                }
            });
            cx.run_until_parked();
            let actual = cx.update(|window, app| {
                window
                    .focused(app)
                    .and_then(|current| handles.borrow().iter().position(|h| *h == current))
                    .map(|i| i + 1)
            });
            trace.borrow_mut().clear();
            let keystroke = Keystroke {
                key: s["key"].as_str().unwrap().into(),
                key_char: None,
                modifiers: Modifiers::default(),
            };
            if s["event"] == "up" {
                cx.simulate_event(KeyUpEvent { keystroke });
            } else {
                cx.simulate_event(KeyDownEvent {
                    keystroke,
                    is_held: false,
                    prefer_character_input: false,
                });
            }
            steps.push(json!({"focused":actual,"events":*trace.borrow()}));
        }
        json!({"steps":steps})
    };
    json!({"id":s["id"],"layer":s["layer"],"status":"observed","observation":observation})
}
