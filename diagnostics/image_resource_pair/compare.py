"""Actual Rust sprites versus actual core image item geometry/opacity."""
import json
import math
from pathlib import Path

def close(a,b):
    assert len(a)==len(b)
    assert all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in [*a,*b])
    assert all(abs(x-y)<=1e-6 for x,y in zip(a,b)),(a,b)
def bounds(b):return [b['x'],b['y'],b['width'],b['height']]
def intersection(a,b):
    x=max(a[0],b[0]);y=max(a[1],b[1]);return [x,y,max(0,min(a[0]+a[2],b[0]+b[2])-x),max(0,min(a[1]+a[3],b[1]+b[3])-y)]
def compare(rust,core):
    assert rust['backend']=='actual-rust-gpui-test-platform' and core['backend']=='actual-moonbit-core'
    assert rust['run_token']==core['run_token'] and rust['run_token']
    expected=['original_png_nested','original_png_clipped','portrait_contain','painter_order']
    assert [c['case'] for c in rust['cases']]==[c['case'] for c in core['cases']]==expected
    for r,c in zip(rust['cases'],core['cases']):
        close(r['viewport'],[160,120])
        snapshot=c['frame']['snapshot'];close(bounds(snapshot['viewport']),[0,0,160,120]);images=[i for i in snapshot['items'] if i['kind']=='image']
        assert len(images)==len(r['sprites'])==(1 if r['case']=='portrait_contain' else 2)
        clips={v['id']:v['rects'] for v in snapshot['clip_chains']}
        for image,sprite in zip(images,r['sprites']):
            visible=intersection(bounds(image['bounds']),bounds(image['image_bounds']))
            close(visible,sprite['bounds']);close([image['opacity']],[sprite['opacity']])
            clip=bounds(snapshot['viewport'])
            for rect in clips.get(image['clip_chain_id'],[]):clip=intersection(clip,bounds(rect))
            close(clip,sprite['content_mask'])
        if r['case']=='portrait_contain':close(r['sprites'][0]['bounds'],[25,0,50,100])
        else:close([s['opacity'] for s in r['sprites']],[.25,1])
    return {'status':'passed-numerical-sprite-proof','cases':4,'full_pixel_parity':False}
if __name__=='__main__':
    import sys
    print(json.dumps(compare(json.loads(Path(sys.argv[1]).read_text()),json.loads(Path(sys.argv[2]).read_text())),indent=2))
