/* Original vector illustrations. anime.js easing only: no playing timelines. */
(()=>{'use strict';
const registry={},NS='http://www.w3.org/2000/svg',clamp=x=>Math.max(0,Math.min(1,x));
const ease=p=>window.anime?anime.easing('easeOutCubic')(clamp(p)):clamp(p);
function el(tag,attrs={},text){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=String(text);return n;}
function group(parent,attrs={}){const n=el('g',attrs);parent.append(n);return n;}
function shape(parent,tag,attrs){const n=el(tag,attrs);parent.append(n);return n;}
function label(parent,text,x,y,size=52,width=650,colour){
 const words=String(text||'').split(/\s+/).filter(Boolean);
 // Preserve phrases up to 4 words (e.g. 'Kinh tế tầm thấp') without arbitrary truncation
 const clampedWords = words.length <= 4 ? words : words.slice(0, 3);
 const lines=[];
 for(let i=0;i<clampedWords.length;i+=2)lines.push(clampedWords.slice(i,i+2).join(' '));
 const finalSize = Math.max(36, size);
 const n=el('text',{x,y,'text-anchor':'middle','font-size':finalSize,...(colour?{fill:colour}:{}),class:'ill-label'});
 lines.forEach((line,i)=>n.append(el('tspan',{x,dy:i?finalSize*1.15:0},line)));parent.append(n);
 let fs=finalSize;const spans=[...n.querySelectorAll('tspan')];
 while(Math.max(0,...spans.map(s=>s.getComputedTextLength()))>width&&fs>36){fs-=2;n.setAttribute('font-size',fs);spans.forEach((s,i)=>s.setAttribute('dy',i?fs*1.15:0));}return n;
}
function box(parent,x,y,w,h,text,p,t){const g=group(parent,{class:'motion-element',transform:`translate(0 ${14*Math.sin(t*.55+x)}) scale(1)`});shape(g,'rect',{x,y,width:w,height:h,rx:30,fill:'#162a43',stroke:p>.5?'var(--accent)':'#6687aa88','stroke-width':4});const lines=Math.max(1,Math.ceil(Math.min(6,String(text).split(/\s+/).length)/2)),fs=Math.max(36,Math.min(54,w*.18,h/(lines*1.3)));label(g,text,x+w/2,y+h/2-(lines-1)*fs*.575+fs*.3,fs,w*.9);return g;}
function dot(parent,x,y,r,t){return shape(parent,'circle',{class:'motion-element',cx:x+10*Math.sin(t),cy:y+10*Math.cos(t*.8),r:r*(1+.06*Math.sin(t*2)),fill:'var(--accent)',opacity:.7});}
const fmt=(value,progress=1)=>{
 const num = Number(value || 0);
 if (Math.abs(num) >= 1e9) {
  const red = (num / 1e9) * ease(progress);
  const prec = Number.isInteger(red) ? 0 : 2;
  return red.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: prec }) + ' tỷ';
 }
 if (Math.abs(num) >= 1e6) {
  const red = (num / 1e6) * ease(progress);
  const prec = Number.isInteger(red) ? 0 : 2;
  return red.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: prec }) + ' triệu';
 }
 const precision=Number.isInteger(num)?0:Math.min(2,(String(num).split('.')[1]||'').length);
 return (num*ease(progress)).toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:precision});
};
const paints={};
paints.versus_scale=c=>{const {mid:m,front:f,d,t,p}=c;const sides=d.bars?.length>=2?d.bars.slice(0,2):(d.items||[]).slice(0,2).map(label=>({label}));
 sides.forEach((b,i)=>{box(m,70+i*480,260,410,560,b.label,ease(p*3-i*.25),t);if(Number.isFinite(b.value))label(f,fmt(b.value,p*2)+(b.unit||''),275+i*480,720,80,360,'var(--accent)');});
 const a=sides[0]?.value,b=sides[1]?.value,tilt=Number.isFinite(a)&&Number.isFinite(b)?Math.sign(b-a)*12*ease(p*2):0;const beam=group(f,{class:'motion-element',transform:`rotate(${tilt} 540 850)`});shape(beam,'path',{d:'M120 850H960M540 850V1000',stroke:'var(--accent)','stroke-width':18,fill:'none'});shape(f,'circle',{cx:540,cy:540,r:65,fill:'var(--accent)',class:'motion-element'});label(f,'VS',540,560,56,120,'#0c1829');};
