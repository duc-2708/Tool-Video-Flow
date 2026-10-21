"""Continuous cover/crop motion without stretching or changing the timeline."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def cover_box(source, target, zoom=1.0, pan=0.5):
    sw, sh = source
    tw, th = target
    scale = max(tw/sw, th/sh)*zoom
    width, height = tw/scale, th/scale
    left = (sw-width)*pan
    top = (sh-height)/2
    return left, top, left+width, top+height


def cover(frame, size, effect="none", progress=0.0):
    p = min(1.,max(0.,progress))
    eased = p*p*(3-2*p)
    zoom = 1+.12*(eased if effect == "zoom_in" else 1-eased) if effect in {"zoom_in","zoom_out"} else 1.
    pan = .5
    if effect in {"pan_left","pan_right"}:
        zoom = 1.12
        pan = .2+.6*(eased if effect == "pan_right" else 1-eased)
    picture = Image.fromarray(np.asarray(frame,dtype=np.uint8))
    return np.asarray(picture.resize(size,Image.Resampling.BICUBIC,box=cover_box(picture.size,size,zoom,pan)))


def transition(first, second, progress, kind):
    p = min(1.,max(0.,progress))
    p = p*p*(3-2*p)
    if kind == "zoom":
        first = cover(first,(first.shape[1],first.shape[0]),"zoom_in",p)
    if kind == "whip":
        shift = min(first.shape[1],round(first.shape[1]*p))
        return np.concatenate((first[:,shift:],second[:,:shift]),axis=1)
    return np.asarray(first*(1-p)+second*p,dtype=np.uint8)


def color_card(size, text, font_path, seed=0):
    from editor.captions import wrap_lines
    width,height = size
    y = np.linspace(0,1,height)[:,None,None]
    top = np.array([17,33+seed%4*5,65])[None,None,:]
    bottom = np.array([39,72,104])[None,None,:]
    image = Image.fromarray(np.broadcast_to(top*(1-y)+bottom*y,(height,width,3)).astype("uint8").copy())
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path),max(18,round(width*.065)))
    lines = wrap_lines(text,font,width*.78)
    while len(lines)*font.size*1.4 > height*.40 and font.size > 12:
        font = ImageFont.truetype(str(font_path),font.size-1)
        lines = wrap_lines(text,font,width*.78)
    step = int(font.size*1.4)
    start = height*.35-len(lines)*step/2
    draw.rounded_rectangle((width*.1,start-24,width*.9,start+len(lines)*step+24),radius=20,fill=(24,48,76))
    draw.rounded_rectangle((width*.1,start-24,width*.32,start-18),radius=3,fill=(255,205,88))
    for i,line in enumerate(lines):
        draw.text((width/2,start+i*step),line,font=font,fill="white",anchor="mt")
    return np.asarray(image)
