#!/usr/bin/env python3
"""Source-specific comparison. Original PNG bytes are never changed or normalized."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image

CONTRACT = Path(__file__).resolve().parents[1] / 'pairs/pattern.json'

def check(ok, message):
    if not ok:
        raise AssertionError(message)

def pixel(image, x, y):
    return image.getpixel((x, y))

def blue_boxes(image):
    # Source blue borders, not candidate scene claims, establish independent geometry.
    pixels = image.load()
    unseen = {(x,y) for y in range(600) for x in range(600)
              if pixels[x,y][0] <= 2 and pixels[x,y][1] <= 2 and pixels[x,y][2] >= 253 and pixels[x,y][3] == 255}
    boxes=[]
    while unseen:
        point=unseen.pop(); stack=[point]; group=[point]
        while stack:
            x,y=stack.pop()
            for n in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if n in unseen:
                    unseen.remove(n); stack.append(n); group.append(n)
        xs,ys=zip(*group); box=(min(xs),min(ys),max(xs)+1,max(ys)+1)
        if box[2]-box[0]>=50 and box[3]-box[1]>=30: boxes.append(box)
    boxes.sort(key=lambda b:b[1])
    check(len(boxes)==4, f'expected four connected blue source borders; got {boxes}')
    return boxes

def regions(boxes):
    small,large,solid,gradient=boxes
    rows=[]
    for i in range(4): rows.append((f'red{i+1}',(small[0]+1,small[1]+1+i*18,54,18)))
    start=large[3]-1-194
    for i,name in enumerate(('large_red','large_green','large_blue')):
        rows.append((name,(large[0]+1,start+i*56,256,56)))
    rows.append(('short_yellow',(large[0]+1,start+168,256,26)))
    # A transparent gap within every stripe is also checked; this extra strip is
    # outside rows and excludes the label text in the large source container.
    if large[2]-large[0] > 262:
        rows.append(('green_alpha_background',(large[0]+258,start+2,large[2]-large[0]-260,190)))
    rows.extend([('red_solid',(solid[0]+2,solid[1]+2,solid[2]-solid[0]-4,solid[3]-solid[1]-4)),
                 ('red_blue_gradient_45deg',(gradient[0]+2,gradient[1]+2,gradient[2]-gradient[0]-4,gradient[3]-gradient[1]-4))])
    return rows

def compare(oracle,candidate,contract=None):
    contract=contract or json.loads(CONTRACT.read_text()); t=contract['thresholds']
    check(oracle.size==candidate.size==(600,600),'viewport must be 600x600 physical pixels')
    oracle=oracle.convert('RGBA');candidate=candidate.convert('RGBA')
    ob,cb=blue_boxes(oracle),blue_boxes(candidate)
    for i,(a,b) in enumerate(zip(ob,cb)):
        check(all(abs(x-y)<=t['geometry_physical_px'] for x,y in zip(a,b)),f'border geometry group {i}: {a} != {b}')
    for boxes in (ob,cb):
        check(abs(boxes[0][2]-boxes[0][0]-56)<=2 and abs(boxes[0][3]-boxes[0][1]-74)<=2,'small stripe group source extent')
        check(boxes[1][2]-boxes[1][0]>=258,'large stripe group source width')
        for b in boxes[2:]: check(abs(b[2]-b[0]-240)<=2 and abs(b[3]-b[1]-40)<=2,'red control source extent')
    results=[]
    for (name,a),(name2,b) in zip(regions(ob),regions(cb)):
        check(name==name2, 'source region correspondence')
        ax,ay,w,h=a;bx,by,bw,bh=b
        check(abs(w-bw)<=2 and abs(h-bh)<=2,f'{name}: extent mismatch')
        count=matched=foreground=background=0
        for y in range(1,min(h,bh)-1):
            for x in range(1,min(w,bw)-1):
                expected=pixel(oracle,ax+x,ay+y)
                # Flat neighborhoods exclude stripe boundaries only. The gradient
                # control samples every interior point, including its slope.
                if name!='red_blue_gradient_45deg' and any(max(abs(u-v) for u,v in zip(expected,pixel(oracle,ax+x+dx,ay+y+dy)))>2 for dx,dy in ((-1,0),(1,0),(0,-1),(0,1))): continue
                actual=pixel(candidate,bx+x,by+y);count+=1
                if name in ('red1','red2','red3','red4','large_red','large_green','large_blue','short_yellow'):
                    source_color=(255,255,0) if name=='short_yellow' else (0,128,0) if name=='large_green' else (0,0,255) if name=='large_blue' else (255,0,0)
                    source_gap=(255,255,255) if name.startswith('red') else (214,235,214)
                    foreground+=int(all(abs(expected[k]-source_color[k])<=2 for k in range(3)))
                    background+=int(all(abs(expected[k]-source_gap[k])<=2 for k in range(3)))
                matched+=int(all(abs(actual[k]-expected[k])<=t['rgb_code'] for k in range(3)) and actual[3]==expected[3]==255)
        check(count>=t['minimum_samples_per_row'], f'{name}: too few independent original screenshot samples ({count})')
        if name in ('red1','red2','red3','red4','large_red','large_green','large_blue','short_yellow'):
            check(foreground>=30 and background>=30,f'{name}: source stripe/gap coverage or green alpha background missing ({foreground}/{background})')
        ratio=matched/count
        check(ratio>=t['minimum_region_agreement'], f'{name}: RGB/alpha/interval/phase mismatch ({matched}/{count}, {ratio:.4f})')
        results.append({'region':name,'samples':count,'matched':matched,'agreement':ratio})
    return {'status':'qualified_source_regions','profile':contract['profile'],'regions':results,'not_claimed':contract['not_claimed']}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('rust_png');parser.add_argument('moonbit_png');parser.add_argument('--output');args=parser.parse_args()
    report=compare(Image.open(args.rust_png),Image.open(args.moonbit_png))
    report['inputs']={name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in [('rust',args.rust_png),('moonbit',args.moonbit_png)]}
    report['contract_sha256']=hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    out=json.dumps(report,indent=2)+'\n'
    if args.output:Path(args.output).write_text(out)
    print(out)
if __name__=='__main__':main()
