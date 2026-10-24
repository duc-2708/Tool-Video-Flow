"""Immutable-input Motion3 regression: clone prepared assets, no text/API calls."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
from config.settings import get_settings
from editor.render import run_render
from editor.motion.memory import MemorySampler
from pipeline.projects import create_project
from utils.atomic_io import write_json_atomic,write_text_atomic
from utils.console import configure_console


def source_fingerprints(root):
    names=('edit_plan.json','edit_plan.resolved.json','assets.json','brief.json','sources.json','credits.txt','visual_decisions.json')
    files=[root/n for n in names]
    files += [p for name in ('audio','clips') for p in (root/name).rglob('*') if p.is_file()]
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()}


def review(source,settings,*,project=None,scales=(.5,1.)):
    source=Path(source).resolve();before=source_fingerprints(source)
    if project is None:
        data=json.loads((source/'edit_plan.resolved.json').read_text(encoding='utf-8'))
        project=create_project(settings.output_dir,'motion-v3-'+data['title'])
        for name in before:
            target=project/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
    else: project=Path(project).resolve()
    report={'source_project':str(source),'project':str(project),'input_fingerprints':before,'runs':[],
        'scope':'Original narration/audio/plan copied unchanged; presentation repaired in memory; no API or time scaling.'}
    last=[0.]
    def progress(value,message):
        if time.monotonic()-last[0]>5 or value==1:
            print(f'{value:.0%} {message}',flush=True);last[0]=time.monotonic()
    for scale in scales:
        options=settings.model_copy(update={'motion_enabled':True,'motion_scale':scale,'motion_fps':30,'render_width':1080,'render_height':1920,'ai_clips_per_video':0})
        with MemorySampler() as memory:
            result=run_render(project/'edit_plan.resolved.json',mode='preview',settings=options,progress=progress)
        tag=str(scale).replace('.','_');folder=project/'render'
        destination=folder/f'motion_scale_{tag}.mp4';shutil.copyfile(result['path'],destination)
        sheet=project/'review_frames'/f'contact_sheet_scale_{tag}.png';shutil.copyfile(result['contact_sheet'],sheet)
        qc=project/f'quality_report_scale_{tag}.json';shutil.copyfile(result['quality_report'],qc)
        result.update(scale=scale,benchmark_path=str(destination),benchmark_contact_sheet=str(sheet),peak_tree_working_set_mb=memory.peak_mb)
        report['runs'].append(result)
        report['original_inputs_unchanged']=before==source_fingerprints(source)
        write_json_atomic(project/'motion_review_benchmark.json',report)
        print(f'Scale {scale}: render {result["render_seconds"]}s, total {result["total_seconds"]}s, {destination}',flush=True)
    lines=['# Motion3 review','',report['scope'],'',f'Original inputs unchanged: {report["original_inputs_unchanged"]}','',
        '| Scale | Dimensions | Video seconds | Render seconds | Total incl QC | RAM MB |','|---|---|---|---|---|---|']
    for r in report['runs']: lines.append(f'|{r["scale"]}|{r["width"]}x{r["height"]}|{r["duration_sec"]:.3f}|{r["render_seconds"]}|{r["total_seconds"]}|{r["peak_tree_working_set_mb"]}|')
    write_text_atomic(project/'motion_review_benchmark.md','\n'.join(lines)+'\n')
    return report


def main():
    configure_console();parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('--project',type=Path);parser.add_argument('--scale',type=float,nargs='+',default=[.5,1.],choices=[.5,1.])
    args=parser.parse_args();report=review(args.source,get_settings(),project=args.project,scales=args.scale)
    print('Project: '+report['project'])


if __name__=='__main__': main()
