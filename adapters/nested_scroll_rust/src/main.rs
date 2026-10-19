use gpui::{prelude::*, *};
use serde_json::{Value, json};
use std::{cell::RefCell, rc::Rc};
type Hits = Rc<RefCell<Vec<u64>>>;
fn block(id: u64, w: f32, h: f32, hits: &Hits) -> Stateful<Div> {
    let hits = hits.clone();
    div()
        .id(id)
        .debug_selector(move || id.to_string().into())
        .w(px(w))
        .h(px(h))
        .flex_shrink_0()
        .flex()
        .flex_col()
        .items_start()
        .on_mouse_down(MouseButton::Left, move |_, _, _| hits.borrow_mut().push(id))
}
struct Probe {
    outer: ScrollHandle,
    inner: ScrollHandle,
    hits: Hits,
}
impl Render for Probe {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().size_full().flex().flex_col().items_start().child(
            block(2, 160., 120., &self.hits)
                .overflow_scroll()
                .track_scroll(&self.outer)
                .child(
                    block(3, 320., 360., &self.hits)
                        .child(
                            block(4, 160., 60., &self.hits)
                                .overflow_scroll()
                                .track_scroll(&self.inner)
                                .child(block(5, 320., 60., &self.hits)),
                        )
                        .child(block(6, 320., 300., &self.hits)),
                ),
        )
    }
}
fn number(v: &Value) -> f32 {
    v.as_f64().expect("finite fixture number") as f32
}
fn point_json(p: Point<Pixels>) -> Value {
    json!([f32::from(p.x), f32::from(p.y)])
}
fn main() {
    let input: Value = serde_json::from_str(&std::env::var("SCROLL_SCENARIOS").unwrap()).unwrap();
    let mut cases = Vec::new();
    for case in input["cases"].as_array().unwrap() {
        let hits = Rc::new(RefCell::new(Vec::new()));
        let outer = ScrollHandle::new();
        let inner = ScrollHandle::new();
        let mut app = TestAppContext::single();
        let handle = app.open_window(size(px(240.), px(180.)), |_, _| Probe {
            outer: outer.clone(),
            inner: inner.clone(),
            hits: hits.clone(),
        });
        let mut cx = VisualTestContext::from_window(*handle, &app);
        cx.run_until_parked();
        let mut frames = Vec::new();
        for step in std::iter::once(None).chain(case["wheels"].as_array().unwrap().iter().map(Some))
        {
            if let Some(step) = step {
                cx.simulate_event(ScrollWheelEvent {
                    position: point(px(number(&step[0])), px(number(&step[1]))),
                    delta: ScrollDelta::Pixels(point(px(number(&step[2])), px(number(&step[3])))),
                    modifiers: Modifiers::default(),
                    touch_phase: TouchPhase::Moved,
                });
                cx.run_until_parked();
            }
            let bounds = (2..=6)
                .map(|id| {
                    let selector = match id {
                        2 => "2",
                        3 => "3",
                        4 => "4",
                        5 => "5",
                        _ => "6",
                    };
                    let b = cx.debug_bounds(selector).expect("drawn bounds");
                    json!([
                        id,
                        [
                            f32::from(b.origin.x),
                            f32::from(b.origin.y),
                            f32::from(b.size.width),
                            f32::from(b.size.height)
                        ]
                    ])
                })
                .collect::<Vec<_>>();
            let targets = input["points"]
                .as_array()
                .unwrap()
                .iter()
                .map(|p| {
                    hits.borrow_mut().clear();
                    cx.simulate_mouse_down(
                        point(px(number(&p[0])), px(number(&p[1]))),
                        MouseButton::Left,
                        Modifiers::default(),
                    );
                    let target = hits.borrow().first().copied();
                    cx.simulate_mouse_up(
                        point(px(number(&p[0])), px(number(&p[1]))),
                        MouseButton::Left,
                        Modifiers::default(),
                    );
                    target
                })
                .collect::<Vec<_>>();
            frames.push(json!({"offsets":[point_json(outer.offset()),point_json(inner.offset())],
                "maximums":[point_json(outer.max_offset()),point_json(inner.max_offset())],"bounds":bounds,"targets":targets}));
        }
        cases.push(json!({"id":case["id"],"frames":frames}));
        cx.update(|window, _| window.remove_window());
        cx.run_until_parked();
    }
    println!(
        "{}",
        json!({"schema_version":1,"backend":"rust-gpui","input":input,"cases":cases})
    );
}
