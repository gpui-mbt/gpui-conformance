// Presentation sizing only; each runtime still owns its grid layout.
export function gridPaneSize({widths, viewportHeight, top, headerHeights, stacked, gap=0, padding=0}) {
  const rows=stacked?2:1;
  return {width:Math.max(16,Math.floor(Math.min(...widths))),
    height:Math.max(160,Math.floor((viewportHeight-Math.max(0,top)-padding-
      (stacked?headerHeights.reduce((a,b)=>a+b,0):Math.max(...headerHeights))-
      (stacked?gap:0))/rows))};
}

export function fitLiveGrid({windowObject=window, documentObject=document, onSize=()=>{}}={}) {
  const panes=documentObject.querySelector('.panes');
  const frames=['rust-frame','moon-frame'].map(id=>documentObject.getElementById(id));
  const containers=frames.map(frame=>frame.parentElement);
  const heads=[...panes.querySelectorAll('.pane-head')];
  let pending=0, stopped=false;
  documentObject.body.classList.add('live-grid');
  function resize() {
    pending=0;if(stopped)return;
    const style=windowObject.getComputedStyle(panes);
    const stacked=windowObject.matchMedia('(max-width: 720px)').matches;
    const size=gridPaneSize({widths:containers.map(node=>node.clientWidth),
      viewportHeight:windowObject.innerHeight,top:panes.getBoundingClientRect().top,
      headerHeights:heads.map(node=>node.getBoundingClientRect().height+2),stacked,
      gap:parseFloat(style.rowGap)||0,padding:(parseFloat(style.paddingTop)||0)+(parseFloat(style.paddingBottom)||0)});
    for(const [index,frame] of frames.entries()) {
      for(const key of ['width','height']) if(frame.style[key]!==`${size[key]}px`)frame.style[key]=`${size[key]}px`;
      if(containers[index].style.height!==`${size.height}px`)containers[index].style.height=`${size.height}px`;
    }
    onSize(size);
  }
  function schedule(){if(!stopped&&!pending)pending=windowObject.requestAnimationFrame(resize);}
  const observer=new windowObject.ResizeObserver(schedule);
  for(const node of [panes,...heads,documentObject.getElementById('notice')])observer.observe(node);
  windowObject.addEventListener('resize',schedule);
  resize();
  return ()=>{stopped=true;observer.disconnect();windowObject.removeEventListener('resize',schedule);if(pending)windowObject.cancelAnimationFrame(pending);documentObject.body.classList.remove('live-grid');};
}