paints.numeric=c=>{const {mid:m,front:f,d,t,p,type}=c;const value=d.value??0,percent=d.unit==='%',q=percent?clamp(value/100):1,progress=ease(c.numberProgress);
 if(type==='ring'||type==='gauge'){const radius=320,arc=type==='gauge'?Math.PI*radius:2*Math.PI*radius;shape(m,'circle',{cx:450,cy:500,r:radius,fill:'none',stroke:'#ffffff18','stroke-width':43,class:'motion-element'});shape(m,'circle',{cx:450,cy:500,r:radius,fill:'none',stroke:'var(--accent)','stroke-width':43,'stroke-linecap':'round','stroke-dasharray':`${arc*q*progress} ${2*Math.PI*radius}`,transform:'rotate(-90 450 500)',class:'motion-element'});if(type==='gauge'){shape(f,'line',{x1:450,y1:500,x2:450+275*Math.cos(Math.PI*(1-q*progress)),y2:500-275*Math.sin(Math.PI*(1-q*progress)),stroke:'var(--secondary)','stroke-width':14,'stroke-linecap':'round',class:'motion-element'});}}
 else {for(let i=0;i<5;i++)shape(m,'line',{x1:100,y1:210+i*140,x2:800,y2:210+i*140,stroke:'#ffffff18','stroke-width':2,class:'motion-element'});shape(m,'rect',{x:230,y:850-650*progress,width:440,height:Math.max(4,650*progress),rx:38,fill:'var(--accent)',class:'motion-element'});}
 label(f,fmt(value,c.numberProgress)+(d.unit||''),450,type==='bar_grow'?180:530,126,760,'var(--foreground)');label(f,d.label||d.text,450,900,50,800);
 if(d.source)label(f,'Nguồn: '+d.source,450,1080,26,820);
};
paints.line_draw=c=>{const{mid:m,front:f,d,t,p}=c;const bars=d.bars.slice(0,5),lo=Math.min(...bars.map(b=>b.value)),hi=Math.max(lo+1,...bars.map(b=>b.value));const points=bars.map((b,i)=>[100+i*700/(bars.length-1),800-(b.value-lo)/(hi-lo)*570]);shape(m,'polyline',{points:points.map(x=>x.join(',')).join(' '),fill:'none',stroke:'var(--accent)','stroke-width':15,pathLength:1,'stroke-dasharray':1,'stroke-dashoffset':1-ease(p*2),class:'motion-element'});bars.forEach((b,i)=>{dot(f,points[i][0],points[i][1],20,t+i);label(f,fmt(b.value,p*2)+(b.unit||''),points[i][0],points[i][1]-40,52,220);label(f,b.label,points[i][0],950,34,200);});};
paints.flow_chain=c=>{const{mid:m,front:f,d,t,p}=c,items=d.items.slice(0,5),gap=850/Math.max(1,items.length-1);items.forEach((item,i)=>{const x=i%2?500:60,y=70+i*gap*.85;box(m,x,y,340,155,item,c.row(i),t+i);if(i){const x0=(i-1)%2?670:230,y0=70+(i-1)*gap*.85+155;shape(m,'path',{d:`M${x0} ${y0}L${x+170} ${y}`,stroke:'var(--secondary)','stroke-width':8,fill:'none'});const u=(t*.45+i*.3)%1;dot(f,x0+(x+170-x0)*u,y0+(y-y0)*u,15,t+i);}});};
paints.magnifier_check=c=>{
  if(window.MotionRecipes && window.MotionRecipes.renderMagnifierCheck) {
    window.MotionRecipes.renderMagnifierCheck(null, c.mid || c.front, c.d, c.t, c.duration, c);
  }
};
paints.funnel_filter=c=>{const{mid:m,front:f,d,t,p}=c;shape(m,'path',{d:'M80 210H820L550 680V830L350 940V680Z',fill:'#3e668a66',stroke:'var(--secondary)','stroke-width':7,class:'motion-element'});d.items.slice(0,-1).forEach((item,i)=>{const x=170+i*230;box(f,x-110,35,215,145,item,p*3-i*.2,t+i);const u=(t*.33+i*.22)%1;dot(f,x+(450-x)*u,220+u*520,15,t+i);});label(f,d.items.at(-1),450,1030,58,760,'var(--accent)');};
paints.checklist=c=>{
  if(window.MotionRecipes && window.MotionRecipes.renderChecklist) {
    window.MotionRecipes.renderChecklist(null, c.mid || c.front, c.d, c.t, c.duration, 0);
  }
};
paints.terminal_type=c=>{
  if(window.MotionRecipes && window.MotionRecipes.renderTerminalTyping) {
    window.MotionRecipes.renderTerminalTyping(null, c.mid || c.front, c.d, c.t, c.duration, 0);
  }
};
paints.timeline_march=c=>{const{mid:m,front:f,d,t,p}=c;const items=d.items.slice(0,5),span=Math.max(0,items.length*320-780);const g=group(m,{transform:`translate(${-span*p} 0)`,class:'motion-element'});shape(g,'line',{x1:100,y1:570,x2:items.length*320,y2:570,stroke:'var(--accent)','stroke-width':14});items.forEach((item,i)=>{const x=160+i*320;shape(g,'rect',{x:x-115,y:150,width:230,height:730,rx:28,fill:'#13283b',stroke:'#98c3da44','stroke-width':3});dot(g,x,570,33,t+i);label(g,item,x,330,43,210);label(g,item,x,760,32,210);});};
paints.stack_cards=c=>{const{mid:m,front:f,d,t,p}=c;d.items.slice(0,5).forEach((item,i)=>{const g=group(m,{transform:`translate(${15*Math.sin(t*.6+i)} ${i*195}) rotate(${(i-2)*1.2+Math.sin(t*.4)*.5} 450 140)`,class:'motion-element'});box(g,105,55,690,170,item,c.row(i),t+i);});};
paints.network_nodes=c=>{
  if(window.MotionRecipes && window.MotionRecipes.renderNetworkNodes) {
    window.MotionRecipes.renderNetworkNodes(null, c.mid || c.front, c.d, c.t, c.duration, 0);
  }
};

