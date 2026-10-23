/* All state is a pure function of absolute seconds. No timers/CSS animations. */
(()=>{'use strict';
const C=window.MOTION_DATA, stage=document.getElementById('stage');
const clamp=x=>Math.max(0,Math.min(1,x));
const easeOutCubic=x=>1-Math.pow(1-clamp(x),3);
const easeOutBack=x=>{x=clamp(x)-1;return 1+2.70158*x*x*x+1.70158*x*x;};
const countUp=(v,p)=>Number(v||0)*easeOutCubic(p);
const fadeSlideIn=(el,p,back=false)=>{el.style.opacity=clamp(p);el.style.transform=`translateY(${(1-(back?easeOutBack(p):easeOutCubic(p)))*65}px)`;};
const growBar=(el,p)=>el.style.transform=`scaleX(${easeOutCubic(p)})`;
const ringPercent=(p)=>`conic-gradient(var(--accent) ${clamp(p)*360}deg,#ffffff18 0deg)`;
const typing=(text,p)=>String(text).slice(0,Math.round(String(text).length*clamp(p)));
const strikeThenReplace=(el,oldValue,newValue,p)=>{el.replaceChildren();const old=node('span','old',oldValue),line=node('span','strike');line.style.width='100%';line.style.transform=`scaleX(${clamp(p*2)})`;old.append(line);const fresh=node('span','new',newValue);fresh.style.opacity=clamp((p-.45)*2);el.append(old,fresh);};
window.Motion={easeOutCubic,easeOutBack,fadeSlideIn,countUp,strikeThenReplace,growBar,ringPercent,typing};
function node(tag,cls,text){const n=document.createElement(tag);n.className=cls||'';if(text!==undefined)n.textContent=String(text);return n;}
const fmt=n=>Number.isInteger(n)?Math.round(n).toLocaleString('vi-VN'):n.toLocaleString('vi-VN',{maximumFractionDigits:2});
const short=(s,n=140)=>String(s||'').slice(0,n);
stage.style.setProperty('--w',C.width+'px');stage.style.setProperty('--h',C.height+'px');
stage.style.setProperty('--accent',C.captions.highlight_color||'#ffc84a');stage.style.setProperty('--stroke',C.captions.stroke_color||'#000');
const baseWidth=C.width, ratio=baseWidth/1080;
const profileStyle=document.createElement('style');profileStyle.textContent='.word{-webkit-text-stroke-width:'+Math.max(2,Math.round(1080*(C.captions.stroke_width_ratio||.006)))+'px}';document.head.append(profileStyle);
// Layout uses a stable 1080px design grid, scaled only after composition.
stage.style.width='1080px';stage.style.height=(C.height/ratio)+'px';stage.style.transform=`scale(${ratio})`;
const background=node('div');stage.append(background);for(let i=0;i<7;i++){const orb=node('div','orb');orb.style.cssText=`width:${170+i*21}px;height:${170+i*21}px;left:${(i*173)%950}px;top:${(i*293)%1700}px`;background.append(orb);}
const content=node('div','content'),caption=node('div'),footer=node('div');caption.id='captions';footer.id='footer';footer.append(node('span'));stage.append(content,caption,footer);
const words=C.words||[];const groups=[];for(let i=0;i<words.length;i+=3)groups.push(words.slice(i,i+3));if(groups.length>1&&groups.at(-1).length===1)groups.at(-2).push(...groups.pop());
function revealTime(shot,i,count){const beats=shot.beats||[];const b=beats[i];if(b){if(Number.isFinite(b.at_sec))return b.at_sec;if(Number.isInteger(b.at_word_index)&&words[b.at_word_index])return words[b.at_word_index].start;}return shot.start+i*Math.min(1.35,shot.duration/Math.max(1,count));}
function eventTime(shot,action,fallback){const b=(shot.beats||[]).find(b=>b.action===action);if(!b)return fallback;if(Number.isFinite(b.at_sec))return b.at_sec;if(Number.isInteger(b.at_word_index)&&words[b.at_word_index])return words[b.at_word_index].start;return fallback;}
function titleText(text,highlights){const title=node('div','title');const marks=(highlights||[]).map(x=>x.toLocaleLowerCase());for(const token of short(text,110).split(/\s+/)){const span=node('span',marks.some(x=>token.toLocaleLowerCase().includes(x))?'accent':'',token+' ');title.append(span);}return title;}
window.renderAt=function(t){
 t=Math.max(0,Math.min(C.duration,t));content.replaceChildren();caption.replaceChildren();
 const shot=C.shots.find(s=>t>=s.start&&t<s.start+s.duration)||C.shots.at(-1);if(!shot)return;
 const d=shot.data||{},local=Math.max(0,t-shot.start),entry=easeOutBack(local/.55),exit=clamp((C.duration-t)/.2);content.style.opacity=exit;content.style.transform=`scale(${.95+.05*entry})`;
 const name=shot.template;
 if(name==='hook_card'){
  const title=titleText(d.text||d.title||d.label,d.highlight);content.append(title);fadeSlideIn(title,(t-eventTime(shot,'reveal',shot.start))/.5,true);
  if(d.value!==null&&d.value!==undefined){const number=node('div','number',fmt(countUp(d.value,(t-eventTime(shot,'count_up',shot.start))/1.25))+(d.unit||''));content.append(number);}
  if(d.source||d.label){const badge=node('div','badge',short(d.source||d.label,50));content.append(badge);fadeSlideIn(badge,(t-eventTime(shot,'badge',shot.start+.25))/.4);}
 }else if(name==='steps_list'){
  if(d.text)content.append(node('div','eyebrow',short(d.text,65)));
  const items=(d.items||[]).slice(0,4);let current=-1;items.forEach((_,i)=>{if(t>=revealTime(shot,i,items.length))current=i;});
  items.forEach((text,i)=>{const row=node('div','row'+(i===current?' active':''));row.append(node('span','tick',i<current?'✓':String(i+1).padStart(2,'0')),node('span','',short(text,105)));content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,items.length))/.45);});
 }else if(name==='compare_bars'){
  if(d.text)content.append(titleText(d.text, d.highlight));const bars=(d.bars||[]).slice(0,4),maximum=Math.max(1,...bars.map(b=>Math.abs(b.value||0)));
  bars.forEach((b,i)=>{const p=clamp((t-revealTime(shot,i,bars.length))/.9),row=node('div','bar-row'),label=node('div','bar-label'),value=node('span');label.append(node('span','',short(b.label,48)),value);if(i>0&&(shot.beats||[]).some(beat=>beat.action==="strike_replace"))strikeThenReplace(value,fmt(bars[i-1].value),fmt(countUp(b.value,p))+(b.unit||''),p);else value.textContent=fmt(countUp(b.value,p))+(b.unit||'');const track=node('div','bar-track'),fill=node('div','bar-fill');fill.style.width=(Math.abs(b.value||0)/maximum*100)+'%';growBar(fill,p);track.append(fill);row.append(label,track);content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,bars.length))/.45);});
 }
 // Shrink long copy in a fixed graphic-safe area, never covering captions.
 content.style.fontSize='';for(const el of content.querySelectorAll('.title,.row,.bar-label')){let size=parseFloat(getComputedStyle(el).fontSize);while((el.scrollWidth>el.clientWidth+1||content.scrollHeight>content.clientHeight+1)&&size>22){size-=2;el.style.fontSize=size+'px';}}
 if(C.captions.enabled!==false){const group=groups.find(g=>t>=g[0].start&&t<g.at(-1).end);if(group){for(const w of group){const active=t>=w.start&&t<w.end;const el=node('span','word'+(active?' current':'')+(C.captions.appearance==='pill'?' pill':''),short(w.text,60));if(!active)el.style.color=C.captions.color||'#fff';caption.append(el);}let fs=Math.round(1080*(C.captions.font_scale||.064));caption.style.fontSize=fs+'px';while(caption.scrollHeight>caption.clientHeight+1&&fs>26){fs-=2;caption.style.fontSize=fs+'px';}}}
 footer.firstChild.style.transform=`scaleX(${clamp(t/C.duration)})`;
 [...background.children].forEach((orb,i)=>{orb.style.transform=`translate(${Math.sin(t*.15+i)*15}px,${Math.cos(t*.12+i)*19}px)`;orb.style.opacity=.5+.15*Math.sin(t*.4+i);});
 return {time:t,template:name};
};window.renderAt(0);
})();
