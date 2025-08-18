# clip_selector.py
import os, tempfile, subprocess, numpy as np
from typing import List
from hype_analyzer import combined_hype_score

def _select_top_times(scores, duration, top_n=5, min_gap=30.0):
    if len(scores)==0:
        return [0.0]
    idxs = np.argsort(scores)[::-1][:max(1, top_n)]
    step = duration / max(len(scores), 1)
    candidates = [(min(idx*step, max(0.0, duration-1e-3)), float(scores[idx])) for idx in idxs]
    selected=[]
    for start, score in sorted(candidates, key=lambda x: x[1], reverse=True):
        if all(abs(start - s0) >= min_gap for s0, _ in selected):
            selected.append((start, score))
    selected = sorted(selected, key=lambda x: x[0])
    return [s for s,_ in selected]

def _ffmpeg_extract_subclip(in_file, start, end, out_file):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", in_file,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        out_file
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def generate_final_mix(vod_paths: List[str], streamer_name: str, clip_length=60, top_n_per_vod=3, max_total_seconds=3600):
    tmpdir = tempfile.mkdtemp(prefix=f"{streamer_name}_mix_")
    subclip_files = []
    for i, vod in enumerate(vod_paths):
        # get duration via ffprobe (fast)
        try:
            res = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", vod],
                                 capture_output=True, text=True, check=True)
            duration = float(res.stdout.strip())
        except Exception:
            duration = 0.0
        scores = combined_hype_score(vod)
        starts = _select_top_times(scores, duration, top_n=top_n_per_vod, min_gap=30.0)
        for j, start in enumerate(starts):
            end = min(start + clip_length, duration)
            if end <= start: continue
            out_path = os.path.join(tmpdir, f"{streamer_name}_v{i}_c{j}.mp4")
            try:
                _ffmpeg_extract_subclip(vod, start, end, out_path)
                subclip_files.append(out_path)
            except Exception:
                continue
    if not subclip_files:
        raise RuntimeError("No subclips generados.")
    # Create concat file for ffmpeg demuxer
    list_file = os.path.join(tmpdir, "files.txt")
    with open(list_file, "w") as f:
        for p in subclip_files:
            f.write(f"file '{p}'\n")
    final_out = os.path.join(tmpdir, f"{streamer_name}_mix_final.mp4")
    # concat using ffmpeg demuxer (no re-encode)
    cmd_concat = ["ffmpeg","-y","-f","concat","-safe","0","-i",list_file,"-c","copy",final_out]
    try:
        subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        # Fallback: re-encode concat to ensure compatibility
        cmd_concat = ["ffmpeg","-y","-f","concat","-safe","0","-i",list_file,"-c:v","libx264","-preset","veryfast","-crf","28","-c:a","aac","-b:a","96k", final_out]
        subprocess.run(cmd_concat, check=True)
    # Limit length
    try:
        res = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1", final_out],
                             capture_output=True, text=True, check=True)
        dur = float(res.stdout.strip())
    except Exception:
        dur = 0.0
    if dur > max_total_seconds:
        tmp_trim = os.path.join(tmpdir, f"{streamer_name}_mix_final_trim.mp4")
        subprocess.run(["ffmpeg","-y","-ss","0","-to",str(max_total_seconds),"-i",final_out,"-c:v","libx264","-preset","veryfast","-crf","28","-c:a","aac","-b:a","96k", tmp_trim], check=True)
        os.replace(tmp_trim, final_out)
    return final_out

