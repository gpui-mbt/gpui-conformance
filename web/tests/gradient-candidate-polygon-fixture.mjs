// Synthetic checker fixtures only. Not candidate output or compiled-engine controls.
// Independent convex-edge inclusion rasterizer on exact twentieth-pixel units.
export function rasterSourcePolygon(width,height,{originX=0,widthDelta=0}={}) {
 const image={width,height,data:new Uint8Array(width*height*4).fill(255)},canvasWidth=width-32,canvasTop=height-16-96;
 const x=2*canvasWidth+originX*20,w=16*canvasWidth+widthDelta*20;
 const points=[[x,(canvasTop+80)*20],[x+80*20,(canvasTop+30)*20],[x+w-80*20,(canvasTop+30)*20],[x+w,(canvasTop+80)*20]];
 let minX=width,minY=height,maxX=-1,maxY=-1;
 for(let py=Math.max(0,canvasTop+30);py<Math.min(height,canvasTop+81);py++)for(let px=0;px<width;px++){
  const q=[px*20+10,py*20+10];let sign=0,inside=true;
  for(let i=0;i<4;i++){const a=points[i],b=points[(i+1)%4],cross=(b[0]-a[0])*(q[1]-a[1])-(b[1]-a[1])*(q[0]-a[0]);if(cross!==0){const next=Math.sign(cross);if(sign&&next!==sign){inside=false;break;}sign=next;}}
  if(inside){image.data.set([255,0,0,255],(py*width+px)*4);minX=Math.min(minX,px);maxX=Math.max(maxX,px);minY=Math.min(minY,py);maxY=Math.max(maxY,py);}
 }
 return {image,bounds:{x:minX,y:minY,width:maxX-minX+1,height:maxY-minY+1}};
}
