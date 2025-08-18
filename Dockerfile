FROM python:3.10-slim

# Evitar prompts interactivos en apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requisitos
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY . .

# Hugging Face asigna dinámicamente $PORT
EXPOSE 7860

# Comando de inicio
CMD streamlit run app.py --server.port $PORT --server.address 0.0.0.0
