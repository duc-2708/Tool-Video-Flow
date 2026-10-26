/* Original vector illustrations. anime.js easing only: no playing timelines. */
(()=>{'use strict';
const registry={},NS='http://www.w3.org/2000/svg',clamp=x=>Math.max(0,Math.min(1,x));
const ease=p=>window.anime?anime.easing('easeOutCubic')(clamp(p)):clamp(p);
function el(tag,attrs={},text){const n=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=String(text);return n;}
function group(parent,attrs={}){const n=el('g',attrs);parent.append(n);return n;}
function shape(parent,tag,attrs){const n=el(tag,attrs);parent.append(n);return n;}
function label(parent,text,x,y,size=52,width=650,colour){
 const words=String(text||'').split(/\s+/).filter(Boolean).slice(0,6),lines=[];
 for(let i=0;i<words.length;i+=2)lines.push(words.slice(i,i+2).join(' '));
 const n=el('text',{x,y,'text-anchor':'middle','font-size':size,...(colour?{fill:colour}:{}),class:'ill-label'});
 lines.forEach((line,i)=>n.append(el('tspan',{x,dy:i?size*1.15:0},line)));parent.append(n);
 let fs=size;const spans=[...n.querySelectorAll('tspan')];
 while(Math.max(0,...spans.map(s=>s.getComputedTextLength()))>width&&fs>24){fs-=2;n.setAttribute('font-size',fs);spans.forEach((s,i)=>s.setAttribute('dy',i?fs*1.15:0));}return n;
}
function box(parent,x,y,w,h,text,p,t){const g=group(parent,{class:'motion-element',transform:`translate(0 ${14*Math.sin(t*.55+x)}) scale(1)`});shape(g,'rect',{x,y,width:w,height:h,rx:30,fill:'#162a43',stroke:p>.5?'var(--accent)':'#6687aa88','stroke-width':4});const lines=Math.max(1,Math.ceil(Math.min(6,String(text).split(/\s+/).length)/2)),fs=Math.min(54,w*.18,h/(lines*1.3));label(g,text,x+w/2,y+h/2-(lines-1)*fs*.575+fs*.3,fs,w*.9);return g;}
function dot(parent,x,y,r,t){return shape(parent,'circle',{class:'motion-element',cx:x+10*Math.sin(t),cy:y+10*Math.cos(t*.8),r:r*(1+.06*Math.sin(t*2)),fill:'var(--accent)',opacity:.7});}
const fmt=(value,progress=1)=>{const precision=Number.isInteger(value)?0:Math.min(6,(String(value).split('.')[1]||'').length);return (value*ease(progress)).toLocaleString('vi-VN',{minimumFractionDigits:0,maximumFractionDigits:precision});};
const paints={};
paints.versus_scale=c=>{const {mid:m,front:f,d,t,p}=c;const sides=d.bars?.length>=2?d.bars.slice(0,2):d.items.slice(0,2).map(label=>({label}));
 sides.forEach((b,i)=>{box(m,35+i*450,150,380,570,b.label,ease(p*3-i*.25),t);if(Number.isFinite(b.value))label(f,fmt(b.value,p*2)+(b.unit||''),225+i*450,610,100,340,'var(--accent)');});
 const a=sides[0]?.value,b=sides[1]?.value,tilt=Number.isFinite(a)&&Number.isFinite(b)?Math.sign(b-a)*12*ease(p*2):0;const beam=group(f,{class:'motion-element',transform:`rotate(${tilt} 450 810)`});shape(beam,'path',{d:'M120 810H780M450 810V960',stroke:'var(--accent)','stroke-width':18,fill:'none'});shape(f,'circle',{cx:450,cy:415,r:67,fill:'var(--accent)',class:'motion-element'});label(f,'VS',450,440,61,140,'#0c1829');};
paints.numeric=c=>{const {mid:m,front:f,d,t,p,type}=c;const value=d.value??0,percent=d.unit==='%',q=percent?clamp(value/100):1,progress=ease(c.numberProgress);
 if(type==='ring'||type==='gauge'){const radius=320,arc=type==='gauge'?Math.PI*radius:2*Math.PI*radius;shape(m,'circle',{cx:450,cy:500,r:radius,fill:'none',stroke:'#ffffff18','stroke-width':43,class:'motion-element'});shape(m,'circle',{cx:450,cy:500,r:radius,fill:'none',stroke:'var(--accent)','stroke-width':43,'stroke-linecap':'round','stroke-dasharray':`${arc*q*progress} ${2*Math.PI*radius}`,transform:'rotate(-90 450 500)',class:'motion-element'});if(type==='gauge'){shape(f,'line',{x1:450,y1:500,x2:450+275*Math.cos(Math.PI*(1-q*progress)),y2:500-275*Math.sin(Math.PI*(1-q*progress)),stroke:'var(--secondary)','stroke-width':14,'stroke-linecap':'round',class:'motion-element'});}}
 else {for(let i=0;i<5;i++)shape(m,'line',{x1:100,y1:210+i*140,x2:800,y2:210+i*140,stroke:'#ffffff18','stroke-width':2,class:'motion-element'});shape(m,'rect',{x:230,y:850-650*progress,width:440,height:Math.max(4,650*progress),rx:38,fill:'var(--accent)',class:'motion-element'});}
 label(f,fmt(value,c.numberProgress)+(d.unit||''),450,type==='bar_grow'?180:530,126,760,'var(--foreground)');label(f,d.label||d.text,450,900,50,800);
 if(d.source)label(f,'Nguồn: '+d.source,450,1080,26,820);
};
paints.line_draw=c=>{const{mid:m,front:f,d,t,p}=c;const bars=d.bars.slice(0,5),lo=Math.min(...bars.map(b=>b.value)),hi=Math.max(lo+1,...bars.map(b=>b.value));const points=bars.map((b,i)=>[100+i*700/(bars.length-1),800-(b.value-lo)/(hi-lo)*570]);shape(m,'polyline',{points:points.map(x=>x.join(',')).join(' '),fill:'none',stroke:'var(--accent)','stroke-width':15,pathLength:1,'stroke-dasharray':1,'stroke-dashoffset':1-ease(p*2),class:'motion-element'});bars.forEach((b,i)=>{dot(f,points[i][0],points[i][1],20,t+i);label(f,fmt(b.value,p*2)+(b.unit||''),points[i][0],points[i][1]-40,52,220);label(f,b.label,points[i][0],950,34,200);});};
paints.flow_chain=c=>{const{mid:m,front:f,d,t,p}=c,items=d.items.slice(0,5),gap=850/Math.max(1,items.length-1);items.forEach((item,i)=>{const x=i%2?500:60,y=70+i*gap*.85;box(m,x,y,340,155,item,c.row(i),t+i);if(i){const x0=(i-1)%2?670:230,y0=70+(i-1)*gap*.85+155;shape(m,'path',{d:`M${x0} ${y0}L${x+170} ${y}`,stroke:'var(--secondary)','stroke-width':8,fill:'none'});const u=(t*.45+i*.3)%1;dot(f,x0+(x+170-x0)*u,y0+(y-y0)*u,15,t+i);}});};
paints.magnifier_check=c=>{const{mid:m,front:f,d,t,p}=c;shape(m,'rect',{x:75,y:70,width:750,height:900,rx:35,fill:'#14283e',stroke:'#91c6e277','stroke-width':5});d.items.slice(0,5).forEach((item,i)=>{const y=210+i*150;shape(m,'line',{x1:130,y1:y+55,x2:760,y2:y+55,stroke:'#ffffff24','stroke-width':3});label(m,item,430,y,47,540);const mark=/\b(sai|không|giả)\b/i.test(item)?'✗':/đúng|xác nhận|có căn cứ/i.test(item)?'✓':'·';const verdict=label(f,mark,755,y,66,90,'var(--accent)');verdict.classList.add('verdict');verdict.setAttribute('opacity',c.row(i));});const x=380+180*Math.sin(t*.75),y=420+230*Math.cos(t*.5);shape(f,'circle',{cx:x,cy:y,r:135,fill:'#85d9f018',stroke:'var(--accent)','stroke-width':16,class:'motion-element'});shape(f,'line',{x1:x+95,y1:y+95,x2:x+200,y2:y+210,stroke:'var(--accent)','stroke-width':30,'stroke-linecap':'round',class:'motion-element'});};
paints.funnel_filter=c=>{const{mid:m,front:f,d,t,p}=c;shape(m,'path',{d:'M80 210H820L550 680V830L350 940V680Z',fill:'#3e668a66',stroke:'var(--secondary)','stroke-width':7,class:'motion-element'});d.items.slice(0,-1).forEach((item,i)=>{const x=170+i*230;box(f,x-110,35,215,145,item,p*3-i*.2,t+i);const u=(t*.33+i*.22)%1;dot(f,x+(450-x)*u,220+u*520,15,t+i);});label(f,d.items.at(-1),450,1030,58,760,'var(--accent)');};
paints.checklist=c=>{const{mid:m,front:f,d,t,p}=c;d.items.slice(0,5).forEach((item,i)=>{const y=85+i*190;box(m,65,y,770,155,item,c.row(i),t+i);shape(f,'circle',{cx:125,cy:y+80,r:31,fill:c.row(i)>.5?'var(--accent)':'#506a84',class:'motion-element'});if(c.row(i)>.5)label(f,'✓',125,y+98,46,70,'#0c1829');});};
paints.terminal_type=c=>{const{mid:m,front:f,d,t,p,hold,duration}=c;shape(m,'rect',{x:40,y:110,width:820,height:820,rx:28,fill:'#091c29',stroke:'var(--secondary)','stroke-width':5});for(let i=0;i<3;i++)dot(f,90+i*45,160,12,t+i);const available=Math.max(.1,duration-hold),typed=clamp(t/available);d.items.slice(0,5).forEach((item,i)=>{const count=Math.floor(String(item).length*clamp(typed*d.items.length-i));const y=285+i*135;shape(m,'rect',{x:75,y:y-65,width:750,height:110,rx:15,fill:typed*d.items.length>=i&&typed*d.items.length<i+1?'#26546c':'#ffffff06',class:'motion-element'});label(f,'› '+String(item).slice(0,count),450,y,46,700);});dot(f,775,855,14,t);};
paints.timeline_march=c=>{const{mid:m,front:f,d,t,p}=c;const items=d.items.slice(0,5),span=Math.max(0,items.length*320-780);const g=group(m,{transform:`translate(${-span*p} 0)`,class:'motion-element'});shape(g,'line',{x1:100,y1:570,x2:items.length*320,y2:570,stroke:'var(--accent)','stroke-width':14});items.forEach((item,i)=>{const x=160+i*320;shape(g,'rect',{x:x-115,y:150,width:230,height:730,rx:28,fill:'#13283b',stroke:'#98c3da44','stroke-width':3});dot(g,x,570,33,t+i);label(g,item,x,330,43,210);label(g,item,x,760,32,210);});};
paints.stack_cards=c=>{const{mid:m,front:f,d,t,p}=c;d.items.slice(0,5).forEach((item,i)=>{const g=group(m,{transform:`translate(${15*Math.sin(t*.6+i)} ${i*195}) rotate(${(i-2)*1.2+Math.sin(t*.4)*.5} 450 140)`,class:'motion-element'});box(g,105,55,690,170,item,c.row(i),t+i);});};
paints.network_nodes=c=>{const{mid:m,front:f,d,t,p}=c;const items=d.items.slice(0,5),locations=[[450,520],[175,180],[725,190],[180,860],[725,855]];items.forEach((item,i)=>{const[x,y]=locations[i];if(i)shape(m,'line',{x1:450,y1:520,x2:x,y2:y,stroke:'var(--secondary)','stroke-width':7,opacity:.6});const u=(t*.35+i*.2)%1;if(i)dot(f,450+(x-450)*u,520+(y-520)*u,12,t+i);shape(m,'circle',{cx:x+8*Math.sin(t*.6+i),cy:y+9*Math.cos(t*.5+i),r:i?140:190,fill:i?'#1a344d':'#23526a',stroke:'var(--accent)','stroke-width':5,class:'motion-element'});label(f,item,x,y-20,i?45:62,i?240:330);});};

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
 if(!registry[stype] && (!window.MotionRecipes || !window.MotionRecipes.renderStatNumber)) return false;

 host.replaceChildren();
 const holder=document.createElement('div');
 holder.className='scene-art';
 holder.dataset.sceneType=stype;
 holder.innerHTML=(window.MOTION_SCENE_HTML||{})[stype]||'<svg viewBox="0 0 900 1100"></svg>';
 host.append(holder);

 const svg=holder.querySelector('svg');
 const back=group(svg,{class:'depth-background',transform:`translate(${12*Math.sin(t*.21)} ${16*Math.cos(t*.19)})`});
 for(let i=0;i<4;i++){shape(back,'circle',{cx:130+i%2*620,cy:140+Math.floor(i/2)*760,r:80+24*Math.sin(t*.7+i),fill:'var(--accent)',opacity:.07,class:'motion-element'});}
 const cam=spec.camera||{},p=clamp(t/Math.max(.1,duration)),amount=Math.min(.08,Math.max(.04,cam.amount||.06));
 const zoom=cam.kind==='pull_out'?1+amount*(1-p):1+amount*p,tx=cam.kind==='pan_left'?-amount*700*p:cam.kind==='pan_right'?amount*700*p:0;
 const mid=group(svg,{class:'depth-middle',transform:`translate(${450+tx} 550) scale(${zoom}) translate(-450 -550)`});
 const front=group(svg,{class:'depth-foreground',transform:`translate(${8*Math.sin(t*.45)} ${8*Math.cos(t*.4)})`});
 const beats=spec.beats||[],at=(action,otherwise)=>beats.find(b=>b.action===action)?.at_sec??otherwise,start=at('count_up',0),finish=at('count_end',start+1.2);
 const context={svg,back,mid,front,d:spec.data,t,p,type:stype,duration,hold:C.min_card_hold_sec||1.2,numberProgress:clamp((t-start)/Math.max(.1,finish-start)),row:i=>ease((t-at('reveal_item_'+i,.15+i*.6))/.35)};

 if (window.MotionRecipes) {
   if (stype === 'stat_number') {
     window.MotionRecipes.renderStatNumber(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'bar_compare') {
     window.MotionRecipes.renderBarCompare(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'flow_chain') {
     window.MotionRecipes.renderFlowChain(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'hub_spoke') {
     window.MotionRecipes.renderHubSpoke(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'container_fill') {
     window.MotionRecipes.renderContainerFill(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'checklist') {
     window.MotionRecipes.renderChecklist(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'mock_ui_window') {
     window.MotionRecipes.renderMockUIWindow(null, mid, spec.data, t, duration);
   } else if (stype === 'magnifier_check') {
     window.MotionRecipes.renderMagnifierCheck(null, mid, spec.data, t, duration, context);
   } else if (stype === 'versus_split') {
     window.MotionRecipes.renderVersusSplit(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'line_chart_draw') {
     window.MotionRecipes.renderLineChartDraw(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'terminal_typing' || stype === 'code_card') {
     window.MotionRecipes.renderTerminalTyping(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'timeline') {
     window.MotionRecipes.renderTimeline(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'funnel') {
     window.MotionRecipes.renderFunnel(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'progress_tracker') {
     window.MotionRecipes.renderProgressTracker(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'source_badge') {
     window.MotionRecipes.renderSourceBadge(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'icon_tile') {
     window.MotionRecipes.renderIconTile(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'chat_bubble_poll') {
     window.MotionRecipes.renderChatBubblePoll(null, mid, spec.data, t, duration, 0);
   } else if (stype === 'gauge_ring') {
     window.MotionRecipes.renderGaugeRing(null, mid, spec.data, t, duration, 0);
   } else if (registry[stype]) {
     registry[stype](context);
   } else {
     paints.numeric(context);
   }
 } else if (registry[stype]) {
   registry[stype](context);
 } else {
   paints.numeric(context);
 }

 // Render Annotations (strike, stamp, underline)
 const annots = spec.annotations || (C && C.annotations) || [];
 if (annots.length && window.MotionRecipes && window.MotionRecipes.renderAnnotation) {
   annots.forEach(annot => {
     const bounds = { x: 200, y: 350, w: 500, h: 200 };
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
