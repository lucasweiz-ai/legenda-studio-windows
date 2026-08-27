from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class MediaError(RuntimeError):
    """Erro amigável para mídia ou dependências ausentes."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    frame_rate: str
    has_audio: bool


def find_binary(name: str) -> str:
    candidate = shutil.which(name)
    if candidate:
        return candidate
    bundled = Path(__file__).resolve().parent.parent / "runtime" / f"{name}.exe"
    if bundled.exists():
        return str(bundled)
    raise MediaError(f"{name} não foi encontrado. Inclua FFmpeg no pacote do aplicativo.")


def probe_media(path: Path, ffprobe: str | None = None) -> MediaInfo:
    probe = ffprobe or find_binary("ffprobe")
    command = [
        probe,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,width,height,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise MediaError("Não foi possível ler este vídeo. O arquivo pode estar danificado ou não ser compatível.") from exc
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video is None:
        raise MediaError("O arquivo não contém uma faixa de vídeo válida.")
    try:
        duration = float(payload["format"]["duration"])
        width, height = int(video["width"]), int(video["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaError("A duração ou resolução do vídeo não pôde ser identificada.") from exc
    return MediaInfo(
        duration=duration,
        width=width,
        height=height,
        frame_rate=str(video.get("r_frame_rate", "0/1")),
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
    )