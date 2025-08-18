from typing import Dict, List
from pathlib import Path
import cv2
from scenedetect import SceneManager
from scenedetect.detectors import ContentDetector
from scenedetect.video_manager import VideoManager
from scenedetect.frame_timecode import FrameTimecode

def detect_scenes_and_motion(mp4_path: str, downscale=0.5, frame_skip=4) -> Dict:
    """
    Devuelve:
      {
        'scenes': [(start_s, end_s), ...],
        'motion': [(t_s, motion_score), ...]
      }
    RAM baja: lectura secuencial, sin buffers grandes.
    """
    # Escenas con PySceneDetect (content) a resolución reducida
    video_manager = VideoManager([mp4_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=27.0, min_scene_len=15))  # robusto

    video_manager.set_downscale_factor(max(1, int(1.0/downscale)))
    video_manager.start()
    scene_manager.detect_scenes(video_manager)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    for s, e in scene_list:
        start_s = s.get_seconds()
        end_s = e.get_seconds()
        scenes.append((start_s, end_s))
    video_manager.release()

    # Motion score simple (frame diff) con frame_skip
    cap = cv2.VideoCapture(mp4_path)
    prev = None
    t = 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    hop = int(max(1, frame_skip))
    motion = []
    i = 0
    while True:
        ret = cap.grab()
        if not ret:
            break
        if i % hop == 0:
            ret, frame = cap.retrieve()
            if not ret:
                break
            if downscale < 1.0:
                frame = cv2.resize(frame, (0,0), fx=downscale, fy=downscale)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                diff = cv2.absdiff(gray, prev)
                score = float(diff.mean())  # simple, barato en CPU
                motion.append((t, score))
            prev = gray
            t += hop / fps
        i += 1
    cap.release()
    return {"scenes": scenes, "motion": motion}
