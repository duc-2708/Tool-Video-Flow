"""Shared card/caption safe geometry, expressed in output pixels."""
def card_box(size,name="text_focus"):
    w,h=size
    top,height=(.25,.30) if name=="text_focus" else (.21,.34) if name=="hook_card" else (.33,.22) if name=="source_card" else (.18,.40)
    return w*.07,h*top,w*.86,h*height


def caption_box(size,name="text_focus"):
    w,h=size;_,y,_,height=card_box(size,name)
    top=y+height+h*.016
    return w*.11,top,w*.76,min(h*.20,h*.82-top)
