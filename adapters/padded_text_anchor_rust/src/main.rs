//! Source-only observer: real GPUI text/layout using upstream NoopTextSystem.
//! Not the unchanged example, native font shaping, or screenshot parity.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{cell::RefCell, error::Error, rc::Rc};
const UPSTREAM: &str = "5a5fbe79917971a4d52a96b6ddb04da198a5012e";
const FIRST: &str = "This is first level Popover, \
                                                   we can use deferred to render it \
                                                   in a floating layer.\n\
                                                   Click outside to close.";
const SECOND: &str = "This is second level Popover with nested deferred!";
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input { schema_version: u32, variants: Vec<String>, steps: Vec<Step> }
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Step { id: String, viewport: [f32; 2], scale: f32, nested_open: bool }
#[derive(Default)]
struct Log { events: Vec<Value>, operation: String, frame: usize }
type SharedLog = Rc<RefCell<Log>>;
fn record(log: &SharedLog, event: Value) {
    let mut l = log.borrow_mut();
    let row = json!({"sequence":l.events.len(),"operation":l.operation,"frame":l.frame,"event":event});
    l.events.push(row);
}
fn rect(b: Bounds<Pixels>) -> Value {
    json!([f32::from(b.origin.x),f32::from(b.origin.y),f32::from(b.size.width),f32::from(b.size.height)])
}
struct Observed<E: Element> {
    inner: E, node: &'static str, log: SharedLog,
    hitbox: fn(&E::PrepaintState) -> Option<&Hitbox>,
}
impl<E: Element> IntoElement for Observed<E> {
    type Element = Self;
    fn into_element(self) -> Self { self }
}
impl<E: Element> Element for Observed<E> {
    type RequestLayoutState = E::RequestLayoutState;
    type PrepaintState = E::PrepaintState;
    fn id(&self) -> Option<ElementId> { self.inner.id() }
    fn source_location(&self) -> Option<&'static std::panic::Location<'static>> { self.inner.source_location() }
    fn request_layout(&mut self, id: Option<&GlobalElementId>, inspector: Option<&InspectorElementId>, window: &mut Window, cx: &mut App) -> (LayoutId, Self::RequestLayoutState) {
        if self.node == "host" {
            self.log.borrow_mut().frame += 1;
            record(&self.log,json!({"type":"frame_start","scale":window.scale_factor(),"viewport":[f32::from(window.viewport_size().width),f32::from(window.viewport_size().height)]}));
        }
        // For text nodes this runs inside the owner's inherited text-style scope.
        if self.node.ends_with("_text") {
            let style = window.text_style();
            let rem = window.rem_size();
            let size = style.font_size.to_pixels(rem);
            let text = cx.text_system();
            let font = text.resolve_font(&style.font());
            record(&self.log,json!({"type":"text_inputs","node":self.node,
                "font_family":style.font_family.to_string(),"font_size":f32::from(size),
                "rem_size":f32::from(rem),"line_height":f32::from(style.line_height_in_pixels(rem)),
                "units_per_em":text.units_per_em(font),"ascent":f32::from(text.ascent(font,size)),
                "descent":f32::from(text.descent(font,size)),"em_advance":f32::from(text.em_advance(font,size).expect("test font advance"))}));
        }
        self.inner.request_layout(id,inspector,window,cx)
    }
    fn prepaint(&mut self,id: Option<&GlobalElementId>,inspector: Option<&InspectorElementId>,bounds: Bounds<Pixels>,layout: &mut Self::RequestLayoutState,window: &mut Window,cx: &mut App) -> Self::PrepaintState {
        record(&self.log,json!({"type":"prepaint","node":self.node,"bounds":rect(bounds)}));
        let state = self.inner.prepaint(id,inspector,bounds,layout,window,cx);
        if let Some(hitbox) = (self.hitbox)(&state) {
            record(&self.log,json!({"type":"hitbox","node":self.node,"bounds":rect(hitbox.bounds),"content_mask":rect(hitbox.content_mask.bounds)}));
        }
        state
    }
    fn paint(&mut self,id: Option<&GlobalElementId>,inspector: Option<&InspectorElementId>,bounds: Bounds<Pixels>,layout: &mut Self::RequestLayoutState,state: &mut Self::PrepaintState,window: &mut Window,cx: &mut App) {
        record(&self.log,json!({"type":"paint","node":self.node,"bounds":rect(bounds)}));
        self.inner.paint(id,inspector,bounds,layout,state,window,cx);
        if self.node == "host" { record(&self.log,json!({"type":"host_paint_return"})); }
    }
}
fn observed(element: impl IntoElement,node: &'static str,log: &SharedLog) -> impl IntoElement {
    Observed {inner:element.into_element(),node,log:log.clone(),hitbox: |_| None}
}
fn observed_div<E: Element<PrepaintState=Option<Hitbox>>>(element: impl IntoElement<Element=E>,node: &'static str,log: &SharedLog) -> impl IntoElement {
    Observed {inner:element.into_element(),node,log:log.clone(),hitbox: |state| state.as_ref()}
}
fn button(id: &'static str, asymmetric: bool) -> Stateful<Div> {
    div().id(id).bg(black()).text_color(white()).px_3().py_1()
        // Deliberately separate diagnostic variant; not an upstream example style.
        .when(asymmetric, |d| d.pl(px(11.25)).pr(px(17.5)).pt(px(3.75)).pb(px(6.5)))
        .when(asymmetric, |d| d.border_l(px(1.25)).border_r(px(2.5)).border_t(px(0.75)).border_b(px(1.5)))
}
fn popover() -> Div {
    div().flex().flex_col().items_center().justify_center().shadow_lg().p_3()
        .rounded_md().bg(white()).text_color(black()).border_1().text_sm().border_color(black().opacity(0.1))
}
struct Probe { nested_open: bool, asymmetric: bool, log: SharedLog }
impl Render for Probe {
    fn render(&mut self,_window: &mut Window,cx: &mut Context<Self>) -> impl IntoElement {
        let log = &self.log;
        let child_trigger = button("secondary-btn",self.asymmetric).mt_2()
            .child(observed("Child Popover","secondary_text",log))
            .on_click(cx.listener(|this,_,_,cx| { this.nested_open=true; cx.notify(); }))
            .when(self.nested_open, |d| d.child(deferred(observed(
                anchored().anchor(Anchor::TopLeft).snap_to_window_with_margin(px(8.))
                    .child(observed_div(popover()
                        .child(observed(SECOND,"child_text",log)).bg(white()).border_color(blue())
                        .on_mouse_down_out(cx.listener(|this,_,_,cx| { this.nested_open=false; cx.notify(); })),"child",log)),
                "secondary_anchor_static",log)).priority(2)));
        let parent = popover().w_96().gap_3().child(observed(FIRST,"parent_text",log))
            .when(!self.nested_open, |d| d.on_mouse_down_out(|_,_,_| {}))
            .child(observed_div(child_trigger,"secondary",log));
        let trigger = button("popover1",self.asymmetric)
            .child(observed("Open Popover","primary_text",log))
            .on_click(|_,_,_| {})
            .child(deferred(observed(anchored().anchor(Anchor::TopLeft)
                .snap_to_window_with_margin(px(8.)).child(observed_div(parent,"parent",log)),
                "primary_anchor_static",log)).priority(1));
        observed(div().flex().flex_col().gap_3().size_full().bg(white()).text_color(black())
            .justify_center().items_center().child(observed_div(trigger,"primary",log)),"host",log)
    }
}
fn main() -> Result<(),Box<dyn Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len()!=3 || args[2].is_empty() { return Err("expected scenarios.json and nonempty run token".into()); }
    let input: Value = serde_json::from_slice(&std::fs::read(&args[1])?)?;
    let parsed: Input = serde_json::from_value(input.clone())?;
    if parsed.schema_version!=1 || parsed.variants!=["example_branch","asymmetric_fractional"] || parsed.steps.is_empty() { return Err("unsupported fixture".into()); }
    let mut ids = std::collections::HashSet::new();
    for step in &parsed.steps {
        if step.id.is_empty() || !ids.insert(&step.id) || !step.scale.is_finite() || step.scale<=0. || !step.viewport.iter().all(|v|v.is_finite() && *v>0.) { return Err("invalid step".into()); }
    }
    let mut variants = Vec::new();
    for variant in &parsed.variants {
        let mut app = TestAppContext::single(); // Upstream default NoopTextSystem, not system fonts.
        let log = Rc::new(RefCell::new(Log {operation:"bootstrap".into(),..Default::default()}));
        let handle = app.open_window(size(px(900.),px(700.)),|_,_| Probe {nested_open:false,asymmetric:variant=="asymmetric_fractional",log:log.clone()});
        let mut cx = VisualTestContext::from_window(*handle,&app);
        cx.run_until_parked();
        for step in &parsed.steps {
            log.borrow_mut().operation=step.id.clone();
            record(&log,json!({"type":"operation_start","viewport":step.viewport,"scale":step.scale,"nested_open":step.nested_open}));
            cx.simulate_resize(size(px(step.viewport[0]),px(step.viewport[1])));
            cx.simulate_scale_factor_change(step.scale);
            handle.update(&mut cx,|probe,_,cx| { probe.nested_open=step.nested_open; cx.notify(); })?;
            cx.run_until_parked();
            record(&log,json!({"type":"operation_end"}));
        }
        variants.push(json!({"variant":variant,"events":log.borrow().events}));
    }
    println!("{}",serde_json::to_string(&json!({"schema_version":1,"layer":"source-derived-padded-text-anchor",
        "upstream_revision":UPSTREAM,"text_backend":"upstream-NoopTextSystem","run_token":args[2],"input":input,"variants":variants}))?);
    Ok(())
}
