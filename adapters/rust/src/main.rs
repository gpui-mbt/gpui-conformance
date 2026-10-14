use gpui::{prelude::*, *};
use serde_json::{Value, json};
use std::{cell::RefCell, rc::Rc};

type Trace = Rc<RefCell<Vec<Value>>>;
struct View { scenario: Value, trace: Trace, focus: FocusHandle }
fn n(v: &Value) -> f32 { v.as_f64().expect("scenario number") as f32 }
fn b(v: &Value) -> bool { v.as_bool().expect("scenario bool") }
fn rect(v: &Value) -> Bounds<Pixels> {
    Bounds::new(point(px(n(&v[0])), px(n(&v[1]))), size(px(n(&v[2])), px(n(&v[3]))))
}
fn bounds(v: Bounds<Pixels>) -> Value {
    json!([f32::from(v.origin.x), f32::from(v.origin.y), f32::from(v.size.width), f32::from(v.size.height)])
}
impl Render for View {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let key_trace = self.trace.clone();
        let mut root = div().id("root").debug_selector(|| "root".into())
            .track_focus(&self.focus).flex().flex_row().items_start()
            .w_full().h_full().gap(px(n(&self.scenario["gap"])))
            .on_key_down(move |event, _, _| {
                let k = &event.keystroke;
                key_trace.borrow_mut().push(json!([k.key, k.modifiers.shift,
                    k.modifiers.control, k.modifiers.alt, k.modifiers.platform, event.is_held]));
            });
        for (i, dimensions) in self.scenario["children"].as_array().unwrap().iter().enumerate() {
            let trace = self.trace.clone();
            let child = div().id(i + 2).debug_selector(move || if i == 0 { "a" } else { "b" }.into())
                .w(px(n(&dimensions[0]))).h(px(n(&dimensions[1]))).min_w(px(0.))
                .flex_shrink(1.).bg(rgb(0x204060))
                .on_mouse_down(MouseButton::Left, move |_, _, _| trace.borrow_mut().push(json!(i + 2)));
            root = root.child(child);
        }
        root
    }
}
fn observe(s: &Value) -> Value {
    let kind = s["kind"].as_str().unwrap();
    let mut result = json!({"id":s["id"], "layer":s["layer"], "status":"observed"});
    if kind == "pixels" || kind == "ime" {
        result["status"] = json!(if kind == "ime" { "unsupported" } else { "unverified" });
        result["reason"] = json!(if kind == "ime" { "IME composition is outside this first slice" } else { "No native GPU capture was executed" });
        return result;
    }
    let mut app = TestAppContext::single();
    let trace: Trace = Rc::new(RefCell::new(Vec::new()));
    let view_scenario = if kind == "window" || kind == "clip" {
        json!({"gap":0,"children":[[20,30],[25,40]]})
    } else { s.clone() };
    // Real GPUI Render path. TestPlatform creates no NSWindow.
    let handle = app.open_window(size(px(n(&s["width"])), px(n(&s["height"]))), |window, cx| {
        let focus = cx.focus_handle();
        window.focus(&focus, cx);
        View { scenario: view_scenario, trace: trace.clone(), focus }
    });
    let mut cx = VisualTestContext::from_window(*handle, &app);
    cx.run_until_parked();
    match kind {
        "layout" => {
            let observed: Vec<_> = ["root", "a", "b"].iter().map(|selector| bounds(cx.debug_bounds(selector).expect("drawn selector"))).collect();
            result["observation"] = json!({"bounds":observed});
        }
        "pointer" => {
            let mut hits = Vec::new();
            for p in s["points"].as_array().unwrap() {
                trace.borrow_mut().clear();
                cx.simulate_mouse_down(point(px(n(&p[0])), px(n(&p[1]))), MouseButton::Left, Modifiers::default());
                hits.push(trace.borrow().first().cloned().unwrap_or(Value::Null));
            }
            result["observation"] = json!({"targets":hits});
        }
        "key" => {
            trace.borrow_mut().clear();
            for k in s["keys"].as_array().unwrap() {
                cx.simulate_event(KeyDownEvent {
                    keystroke: Keystroke { key:k[0].as_str().unwrap().into(), key_char:None,
                        modifiers:Modifiers { shift:b(&k[1]), control:b(&k[2]), alt:b(&k[3]), platform:b(&k[4]), function:false } },
                    is_held:b(&k[5]), prefer_character_input:false,
                });
            }
            result["observation"] = json!({"keys":*trace.borrow()});
        }
        "clip" => {
            let masks: Vec<_> = s["clips"].as_array().unwrap().iter().map(|v| ContentMask{bounds:rect(v)}).collect();
            let sample = Rc::new(RefCell::new(Value::Null));
            let captured = sample.clone();
            cx.draw(point(px(0.),px(0.)), size(px(n(&s["width"])),px(n(&s["height"]))), move |_, _| {
                canvas(move |_, window, _| {
                    window.with_content_mask(Some(masks[0].clone()), |window| {
                        window.with_content_mask(Some(masks[1].clone()), |window| {
                            *captured.borrow_mut() = bounds(window.content_mask().bounds);
                        });
                    });
                }, |_, _, _, _| {}).size_full()
            });
            result["observation"] = json!({"effective_clip":*sample.borrow()});
        }
        "window" => {
            let initial = cx.update(|window, _| bounds(window.bounds()));
            let count = app.windows().len();
            cx.simulate_resize(size(px(n(&s["resize"][0])), px(n(&s["resize"][1]))));
            cx.run_until_parked();
            let resized = cx.update(|window, _| bounds(window.bounds()));
            cx.update(|window, _| window.remove_window());
            cx.run_until_parked();
            result["layer"] = json!("headless-window");
            result["observation"] = json!({"initial":initial,"resized":resized,"count_before":count,"count_after":app.windows().len()});
        }
        _ => panic!("unknown scenario kind"),
    }
    result
}
fn main() {
    let scenarios: Value = serde_json::from_str(&std::env::var("GPUI_SCENARIOS").expect("shared scenarios")).unwrap();
    let cases: Vec<_> = scenarios["cases"].as_array().unwrap().iter().map(observe).collect();
    println!("GPUI_CONFORMANCE {}", json!({"implementation":"upstream", "run_token":std::env::var("GPUI_RUN_TOKEN").unwrap(), "cases":cases}));
}
