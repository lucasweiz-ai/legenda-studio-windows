from __future__ import annotations

import re
import subprocess
from pathlib import Path
from threading import Event

from .media import MediaError, find_binary
from .models import CutRange


_START = re.compile(r"silence_start:\s*([0-9.]+)")
_END = re.compile(r"silence_end:\s*([0-9.]+)")
_TIME = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class SilenceDetectionCancelled(RuntimeError):
    pass


def parse_silence_output(output: str, duration: float, padding: float = 0.10) -> list[CutRange]:
    starts = [float(match.group(1)) for match in _START.finditer(output)]
    ends = [float(match.group(1)) for match in _END.finditer(output)]
    ranges: list[CutRange] = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else duration
        cut_start = max(0.0, start + padding)
        cut_end = min(duration, end - padding)
        if cut_end - cut_start >= 0.20:
            ranges.append(CutRange(cut_start, cut_end))
    return ranges


def detect_silences(
    source: Path,
    duration: float,
    cancel_event: Event,
    progress: callable | None = None,
    noise_db: int = -35,
    minimum_duration: float = 0.65,
) -> list[CutRange]:
    ffmpeg = find_binary("ffmpeg")
    command = [
        ffmpeg,
        "-hide_banner",
        "-stats_period",
        "0.5",
        "-i",
        str(source),
        "-vn",
        "-af",
        f"silencedetect=noise={noise_db}dB:d={minimum_duration}",
        "-f",
        "null",
        "-",
    ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise MediaError("Não foi possível iniciar a análise de silêncios.") from exc

    lines: list[str] = []
    try:
        if process.stdout:
            for line in process.stdout:
                lines.append(line)
                if cancel_event.is_set():
                    process.terminate()
                    process.wait(timeout=5)
                    raise SilenceDetectionCancelled("Análise cancelada.")
                match = _TIME.search(line)
                if match and progress:
                    elapsed = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
                    percentage = min(99, int(elapsed * 100 / max(duration, 0.001)))
                    progress(percentage, "Analisando silêncios…")
        return_code = process.wait()
        output = "".join(lines)
        if return_code != 0:
            detail = output.strip().splitlines()[-1] if output.strip() else "FFmpeg não informou o motivo."
            raise MediaError(f"Não foi possível analisar os silêncios: {detail}")
        if progress:
            progress(100, "Análise de silêncios concluída.")
        return parse_silence_output(output, duration)
    except Exception:
        if process.poll() is None:
            process.terminate()
        raise

