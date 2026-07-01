# Imagen base oficial de Apify con Python ya configurado para Actors
FROM apify/actor-python:3.12

# Pydub necesita FFmpeg instalado en el sistema para poder leer/escribir
# y procesar archivos de audio (mp3, wav, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

CMD ["python3", "-m", "src"]
