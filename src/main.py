"""
Audio Overlay Actor
Lee el input desde la API de Apify usando las variables de entorno
que Apify inyecta automáticamente en cada run.
"""

import json
import os
import tempfile
from pathlib import Path

import requests
from pydub import AudioSegment


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
        inicio_ms = int(overlay["startTimeSec"] * 1000)
        resultado = resultado.overlay(audio_overlay, position=inicio_ms)
    return resultado


def log(nivel: str, mensaje: str) -> None:
    print(f"[{nivel}] {mensaje}", flush=True)


def get_input() -> dict:
    """
    Apify inyecta estas variables en cada run:
    - APIFY_TOKEN: token de autenticación
    - APIFY_DEFAULT_KEY_VALUE_STORE_ID: ID del store donde está el input
    Las usamos para leer el INPUT directamente desde la API.
    """
    token = os.environ.get("APIFY_TOKEN", "")
    store_id = os.environ.get("APIFY_DEFAULT_KEY_VALUE_STORE_ID", "")

    log("INFO", f"Store ID: {store_id}")

    if token and store_id:
        url = (
            f"https://api.apify.com/v2/key-value-stores/{store_id}"
            f"/records/INPUT?token={token}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError(
        "No se encontraron las variables APIFY_TOKEN o "
        "APIFY_DEFAULT_KEY_VALUE_STORE_ID. "
        "¿Estás corriendo esto fuera de Apify?"
    )


async def main() -> None:
    log("INFO", "Leyendo input...")
    actor_input = get_input()
    log("INFO", f"Input recibido: {json.dumps(actor_input)}")

    base_audio_url = actor_input["baseAudioUrl"]
    overlays = actor_input.get("overlays", [])
    output_format = actor_input.get("outputFormat", "mp3")

    if not overlays:
        log("WARN", "No se especificaron overlays.")

    with tempfile.TemporaryDirectory() as carpeta_temp:
        carpeta_temp_path = Path(carpeta_temp)

        log("INFO", f"Descargando audio base: {base_audio_url}")
        ruta_base = download_audio(base_audio_url, carpeta_temp_path / "base_audio")
        audio_base = AudioSegment.from_file(ruta_base)
        duracion_base_seg = len(audio_base) / 1000
        log("INFO", f"Duración del audio base: {duracion_base_seg:.2f}s")

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

        ruta_resultado = carpeta_temp_path / f"resultado.{output_format}"
        resultado.export(ruta_resultado, format=output_format)
        log("INFO", f"Audio procesado: {duracion_base_seg:.2f}s")

        token = os.environ.get("APIFY_TOKEN", "")
        store_id = os.environ.get("APIFY_DEFAULT_KEY_VALUE_STORE_ID", "")
        content_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"

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
