# clip_selector.py
from typing import List, Tuple
import heapq
from utils_ffmpeg import cut_segment_copy, concat_mp4
import os, tempfile

def select_top(intervals: List[Tuple[float,float,float]], max_total_seconds: float = 3600.0) -> List[Tuple[float,float,float]]:
    # greedy by score/duration
    items = []
    for s,e,sc in intervals:
        dur = max(0.01, e-s)
        items.append(((sc/dur), s,e,sc))
    items.sort(reverse=True)
    chosen=[]
    used=0.0
    timeline=[]
    for dens,s,e,sc in items:
        dur = e-s
        if used + dur > max_total_seconds:
            remain = max_total_seconds - used
            if remain < 2.0:
                continue
            e = s + remain
            dur = remain
        conflict=False
        for cs,ce,_ in timeline:
            if not (e <= cs or s >= ce):
                conflict=True; break
        if conflict: continue
        timeline.append((s,e,sc))
        used += dur
        if used >= max_total_seconds - 1: break
    timeline.sort(key=lambda x:x[0])
    return timeline

def render_mix(intervals: List[Tuple[float,float,float]], source_media: str, output_path: str):
    tmpdir = tempfile.mkdtemp()
    parts=[]
    for i,(s,e,sc) in enumerate(intervals):
        outp=os.path.join(tmpdir, f"part_{i:03d}.mp4")
        cut_segment_copy(source_media, s, e, outp)
        parts.append(outp)
    concat_mp4(parts, output_path)
    # optional: cleanup parts
    for p in parts:
        try: os.remove(p)
        except: pass
