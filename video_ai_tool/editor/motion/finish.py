"""Fast final mux for complete motion scenes and auditable review artifacts."""
from pathlib import Path
import shutil
import subprocess
from PIL import Image,ImageDraw
from imageio_ffmpeg import get_ffmpeg_exe
from utils.atomic_io import write_json_atomic,write_text_atomic,discard_temp_file


def mux_scenes(results,timeline,audio,destination,render_dir,fps,mode,notify):
    concat=Path(render_dir)/".motion_concat.txt";sound=Path(render_dir)/".motion_audio.wav"
    by_id={r["scene_id"]:r for r in results}
    lines=["ffconcat version 1.0"]
    for scene in timeline.scenes:
        path=str(Path(by_id[scene.spec.id]["path"]).resolve()).replace("\\","/").replace("'","'\\''")
        lines.extend(["file '"+path+"'",f"duration {scene.duration:.9f}"])
    try:
        write_text_atomic(concat,"\n".join(lines)+"\n")
        audio.write_audiofile(str(sound),fps=44100,codec="pcm_s16le",logger=None)
        command=[get_ffmpeg_exe(),"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),"-i",str(sound),
            "-t",str(timeline.duration),"-map","0:v:0","-map","1:a:0","-vf",f"fps={fps},scale=out_range=tv:out_color_matrix=bt709,format=yuv420p","-c:v","libx264","-preset","ultrafast" if mode=="preview" else "fast","-crf","27" if mode=="preview" else "20",
            "-threads","4","-pix_fmt","yuv420p","-color_range","tv","-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-x264-params","colorprim=bt709:transfer=bt709:colormatrix=bt709","-c:a","aac","-b:a","192k","-movflags","+faststart",str(destination)]
        notify(.80,"Đang ghép các cảnh motion và âm thanh bằng FFmpeg")
        result=subprocess.run(command,capture_output=True,timeout=max(180,timeline.duration*12))
        if result.returncode: raise RuntimeError(result.stderr.decode("utf-8",errors="replace")[:2000])
    finally: discard_temp_file(concat);discard_temp_file(sound)


def save_review(timeline,results,video_path,*,scene_id=None):
    folder=timeline.project/"review_frames";folder.mkdir(exist_ok=True)
    frames=[];notes=[];checks=[];suffix=f"_scene_{scene_id}" if scene_id is not None else ""
    by_id={r["scene_id"]:r for r in results}
    reader=None
    try:
        for scene in timeline.scenes:
            result=by_id.get(scene.spec.id,{})
            target=folder/f"scene_{scene.spec.id}.png"
            source=Path(result.get("review_frame", "__missing__"))
            if source.is_file(): shutil.copyfile(source,target)
            else:
                if reader is None:
                    from editor.runtime import VideoFileClip
                    reader=VideoFileClip(str(video_path),audio=False)
                Image.fromarray(reader.get_frame(min(reader.duration-.05,scene.start+scene.duration*.5))).save(target)
                notes.append(f"Cảnh {scene.spec.id}: motion_layout nhóm 3: dự phòng Pillow, chưa đo bố cục DOM.")
            frames.append(str(target))
            for repair in result.get("repair_notes",[]): notes.append(f"Cảnh {scene.spec.id}: {repair}")
            for check in result.get("quality",[]):
                checks.append(dict(check,scene_id=scene.spec.id))
                if check["issues"]: notes.append(f"Cảnh {scene.spec.id}, shot {check['shot_id']}: motion_layout nhóm 3 sau tự sửa: {', '.join(check['issues'])}.")
            from agents.motion_beats import max_gap
            beats=[b.model_dump(mode="json") for shot in scene.shots if shot.spec.visual for b in shot.spec.visual.beats]
            gap=max_gap(beats,scene.duration)
            if gap>3.5+.001: notes.append(f"Cảnh {scene.spec.id}: motion_rhythm nhóm 3: khoảng beats {gap:.2f}s; cần kiểm tra chuyển động thực.")
        columns=min(3,max(1,len(frames)));thumb=(270,480)
        sheet=Image.new("RGB",(columns*thumb[0],((len(frames)+columns-1)//columns)*(thumb[1]+34)),"#0a1220")
        draw=ImageDraw.Draw(sheet)
        for i,path in enumerate(frames):
            with Image.open(path) as image:
                image.thumbnail(thumb)
                x=(i%columns)*thumb[0]+(thumb[0]-image.width)//2;y=(i//columns)*(thumb[1]+34)
                sheet.paste(image,(x,y));draw.text(((i%columns)*thumb[0]+8,y+thumb[1]+8),f"Scene {timeline.scenes[i].spec.id}",fill="white")
        sheet.save(folder/("contact_sheet"+suffix+".png"))
    finally:
        if reader: reader.close()
    unique=list(dict.fromkeys(notes))
    for note in unique:
        if note not in timeline.plan.review_notes: timeline.plan.review_notes.append(note)
    warnings=[n for n in unique if "nhóm 3" in n]
    timeline.warnings.extend(n for n in warnings if n not in timeline.warnings)
    all_notes=list(dict.fromkeys(timeline.plan.review_notes+unique))
    report={"checks":checks,"review_notes":all_notes,"frames":frames,"contact_sheet":str(folder/("contact_sheet"+suffix+".png")),"scope":"DOM samples after one layout repair; not semantic fact validation or exhaustive per-frame proof"}
    write_json_atomic(timeline.project/("render/motion_review"+suffix+".json"),report)
    return report
