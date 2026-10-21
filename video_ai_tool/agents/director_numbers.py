"""Numeric comparison without currency punctuation/locale false positives."""
from datetime import datetime
from decimal import Decimal,InvalidOperation
import re
from agents.vietnamese_tts import spoken_to_digits


def normalized_numbers(text, *, ignore_current_year=True):
    # Lowercase m/mét in article lengths is not the uppercase financial suffix M.
    text=re.sub(r"(\d+(?:[.,]\d+)*)\s*m\b",r"\1 mét",text)
    text = spoken_to_digits(text.casefold()).replace("phần trăm","%")
    text = re.sub(r"\b(?:cảnh|scene|bước|thứ|mục|phần|stt|số thứ tự)\s*#?\s*\d+\b","",text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+","",text)
    result = set()
    for match in re.finditer(r"(?<!\d)(\d+(?:[.,]\d+)*)(?:\s*(triệu|tỷ|nghìn|ngàn|million|billion|thousand|[mkb])(?!\w))?\s*(%)?",text):
        value,unit,percent = match.groups()
        # Product versions remain numbers: 5.5 is matched against a version in
        # its referenced fact, never discarded merely for following a name.
        if "," in value and "." in value:
            decimal = "," if value.rfind(",")>value.rfind(".") else "."
            value = value.replace("." if decimal == "," else ",","").replace(decimal,".")
        elif re.fullmatch(r"[1-9]\d{0,2}(?:[.,]\d{3})+",value):
            value = value.replace(".","").replace(",","")
        else:
            value = value.replace(",",".")
        try:
            number = Decimal(value)
            factor = {"triệu":1000000,"million":1000000,"m":1000000,"tỷ":1000000000,"billion":1000000000,"b":1000000000,
                "nghìn":1000,"ngàn":1000,"thousand":1000,"k":1000}.get(unit,1)
            number *= factor
            if ignore_current_year and number == datetime.now().year and not unit and not percent:
                continue
            result.add(format(number.normalize(),"f")+("%" if percent else ""))
        except InvalidOperation:
            result.add(match.group(0).strip())
    return result
