import streamlit as st
from twitch_streamer import obtener_urls_ultimos_directos
from clip_selector import generar_clip_final

def main():
    st.set_page_config(page_title="🎬 Twitch Clip Generator", layout="wide")
    st.title("🎬 Twitch Clip Generator")
    st.write("Genera un mix de clips de los streamers automáticamente.")

    streamers = ["Illojuan", "ElXokas", "Ibai", "AuronPlay", "TheGrefg"]

    for streamer in streamers:
        st.subheader(f"🔴 Analizando a {streamer}...")

        try:
            urls = obtener_urls_ultimos_directos(streamer, max_videos=3)
        except Exception as e:
            st.error(f"Error al obtener directos de {streamer}: {e}")
            continue

        if not urls:
            st.warning(f"No encontré directos recientes de {streamer}")
            continue

        st.success(f"✅ Encontrados {len(urls)} VODs de {streamer}")
        st.write(urls)

        if st.button(f"Generar mix de {streamer}", key=streamer):
            with st.spinner("⏳ Procesando clips, esto puede tardar..."):
                output_file = generar_clip_final(urls, streamer)
            st.video(output_file)
            st.download_button("⬇️ Descargar clip", data=open(output_file, "rb"), file_name=f"{streamer}_mix.mp4")

if __name__ == "__main__":
    main()
