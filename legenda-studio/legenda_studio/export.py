from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path
from threading import Event

from .ass import generate_ass
from .cuts import normalize_cuts, remaining_segments
from .media import MediaError, find_binary
from .models import CutRange, WordCaption


class ExportCancelled(RuntimeError):
    pass


def _filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _subtitle_filter(ass_path: Path, font_dir: Path) -> str:
    return f"subtitles=filename='{_filter_path(ass_path)}':fontsdir='{_filter_path(font_dir)}'"


def build_ffmpeg_command(
    source: Path,
    destination: Path,
    ass_path: Path,
    font_dir: Path,
    duration: float,
    cuts: Iterable[CutRange],
    has_audio: bool,
    ffmpeg: str | None = None,
) -> list[str]:
    binary = ffmpeg or find_binary("ffmpeg")
    normalized = normalize_cuts(cuts)
    command = [binary, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    subtitle = _subtitle_filter(ass_path, font_dir)

    if normalized:
        segments = remaining_segments(duration, normalized)
        if not segments:
            raise MediaError("Os cortes removeriam todo o vídeo.")
        filters: list[str] = []
        for index, (start, end) in enumerate(segments):
            filters.append(
                f"[0:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS[v{index}]"
            )
            if has_audio:
                filters.append(
                    f"[0:a]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[a{index}]"
                )
        video_inputs = "".join(f"[v{index}]" for index in range(len(segments)))
        if has_audio:
            concat_inputs = "".join(
                f"[v{index}][a{index}]" for index in range(len(segments))
            )
            filters.append(
                f"{concat_inputs}concat=n={len(segments)}:v=1:a=1[vbase][abase]"
            )
            filters.append(f"[vbase]{subtitle}[vout]")
            command += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[abase]"]
        else:
            filters.append(f"{video_inputs}concat=n={len(segments)}:v=1:a=0[vbase]")
            filters.append(f"[vbase]{subtitle}[vout]")
            command += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an"]
    else:
        command += ["-vf", subtitle, "-map", "0:v:0"]
        if has_audio:
            command += ["-map", "0:a:0"]
        else:
            command += ["-an"]

    command += [
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
    ]
    if has_audio:
        command += ["-c:a", "aac", "-b:a", "256k"]
    command += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(destination)]
    return command


def export_video(
    source: Path,
    destination: Path,
    ass_path: Path,
    font_dir: Path,
    duration: float,
    cuts: Iterable[CutRange],
    has_audio: bool,
    cancel_event: Event,
    progress: callable | None = None,
) -> None:
    if source.resolve() == destination.resolve():
        raise MediaError("Escolha um destino diferente do vídeo original.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = build_ffmpeg_command(
        source, destination, ass_path, font_dir, duration, cuts, has_audio
    )
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except OSError as exc:
        raise MediaError("Não foi possível iniciar o FFmpeg para exportar o vídeo.") from exc
    try:
        output_lines: list[str] = []
        output_duration = duration - sum(cut.end - cut.start for cut in normalize_cuts(cuts))
        if process.stdout:
            for line in process.stdout:
                output_lines.append(line)
                if cancel_event.is_set():
                    process.terminate()
                    process.wait(timeout=5)
                    raise ExportCancelled("Exportação cancelada.")
                if progress and line.startswith("out_time_ms="):
                    try:
                        elapsed = int(line.partition("=")[2]) / 1_000_000
                        progress(min(99, int(elapsed * 100 / max(output_duration, 0.001))), "Exportando MP4…")
                    except ValueError:
                        pass
        while process.poll() is None:
            if cancel_event.is_set():
                process.terminate()
                process.wait(timeout=5)
                raise ExportCancelled("Exportação cancelada.")
        output = "".join(output_lines)
        if process.returncode != 0:
            detail = output.strip().splitlines()[-1] if output.strip() else "FFmpeg não informou o motivo."
            raise MediaError(f"Não foi possível exportar o vídeo: {detail}")
    except Exception:
        if destination.exists():
            destination.unlink()
        raise