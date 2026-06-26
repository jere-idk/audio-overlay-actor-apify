"""
Audio Overlay Actor
--------------------
Toma un audio "base" y le superpone uno o más audios en momentos
específicos (en segundos). La duración del resultado final SIEMPRE
es igual a la duración del audio base, sin importar cuánto duren
los audios superpuestos.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import requests
from pydub import AudioSegment

from apify import Actor


def download_audio(url: str, destino: Path) -> Path:
    """
    Descarga un archivo de audio desde una URL pública y lo guarda
    en disco. Devuelve la ruta del archivo descargado.
    """
    respuesta = requests.get(url, timeout=60)
    respuesta.raise_for_status()  # lanza un error si la URL falla (404, 500, etc.)
    destino.write_bytes(respuesta.content)
    return destino


def hacer_overlay(
    audio_base: AudioSegment,
    overlays: list[dict],
    audios_temporales: dict[str, Path],
) -> AudioSegment:
    """
    Superpone cada audio de 'overlays' sobre 'audio_base', respetando
    el 'startTimeSec' de cada uno.

    Regla clave: la duración final SIEMPRE es la del audio_base.
    Pydub recorta automáticamente cualquier parte del overlay que
    se pase del final del audio base, así que no necesitamos
    lógica extra para eso.
    """
    resultado = audio_base

    for overlay in overlays:
        ruta_audio = audios_temporales[overlay["audioUrl"]]
        audio_overlay = AudioSegment.from_file(ruta_audio)

        # Pydub trabaja en milisegundos, por eso convertimos los segundos
        inicio_ms = int(overlay["startTimeSec"] * 1000)

        # .overlay() mezcla el audio_overlay sobre 'resultado' a partir
        # de 'position'. Si el audio_overlay se pasa del final de
        # 'resultado', Pydub simplemente lo corta ahí. Esto es
        # exactamente la regla de negocio que necesitamos.
        resultado = resultado.overlay(audio_overlay, position=inicio_ms)

    return resultado


async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        base_audio_url: str = actor_input["baseAudioUrl"]
        overlays: list[dict] = actor_input.get("overlays", [])
        output_format: str = actor_input.get("outputFormat", "mp3")

        if not overlays:
            Actor.log.warning(
                "No se especificaron overlays; el resultado será "
                "igual al audio base sin modificaciones."
            )

        with tempfile.TemporaryDirectory() as carpeta_temp:
            carpeta_temp_path = Path(carpeta_temp)

            # 1. Descargamos el audio base
            Actor.log.info(f"Descargando audio base: {base_audio_url}")
            ruta_base = download_audio(
                base_audio_url, carpeta_temp_path / "base_audio"
            )
            audio_base = AudioSegment.from_file(ruta_base)

            duracion_base_seg = len(audio_base) / 1000
            Actor.log.info(f"Duración del audio base: {duracion_base_seg:.2f}s")

            # 2. Descargamos cada audio a superponer
            audios_temporales: dict[str, Path] = {}
            for i, overlay in enumerate(overlays):
                url = overlay["audioUrl"]
                if url not in audios_temporales:
                    Actor.log.info(f"Descargando overlay {i + 1}: {url}")
                    audios_temporales[url] = download_audio(
                        url, carpeta_temp_path / f"overlay_{i}"
                    )

            # 3. Hacemos el overlay
            Actor.log.info("Procesando overlay de audios...")
            resultado = hacer_overlay(audio_base, overlays, audios_temporales)

            # 4. Exportamos el resultado al formato pedido
            ruta_resultado = carpeta_temp_path / f"resultado.{output_format}"
            resultado.export(ruta_resultado, format=output_format)

            # 5. Guardamos el archivo final en el Key-Value Store del Actor
            #    y obtenemos una URL pública para descargarlo.
            store = await Actor.open_key_value_store()
            content_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"
            await store.set_value(
                "OUTPUT",
                ruta_resultado.read_bytes(),
                content_type=content_type,
            )

            store_id = store.id
            base_url = (
                f"https://api.apify.com/v2/key-value-stores/{store_id}"
                f"/records/OUTPUT"
            )

            Actor.log.info(f"Audio final disponible en: {base_url}")

            # También lo dejamos en el dataset, por si preferís
            # consumir el resultado desde ahí en vez del KV store.
            await Actor.push_data(
                {
                    "outputUrl": base_url,
                    "durationSec": duracion_base_seg,
                    "format": output_format,
                }
            )
