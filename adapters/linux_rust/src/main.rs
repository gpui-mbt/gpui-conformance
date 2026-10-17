//! Visible, interactive X11 GPUI fixture. The launcher owns this process.
use gpui::{prelude::*, *};
use serde_json::{Value, json};
use std::time::{Duration, Instant};

struct Rectangle {
    bounds: [f32; 4],
    background: u32,
    foreground: u32,
}

impl Render for Rectangle {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().w_full().h_full().bg(rgb(self.background)).child(
            div()
                .absolute()
                .left(px(self.bounds[0]))
                .top(px(self.bounds[1]))
                .w(px(self.bounds[2]))
                .h(px(self.bounds[3]))
                .bg(rgb(self.foreground)),
        )
    }
}

fn color(v: &Value) -> u32 {
    let channel = |i: usize| v[i].as_u64().expect("RGBA channel") as u32;
    (channel(0) << 16) | (channel(1) << 8) | channel(2)
}

fn emit(event: &str, token: &str, width: f32, height: f32, scale: f32, elapsed_ms: u128) {
    println!(
        "GPUI_NATIVE_LAB {}",
        json!({
            "protocol": 1,
            "implementation": "upstream",
            "run_token": token,
            "event": event,
            "width": width,
            "height": height,
            "scale": scale,
            "elapsed_ms": elapsed_ms
        })
    );
}

fn main() {
    let input: Value = serde_json::from_str(
        &std::env::var("GPUI_SCENARIOS").expect("shared native scenarios"),
    ).expect("valid native scenarios");
    let cases = input["cases"].as_array().expect("cases");
    let window_case = cases.iter().find(|v| v["kind"] == "window").expect("window fixture");
    let pixels = cases.iter().find(|v| v["kind"] == "pixels").expect("pixel fixture");
    let n = |v: &Value| v.as_f64().expect("number") as f32;
    let rect = pixels["rect"].as_array().expect("rect");
    let rectangle = Rectangle {
        bounds: [n(&rect[0]), n(&rect[1]), n(&rect[2]), n(&rect[3])],
        background: color(&pixels["background"]),
        foreground: color(&pixels["color"]),
    };
    let width = n(&window_case["width"]);
    let height = n(&window_case["height"]);
    let token = std::env::var("GPUI_RUN_TOKEN").expect("run token");
    let start = Instant::now();
    gpui_platform::application().run(move |cx| {
        let handle = cx.open_window(
            WindowOptions {
                window_bounds: Some(WindowBounds::Windowed(Bounds::new(
                    point(px(0.), px(0.)),
                    size(px(width), px(height)),
                ))),
                focus: true,
                show: true,
                ..Default::default()
            },
            |_, cx| cx.new(|_| rectangle),
        ).expect("X11 native window");
        emit("opened", &token, width, height, 0., start.elapsed().as_millis());
        cx.activate(true);
        cx.spawn(async move |cx| {
            let mut first_frame = false;
            let mut last_size = (width, height);
            loop {
                cx.background_executor().timer(Duration::from_millis(100)).await;
                let observed = cx.update_window(*handle, |_, window, cx| {
                    if !first_frame {
                        let _ = window.draw(cx);
                    }
                    let size = window.viewport_size();
                    (f32::from(size.width), f32::from(size.height), window.scale_factor())
                });
                match observed {
                    Ok((w, h, scale)) => {
                        if !first_frame {
                            emit("frame_ready", &token, w, h, scale, start.elapsed().as_millis());
                            first_frame = true;
                            last_size = (w, h);
                        } else if (w, h) != last_size {
                            emit("resized", &token, w, h, scale, start.elapsed().as_millis());
                            last_size = (w, h);
                        }
                    }
                    Err(_) => {
                        emit("closed", &token, 0., 0., 0., start.elapsed().as_millis());
                        break;
                    }
                }
            }
        }).detach();
    });
}
