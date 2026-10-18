//! Bounded real GPUI scene/event observer. No expected scene values emitted.
use gpui::{prelude::*, *};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{cell::RefCell, rc::Rc};
#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
struct Case { id:String, parent:Option<f32>, child:Option<f32>, grandchild:Option<f32>, alpha:u8, binding:f32, clip:bool, deferred:bool, nested:bool }
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input { schema_version:u32, viewport:[f32;2], cases:Vec<Case> }
type Hits = Rc<RefCell<Vec<u64>>>;
fn block(id:u64,w:f32,h:f32,color:Hsla,opacity:Option<f32>,hits:&Hits)->Stateful<Div> {
    let hits=hits.clone();
    div().id(id).debug_selector(move || id.to_string().into())
        .w(px(w)).h(px(h)).flex_shrink_0().flex().flex_col().items_start()
        .bg(color).when_some(opacity,|d,o|d.opacity(o))
        .on_mouse_down(MouseButton::Left,move |_,_,_|hits.borrow_mut().push(id))
}
struct Probe { case:Case, hits:Hits }
impl Render for Probe {
    fn render(&mut self,_:&mut Window,_:&mut Context<Self>)->impl IntoElement {
        let c=&self.case;
        let mut child=block(3,120.,100.,rgb(0x00ff00).into(),c.child,&self.hits)
            .child(block(4,40.,40.,Hsla::from(rgb(0x0000ff)).opacity(c.alpha as f32/255.*c.binding),c.grandchild,&self.hits));
        if c.nested {
            child=child.child(deferred(anchored().anchor(Anchor::TopLeft)
                .position(point(px(60.),px(50.))).snap_to_window_with_margin(px(0.))
                .child(block(7,20.,20.,rgb(0xffff00).into(),Some(0.25),&self.hits))).priority(2));
        }
        let mut parent=block(2,100.,80.,rgb(0xff0000).into(),c.parent,&self.hits)
            .when(c.clip,|d|d.overflow_hidden());
        if c.deferred {
            parent=parent.child(div().id(8u64).w(px(40.)).h(px(40.)).flex_shrink_0())
                .child(deferred(anchored().anchor(Anchor::TopLeft)
                    .position(point(px(20.),px(20.))).snap_to_window_with_margin(px(0.))
                    .child(child)).priority(1));
        } else { parent=parent.child(child); }
        div().size_full().flex().flex_row().items_start().child(parent)
            .child(block(5,40.,80.,rgb(0xff00ff).into(),None,&self.hits))
    }
}
fn main() {
    let input:Value=serde_json::from_str(&std::env::var("GPUI_SCENARIOS").unwrap()).unwrap();
    let parsed:Input=serde_json::from_value(input.clone()).unwrap();
    assert_eq!(parsed.schema_version,1);
    let token=std::env::var("GPUI_RUN_TOKEN").unwrap();assert!(!token.is_empty());
    let mut cases=Vec::new();
    for case in parsed.cases {
        let hits=Rc::new(RefCell::new(Vec::new()));
        let mut app=TestAppContext::single();
        let handle=app.open_window(size(px(parsed.viewport[0]),px(parsed.viewport[1])),|_,_|Probe{case:case.clone(),hits:hits.clone()});
        let mut cx=VisualTestContext::from_window(*handle,&app);cx.run_until_parked();
        let quads=cx.update(|window,_|{
            let scale=window.scale_factor();
            window.painted_quads().iter().map(|q|{
                let c=Rgba::from(q.background.as_solid().expect("solid quad"));
                json!({"bounds":[q.bounds.origin.x.0/scale,q.bounds.origin.y.0/scale,q.bounds.size.width.0/scale,q.bounds.size.height.0/scale],
                    "clip":[q.content_mask.bounds.origin.x.0/scale,q.content_mask.bounds.origin.y.0/scale,q.content_mask.bounds.size.width.0/scale,q.content_mask.bounds.size.height.0/scale],
                    "rgba":[c.r,c.g,c.b,c.a]})
            }).collect::<Vec<_>>()
        });
        let bounds=[2u64,3,4,5].into_iter().chain(if case.nested {Some(7)}else{None}).map(|id|{
            let selector=match id { 2=>"2",3=>"3",4=>"4",5=>"5",7=>"7",_=>unreachable!() };
            let b=cx.debug_bounds(selector).expect("drawn bounds");
            json!({"id":id,"bounds":[f32::from(b.origin.x),f32::from(b.origin.y),f32::from(b.size.width),f32::from(b.size.height)]})
        }).collect::<Vec<_>>();
        hits.borrow_mut().clear();
        let p=if case.deferred {25.}else{10.};
        cx.simulate_mouse_down(point(px(p),px(p)),MouseButton::Left,Modifiers::default());
        let target=hits.borrow().first().copied();
        cases.push(json!({"id":case.id,"quads":quads,"bounds":bounds,"target":target}));
        cx.update(|window,_|window.remove_window());cx.run_until_parked();
    }
    println!("{}",json!({"schema_version":1,"backend":"rust-gpui","upstream_revision":"5a5fbe79917971a4d52a96b6ddb04da198a5012e","run_token":token,"input":input,"cases":cases}));
}
