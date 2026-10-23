use gpui::{prelude::*, *};
use serde_json::{Value, json};

struct View {
    scenario: Value,
}
fn n(value: &Value) -> f32 {
    value.as_f64().expect("scenario number") as f32
}
fn bounds(value: Bounds<Pixels>) -> Value {
    json!([
        f32::from(value.origin.x),
        f32::from(value.origin.y),
        f32::from(value.size.width),
        f32::from(value.size.height)
    ])
}
impl Render for View {
    fn render(&mut self, _: &mut Window, _: &mut Context<Self>) -> impl IntoElement {
        let mut root = div()
            .id("root")
            .debug_selector(|| "root".into())
            .flex()
            .flex_row()
            .items_start()
            .w_full()
            .h_full()
            .gap(px(n(&self.scenario["gap"])));
        root = match self.scenario["wrap"].as_str().unwrap_or("nowrap") {
            "wrap" => root.flex_wrap(),
            "wrap_reverse" => root.flex_wrap_reverse(),
            _ => root.flex_nowrap(),
        };
        root = match self.scenario["direction"].as_str().unwrap_or("row") {
            "column" => root.flex_col(),
            "column_reverse" => root.flex_col_reverse(),
            "row_reverse" => root.flex_row_reverse(),
            _ => root.flex_row(),
        };
        if let Some(padding) = self.scenario["padding"].as_array() {
            root = root
                .pt(px(n(&padding[0])))
                .pr(px(n(&padding[1])))
                .pb(px(n(&padding[2])))
                .pl(px(n(&padding[3])));
        }
        if let Some(border) = self.scenario["border"].as_array() {
            root.style().border_widths.top = Some(px(n(&border[0])).into());
            root.style().border_widths.right = Some(px(n(&border[1])).into());
            root.style().border_widths.bottom = Some(px(n(&border[2])).into());
            root.style().border_widths.left = Some(px(n(&border[3])).into());
        }
        if !self.scenario["gap_x"].is_null() {
            root = root.gap_x(px(n(&self.scenario["gap_x"])));
        }
        if !self.scenario["gap_y"].is_null() {
            root = root.gap_y(px(n(&self.scenario["gap_y"])));
        }
        root = match self.scenario["justify"].as_str().unwrap_or("start") {
            "default" => root,
            "center" => root.justify_center(),
            "end" => root.justify_end(),
            "space-between" => root.justify_between(),
            "space-around" => root.justify_around(),
            "space-evenly" => root.justify_evenly(),
            _ => root.justify_start(),
        };
        if let Some(value) = match self.scenario["justify"].as_str() {
            Some("flex_start") => Some(JustifyContent::FlexStart),
            Some("flex_end") => Some(JustifyContent::FlexEnd),
            _ => None,
        } {
            root.style().justify_content = Some(value);
        }
        root = match self.scenario["align"].as_str().unwrap_or("start") {
            "center" => root.items_center(),
            "end" => root.items_end(),
            "stretch" => root.items_stretch(),
            _ => root.items_start(),
        };
        root = match self.scenario["align_content"].as_str().unwrap_or("stretch") {
            "space-between" => root.content_between(),
            "space-around" => root.content_around(),
            "space-evenly" => root.content_evenly(),
            "start" => root.content_start(),
            "center" => root.content_center(),
            "end" => root.content_end(),
            _ => root.content_stretch(),
        };
        for (i, dimensions) in self.scenario["children"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
        {
            let selector = ["a", "b", "c", "d"][i];
            let mut child = div()
                .id(i + 2)
                .debug_selector(move || selector.into())
                .min_w(px(0.))
                .flex_grow(self.scenario["grow"].get(i).map(n).unwrap_or(0.))
                .flex_shrink(self.scenario["shrink"].get(i).map(n).unwrap_or(1.))
                .min_h(px(0.))
                .bg(rgb(0x204060));
            if let Some(width) = dimensions[0].as_f64() {
                child = child.w(px(width as f32));
            }
            if let Some(height) = dimensions[1].as_f64() {
                child = child.h(px(height as f32));
            }
            if let Some(basis) = self.scenario["flex_basis"].get(i).and_then(Value::as_f64) {
                child = child.flex_basis(px(basis as f32));
            }
            let minimum = self.scenario["min_main"].get(i).map(n).unwrap_or(0.);
            let maximum = self.scenario["max_main"]
                .get(i)
                .filter(|value| !value.is_null())
                .map(n);
            if matches!(
                self.scenario["direction"].as_str(),
                Some("column" | "column_reverse")
            ) {
                child = child.min_h(px(minimum));
                if let Some(limit) = maximum {
                    child = child.max_h(px(limit));
                }
                child = child.min_w(px(self.scenario["min_cross"].get(i).map(n).unwrap_or(0.)));
                if let Some(limit) = self.scenario["max_cross"]
                    .get(i)
                    .filter(|v| !v.is_null())
                    .map(n)
                {
                    child = child.max_w(px(limit));
                }
            } else {
                child = child.min_w(px(minimum));
                if let Some(limit) = maximum {
                    child = child.max_w(px(limit));
                }
                child = child.min_h(px(self.scenario["min_cross"].get(i).map(n).unwrap_or(0.)));
                if let Some(limit) = self.scenario["max_cross"]
                    .get(i)
                    .filter(|v| !v.is_null())
                    .map(n)
                {
                    child = child.max_h(px(limit));
                }
            }
            child = match self.scenario["align_self"]
                .get(i)
                .and_then(Value::as_str)
                .unwrap_or("auto")
            {
                "start" => child.self_start(),
                "end" => child.self_end(),
                "center" => child.self_center(),
                "stretch" => child.self_stretch(),
                "flex_start" => child.self_flex_start(),
                "flex_end" => child.self_flex_end(),
                "auto" => child,
                value => panic!("unsupported align_self: {value}"),
            };
            root = root.child(child);
        }
        root
    }
}
fn observe(scenario: &Value) -> Value {
    assert_eq!(scenario["kind"], "layout");
    let mut app = TestAppContext::single();
    let handle = app.open_window(
        size(px(n(&scenario["width"])), px(n(&scenario["height"]))),
        |_, _| View {
            scenario: scenario.clone(),
        },
    );
    let mut context = VisualTestContext::from_window(*handle, &app);
    context.simulate_scale_factor_change(n(&scenario["device_scale_factor"]));
    context.run_until_parked();
    assert_eq!(
        context.update(|window, _| window.scale_factor()),
        n(&scenario["device_scale_factor"])
    );
    let children = scenario["children"].as_array().expect("scenario children");
    let selectors = ["a", "b", "c"];
    let rectangles: Vec<_> = std::iter::once("root")
        .chain(selectors.iter().take(children.len()).copied())
        .map(|selector| bounds(context.debug_bounds(selector).expect("drawn selector")))
        .collect();
    let (viewport, scale) = context.update(|window, _| {
        (
            bounds(Bounds {
                origin: point(px(0.), px(0.)),
                size: window.viewport_size(),
            }),
            window.scale_factor(),
        )
    });
    json!({"id":scenario["id"], "layer":"headless-layout", "status":"observed", "observation":{"bounds":rectangles, "test_window_viewport":viewport, "device_scale_factor":scale}})
}
fn main() {
    let scenarios: Value =
        serde_json::from_str(&std::env::var("GPUI_SCENARIOS").expect("shared scenarios"))
            .expect("valid scenarios");
    let cases: Vec<_> = scenarios["cases"]
        .as_array()
        .expect("scenario cases")
        .iter()
        .map(observe)
        .collect();
    println!(
        "GPUI_CONFORMANCE {}",
        json!({"implementation":"upstream", "cases":cases})
    );
}
