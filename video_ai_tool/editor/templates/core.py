"""Animated Pillow cards wrapped as MoviePy 2 VideoClips (no ImageMagick)."""
from functools import lru_cache
import math
import re
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont
from editor.runtime import VideoClip
from editor.captions import wrap_lines
from editor.templates.theme import background, load_theme

NAMES = ("hook_card","stat_card","steps_list","compare_bars","source_card","text_focus")


def ease_out(x): return 1-(1-min(1.,max(0.,x)))**3


def ease_back(x):
    x=min(1.,max(0.,x))-1
    return 1+2.70158*x**3+1.70158*x*x


def number_at(value, t, duration):
    try: value=float(value or 0)
    except (ValueError,TypeError): value=0.
    if not math.isfinite(value): value=0.
    return value*ease_out(t/max(.15,min(1.2,duration*.42)))


def number_label(value, target=None):
    target=value if target is None else target
    if abs(float(target)-round(float(target)))<1e-8:
        return f"{round(value):,}".replace(",",".")
    decimals=min(3,len(str(target).partition(".")[2].rstrip("0"))) or 1
    return f"{value:,.{decimals}f}".replace(",","_").replace(".",",").replace("_",".")


def short(value, limit=180):
    if value is None: return ""
    if isinstance(value,(dict,list)): value=" · ".join(map(str,value.values() if isinstance(value,dict) else value))
    value=" ".join(str(value).split())
    return value if len(value)<=limit else value[:limit].rsplit(" ",1)[0]+"…"


@lru_cache(maxsize=256)
def font(path,size): return ImageFont.truetype(path,max(8,int(size)))


def text_block(draw,text,box,theme,scale=.09,fill=None,highlights=(),align="center"):
    x,y,w,h=box
    text=short(text,260)
    size=max(9,round(w*scale))
    while True:
        f=font(theme["font"],size)
        lines=wrap_lines(text,f,max(1,w))
        if len(lines)*size*1.35<=h or size<=9: break
        size-=1
    lines=lines[:max(1,int(h/(size*1.35)))]
    highlight={str(s).casefold().strip(".,!?:;") for s in highlights}
    for i,line in enumerate(lines):
        left=x+(w-f.getlength(line))/2 if align=="center" else x
        for word in line.split():
            color=theme["accent"] if word.casefold().strip(".,!?:;") in highlight else fill or theme["foreground"]
            draw.text((left,y+i*size*1.35),word,font=f,fill=color,anchor="lt")
            left+=f.getlength(word+" ")
    return len(lines)*size*1.35


def element_times(name,data,duration):
    count=len(data.get("items",[])[:4]) if name=="steps_list" else len(data.get("bars",[])[:4]) if name=="compare_bars" else 1
    # Reveals never more than 3 seconds apart. Refresh pulses continue afterward.
    gap=min(2.8,max(.25,(duration-.7)/max(count,1)))
    return [round(i*gap,3) for i in range(max(1,count))]


def payload(data):
    return data.model_dump(mode="json") if hasattr(data,"model_dump") else data if isinstance(data,dict) else {}


