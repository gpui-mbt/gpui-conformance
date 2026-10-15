use gpui::{prelude::*, *};
use serde_json::{Value, json};
use std::time::Duration;

use std::ffi::{CStr, CString, c_char, c_void};
use std::sync::OnceLock;
unsafe extern "C" {
    fn dlopen(path: *const c_char, flags: i32) -> *mut c_void;
    fn dlsym(handle: *mut c_void, symbol: *const c_char) -> *mut c_void;
}
fn fixture_symbol(symbol: &CStr) -> *mut c_void {
    static GUARD: OnceLock<usize> = OnceLock::new();
    let handle = *GUARD.get_or_init(|| {
        let path = CString::new(std::env::var("GPUI_FIXTURE_GUARD").unwrap()).unwrap();
        let handle = unsafe { dlopen(path.as_ptr(), 2) };
        assert!(!handle.is_null(), "owned fixture guard must load");
        handle as usize
    }) as *mut c_void;
    let symbol = unsafe { dlsym(handle, symbol.as_ptr()) };
    assert!(!symbol.is_null(), "fixture guard symbol");
    symbol
}
fn fixture_state(phase: &str) -> Value {
    let symbol = fixture_symbol(c"conformance_fixture_integer");
    let read: unsafe extern "C" fn(i32) -> i64 = unsafe { std::mem::transmute(symbol) };
    unsafe {
        json!({"phase":phase, "pid":read(0), "fixture_frontmost":read(1)==1,
        "application_active":read(2)==1, "owned_titled_windows":read(3),
        "native_window_id":read(4), "window_visible":read(5)==1,
        "window_key":read(6)==1, "activation_policy":read(7)})
    }
}

struct Fixture {
    rect: [f32; 4],
    background: u32,
    color: u32,
}
impl Render for Fixture {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().w_full().h_full().bg(rgb(self.background)).child(
            div()
                .absolute()
                .left(px(self.rect[0]))
                .top(px(self.rect[1]))
                .w(px(self.rect[2]))
                .h(px(self.rect[3]))
                .bg(rgb(self.color)),
        )
    }
}
fn number(v: &Value) -> f32 {
    v.as_f64().unwrap() as f32
}
fn color(v: &Value) -> u32 {
    ((v[0].as_u64().unwrap() as u32) << 16)
        | ((v[1].as_u64().unwrap() as u32) << 8)
        | (v[2].as_u64().unwrap() as u32)
}
fn main() {
    let scenarios: Value = serde_json::from_str(&std::env::var("GPUI_SCENARIOS").unwrap()).unwrap();
    let cases = scenarios["cases"].as_array().unwrap();
    let window_scenario = cases
        .iter()
        .find(|s| s["kind"] == "window")
        .unwrap()
        .clone();
    let pixels = cases
        .iter()
        .find(|s| s["kind"] == "pixels")
        .unwrap()
        .clone();
    let token = std::env::var("GPUI_RUN_TOKEN").unwrap();
    gpui_platform::application().with_windowing(WindowingRequest::Headless).run(move |cx| {
        let dimensions = size(px(number(&window_scenario["width"])), px(number(&window_scenario["height"])));
        let r = pixels["rect"].as_array().unwrap();
        let rect = [number(&r[0]),number(&r[1]),number(&r[2]),number(&r[3])];
        let handle = cx.open_window(WindowOptions {
            window_bounds:Some(WindowBounds::Windowed(Bounds::new(point(px(0.),px(0.)),dimensions))),
            focus:false, show:false, ..Default::default()
        }, |_, cx| cx.new(|_| Fixture{rect,background:color(&pixels["background"]),color:color(&pixels["color"])})).expect("native window");
        let created=fixture_state("created");
        cx.spawn(async move |cx| {
            cx.background_executor().timer(Duration::from_millis(100)).await;
            let (initial, live_before, scale, image) = cx.update_window(*handle, |_, window, cx| {
                let _ = window.draw(cx);
                let viewport=window.viewport_size();
                let image=window.render_to_image().expect("native Metal readback");
                (json!([0,0,f32::from(viewport.width),f32::from(viewport.height)]),
                 cx.windows().contains(&*handle),window.scale_factor(),image)
            }).unwrap();
            let checkpoint: unsafe extern "C" fn() -> i32 = unsafe { std::mem::transmute(fixture_symbol(c"conformance_fixture_checkpoint")) };
            assert_eq!(unsafe { checkpoint() }, 1, "owned observer checkpoint failed or timed out");
            let rendered=fixture_state("rendered");
            let samples: Vec<_> = pixels["points"].as_array().unwrap().iter().map(|p| {
                let x=(number(&p[0])*scale).floor() as u32;
                let y=(number(&p[1])*scale).floor() as u32;
                image.get_pixel(x,y).0
            }).collect();
            cx.update_window(*handle, |_, window, _| window.resize(size(px(number(&window_scenario["resize"][0])),px(number(&window_scenario["resize"][1]))))).unwrap();
            cx.background_executor().timer(Duration::from_millis(150)).await;
            let resized=cx.update_window(*handle, |_, window, _| {
                let viewport=window.viewport_size();
                json!([0,0,f32::from(viewport.width),f32::from(viewport.height)])
            }).unwrap();
            let resized_state=fixture_state("resized");
            cx.update_window(*handle, |_, window, _| window.remove_window()).unwrap();
            let live_after=cx.update(|cx| cx.windows().contains(&*handle));
            cx.background_executor().timer(Duration::from_millis(150)).await;
            let closed=fixture_state("closed");
            let rows=json!([
                {"id":window_scenario["id"],"layer":"native-window","status":"observed",
                 "observation":{"initial":initial,"resized":resized,"live_before":live_before,"live_after":live_after}},
                {"id":pixels["id"],"layer":"native-gpu","status":"observed",
                 "observation":{"width":image.width(),"height":image.height(),"scale":scale,"samples":samples}}
            ]);
            println!("GPUI_CONFORMANCE {}",json!({"implementation":"upstream","run_token":token,"cases":rows,
                "native_fixture":{"protocol":1,"mode":std::env::var("GPUI_FIXTURE_MODE").unwrap_or_else(|_| "hidden".into()),"snapshots":[created,rendered,resized_state,closed]},
                "frame":{"width":image.width(),"height":image.height(),"scale":scale,"rgba8":image.as_raw()}}));
            cx.update(|cx| cx.quit());
        }).detach();
    });
}
