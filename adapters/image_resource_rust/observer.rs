// Appended as a test-only nested module to the exact pinned elements/img.rs.
// Production bytes before the append must remain hash-identical.
#[cfg(test)]
mod image_resource_conformance_observer {
    use super::*;
    use crate::{prelude::*, TestAppContext, div, point, px, size};
    use serde_json::json;

    #[gpui::test]
    fn observe_image_resources(cx: &mut TestAppContext) {
        let asset_path=std::env::var("GPUI_IMAGE_ASSET").expect("asset path");
        let bytes=std::fs::read(asset_path).expect("asset bytes");
        let decoded=decode_static_image(&bytes,ImageFormat::Png).expect("decode pinned PNG");
        let icon=Arc::new(RenderImage::new(decoded));
        let portrait_bytes=std::fs::read(std::env::var("GPUI_PORTRAIT_ASSET").expect("portrait path")).expect("portrait bytes");
        let portrait=Arc::new(RenderImage::new(decode_static_image(&portrait_bytes,ImageFormat::Png).expect("decode geometry fixture PNG")));
        let window=cx.add_empty_window();
        window.simulate_resize(size(px(160.),px(120.)));
        window.run_until_parked();
        let mut observations=Vec::new();
        for case in ["original_png_nested", "original_png_clipped", "portrait_contain", "painter_order"] {
            window.draw(point(px(0.),px(0.)),size(px(160.),px(120.)),|_,_| {
                if case=="portrait_contain" {
                    div().size(px(100.)).overflow_hidden()
                        .child(img(ImageSource::Render(portrait.clone())).size_full().aspect_square().object_fit(ObjectFit::Contain))
                        .into_any_element()
                } else {
                    div().flex().flex_row().items_start()
                        .child(div().w(px(if case=="original_png_clipped" {20.} else {32.})).h(px(32.)).flex_shrink_0()
                            .overflow_hidden().opacity(0.5).when(case=="painter_order",|d|d.bg(crate::rgb(0xff0000)))
                            .child(div().size(px(32.)).opacity(0.5)
                                .child(img(ImageSource::Render(icon.clone())).size(px(32.)).object_fit(ObjectFit::Contain))))
                        .child(div().size(px(32.)).flex_shrink_0().when(case=="painter_order",|d|d.bg(crate::rgb(0x0000ff)))
                            .child(img(ImageSource::Render(icon.clone())).size(px(32.)).object_fit(ObjectFit::Contain)))
                        .into_any_element()
                }
            });
            let observation=window.update(|window,_| {
                let scale=window.scale_factor();
                let viewport=window.viewport_size();
                let sprites=window.rendered_frame.scene.polychrome_sprites.iter().map(|sprite| {
                    let b=sprite.bounds;let c=sprite.content_mask.bounds;let tile=sprite.tile.bounds;
                    json!({"bounds":[b.origin.x.0/scale,b.origin.y.0/scale,b.size.width.0/scale,b.size.height.0/scale],
                        "content_mask":[c.origin.x.0/scale,c.origin.y.0/scale,c.size.width.0/scale,c.size.height.0/scale],
                        "opacity":sprite.opacity,"order":sprite.order,
                        "tile_bounds":[tile.origin.x.0,tile.origin.y.0,tile.size.width.0,tile.size.height.0]})
                }).collect::<Vec<_>>();
                json!({"case":case,"scale":scale,"viewport":[viewport.width.0,viewport.height.0],"sprites":sprites})
            });
            observations.push(observation);
        }
        let token=std::env::var("GPUI_RUN_TOKEN").expect("fresh run token");
        assert!(!token.is_empty());
        let result=json!({"schema_version":1,"backend":"actual-rust-gpui-test-platform",
            "upstream_revision":"5a5fbe79917971a4d52a96b6ddb04da198a5012e",
            "run_token":token,"cases":observations});
        std::fs::write(std::env::var("GPUI_OBSERVATION_OUT").expect("output path"),serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    }
}
