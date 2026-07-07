"""
Audio Overlay Actor
Lee el input desde la API de Apify usando las variables de entorno
que Apify inyecta automaticamente en cada run.
"""

import json
import os
import tempfile
from pathlib import Path

import requests
from pydub import AudioSegment


CONTENT_TYPES = {
    "mp3":  "audio/mpeg",
    "wav":  "audio/wav",
    "ogg":  "audio/ogg",
    "flac": "audio/flac",
    "aac":  "audio/aac",
    "m4a":  "audio/mp4",
    "opus": "audio/opus",
    "wma":  "audio/x-ms-wma",
}

SUPPORTED_FORMATS = list(CONTENT_TYPES.keys())

# Formatos que soportan control de bitrate (comprimidos con pérdida)
FORMATS_WITH_BITRATE = {"mp3", "ogg", "aac", "m4a", "opus", "wma"}


def download_audio(url: str, destino: Path) -> Path:
    respuesta = requests.get(url, timeout=60)
    respuesta.raise_for_status()
    destino.write_bytes(respuesta.content)
    return destino


def hacer_overlay(
    audio_base: AudioSegment,
    overlays: list,
    audios_temporales: dict,
) -> AudioSegment:
    resultado = audio_base
    for overlay in overlays:
        ruta_audio = audios_temporales[overlay["audioUrl"]]
        audio_overlay = AudioSegment.from_file(ruta_audio)

        # Aplicar volumen individual si se especificó (en dB)
        # +6dB = doble de volumen, -6dB = mitad, -20dB = muy suave
        volume_db = overlay.get("volumeDb", 0)
        if volume_db != 0:
            audio_overlay = audio_overlay + volume_db

        inicio_ms = int(overlay["startTimeSec"] * 1000)
        resultado = resultado.overlay(audio_overlay, position=inicio_ms)
    return resultado


def log(nivel: str, mensaje: str) -> None:
    print(f"[{nivel}] {mensaje}", flush=True)


def get_input(token: str, store_id: str) -> dict:
    url = (
        f"https://api.apify.com/v2/key-value-stores/{store_id}"
        f"/records/INPUT?token={token}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


async def main() -> None:
    token = os.environ.get("APIFY_TOKEN", "")
    store_id = os.environ.get("APIFY_DEFAULT_KEY_VALUE_STORE_ID", "")
    dataset_id = os.environ.get("APIFY_DEFAULT_DATASET_ID", "")

    if not token or not store_id:
        raise RuntimeError("No se encontraron APIFY_TOKEN o APIFY_DEFAULT_KEY_VALUE_STORE_ID.")

    log("INFO", "Leyendo input...")
    actor_input = get_input(token, store_id)
    log("INFO", f"Input recibido: {json.dumps(actor_input)}")

    base_audio_url = actor_input["baseAudioUrl"]
    overlays = actor_input.get("overlays", [])
    output_format = actor_input.get("outputFormat", "mp3").lower()
    bitrate = actor_input.get("bitrate", None)
    base_volume_db = actor_input.get("baseVolumeDb", 0)

    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Formato '{output_format}' no soportado. "
            f"Formatos válidos: {', '.join(SUPPORTED_FORMATS)}"
        )

    if not overlays:
        log("WARN", "No se especificaron overlays.")

    with tempfile.TemporaryDirectory() as carpeta_temp:
        carpeta_temp_path = Path(carpeta_temp)

        log("INFO", f"Descargando audio base: {base_audio_url}")
        ruta_base = download_audio(base_audio_url, carpeta_temp_path / "base_audio")
        audio_base = AudioSegment.from_file(ruta_base)

        # Volumen del audio base
        if base_volume_db != 0:
            log("INFO", f"Ajustando volumen del audio base: {base_volume_db:+}dB")
            audio_base = audio_base + base_volume_db

        duracion_base_seg = len(audio_base) / 1000
        log("INFO", f"Duracion del audio base: {duracion_base_seg:.2f}s")

        audios_temporales = {}
        for i, overlay in enumerate(overlays):
            url = overlay["audioUrl"]
            if url not in audios_temporales:
                log("INFO", f"Descargando overlay {i + 1}: {url}")
                audios_temporales[url] = download_audio(
                    url, carpeta_temp_path / f"overlay_{i}"
                )

        log("INFO", "Procesando overlay...")
        resultado = hacer_overlay(audio_base, overlays, audios_temporales)

        # Armar parametros de exportacion
        export_params = {"format": output_format}
        if bitrate and output_format in FORMATS_WITH_BITRATE:
            export_params["bitrate"] = f"{bitrate}k"
            log("INFO", f"Exportando en formato {output_format} a {bitrate}kbps")
        elif bitrate and output_format not in FORMATS_WITH_BITRATE:
            log("WARN", f"El formato {output_format} no soporta control de bitrate — ignorando parámetro.")
        else:
            log("INFO", f"Exportando en formato {output_format} (bitrate por defecto)")

        ruta_resultado = carpeta_temp_path / f"resultado.{output_format}"
        resultado.export(ruta_resultado, **export_params)
        log("INFO", f"Audio procesado: {duracion_base_seg:.2f}s")

        content_type = CONTENT_TYPES[output_format]
        upload_url = (
            f"https://api.apify.com/v2/key-value-stores/{store_id}"
            f"/records/OUTPUT?token={token}"
        )
        with open(ruta_resultado, "rb") as f:
            resp = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": content_type},
                timeout=120,
            )
            resp.raise_for_status()

        output_url = (
            f"https://api.apify.com/v2/key-value-stores/{store_id}/records/OUTPUT"
        )
        log("INFO", f"Audio final disponible en: {output_url}")

        if dataset_id:
            dataset_url = (
                f"https://api.apify.com/v2/datasets/{dataset_id}"
                f"/items?token={token}"
            )
            requests.post(
                dataset_url,
                json=[{
                    "outputUrl": output_url,
                    "durationSec": duracion_base_seg,
                    "format": output_format,
                    "bitrate": f"{bitrate}kbps" if bitrate else "default",
                }],
                timeout=30,
            )
            log("INFO", "Resultado guardado en dataset.")
