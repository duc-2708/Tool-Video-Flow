"""Local Lucide SVG only. Missing/unsafe map or icon is a recoverable warning."""
import base64
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml


def icon_for(root,text):
    root=Path(root);folder=root/'assets/icons'
    try: data=yaml.safe_load((root/'config/icons.yaml').read_text(encoding='utf-8')) or {}
    except (OSError,ValueError,yaml.YAMLError): data={}
    name=next((key for key,terms in data.get('keywords',{}).items() if any(str(t).casefold() in text.casefold() for t in terms)),data.get('default','lightbulb'))
    for candidate in (name,'lightbulb'):
        if not isinstance(candidate,str) or Path(candidate).name!=candidate: continue
        path=folder/(candidate+'.svg')
        try:
            raw=path.read_bytes()
            if len(raw)>30000: continue
            element=ET.fromstring(raw)
            if any(n.tag.split('}')[-1] not in {'svg','path','circle','rect','line','polyline','polygon','ellipse','g'} or any(k.lower().startswith('on') or k.lower() in {'href','style'} or 'url(' in v for k,v in n.attrib.items()) for n in element.iter()): continue
            raw=raw.replace(b'currentColor',b'#7bdffa')
            return candidate,'data:image/svg+xml;base64,'+base64.b64encode(raw).decode('ascii')
        except (OSError,ET.ParseError): continue
    return 'none',''


def chip_text(scene):
    from agents.visual_diversity import concept_card
    text,_=concept_card(scene.narration)
    for phrase in ('an ninh mạng','hạ tầng','lỗ hổng','quét tự động','mã độc','tài liệu mật','dữ liệu','công nghiệp','việc làm','chi phí','kỹ năng','thói quen'):
        if phrase in text.casefold(): return phrase[:1].upper()+phrase[1:]
    words=text.split()
    return ' '.join(words if len(words)<=3 else words[-2:])
