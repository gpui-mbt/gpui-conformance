export async function decodeScreenshotRgba(page,buffer) {
  const image=await page.evaluate(async url=>{
    const source=new Image();source.src=url;await source.decode();
    const canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;
    const context=canvas.getContext('2d',{willReadFrequently:true});context.drawImage(source,0,0);
    const bytes=context.getImageData(0,0,source.width,source.height).data;
    // Numeric arrays make Playwright serialize a separate value for every color byte.
    const chunks=[];
    for(let offset=0;offset<bytes.length;offset+=0x8000)
      chunks.push(String.fromCharCode(...bytes.subarray(offset,offset+0x8000)));
    // Encoding after joining avoids base64 padding between the bounded chunks.
    return {width:source.width,height:source.height,rgbaBase64:btoa(chunks.join(''))};
  },'data:image/png;base64,'+buffer.toString('base64'));
  return {width:image.width,height:image.height,data:new Uint8Array(Buffer.from(image.rgbaBase64,'base64'))};
}
