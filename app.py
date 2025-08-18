# app.py
import os, tempfile, shutil, streamlit as st
from twitch_streamer import get_latest_vods_urls
from analyzer import analyze_by_chunks
from clip_selector import select_top, render_mix
from utils_ffmpeg import ffprobe_duration
from pathlib import Path
import subprocess

st.set_page_config(page_title="Twitch Clips Final", layout="wide")
st.title("🎬 Twitch Clips — Última versión optimizada")

st.markdown("Introduce nombres de streamers (ej: Illojuan, ElXokas, Ibai) separados por comas.")

streamers_input = st.text_input("Streamers:", value="Illojuan,ElXokas,Ibai,AuronPlay,TheGrefg")
max_vods = st.slider("VODs por streamer (últimos):", 1, 5, 5)
chunk_minutes = st.slider("Tamaño chunk análisis (minutos):", 2, 10, 5)
model_choice = st.selectbox("Modelo Whisper (más rápido = tiny, más preciso = small)", ["tiny","small"], index=0)
st.session_state.setdefault("whisper_model_name", model_choice)

run = st.button("Generar mixes (1h por streamer)")

if run:
    streamers = [s.strip() for s in streamers_input.split(",") if s.strip()]
    for sname in streamers:
        st.header(f"🔎 {sname}")
        try:
            urls = get_latest_vods_urls(sname, max_videos=max_vods)
            if not urls:
                st.warning("No VODs encontrados.")
                continue
            tmpdir = tempfile.mkdtemp(prefix=f"{sname}_")
            vod_paths=[]
            st.info("Descargando VODs (yt-dlp)…")
            for i,url in enumerate(urls,1):
                # download via yt-dlp to tmpdir
                cmd = ["yt-dlp","-f","best[ext=mp4]/best","-o", os.path.join(tmpdir, f"vod_{i}.%(ext)s"), url]
                subprocess.run(cmd, check=True)
                # find file
                found=None
                for f in os.listdir(tmpdir):
                    if f.startswith(f"vod_{i}.") and f.endswith(".mp4"):
                        found=os.path.join(tmpdir,f); break
                if not found:
                    # fallback search
                    for f in os.listdir(tmpdir):
                        if f.startswith("vod_") and f.endswith(".mp4"):
                            found=os.path.join(tmpdir,f); break
                if found:
                    vod_paths.append(found)
            if not vod_paths:
                st.warning("No se pudieron descargar VODs.")
                shutil.rmtree(tmpdir, ignore_errors=True)
                continue

            st.info("Analizando VODs por chunks (esto puede tardar unos minutos en la primera transcripción).")
            all_intervals=[]
            for vp in vod_paths:
                iv = analyze_by_chunks(vp, chunk_seconds=int(chunk_minutes*60))
                # Note: analyze_by_chunks returns intervals relative to that VOD; we keep them as is and later cut each from its origin
                # For simplicity, attach source path in tuple: (start,end,score,source)
                for (a,b,c) in iv:
                    all_intervals.append((a,b,c,vp))

            # select top until 1h
            st.info("Seleccionando top intervals para mix (≤1h)…")
            # convert to (start,end,score) list (we will cut each from its origin)
            intervals = [(a,b,c,src) for (a,b,c,src) in all_intervals]
            # For selection we ignore source in density calc but keep mapping
            # use select_top adapted:
            # create list (s,e,score,src)
            dens_list=[]
            for s,e,sc,src in intervals:
                dur = max(0.01,e-s)
                dens_list.append(((sc/dur),s,e,sc,src))
            dens_list.sort(reverse=True)
            chosen=[]
            used=0.0
            timeline=[]
            for dens,s,e,sc,src in dens_list:
                dur=e-s
                if used+dur>3600.0:
                    remain=3600.0-used
                    if remain < 2.0:
                        continue
                    e = s+remain
                    dur = remain
                conflict=False
                for cs,ce,*_ in timeline:
                    if not (e <= cs or s >= ce):
                        conflict=True; break
                if conflict: continue
                timeline.append((s,e,sc,src))
                used += dur
                if used >= 3599: break
            timeline.sort(key=lambda x:x[0])

            st.info("Cortando segmentos y concatenando (FFmpeg)…")
            parts=[]
            for idx,(s,e,sc,src) in enumerate(timeline):
                outp = os.path.join(tmpdir, f"part_{idx:03d}.mp4")
                # cut from its origin src
                subprocess.run(["ffmpeg","-y","-ss",str(s),"-i",src,"-t",str(e-s),"-c","copy",outp], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                parts.append(outp)
            final_out = os.path.join(tmpdir, f"{sname}_mix.mp4")
            if parts:
                # write list
                listf = os.path.join(tmpdir, "list.txt")
                with open(listf,"w") as f:
                    for p in parts:
                        f.write(f"file '{os.path.abspath(p)}'\n")
                try:
                    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",listf,"-c","copy",final_out], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError:
                    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",listf,"-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac","-b:a","128k",final_out], check=True)
                st.video(final_out)
                with open(final_out,"rb") as f:
                    st.download_button("⬇️ Descargar mix .mp4", data=f, file_name=os.path.basename(final_out), mime="video/mp4")
            else:
                st.info("No se generaron segmentos.")

            shutil.rmtree(tmpdir, ignore_errors=True)

        except Exception as e:
            st.error(f"Error procesando {sname}: {e}")