// Register all legacy paints into registry
for (const [k, v] of Object.entries(paints)) {
  registry[k] = v;
}
registry.bar_grow = paints.numeric;
registry.ring = paints.numeric;
registry.gauge = paints.numeric;

function register(name,paint){registry[name]=paint;}
let current=null;

function draw(host,spec,t,duration,C){
 if(!spec||!window.anime)return false;
 const stype = spec.scene_type || 'stat_number';

 host.replaceChildren();
 const holder=document.createElement('div');
 holder.className='scene-art';
 holder.dataset.sceneType=stype;
 holder.innerHTML=(window.MOTION_SCENE_HTML||{})[stype]||'<svg viewBox="0 0 1080 1920" width="1080" height="1920"></svg>';
 host.append(holder);

 const svg=holder.querySelector('svg');
 const back=group(svg,{class:'depth-background',transform:`translate(${14*Math.sin(t*.21)} ${18*Math.cos(t*.19)})`});
 for(let i=0;i<4;i++){shape(back,'circle',{cx:180+(i%2)*720,cy:320+Math.floor(i/2)*860,r:110+30*Math.sin(t*.7+i),fill:'var(--accent)',opacity:.06,class:'motion-element'});}
 const defs=el('defs');defs.innerHTML='<clipPath id="content-safe-clip"><rect x="70" y="240" width="940" height="1090" rx="24"/></clipPath>';svg.prepend(defs);
 const cam=spec.camera||{},p=clamp(t/Math.max(.1,duration)),amount=Math.min(.05,Math.max(.02,cam.amount||.04));
 const zoom=cam.kind==='pull_out'?1+amount*(1-p):1+amount*p,tx=cam.kind==='pan_left'?-amount*240*p:cam.kind==='pan_right'?amount*240*p:0;
 const mid=group(svg,{class:'depth-middle',transform:`translate(${540+tx} 785) scale(${zoom}) translate(-540 -785)`,'clip-path':'url(#content-safe-clip)'});
 const front=group(svg,{class:'depth-foreground',transform:`translate(${8*Math.sin(t*.45)} ${8*Math.cos(t*.4)})`});
 const beats=spec.beats||[],at=(action,otherwise)=>beats.find(b=>b.action===action)?.at_sec??otherwise,start=at('count_up',0),finish=at('count_end',start+1.2);
 const context={svg,back,mid,front,d:spec.data,t,p,type:stype,duration,hold:C.min_card_hold_sec||1.2,numberProgress:clamp((t-start)/Math.max(.1,finish-start)),row:i=>ease((t-at('reveal_item_'+i,.15+i*.7))/.35)};

 if (window.MotionVocabulary && typeof window.MotionVocabulary[stype] === 'function') {
   window.MotionVocabulary[stype](null, mid, spec.data, t, duration);
 } else if (window.MotionRecipes) {
   if (stype === 'stat_number' || stype === 'stat_card') {
     window.MotionRecipes.renderStatNumber(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'bar_compare' || stype === 'bar_grow' || stype === 'compare_bars') {
     window.MotionRecipes.renderBarCompare(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'ring' || stype === 'gauge' || stype === 'gauge_ring' || stype === 'ring_percent') {
     window.MotionRecipes.renderGaugeRing(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'line_draw' || stype === 'line_chart_draw') {
     window.MotionRecipes.renderLineChartDraw(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'flow_chain') {
     window.MotionRecipes.renderFlowChain(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'hub_spoke' || stype === 'network_nodes') {
     window.MotionRecipes.renderNetworkNodes(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'stack_cards') {
     window.MotionRecipes.renderStackCards(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'checklist' || stype === 'steps_list' || stype === 'steps_ladder') {
     window.MotionRecipes.renderChecklist(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'mock_ui_window') {
     window.MotionRecipes.renderMockUIWindow(null, mid, spec.data, t, duration);
   } else if (stype === 'magnifier_check') {
     window.MotionRecipes.renderMagnifierCheck(null, mid, spec.data, t, duration, context);
   } else if (stype === 'versus_scale' || stype === 'versus_split') {
     window.MotionRecipes.renderVersusScale(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'terminal_typing' || stype === 'terminal_type' || stype === 'code_card') {
     window.MotionRecipes.renderTerminalTyping(null, front, spec.data, t, duration, 0);
   } else if (stype === 'timeline_march' || stype === 'timeline') {
     window.MotionRecipes.renderTimeline(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'funnel_filter' || stype === 'funnel') {
     window.MotionRecipes.renderFunnel(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'progress_tracker') {
     window.MotionRecipes.renderProgressTracker(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'source_badge') {
     window.MotionRecipes.renderSourceBadge(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'icon_tile') {
     window.MotionRecipes.renderIconTile(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'chat_bubble_poll') {
     window.MotionRecipes.renderChatBubblePoll(null, mid, spec.data, t, duration, 0);
   } else if (registry[stype]) {
     registry[stype](context);
   } else {
     window.MotionRecipes.renderTextFocus(null, mid, spec.data, t, duration, 0);
   }
 } else if (registry[stype]) {
   registry[stype](context);
 } else {
   paints.numeric(context);
 }

 // Render Source line at bottom of content zone if present
 if (spec.data && spec.data.source && window.MotionRecipes && window.MotionRecipes.renderSourceBadge && stype !== 'source_badge') {
   window.MotionRecipes.renderSourceBadge(null, front, spec.data, t, duration, 0);
 }

 // Render Annotations (strike, stamp, underline)
 const annots = spec.annotations || (C && C.annotations) || [];
 if (annots.length && window.MotionRecipes && window.MotionRecipes.renderAnnotation) {
   annots.forEach(annot => {
     const bounds = { x: 200, y: 350, w: 680, h: 200 };
     window.MotionRecipes.renderAnnotation(front, annot, bounds, t);
   });
 }

 // Check for text overlaps and apply 1-pass layout repair
 if (window.MotionLayout && window.MotionLayout.repairCollisions) {
   try {
     const textNodes = [...svg.querySelectorAll('.ill-label, text')];
     if (textNodes.length >= 2) {
       const boxes = textNodes.map(node => {
         const b = node.getBBox ? node.getBBox() : { x: 0, y: 0, width: 0, height: 0 };
         return { node, x: b.x, y: b.y, w: b.width, h: b.height };
       }).filter(b => b.w > 0 && b.h > 0);
       const repaired = window.MotionLayout.repairCollisions(boxes);
       repaired.forEach((rep, idx) => {
         if (boxes[idx] && (rep.x !== boxes[idx].x || rep.y !== boxes[idx].y)) {
           boxes[idx].node.setAttribute('transform', `translate(0, ${rep.y - boxes[idx].y})`);
         }
       });
     }
   } catch(e) {}
 }

 current={scene_type:stype,moving_elements:svg.querySelectorAll('.motion-element, text, rect, circle, line, path').length,area_ratio:.56};
 return true;
}

function metrics(){return current;}
function clear(){current=null;}
window.MotionScenes={register,draw,metrics,clear,paint:paints};
})();
