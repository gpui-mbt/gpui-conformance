#![cfg_attr(target_family = "wasm", no_main)]
// Synthetic diagnostic only. Not the upstream gradient example or a candidate.
use gpui::{App, Bounds, ColorSpace, ContentMask, Context, Render, Window, WindowOptions,
    canvas, div, fill, linear_color_stop, linear_gradient, point, prelude::*, px, size};
use gpui_platform::application;
struct Probe { kind: &'static str, space: ColorSpace, x: f32, y: f32,
    width: f32, height: f32, angle: f32, stop0: f32, stop1: f32 }
const PROBES: &[Probe] = &[
    Probe { kind: "solid", space: ColorSpace::Srgb, x: 16., y: 16., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "alpha", space: ColorSpace::Srgb, x: 208., y: 16., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 400., y: 16., width: 161., height: 65., angle: 45., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 592., y: 16., width: 65., height: 81., angle: 45., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 784., y: 16., width: 161., height: 65., angle: 135., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 16., y: 124., width: 161., height: 65., angle: 225., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 208., y: 124., width: 161., height: 65., angle: 315., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 400., y: 124., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 592., y: 124., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 784., y: 124., width: 161., height: 65., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 16., y: 232., width: 161., height: 65., angle: 360., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 208., y: 232., width: 161., height: 65., angle: 90., stop0: 0.5, stop1: 0.5 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 400., y: 232., width: 161., height: 65., angle: 90., stop0: -0.25, stop1: 1.25 },
    Probe { kind: "quad", space: ColorSpace::Srgb, x: 592., y: 232., width: 161., height: 65., angle: 90., stop0: 1.0, stop1: 0.0 },
    Probe { kind: "path", space: ColorSpace::Srgb, x: 784., y: 232., width: 161., height: 80., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "clip", space: ColorSpace::Srgb, x: 16., y: 340., width: 161., height: 80., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "unequal", space: ColorSpace::Srgb, x: 208., y: 340., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "transparent", space: ColorSpace::Srgb, x: 400., y: 340., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "solid", space: ColorSpace::Oklab, x: 16., y: 448., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "alpha", space: ColorSpace::Oklab, x: 208., y: 448., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 400., y: 448., width: 161., height: 65., angle: 45., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 592., y: 448., width: 65., height: 81., angle: 45., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 784., y: 448., width: 161., height: 65., angle: 135., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 16., y: 556., width: 161., height: 65., angle: 225., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 208., y: 556., width: 161., height: 65., angle: 315., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 400., y: 556., width: 161., height: 65., angle: 0., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 592., y: 556., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 784., y: 556., width: 161., height: 65., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 16., y: 664., width: 161., height: 65., angle: 360., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 208., y: 664., width: 161., height: 65., angle: 90., stop0: 0.5, stop1: 0.5 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 400., y: 664., width: 161., height: 65., angle: 90., stop0: -0.25, stop1: 1.25 },
    Probe { kind: "quad", space: ColorSpace::Oklab, x: 592., y: 664., width: 161., height: 65., angle: 90., stop0: 1.0, stop1: 0.0 },
    Probe { kind: "path", space: ColorSpace::Oklab, x: 784., y: 664., width: 161., height: 80., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "clip", space: ColorSpace::Oklab, x: 16., y: 772., width: 161., height: 80., angle: 180., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "unequal", space: ColorSpace::Oklab, x: 208., y: 772., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
    Probe { kind: "transparent", space: ColorSpace::Oklab, x: 400., y: 772., width: 161., height: 65., angle: 90., stop0: 0.0, stop1: 1.0 },
];
struct Diagnostic;
impl Render for Diagnostic {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        div().size_full().bg(gpui::white()).child(canvas(
            |_, _, _| {},
            |_, _, window, _| {
                for probe in PROBES {
                    let bounds = Bounds::new(point(px(probe.x), px(probe.y)), size(px(probe.width), px(probe.height)));
                    if probe.kind == "solid" || probe.kind == "alpha" {
                        let mut color = gpui::green();
                        if probe.kind == "alpha" { color.a = 0.5; }
                        window.paint_quad(fill(bounds, color));
                        continue;
                    }
                    let mut first = gpui::red();
                    let mut second = gpui::blue();
                    if probe.kind == "unequal" { first = gpui::green(); first.a = 0.25; second.a = 0.75; }
                    if probe.kind == "transparent" {
                        first.a = 0.0; second.a = 0.75;
                        window.paint_quad(fill(bounds, gpui::black()));
                    }
                    let background = linear_gradient(probe.angle,
                        linear_color_stop(first, probe.stop0),
                        linear_color_stop(second, probe.stop1)).color_space(probe.space);
                    if probe.kind == "path" || probe.kind == "clip" {
                        let mut path = gpui::PathBuilder::fill();
                        path.move_to(bounds.origin + point(px(0.), px(80.)));
                        path.line_to(bounds.origin + point(px(80.), px(30.)));
                        path.line_to(bounds.origin + point(px(81.), px(30.)));
                        path.line_to(bounds.origin + point(px(161.), px(80.)));
                        path.line_to(bounds.origin + point(px(0.), px(80.)));
                        let path = path.build().unwrap();
                        if probe.kind == "clip" {
                            let clip = Bounds::new(bounds.origin + point(px(0.), px(45.)), size(px(161.), px(35.)));
                            window.with_content_mask(Some(ContentMask { bounds: clip }), |window| window.paint_path(path, background));
                        } else { window.paint_path(path, background); }
                    } else { window.paint_quad(fill(bounds, background)); }
                }
            },
        ).size_full())
    }
}
fn run_example() {
    application().run(|cx: &mut App| {
        cx.open_window(WindowOptions { focus: true, ..Default::default() }, |_, cx| cx.new(|_| Diagnostic)).unwrap();
        cx.activate(true);
    });
}
#[cfg(not(target_family = "wasm"))]
fn main() { run_example(); }
#[cfg(target_family = "wasm")]
#[wasm_bindgen::prelude::wasm_bindgen(start)]
pub fn start() { gpui_platform::web_init(); run_example(); }
