# utils_ffmpeg.py
import subprocess, json, os, tempfile
from typing import List

def ffprobe_duration(path: str) -> float:
    cmd = ["ffprobe","-v","error","-print_format","json","-show_entries","format=duration", path]
    out = subprocess.check_output(cmd).decode()
    data = json.loads(out)
    return float(data["format"]["duration"])

def cut_segment_copy(input_path: str, start: float, end: float, out_path: str):
    # cut using stream copy when possible
    duration = max(0.01, end - start)
    cmd = ["ffmpeg","-y","-ss",str(start),"-i",input_path,"-t",str(duration),"-c","copy",out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def concat_mp4(paths: List[str], out_path: str):
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        for p in paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        listfile = f.name
    cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c","copy",out_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        # fallback re-encode
        cmd = ["ffmpeg","-y","-f","concat","-safe","0","-i",listfile,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","128k",out_path]
        subprocess.run(cmd, check=True)
    os.remove(listfile)

def measure_volume_segment(input_path: str, start: float, end: float) -> float:
    # approximate RMS by astats and parse stderr; returns RMS dB (negative)
    duration = max(0.01, end - start)
    cmd = ["ffmpeg","-ss",str(start),"-t",str(duration),"-i",input_path,"-af","astats=metadata=1:reset=1","-f","null","-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    vol = -60.0
    for line in proc.stderr.splitlines():
        if "RMS level dB" in line:
            try:
                vol = float(line.split(":")[-1].strip())
            except:
                pass
    return vol

