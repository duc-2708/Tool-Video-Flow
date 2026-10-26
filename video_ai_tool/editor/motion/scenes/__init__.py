"""Bundle original local scenes and the pinned MIT anime.js; no network."""
import hashlib,json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[2]


def bundle():
    vendor=ROOT/'assets/vendor/anime/anime.min.js'
    if not vendor.is_file(): return '', '', 'anime-missing'
    files=[FOLDER/'engine.js',FOLDER/'scenes.css',vendor]
    files+=sorted(FOLDER.glob('*/scene.js'))+sorted(FOLDER.glob('*/scene.css'))+sorted(FOLDER.glob('*/scene.html'))
    try:
        html={p.parent.name:p.read_text(encoding='utf-8') for p in files if p.suffix=='.html'}
        css='\n'.join(p.read_text(encoding='utf-8') for p in files if p.suffix=='.css')
        js=vendor.read_text(encoding='utf-8')+'\nwindow.MOTION_SCENE_HTML='+json.dumps(html).replace('<','\\u003c')+';\n'+(FOLDER/'engine.js').read_text(encoding='utf-8')
        js+='\n'+'\n'.join(p.read_text(encoding='utf-8') for p in files if p.name=='scene.js')
        digest=hashlib.sha256(b''.join(p.read_bytes() for p in files)).hexdigest()
        return css,js,digest
    except OSError: return '', '', 'scene-files-missing'