class Card:
    def __init__(self,name,data,duration,size,theme=None):
        self.name,self.data,self.duration,self.size=name,payload(data),max(.01,float(duration)),tuple(size)
        self.theme={**load_theme(),**(theme or {})}
        self.base=background(self.size,self.theme)
        self.events=element_times(name,self.data,self.duration)
        self.panel_cache={}

    def panel(self,t):
        w,h=self.size;theme=self.theme;data=self.data
        layer=Image.new("RGBA",self.size)
        draw=ImageDraw.Draw(layer)
        # Upper/middle band reserved for cards; captions occupy the lower safe band.
        x,y,cw,ch=w*.07,h*.20,w*.86,h*.43
        radius=max(8,round(w*float(theme.get("radius",28))/540))
        draw.rounded_rectangle((x+4,y+8,x+cw+4,y+ch+8),radius=radius,fill=(0,0,0,round(255*float(theme.get("shadow",.35)))))
        draw.rounded_rectangle((x,y,x+cw,y+ch),radius=radius,fill=theme["card"])
        draw.rounded_rectangle((x,y,x+cw,y+max(3,h*.005)),radius=2,fill=theme["accent"])
        pad=w*.055
        box=(x+pad,y+h*.04,cw-2*pad,ch-h*.07)
        bx,by,bw,bh=box
        name=self.name
        if name in {"hook_card","text_focus"}:
            text=data.get("text") or data.get("title") or data.get("label") or "Thông tin nổi bật"
            highlights=data.get("highlight") or text.split()[:min(6,len(text.split()))]
            text_block(draw,text,box,theme,.12 if name=="hook_card" else .095,highlights=highlights)
        elif name=="stat_card":
            target=data.get("value") or 0
            text=number_label(number_at(target,t,self.duration),target)
            text_block(draw,text,(bx,by,bw,bh*.42),theme,.25,theme["accent"])
            text_block(draw,data.get("unit",""),(bx,by+bh*.39,bw,bh*.12),theme,.055,theme["secondary"])
            text_block(draw,data.get("label") or "Số liệu từ nguồn",(bx,by+bh*.55,bw,bh*.23),theme,.075)
            text_block(draw,data.get("source",""),(bx,by+bh*.87,bw,bh*.12),theme,.038,theme["muted"])
        elif name=="steps_list":
            items=data.get("items",[])[:4] or [data.get("text") or "Nội dung từ nguồn"]
            row=bh/max(2,len(items))
            for i,item in enumerate(items):
                reveal=ease_out((t-self.events[min(i,len(self.events)-1)])/.4)
                if reveal<=0: continue
                yy=by+i*row
                xx=bx+(1-reveal)*w*.07
                r=w*.022
                draw.ellipse((xx,yy+r,xx+2*r,yy+3*r),fill=theme["secondary"])
                draw.line([(xx+r*.45,yy+r*2),(xx+r*.9,yy+r*2.4),(xx+r*1.6,yy+r*1.5)],fill=theme["card"],width=max(2,round(w*.004)))
                text_block(draw,item,(xx+w*.065,yy,bw-w*.09,row*.88),theme,.065,align="left")
        elif name=="compare_bars":
            bars=data.get("bars",[])[:4] or [{"label":"Chưa có số liệu","value":0}]
            values=[]
            for bar in bars:
                try: v=float(bar.get("value",0))
                except (ValueError,TypeError): v=0
                values.append(v if math.isfinite(v) else 0)
            maximum=max([abs(v) for v in values]+[1.]);row=bh/max(2,len(bars))
            for i,(bar,v) in enumerate(zip(bars,values)):
                p=ease_out((t-self.events[min(i,len(self.events)-1)])/.65)
                yy=by+i*row
                label=short(bar.get("label", ""),55)+"  "+number_label(v)+str(bar.get("unit", ""))
                if p>0: text_block(draw,label,(bx,yy,bw,row*.42),theme,.055,align="left")
                draw.rounded_rectangle((bx,yy+row*.50,bx+bw,yy+row*.69),radius=4,fill=theme["muted"])
                length=bw*abs(v)/maximum*p
                if length>1: draw.rounded_rectangle((bx,yy+row*.50,bx+length,yy+row*.69),radius=4,fill=theme["accent"] if i%2==0 else theme["secondary"])
        elif name=="source_card":
            text_block(draw,data.get("source") or "Nguồn bài viết",(bx,by,bw,bh*.22),theme,.10,theme["accent"])
            text_block(draw,data.get("date", ""),(bx,by+bh*.27,bw,bh*.13),theme,.045,theme["muted"])
            text_block(draw,data.get("title") or data.get("text", ""),(bx,by+bh*.47,bw,bh*.48),theme,.075)
        return layer

    def frame(self,t,transparent=False):
        w,h=self.size
        name=self.name
        if self.name=="stat_card":
            key=round(number_at(self.data.get("value"),t,self.duration),3)
        elif self.name in {"steps_list","compare_bars"}:
            key=tuple(round(ease_out((t-e)/(.4 if self.name=="steps_list" else .65)),3) for e in self.events)
        else: key=0
        if key not in self.panel_cache:
            if len(self.panel_cache)>=4: self.panel_cache.clear()
            self.panel_cache[key]=self.panel(t)
        layer=self.panel_cache[key].copy()
        draw=ImageDraw.Draw(layer)
        sweep=(max(0.,t)%3)/3
        x,y,cw,ch=w*.07,h*.20,w*.86,h*.43
        draw.rounded_rectangle((x+cw*sweep,y+ch-h*.008,min(x+cw,x+cw*sweep+w*.08),y+ch),radius=2,fill=self.theme["secondary"])
        # Eased entry/exit plus gentle continuous motion; never a frozen >4s hold.
        entry=ease_back(t/.42) if name=="hook_card" else ease_out(t/.4)
        scale=max(.5,.86+.14*entry)+.009*math.sin(t*2*math.pi/3)
        exit_alpha=min(1.,max(0.,(self.duration-t)/.20))
        resized=layer.resize((max(1,round(w*scale)),max(1,round(h*scale))),Image.Resampling.BILINEAR)
        shift=round((1-ease_out(t/.4))*w*.16) if name=="source_card" else 0
        motion=Image.new("RGBA",self.size)
        motion.paste(resized,((w-resized.width)//2+shift,(h-resized.height)//2),resized)
        if exit_alpha<1: motion.putalpha(motion.getchannel("A").point(lambda a:round(a*exit_alpha)))
        if transparent: return motion
        return np.asarray(Image.alpha_composite(self.base,motion).convert("RGB"))


def render_template(name,data,duration,size,theme=None):
    if name not in NAMES: name="text_focus"
    card=Card(name,data,duration,size,theme)
    clip=VideoClip(card.frame,duration=card.duration)
    clip.visual_card=card
    return clip
