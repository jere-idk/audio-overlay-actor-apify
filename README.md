# 🎵 Audio Overlay Actor

An [Apify](https://apify.com) Actor that merges one or more audio files on top of a base audio track, at specific points in time.

## How it works

- The **base audio** (`baseAudioUrl`) always determines the total duration of the output.
- Each audio in `overlays` is mixed in starting at its own `startTimeSec` (in seconds from the beginning of the result).
- If an overlay extends beyond the end of the base audio, it is automatically trimmed. The final duration **always** equals the duration of the base audio — no exceptions.

## Input

```json
{
  "baseAudioUrl": "https://example.com/base.mp3",
  "overlays": [
    {
      "audioUrl": "https://example.com/overlay.mp3",
      "startTimeSec": 5
    }
  ],
  "outputFormat": "mp3"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `baseAudioUrl` | string | ✅ | Public URL of the base audio file. Its duration defines the output duration. |
| `overlays` | array | ✅ | List of audio files to mix in, each with their own start time. Can be empty. |
| `overlays[].audioUrl` | string | ✅ | Public URL of the audio to overlay (mp3 or wav). |
| `overlays[].startTimeSec` | number | ✅ | Second at which this overlay starts playing in the final result. Must be ≥ 0. |
| `outputFormat` | string | ❌ | Output file format: `mp3` (default) or `wav`. |

### Supported audio sources

The Actor downloads audio files directly via URL. The URL must return the raw audio file — not an HTML page or a download confirmation screen.

✅ Works: `raw.githubusercontent.com`, direct Dropbox links (`?dl=1`), any direct download URL.  
❌ Doesn't work: Google Drive share links, YouTube, SoundCloud, or any URL that requires login.

### Multiple overlays example

You can mix more than one audio on top of the base:

```json
{
  "baseAudioUrl": "https://example.com/music.mp3",
  "overlays": [
    { "audioUrl": "https://example.com/voiceover.mp3", "startTimeSec": 0 },
    { "audioUrl": "https://example.com/jingle.mp3", "startTimeSec": 30 }
  ],
  "outputFormat": "mp3"
}
```

## Output

The Actor saves the resulting audio file to the run's Key-Value Store under the key `OUTPUT`. You can access it from:

- The **Storage** tab in the Apify Console after the run completes.
- Directly via the API:
  ```
  https://api.apify.com/v2/key-value-stores/{storeId}/records/OUTPUT
  ```

The run log also prints the full download URL at the end:
```
[INFO] Audio final disponible en: https://api.apify.com/v2/key-value-stores/.../records/OUTPUT
```

## Tech stack

- **Python 3.12**
- **Pydub** — audio mixing and processing
- **FFmpeg** — underlying audio engine (installed via Dockerfile)
- **Requests** — downloading audio files from URLs

## Roadmap (v2)

- [ ] Per-overlay volume control (`volumeDb`)
- [ ] Fade in / fade out
- [ ] Audio sequencing (back-to-back, not just simultaneous)
- [ ] Loop an overlay N times
- [ ] Trim the base audio before processing
