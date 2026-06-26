# Audio Overlay Actor

Actor de Apify que superpone uno o más audios sobre un audio base, en
momentos de tiempo específicos.

## Regla de negocio

- El **audio base** (`baseAudioUrl`) determina la duración total del
  resultado final.
- Cada audio en `overlays` se mezcla a partir de su propio
  `startTimeSec` (en segundos, contado desde el inicio del resultado).
- Si un overlay se extiende más allá del final del audio base, se
  recorta automáticamente. La duración final **siempre** es igual a
  la duración del audio base.

## Input

```json
{
  "baseAudioUrl": "https://.../audio1.mp3",
  "overlays": [
    { "audioUrl": "https://.../audio2.mp3", "startTimeSec": 5 }
  ],
  "outputFormat": "mp3"
}
```

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `baseAudioUrl` | string | Sí | URL pública del audio base |
| `overlays` | array | Sí (puede ser vacío) | Lista de `{ audioUrl, startTimeSec }` |
| `outputFormat` | string | No (default `mp3`) | `mp3` o `wav` |

## Output

El Actor guarda el audio resultante en el Key-Value Store bajo la key
`OUTPUT`, y además registra en el dataset un objeto con la URL de
descarga, la duración y el formato:

```json
{
  "outputUrl": "https://api.apify.com/v2/key-value-stores/<id>/records/OUTPUT",
  "durationSec": 10.0,
  "format": "mp3"
}
```

## Correr localmente

```bash
pip install -r requirements.txt
# necesitás ffmpeg instalado en el sistema: apt-get install ffmpeg

mkdir -p storage/key_value_stores/default
cat > storage/key_value_stores/default/INPUT.json << 'EOF'
{
  "baseAudioUrl": "https://.../base.mp3",
  "overlays": [{ "audioUrl": "https://.../overlay.mp3", "startTimeSec": 5 }],
  "outputFormat": "mp3"
}
EOF

APIFY_LOCAL_STORAGE_DIR=./storage python3 -m src
```

## Próximos pasos (v2)

- Fades in/out
- Secuenciar audios (en vez de solo superponer)
- Ajuste de volumen por overlay
- Loops de audio
