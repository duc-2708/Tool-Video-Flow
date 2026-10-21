"""Deterministic spoken numbers, never adds exchange rates or new assertions."""
import re
DIGITS = "không một hai ba bốn năm sáu bảy tám chín".split()
SCALES = [(10**9,"tỷ"),(10**6,"triệu"),(1000,"nghìn")]


def read_integer(n):
    n = int(n)
    if n < 10:
        return DIGITS[n]
    for scale, label in SCALES:
        if n >= scale:
            rest = n % scale
            return read_integer(n//scale)+" "+label+(" "+read_integer(rest) if rest else "")
    if n >= 100:
        rest = n % 100
        return DIGITS[n//100]+" trăm"+(" lẻ "+DIGITS[rest] if 0<rest<10 else " "+read_integer(rest) if rest else "")
    tens, unit = divmod(n,10)
    prefix = "mười" if tens == 1 else DIGITS[tens]+" mươi"
    suffix = "lăm" if unit == 5 else "mốt" if unit == 1 and tens>1 else DIGITS[unit]
    return prefix+(" "+suffix if unit else "")


def speak_number(value):
    if "," in value and "." in value:
        decimal = "," if value.rfind(",")>value.rfind(".") else "."
        value = value.replace("." if decimal=="," else ",","").replace(decimal,".")
    elif re.fullmatch(r"[1-9]\d{0,2}(?:[.,]\d{3})+",value):
        value = value.replace(".","").replace(",","")
    else:
        value = value.replace(",", ".")
    parts = value.split(".")
    if len(parts)>2:
        return " chấm ".join(read_integer(part) for part in parts)
    return read_integer(parts[0])+(" phẩy "+" ".join(DIGITS[int(c)] for c in parts[1]) if len(parts)>1 else "")


ACRONYMS = {"API":"ây pi ai", "AI":"ây ai", "GPU":"gi pi diu", "CPU":"xi pi diu", "USD":"đô la Mỹ", "VND":"đồng", "LLM":"eo eo em", "TTS":"ti ti ét", "FPS":"ép pi ét", "SSD":"ét ét đi"}

def tts_text(text):
    text = re.sub(r"(\d+(?:[.,]\d+)*)\s*([KMB])\b",lambda m:m[1]+" "+{"K":"nghìn","M":"triệu","B":"tỷ"}[m[2]],text)
    units = {"kg":"ki lô gam","km":"ki lô mét","GB":"ghi ga bai","MB":"mê ga bai","ms":"mi li giây","s":"giây"}
    text = re.sub(r"(\d+(?:[.,]\d+)*)\s*(kg|km|GB|MB|ms|s)\b",lambda m:m[1]+" "+units[m[2]],text)
    text = re.sub(r"\$\s*(\d+(?:[.,]\d+)*)",lambda m:speak_number(m[1])+" đô la Mỹ",text)
    text = re.sub(r"(\d+(?:[.,]\d+)*)\s*%",lambda m:speak_number(m[1])+" phần trăm",text)
    text = re.sub(r"\d+(?:[.,]\d+)*",lambda m:speak_number(m[0]),text)
    for word, pronunciation in ACRONYMS.items():
        text = re.sub(r"\b"+word+r"\b",pronunciation,text)
    return " ".join(text.replace("(",", ").replace(")",", ").split())


def spoken_to_digits(text):
    tokens = r"(?:không|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|trăm|nghìn|ngàn|triệu|tỷ|lẻ|linh)"
    digit_words = r"(?:"+"|".join([*DIGITS,"mốt","tư","lăm"])+r")"
    pattern = r"(?<!\w)(?:"+tokens+r"(?:\s+"+tokens+r")+|"+digit_words+r"(?=\s+phẩy))(?:\s+phẩy(?:\s+"+digit_words+r")+(?:\s+(?:nghìn|ngàn|triệu|tỷ))?)?(?!\w)"
    def convert(match):
        from decimal import Decimal
        whole, *decimal = match[0].split(" phẩy ")
        total = group = 0
        current=None
        values = {word:i for i,word in enumerate(DIGITS)}
        values.update({"mốt":1,"tư":4,"lăm":5})
        magnitudes = {"nghìn":1000,"ngàn":1000,"triệu":10**6,"tỷ":10**9}
        for word in whole.split():
            if word in values: current = values[word]
            elif word in {"lẻ","linh"}: continue
            elif word in {"mười","mươi","trăm"}:
                group += (1 if current is None else current)*({"mười":10,"mươi":10,"trăm":100}[word]); current=None
            else:
                total += (group+(current or 0))*magnitudes[word];group=0;current=None
        if decimal:
            fraction = decimal[0].split()
            factor = magnitudes.get(fraction[-1],1)
            if fraction[-1] in magnitudes: fraction.pop()
            value = Decimal(str(total+group+(current or 0))+"."+"".join(str(values[w]) for w in fraction))*factor
            return format(value.normalize(),"f")
        return str(total+group+(current or 0))
    return re.sub(pattern,convert,text,flags=re.I)
