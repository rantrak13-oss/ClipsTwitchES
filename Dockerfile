FROM python:3.10-slim

# Instalar dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio app
WORKDIR /app

# Copiar requirements primero (para cacheo de capas)
COPY requirements.txt .

# Instalar dependencias (optimizado para Hugging Face CPU)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la app
COPY . .

# Puerto para Hugging Face
ENV PORT=7860

# Comando de arranque (Streamlit)
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
