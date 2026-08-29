"""Smoke test do pipeline FFmpeg usando um vídeo curto gerado localmente."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from threading import Event

from legenda_studio.ass import generate_ass
from legenda_studio.cuts import remap_captions
from legenda_studio.export import export_video
from legenda_studio.media import find_binary, probe_media
from legenda_studio.models import CutRange, WordCaption
from legenda_studio.silence import detect_silences


def main() -> None:
    ffmpeg = find_binary("ffmpeg")
    with tempfile.TemporaryDirectory(prefix="glimo-editor-e2e-") as folder:
        root = Path(folder)
        source = root / "entrada.mp4"
        destination = root / "saida.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x17324d:s=320x240:r=25:d=4",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=4",
                "-af",
                "volume=enable='between(t,1,2)':volume=0",
                "-shortest",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(source),
            ],
            check=True,
            capture_output=True,
        )
        cuts = [CutRange(1, 2)]
        detected = detect_silences(source, 4, Event())
        if not detected or not any(cut.start < 1.5 < cut.end for cut in detected):
            raise AssertionError(f"Silêncio central não foi detectado: {detected}")
        captions = [
            WordCaption("olá", 0.2, 0.7),
            WordCaption("removida", 1.2, 1.6),
            WordCaption("mundo", 2.2, 2.8),
        ]
        ass_path = root / "legendas.ass"
        ass_path.write_text(generate_ass(remap_captions(captions, cuts)), encoding="utf-8")
        export_video(
            source,
            destination,
            ass_path,
            Path(__file__).resolve().parents[1] / "assets" / "fonts",
            4,
            cuts,
            True,
            Event(),
        )
        result = probe_media(destination)
        if not (2.8 <= result.duration <= 3.2):
            raise AssertionError(f"Duração exportada inesperada: {result.duration}")
        if not result.has_audio or result.width != 320 or result.height != 240:
            raise AssertionError("O MP4 exportado perdeu vídeo, áudio ou resolução.")
        print("E2E FFmpeg OK:", destination.name, f"{result.duration:.2f}s")


if __name__ == "__main__":
    main()

