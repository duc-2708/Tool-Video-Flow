"""Small, SSML-free text chunks for Edge TTS; retain Vietnamese letters."""
import html
import re
import unicodedata
from html.parser import HTMLParser


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]
        self.hidden=0

    def handle_starttag(self,tag,attrs):
        if tag in {"script","style"}: self.hidden+=1
        self.parts.append(" ")

    def handle_endtag(self,tag):
        if tag in {"script","style"}: self.hidden=max(0,self.hidden-1)
        self.parts.append(" ")

    def handle_data(self,data):
        if not self.hidden: self.parts.append(data)


def clean_tts_text(value,*,simple=False):
    text=html.unescape(unicodedata.normalize("NFKC",str(value or "")))
    text=re.sub(r"[0-9#*]\ufe0f?\u20e3"," ",text)
    text=re.sub(r"\[([^\]]+)\]\(https?://[^)]+\)",r"\1",text)
    parser=_PlainText()
    parser.feed(text);parser.close()
    text=html.unescape(" ".join(parser.parts))
    text=re.sub(r"https?://\S+"," ",text)
    text=text.translate(str.maketrans({"&":" và ","<":" nhỏ hơn ",">":" lớn hơn ",
        "“":'"',"”":'"',"‘":"'","’":"'","…":"...","–":", ","—":", ",
        "（":", ","）":", ","【":", ","】":", ","「":", ","」":", "}))
    text=re.sub(r"[\[\]{}()*#`_]+"," ",text)
    safe=".,!?;:'\"-/%$+=" if not simple else ".,!?;:'\"-"
    cleaned=[]
    for char in text:
        category=unicodedata.category(char)
        # Mark/variation/emoji joiners never enter SSML; NFC below restores accents.
        if category[0] in {"L","N"} or category[0]=="M" and 0x0300<=ord(char)<=0x036F:
            cleaned.append(char)
        elif char in safe or char.isspace(): cleaned.append(char)
        else: cleaned.append(" ")
    return " ".join(unicodedata.normalize("NFC","".join(cleaned)).split())


def has_speech(text):
    return any(char.isalnum() for char in text)


def split_tts_text(text,limit=300):
    """Sentence boundaries first; split unusually long sentences at word boundaries."""
    chunks=[];current=""
    for sentence in re.split(r"(?<=[.!?;])\s+",text):
        if current and len(current)+len(sentence)+1>limit:
            if has_speech(current): chunks.append(current)
            current=""
        for word in sentence.split():
            # A single malformed token must also respect the service limit.
            for part in (word[i:i+limit] for i in range(0,len(word),limit)):
                candidate=(current+" "+part).strip()
                if len(candidate)>limit:
                    if has_speech(current): chunks.append(current)
                    current=part
                else: current=candidate
        if current and len(current)>=limit*.5:
            if has_speech(current): chunks.append(current)
            current=""
    if has_speech(current): chunks.append(current)
    return chunks
