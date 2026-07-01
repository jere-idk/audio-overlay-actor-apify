import asyncio
from .main import main

asyncio.run(main())
"""
Audio Overlay Actor
Sin dependencia del SDK de Apify — usa variables de entorno y
el filesystem directamente, que es lo que hace el SDK por debajo.
"""

from __future__ import annotations

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
    overlays: list[dict],
    audios_temporales: dict[str, Path],
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


async def main() -> None:
    # Apify pasa el input como archivo JSON en el Key-Value Store local
    input_path = Path(
        os.environ.get("APIFY_INPUT_KEY", "INPUT")
    )
    kv_dir = Path(
        os.environ.get(
            "APIFY_LOCAL_STORAGE_DIR",
            "/usr/src/app/apify_storage"
        )
    ) / "key_value_stores" / "default"

    input_file = kv_dir / "INPUT.json"
    if not input_file.exists():
        # En producción Apify lo pasa por variable de entorno directamente
        raw = os.environ.get("APIFY_INPUT", "{}")
        actor_input = json.loads(raw)
    else:
        actor_input = json.loads(input_file.read_text())

    base_audio_url: str = actor_input["baseAudioUrl"]
    overlays: list[dict] = actor_input.get("overlays", [])
    output_format: str = actor_input.get("outputFormat", "mp3")

    if not overlays:
        log("WARN", "No se especificaron overlays; el resultado será igual al audio base.")

    with tempfile.TemporaryDirectory() as carpeta_temp:
        carpeta_temp_path = Path(carpeta_temp)

        log("INFO", f"Descargando audio base: {base_audio_url}")
        ruta_base = download_audio(base_audio_url, carpeta_temp_path / "base_audio")
        audio_base = AudioSegment.from_file(ruta_base)
        duracion_base_seg = len(audio_base) / 1000
        log("INFO", f"Duración del audio base: {duracion_base_seg:.2f}s")

        audios_temporales: dict[str, Path] = {}
        for i, overlay in enumerate(overlays):
            url = overlay["audioUrl"]
            if url not in audios_temporales:
                log("INFO", f"Descargando overlay {i + 1}: {url}")
                audios_temporales[url] = download_audio(
                    url, carpeta_temp_path / f"overlay_{i}"
                )

        log("INFO", "Procesando overlay de audios...")
        resultado = hacer_overlay(audio_base, overlays, audios_temporales)

        ruta_resultado = carpeta_temp_path / f"resultado.{output_format}"
        resultado.export(ruta_resultado, format=output_format)
        log("INFO", f"Audio procesado: {duracion_base_seg:.2f}s")

        # Guardamos el resultado en el Key-Value Store de Apify
        token = os.environ.get("APIFY_TOKEN", "")
        store_id = os.environ.get("APIFY_DEFAULT_KEY_VALUE_STORE_ID", "")

        if token and store_id:
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
        else:
            # Modo local: guardamos en disco
            output_local = Path("output") / f"resultado.{output_format}"
            output_local.parent.mkdir(exist_ok=True)
            import shutil
            shutil.copy(ruta_resultado, output_local)
            log("INFO", f"Modo local: archivo guardado en {output_local}")
