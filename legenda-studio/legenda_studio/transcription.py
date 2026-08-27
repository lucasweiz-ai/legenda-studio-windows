from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Event

from .models import WordCaption


def transcribe_brazilian_portuguese(
    path: Path,
    cancel_event: Event,
    duration: float | None = None,
    progress: Callable[[int, str], None] | None = None,
) -> list[WordCaption]:
    """Transcreve sob demanda para manter a inicialização leve."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("A transcrição não está instalada neste pacote.") from exc

    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(path),
        language="pt",
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
    )
    captions: list[WordCaption] = []
    for segment in segments:
        if cancel_event.is_set():
            return []
        words = getattr(segment, "words", None) or []
        for word in words:
            if cancel_event.is_set():
                return []
            text = (word.word or "").strip()
            if text and word.start is not None and word.end is not None and word.end > word.start:
                captions.append(WordCaption(text, float(word.start), float(word.end)))
        if progress:
            percentage = (
                min(99, int(float(segment.end) * 100 / duration))
                if duration and duration > 0
                else 0
            )
            progress(percentage, "Transcrevendo áudio…")
    return captions