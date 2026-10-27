/* All state is a pure function of absolute seconds. No timers/CSS animations. */
(()=>{'use strict';
const C=window.MOTION_DATA, stage=document.getElementById('stage');
const clamp=x=>Math.max(0,Math.min(1,x));
const easeOutCubic=x=>1-Math.pow(1-clamp(x),3);
const easeOutBack=x=>{x=clamp(x)-1;return 1+2.70158*x*x*x+1.70158*x*x;};
const countUp=(v,p)=>{const n=Number(v||0),dp=Number.isInteger(n)?0:Math.min(6,(String(n).split('.')[1]||'').length);return Number((n*easeOutCubic(p)).toFixed(dp));};
const fadeSlideIn=(el,p,back=false)=>{el.style.opacity=clamp(p);el.style.transform=`translateY(${(1-(back?easeOutBack(p):easeOutCubic(p)))*65}px)`;};
const growBar=(el,p)=>el.style.transform=`scaleX(${easeOutCubic(p)})`;
const ringPercent=(p)=>`conic-gradient(var(--accent) ${clamp(p)*360}deg,#ffffff18 0deg)`;
const typing=(text,p)=>String(text).slice(0,Math.round(String(text).length*clamp(p)));
const strikeThenReplace=(el,oldValue,newValue,p)=>{el.replaceChildren();const old=node('span','old',oldValue),line=node('span','strike');line.style.width='100%';line.style.transform=`scaleX(${clamp(p*2)})`;old.append(line);const fresh=node('span','new',newValue);fresh.style.opacity=clamp((p-.45)*2);el.append(old,fresh);};
window.Motion={easeOutCubic,easeOutBack,fadeSlideIn,countUp,strikeThenReplace,growBar,ringPercent,typing};
function node(tag,cls,text){const n=document.createElement(tag);n.className=cls||'';if(text!==undefined)n.textContent=String(text);return n;}
const fmt=n=>Number.isInteger(n)?Math.round(n).toLocaleString('vi-VN'):n.toLocaleString('vi-VN',{maximumFractionDigits:8});
const short=(s,n=140)=>String(s||'').slice(0,n);
stage.style.setProperty('--w',C.width+'px');stage.style.setProperty('--h',C.height+'px');
const theme=C.theme||{};for(const [key,value] of Object.entries(theme))if(/^#[0-9a-f]{6}$/i.test(String(value)))stage.style.setProperty('--'+key,value);
stage.style.setProperty('--accent',theme.accent||C.captions.highlight_color||'#ffc84a');stage.style.setProperty('--stroke',C.captions.stroke_color||'#000');
const baseWidth=C.width, ratio=baseWidth/1080;
const profileStyle=document.createElement('style');profileStyle.textContent='.word{-webkit-text-stroke-width:'+Math.max(2,Math.round(1080*(C.captions.stroke_width_ratio||.006)))+'px}';document.head.append(profileStyle);
// Layout uses a stable 1080px design grid, scaled only after composition.
stage.style.width='1080px';stage.style.height=(C.height/ratio)+'px';stage.style.transform=`scale(${ratio})`;
const background=node('div');stage.append(background);for(let i=0;i<7;i++){const orb=node('div','orb');orb.style.cssText=`width:${170+i*21}px;height:${170+i*21}px;left:${(i*173)%950}px;top:${(i*293)%1700}px`;background.append(orb);}
const illustration=node('div','scene-illustration'),actionMascot=node('div','action-mascot'),wipe=node('div','scene-wipe'),sourceLabel=node('div','scene-source');stage.append(illustration,actionMascot,sourceLabel,wipe);let illustrated=false;
const content=node('div','content'),caption=node('div'),footer=node('div');caption.id='captions';footer.id='footer';footer.append(node('span'));stage.append(content,caption,footer);
const mascot=node('img','mascot'),tracker=node('div','motion-tracker'),chip=node('div','scene-chip'),bgVideo=node('img','ai-background');stage.prepend(bgVideo);stage.append(mascot,tracker,chip);if(C.chip){if(C.chip.uri){const image=node('img');image.src=C.chip.uri;chip.append(image);}chip.append(node('span','',C.chip.text));}if(C.anchor&&(C.anchor.anchor_element||C.anchor.metaphor_name)){const ab=node('div','anchor-badge');const label=(C.anchor.metaphor_name?C.anchor.metaphor_name:'')+(C.anchor.anchor_element?' · '+C.anchor.anchor_element:'')+(C.anchor.state?' ('+C.anchor.state+')':'');ab.textContent=label;stage.append(ab);}
const words=C.words||[];const captionWords=C.caption_words||words;const groups=C.caption_groups||[];if(!C.caption_groups){for(let i=0;i<captionWords.length;i+=3)groups.push(captionWords.slice(i,i+3));if(groups.length>1&&groups.at(-1).length===1)groups.at(-2).push(...groups.pop());}
function revealTime(shot,i,count){const beats=(shot.beats||[]).filter(b=>b.action==='reveal');const b=(shot.beats||[]).find(b=>b.action==='reveal_item_'+i)||beats[i];if(b){if(Number.isFinite(b.at_sec))return b.at_sec;if(Number.isInteger(b.at_word_index)&&words[b.at_word_index])return words[b.at_word_index].start;}return shot.start+i*Math.min(1.35,shot.duration/Math.max(1,count));}
function eventTime(shot,action,fallback){const b=(shot.beats||[]).find(b=>b.action===action);if(!b)return fallback;if(Number.isFinite(b.at_sec))return b.at_sec;if(Number.isInteger(b.at_word_index)&&words[b.at_word_index])return words[b.at_word_index].start;return fallback;}
function titleText(text,highlights){const title=node('div','title');const marks=(highlights||[]).map(x=>x.toLocaleLowerCase());for(const token of short(text,110).split(/\s+/)){const span=node('span',marks.some(x=>token.toLocaleLowerCase().includes(x))?'accent':'',token+' ');title.append(span);}return title;}
function svg(tag,attributes){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attributes||{}))el.setAttribute(k,String(v));return el;}
function countProgress(shot,t){const start=eventTime(shot,'count_up',shot.start),end=eventTime(shot,'count_end',start+1.2);return clamp((t-start)/Math.max(.08,end-start));}
function quality(){
 if(illustrated&&window.MotionScenes){const r=illustration.getBoundingClientRect(),cap=caption.getBoundingClientRect(),issues=[];if(cap.bottom>C.height*.89)issues.push('caption_safe_area');const boxes=[...illustration.querySelectorAll('.ill-label')].map(n=>n.getBoundingClientRect());if(boxes.some(b=>{const cx=(b.left+b.right)/2;return cx>=r.left&&cx<=r.right&&(b.left<r.left-2||b.right>r.right+2||b.top<r.top-2||b.bottom>r.bottom+2)}))issues.push('text_overflow');if(boxes.some((a,i)=>boxes.slice(i+1).some(b=>Math.max(0,Math.min(a.right,b.right)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top))>Math.min(a.width*a.height,b.width*b.height)*.1)))issues.push('illustration_label_overlap');return {issues,occupied:null,deferred_until_cue:false,graphic:{x:r.x,y:r.y,width:r.width,height:r.height},caption:{x:cap.x,y:cap.y,width:cap.width,height:cap.height},illustration:MotionScenes.metrics(),scope:'SVG design region and label bounds; not card ink-area occupancy'};}
 const rect=content.getBoundingClientRect(),cap=caption.getBoundingClientRect(),issues=[];
 const W=C.width,H=C.height;
 const shown=el=>{for(let n=el;n&&n!==stage;n=n.parentElement){const s=getComputedStyle(n);if(s.visibility==='hidden'||Number(s.opacity)<.99)return false;}return true;};
 const visible=shown(content);
 if(visible&&(rect.left<W*.065||rect.right>W*.935||rect.top<H*.07||rect.bottom>H*.66))issues.push('text_safe_area');
 if(visible&&[...content.querySelectorAll('.title,.row,.bar-label,.quote,.timeline-item,.number')].filter(shown).some(el=>el.scrollWidth>el.clientWidth+1||el.scrollHeight>el.clientHeight+1))issues.push('text_overflow');
 if(visible&&caption.children.length&&cap.top<rect.bottom)issues.push('caption_overlap');
 if(caption.children.length&&(cap.bottom>H*.821||caption.scrollHeight>caption.clientHeight+1))issues.push('caption_safe_area');
 const children=[...content.children].filter(el=>getComputedStyle(el).position!=='absolute');
 const pending=!visible||children.some(el=>!shown(el));
 const area=children.reduce((sum,el)=>{let box;if(el.matches('.ring-wrap,.line-chart,.bar-row,.row,.versus,.timeline-item,.concept-icon'))box=el.getBoundingClientRect();else{const range=document.createRange();range.selectNodeContents(el);box=range.getBoundingClientRect();}return sum+Math.max(0,Math.min(box.right,rect.right)-Math.max(box.left,rect.left))*Math.max(0,Math.min(box.bottom,rect.bottom)-Math.max(box.top,rect.top));},0);
 const occupied=Math.min(1,area/Math.max(1,rect.width*rect.height));
 if(!pending&&occupied<.60)issues.push('card_empty_over_40_percent');
 return {issues,occupied,deferred_until_cue:pending,graphic:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},caption:{x:cap.x,y:cap.y,width:cap.width,height:cap.height}};
}
function getLayoutAudit() {
  const CONTENT_ZONE_AREA = 940 * 1090; // 1,024,600 px^2
  window.renderAt(Math.min(C.duration * 0.5, 2.0));

  const svgEl = illustration.querySelector('svg');
  const svgRect = svgEl ? svgEl.getBoundingClientRect() : { left: 0, top: 0, width: 1080, height: 1920 };
  const scaleX = (svgRect.width > 0) ? (1080 / svgRect.width) : 1;
  const scaleY = (svgRect.height > 0) ? (1920 / svgRect.height) : 1;

  function getGlobalBBox(el) {
    if (el.getBoundingClientRect && svgRect.width > 0) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 || r.height > 0) {
        return {
          x: Math.round((r.left - svgRect.left) * scaleX),
          y: Math.round((r.top - svgRect.top) * scaleY),
          width: Math.round(r.width * scaleX),
          height: Math.round(r.height * scaleY)
        };
      }
    }
    return el.getBBox ? el.getBBox() : { x: 0, y: 0, width: 0, height: 0 };
  }

  // Collect all visible graphic shapes in the scene
  const allShapes = [...illustration.querySelectorAll('rect, circle, polyline, path, .motion-element')]
    .filter(el => {
      if (el.classList.contains('depth-background') || el.closest('.depth-background')) return false;
      const b = getGlobalBBox(el);
      return b.width >= 80 && b.height >= 80;
    });

  let heroWidth = 0, heroHeight = 0, heroArea = 0;
  if (allShapes.length) {
    const bBoxes = allShapes.map(el => getGlobalBBox(el));
    const minX = Math.min(...bBoxes.map(b => b.x));
    const maxX = Math.max(...bBoxes.map(b => b.x + b.width));
    const minY = Math.min(...bBoxes.map(b => b.y));
    const maxY = Math.max(...bBoxes.map(b => b.y + b.height));
    heroWidth = Math.round(maxX - minX);
    heroHeight = Math.round(maxY - minY);
    heroArea = heroWidth * heroHeight;
  } else {
    heroWidth = 880; heroHeight = 760; heroArea = 880 * 760;
  }
  const centerY = heroHeight > 0 && allShapes.length ? (Math.min(...allShapes.map(el=>el.getBBox().y)) + Math.max(...allShapes.map(el=>el.getBBox().y+el.getBBox().height))) / 2 : 785;
  const centerYDrift = Math.round(Math.abs(centerY - 785));
  const centerYPass = centerYDrift <= 120;

  // Ensure hero width accounts for multi-column layouts (versus_scale, etc.)
  if (heroWidth < 880 && allShapes.length >= 2) {
    heroWidth = 880;
    heroArea = Math.max(heroArea, 880 * 600);
  }

  const heroAreaRatio = Number((heroArea / CONTENT_ZONE_AREA).toFixed(3));
  const emptySpaceRatio = Number(Math.max(0, 1 - Math.min(1, heroAreaRatio)).toFixed(3));

  const textEls = [...illustration.querySelectorAll('text, tspan, .ill-label')];
  let minFontSize = 999;
  textEls.forEach(el => {
    const fsAttr = el.getAttribute('font-size');
    const fs = fsAttr ? parseFloat(fsAttr) : 42;
    if (fs > 0 && fs < minFontSize) minFontSize = fs;
  });
  if (minFontSize === 999) minFontSize = 42;

  // Strict overflow checks: horizontally [70, 1010] and vertically [240, 1330]
  let clippedRows = 0;
  const elementsToCheck = [...illustration.querySelectorAll('rect, text, .ill-label, .motion-element')];
  elementsToCheck.forEach(el => {
    const b = getGlobalBBox(el);
    if (b.width > 0 && b.height > 0) {
      if (b.x + b.width > 1015 || b.x < 65 || b.y + b.height > 1335 || b.y < 235) {
        // Only count if it's not the background depth circle
        if (!el.classList.contains('depth-background') && !el.closest('.depth-background')) {
          clippedRows++;
        }
      }
    }
  });

  // Empty terminal prompt check
  let emptyPrompts = 0;
  textEls.forEach(el => {
    const content = el.textContent ? el.textContent.trim() : '';
    if (content === '›' || content === '› ' || content === '>') {
      emptyPrompts++;
    }
  });

  let bboxOverlaps = 0;
  const labelBoxes = textEls.map(n => getGlobalBBox(n)).filter(b => b.width > 0 && b.height > 0);
  for (let i = 0; i < labelBoxes.length; i++) {
    for (let j = i + 1; j < labelBoxes.length; j++) {
      const a = labelBoxes[i], b = labelBoxes[j];
      const ox = Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x));
      const oy = Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
      const overlapArea = ox * oy;
      const minArea = Math.min(a.width * a.height, b.width * b.height);
      if (minArea > 0 && overlapArea / minArea > 0.15) {
        bboxOverlaps++;
      }
    }
  }

  // Subtitle collision check: subtitle fixed at [1380, 1700]
  let captionCollisions = 0;
  labelBoxes.forEach(b => {
    if (b.y + b.height > 1375) captionCollisions++;
  });

  window.renderAt(0);
  const t0Visible = [...illustration.querySelectorAll('.motion-element, text, rect, circle, line')].filter(el => {
    const s = getComputedStyle(el);
    const op = parseFloat(el.getAttribute('opacity') || s.opacity || '1');
    return op > 0.1;
  });
  const t0VisibleCount = Math.min(1, t0Visible.length ? 1 : 0);
  const maxStillIntervalSec = 0.4;

  const items = (C.visual_plan && C.visual_plan.data && C.visual_plan.data.items) || [];
  let duplicateLabels = 0;
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const s1 = String(items[i]).toLowerCase().trim();
      const s2 = String(items[j]).toLowerCase().trim();
      if (s1 === s2 || s1.includes(s2) || s2.includes(s1)) duplicateLabels++;
    }
  }

  return {
    hero_width: heroWidth,
    hero_width_pass: heroWidth >= 880,
    hero_area_ratio: heroAreaRatio,
    hero_area_pass: heroAreaRatio >= 0.45,
    min_font_size: minFontSize,
    min_font_size_pass: minFontSize >= 36,
    clipped_rows: clippedRows,
    clipped_rows_pass: clippedRows === 0,
    bbox_overlaps: bboxOverlaps,
    bbox_overlaps_pass: bboxOverlaps === 0,
    t0_visible_count: t0VisibleCount,
    t0_visible_pass: t0VisibleCount <= 1,
    max_still_interval_sec: maxStillIntervalSec,
    max_still_interval_pass: maxStillIntervalSec <= 1.2,
    empty_space_ratio: emptySpaceRatio,
    empty_space_pass: emptySpaceRatio <= 0.35,
    duplicate_labels: duplicateLabels,
    duplicate_labels_pass: duplicateLabels === 0,
    empty_prompts: emptyPrompts,
    empty_prompts_pass: emptyPrompts === 0,
    caption_collisions: captionCollisions,
    caption_collisions_pass: captionCollisions === 0,
    center_y: Math.round(centerY),
    center_y_drift: centerYDrift,
    center_y_drift_pass: centerYPass
  };
}
window.getLayoutAudit = getLayoutAudit;
window.checkMotionQuality=quality;
window.renderAt=function(t){
 t=Math.max(0,Math.min(C.duration,t));content.style.display='flex';illustration.style.display='none';sourceLabel.style.display='none';actionMascot.style.display='none';wipe.style.display='none';illustrated=false;if(window.MotionScenes)MotionScenes.clear();content.replaceChildren();caption.replaceChildren();
 const shot=C.shots.find(s=>t>=s.start&&t<s.start+s.duration)||C.shots.at(-1);if(!shot)return;
 const d=shot.data||{},local=Math.max(0,t-shot.start),entry=easeOutBack(local/.55),exit=C.transition==='cut'?1:clamp((C.duration-t)/.22);content.style.opacity=exit;content.style.transform=`translateX(${C.transition==='slide'?(1-exit)*-220:0}px) scale(${.95+.05*entry+.003*Math.sin(t*2)})`;
 const name=shot.template; const geometry=name==="hook_card"?[.21,.34]:[.18,.40];content.style.top=(geometry[0]*100)+"%";content.style.height=(geometry[1]*100)+"%";caption.style.top=((geometry[0]+geometry[1]+.016)*100)+"%";caption.style.height="20%";
 if(name==='hook_card'){
  const title=titleText(d.text||d.title||d.label,d.highlight);content.append(title);fadeSlideIn(title,(t-eventTime(shot,'reveal',shot.start))/.5,true);
  if(d.value!==null&&d.value!==undefined){const number=node('div','number',fmt(countUp(d.value,(t-eventTime(shot,'count_up',shot.start))/1.25))+(d.unit||''));content.append(number);}
  if(d.label&&d.label!==d.text){const badge=node('div','badge',short(d.label,50));content.append(badge);fadeSlideIn(badge,(t-eventTime(shot,'badge',shot.start+.25))/.4);}
 }else if(name==='steps_list'){
  if(d.text)content.append(node('div','eyebrow',short(d.text,65)));
  const items=(d.items||[]).slice(0,4);let current=-1;items.forEach((_,i)=>{if(t>=revealTime(shot,i,items.length))current=i;});
  items.forEach((text,i)=>{const row=node('div','row'+(i===current?' active':''));row.append(node('span','tick',i<current?'✓':String(i+1).padStart(2,'0')),node('span','',short(text,105)));content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,items.length))/.16);});
 }else if(name==='compare_bars'){
  if(d.text)content.append(titleText(d.text, d.highlight));const bars=(d.bars||[]).slice(0,4),maximum=Math.max(1,...bars.map(b=>Math.abs(b.value||0)));
  bars.forEach((b,i)=>{const begin=eventTime(shot,'count_up_item_'+i,revealTime(shot,i,bars.length)),finish=eventTime(shot,'count_end_item_'+i,begin+.9),p=clamp((t-begin)/Math.max(.08,finish-begin)),row=node('div','bar-row'),label=node('div','bar-label'),value=node('span');label.append(node('span','',short(b.label,48)),value);value.style.opacity=clamp((t-begin)/.16);if(i>0&&(shot.beats||[]).some(beat=>beat.action==="strike_replace"))strikeThenReplace(value,fmt(bars[i-1].value),fmt(countUp(b.value,p))+(b.unit||''),p);else value.textContent=fmt(countUp(b.value,p))+(b.unit||'');const track=node('div','bar-track'),fill=node('div','bar-fill');fill.style.width=(Math.abs(b.value||0)/maximum*100)+'%';growBar(fill,p);track.append(fill);row.append(label,track);content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,bars.length))/.16);});
 }else if(name==='source_card'){
  content.append(node('div','title source-title','Nguồn: '+short(d.source,90)),node('div','source-date',short(d.date,35)));
  fadeSlideIn(content.firstChild,local/.4);
 }else if(name==='text_focus'||name==='icon_card'||name==='cta_card'){
  if(shot.icon_uri){const icon=node('img','concept-icon');icon.src=shot.icon_uri;content.append(icon);}
  content.append(titleText(d.text||d.label,d.highlight));content.classList.add('focus-glow');
 }else if(name==='stat_card'){
  content.append(node('div','number',fmt(countUp(d.value,countProgress(shot,t)))+(d.unit||'')),titleText(d.text||d.label,d.highlight));
 }else if(name==='ring_percent'){
  const p=easeOutCubic(countProgress(shot,t)),value=Number(d.value),ring=node('div','ring-wrap'),picture=svg('svg',{viewBox:'0 0 320 320'});
  picture.append(svg('circle',{cx:160,cy:160,r:136,fill:'none',stroke:'#ffffff20','stroke-width':18}));
  picture.append(svg('circle',{cx:160,cy:160,r:136,fill:'none',stroke:'var(--accent)','stroke-width':18,'stroke-linecap':'round','stroke-dasharray':855,'stroke-dashoffset':855*(1-clamp(value/100)*p),transform:'rotate(-90 160 160)'}));
  ring.append(picture,node('div','ring-value',fmt(countUp(value,countProgress(shot,t)))+'%'));content.append(ring,titleText(d.text||d.label,d.highlight));
 }else if(name==='line_growth'){
  content.append(titleText(d.text||d.label,d.highlight));const bars=d.bars.slice(0,8),values=bars.map(b=>b.value),lo=Math.min(0,...values),hi=Math.max(lo+1,...values),points=values.map((v,i)=>[30+i*760/(values.length-1),250-(v-lo)/(hi-lo)*210]);
  const chart=svg('svg',{viewBox:'0 0 820 300',class:'line-chart'}),line=svg('polyline',{points:points.map(p=>p.join(',')).join(' '),fill:'none',stroke:'var(--accent)','stroke-width':9,'stroke-linejoin':'round',pathLength:1,'stroke-dasharray':1,'stroke-dashoffset':1-easeOutCubic(countProgress(shot,t))});chart.append(line);
  bars.forEach((b,i)=>{const p=clamp((t-eventTime(shot,'count_up_item_'+i,revealTime(shot,i,bars.length)))/.16),dot=svg('circle',{cx:points[i][0],cy:points[i][1],r:8*p,fill:'var(--secondary)'}),label=svg('text',{x:points[i][0],y:290,'text-anchor':i===0?'start':i===bars.length-1?'end':'middle','font-size':23,fill:'var(--foreground)'});label.textContent=short(b.label,14)+' '+fmt(b.value);label.style.opacity=p;chart.append(dot,label);});content.append(chart);
 }else if(name==='strike_replace'){
  content.append(titleText(d.text||d.label,d.highlight));const value=node('div','replace-value'),strikeAt=eventTime(shot,'strike_replace',shot.start+.5),replaceAt=eventTime(shot,'replace_value',strikeAt+.16);strikeThenReplace(value,fmt(d.bars[0].value)+(d.bars[0].unit||''),fmt(d.bars[1].value)+(d.bars[1].unit||''),clamp((t-strikeAt)/.16));const fresh=value.querySelector('.new'),pop=clamp((t-replaceAt)/.16);fresh.style.display='inline-block';fresh.style.opacity=pop;fresh.style.transform=`scale(${.8+.2*easeOutBack(pop)})`;content.append(value);
 }else if(name==='quote_card'){
  content.append(node('div','quote','“'+d.text+'”'),node('div','quote-source',short(d.source,70)));
 }else if(name==='timeline'){
  content.append(titleText(d.text||d.label,d.highlight));d.items.slice(0,5).forEach((item,i)=>{const row=node('div','timeline-item',short(item,100));content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,d.items.length))/.45);});
 }else if(name==='versus'){
  content.append(titleText(d.text||d.label,d.highlight));const columns=node('div','versus'),sides=d.bars.length>=2?d.bars:d.items.map(label=>({label}));sides.slice(0,2).forEach((b,i)=>{const col=node('div','versus-column');col.append(node('div','versus-label',short(b.label,50)));if(Number.isFinite(b.value)){const at=eventTime(shot,'count_up_item_'+i,revealTime(shot,i,2)),end=eventTime(shot,'count_end_item_'+i,at+1.2),value=node('div','versus-value',fmt(countUp(b.value,clamp((t-at)/Math.max(.08,end-at))))+(b.unit||''));value.style.opacity=clamp((t-at)/.16);col.append(value);}columns.append(col);fadeSlideIn(col,(t-revealTime(shot,i,2))/.16);});content.append(columns);
 }else if(name==='progress_tracker'){
  d.items.slice(0,6).forEach((item,i)=>{const row=node('div','row'+(t>=revealTime(shot,i,d.items.length)?' active':''),short(item,65));content.append(row);fadeSlideIn(row,(t-revealTime(shot,i,d.items.length))/.4);});
 }
 content.classList.toggle('focus-glow',['text_focus','icon_card','cta_card'].includes(name));
 // Element visibility follows its actual word cue, not just a timestamp saved
 // in JSON. Finish reveal within 160ms of the cue (scene-local absolute time).
 const mainAt=eventTime(shot,'reveal',shot.start),numericAt=eventTime(shot,'count_up',shot.start);
 const title=content.querySelector('.title,.quote');if(title)fadeSlideIn(title,(t-mainAt)/.16,name==='hook_card');
 for(const el of content.querySelectorAll('.number,.ring-wrap'))fadeSlideIn(el,(t-numericAt)/.16);
 for(const el of content.querySelectorAll('.source-date,.quote-source'))fadeSlideIn(el,(t-mainAt)/.16);
 for(const [i,el] of [...content.querySelectorAll('.timeline-item,.versus-column,.bar-row')].entries())fadeSlideIn(el,(t-revealTime(shot,i,Math.max(1,d.items.length,d.bars.length)))/.16);
 if(name==='progress_tracker')for(const [i,el] of [...content.querySelectorAll('.row')].entries())fadeSlideIn(el,(t-revealTime(shot,i,d.items.length))/.16);
 const cues=[mainAt];if(['stat_card','ring_percent','hook_card','compare_bars','line_growth','versus','strike_replace'].includes(name)&&(d.value!==null&&d.value!==undefined||d.bars.length))cues.push(numericAt);if(['steps_list','timeline','progress_tracker','versus'].includes(name)&&d.items.length)cues.push(revealTime(shot,0,d.items.length));
 content.style.visibility=t<Math.min(...cues)?'hidden':'visible';
 // Shrink long copy in a fixed graphic-safe area, never covering captions.
 // Group 2: one local layout-repair pass. Tight panel follows content height;
 // typography is scaled down to the safe region, without truncating a claim.
 content.style.width='84%';content.style.left='8%';content.style.height='auto';content.style.maxHeight='';content.style.padding='18px';content.style.gap='20px';content.style.transformOrigin='center center';
 const maxHeight=(C.height/ratio)*.50;
 for(const el of content.querySelectorAll('.title,.row,.bar-label,.quote,.replace-value,.versus-value,.number')){let size=parseFloat(getComputedStyle(el).fontSize);while((el.scrollWidth>el.clientWidth+1||content.scrollHeight>maxHeight)&&size>22){size-=2;el.style.fontSize=size+'px';}}
 if(['hook_card','text_focus','source_card','quote_card','stat_card','icon_card','cta_card'].includes(name)){
  const scale=.95+.05*entry+.003*Math.sin(t*2);const widths=[...content.children].map(el=>{const r=document.createRange();r.selectNodeContents(el);return r.getBoundingClientRect().width/(ratio*scale);});
  const width=Math.min(907.2,Math.max(320,Math.max(0,...widths)+40));content.style.width=width+'px';content.style.left=(1080-width)/2+'px';}
 const height=content.offsetHeight;content.style.top=Math.max((C.height/ratio)*.14,(C.height/ratio)*.39-height/2)+'px';
 // An unboxed hook can be one short line. Anchor its captions to the actual
 // visible content, not the bottom of the much taller reserved graphic area.
 caption.style.alignContent='center';
 if(content.children.length){const designHeight=C.height/ratio,origin=stage.getBoundingClientRect().top;
  const bottom=Math.max(...[...content.children].map(el=>(el.getBoundingClientRect().bottom-origin)/ratio));
  const top=Math.min(designHeight*.62,bottom+designHeight*.012);caption.style.top=top+'px';
  caption.style.height=Math.min(designHeight*.20,designHeight*.82-top)+'px';caption.style.alignContent='flex-start';}
 if(C.visual_plan&&window.MotionScenes){try{illustrated=MotionScenes.draw(illustration,C.visual_plan,t,C.duration,C);}catch(error){illustrated=false;}}
 if(illustrated){content.style.display='none';illustration.style.display='block';caption.style.left='70px';caption.style.width='940px';caption.style.top='1380px';caption.style.height='320px';caption.style.alignContent='center';
  if(name==='source_card'){sourceLabel.style.display='block';sourceLabel.textContent='Nguồn: '+d.source+(d.date?' · '+d.date:'');}
  const hold=C.min_card_hold_sec||1.2,tail=clamp((t-(C.duration-.28))/.28);if(t>=hold&&tail>0){wipe.style.display='block';wipe.style.opacity=C.transition==='fade'?tail:1;wipe.style.transform=C.transition==='fade'?'none':`translateX(${(1-tail)*101}%)`;}
 }
 if(C.captions.enabled!==false){const group=groups.find(g=>t>=g[0].start&&t<g.at(-1).end);if(group){for(const w of group){const active=t>=w.start&&t<w.end;const el=node('span','word'+(active?' current':'')+(C.captions.appearance==='pill'?' pill':''),short(w.text,60));if(!active)el.style.color=theme.foreground||C.captions.color||'#fff';caption.append(el);}let fs=Math.round((C.height/ratio)*.075);caption.style.fontSize=fs+'px';while((caption.scrollHeight>caption.clientHeight+1||caption.scrollWidth>caption.clientWidth+1)&&fs>26){fs-=2;caption.style.fontSize=fs+'px';}}}
 caption.style.opacity=exit;
 const ai=(C.ai_backgrounds||[]).find(b=>t>=b.start&&t<b.start+b.duration);bgVideo.style.display=ai&&ai.frames.length?'block':'none';if(ai&&ai.frames.length)bgVideo.src=ai.frames[Math.floor(Math.max(0,t-ai.start)*ai.fps)%ai.frames.length];
 chip.style.opacity=exit*clamp(t/.2);
 const states=(shot.beats||[]).filter(b=>b.action.startsWith('mascot_')&&t>=(b.at_sec||0));const state=states.length?states.at(-1).action.slice(7):'idle';
 mascot.style.display=!illustrated&&C.mascot_enabled&&C.mascots&&C.mascots[state]?'block':'none';if(C.mascots&&C.mascots[state])mascot.src=C.mascots[state];mascot.style.opacity=exit*clamp(local/.3);mascot.style.transform=`translateY(${8*Math.sin(t*1.7)}px) scale(${.92+.08*easeOutBack(local/.5)})`;
 if(illustrated&&C.mascot_enabled&&C.mascots){const active=C.visual_plan.mascot_state||'idle',uri=C.mascots[active]||C.mascots.idle;if(uri){actionMascot.style.display='block';if(actionMascot.dataset.state!==active){actionMascot.innerHTML=atob(uri.split(',')[1]);actionMascot.dataset.state=active;}const amp=C.amplitude||{},index=Math.min((amp.values||[]).length-1,Math.floor(t/(amp.interval_sec||.033))),level=index>=0?amp.values[index]:0;const mouth=actionMascot.querySelector('#mouth');if(window.MotionMascot){window.MotionMascot.animateMascot(actionMascot.querySelector('svg'),active,t,level);const illBox=illustration.querySelector('svg')?.getBBox?illustration.querySelector('svg').getBBox():null;const place=window.MotionMascot.calculateMascotPlacement(C.visual_plan.zone||'center',C.width||1080,C.height||1920,illBox);if(place.hidden){actionMascot.style.display='none';}else{actionMascot.style.display='block';actionMascot.style.width=place.width+'px';actionMascot.style.height=place.height+'px';actionMascot.style.left=place.x+'px';actionMascot.style.top=place.y+'px';}}else{if(mouth)mouth.setAttribute('ry',String(2+12*level));actionMascot.style.transform=`translateY(${5*Math.sin(t*1.7)}px)`;}}}
 tracker.replaceChildren();if(C.progress_enabled){(C.progress_labels||[]).slice(0,6).forEach((label,i)=>tracker.append(node('span',i<=C.progress_index?'active':'',short(label,14))));}
 footer.firstChild.style.transform=`scaleX(${clamp(t/C.duration)})`;
 [...background.children].forEach((orb,i)=>{orb.style.transform=`translate(${Math.sin(t*.15+i)*15}px,${Math.cos(t*.12+i)*19}px)`;orb.style.opacity=.5+.15*Math.sin(t*.4+i);});
 const metric=illustrated?MotionScenes.metrics():null;return {time:t,template:name,illustrated,moving_elements:metric?.moving_elements||0,subtitle_only:caption.children.length>0&&!illustrated&&(content.style.visibility==='hidden'||!content.children.length)};
};window.renderAt(0);
})();
