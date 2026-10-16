import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {decodeScreenshotRgba} from './screenshot-rgba.mjs';

function fixture(width,height,{decodeError}={}) {
  const data=new Uint8ClampedArray(width*height*4);
  for(let i=0;i<data.length;i++)data[i]=(i*73+(i>>>8))&255;
  let decoded=false,drawn=false;
  const source={width,height,data},png=Buffer.from('synthetic PNG transport input');
  class Image {
    width=width;height=height;
    async decode() {
      assert.equal(this.src,'data:image/png;base64,'+png.toString('base64'));
      if(decodeError)throw decodeError;
      decoded=true;
    }
  }
  const document={createElement(tag) {
    assert.equal(tag,'canvas');
    const canvas={width:0,height:0,getContext(kind,options) {
      assert.equal(kind,'2d');assert.equal(options.willReadFrequently,true);
      return {
        drawImage(image,x,y) {
          assert(decoded);assert(image instanceof Image);assert.equal(x,0);assert.equal(y,0);
          assert.equal(canvas.width,width);assert.equal(canvas.height,height);drawn=true;
        },
        getImageData(x,y,w,h) {
          assert(drawn);assert.equal(x,0);assert.equal(y,0);assert.equal(w,width);assert.equal(h,height);
          return {data};
        },
      };
    }};
    return canvas;
  }};
  const page={evaluate(callback,url) {
    return runInNewContext(`(${callback.toString()})(url)`,{Image,document,btoa,url});
  }};
  return {page,png,source};
}

const sha256=data=>createHash('sha256').update(data).digest('hex');
for(const [width,height] of [[1,1],[17,13],[8193,1],[800,600]]) {
  test(`complete ${width}x${height} RGBA bytes survive browser transport, including the last partial chunk`,async()=>{
    const {page,png,source}=fixture(width,height),original=source.data.slice();
    const image=await decodeScreenshotRgba(page,png);
    assert.deepEqual([image.width,image.height],[width,height]);
    assert(image.data instanceof Uint8Array);assert.equal(Buffer.isBuffer(image.data),false);
    assert.equal(image.data.length,width*height*4);
    assert.equal(Buffer.compare(image.data,new Uint8Array(source.data)),0);
    assert.equal(sha256(image.data),sha256(source.data));
    image.data[0]^=255;
    assert.deepEqual(source.data,original);
  });
}

test('an undecodable PNG rejects instead of returning substitute pixels',async()=>{
  const error=new Error('PNG decode failed'),{page,png}=fixture(1,1,{decodeError:error});
  await assert.rejects(decodeScreenshotRgba(page,png),error);
});
