from __future__ import annotations

from collections.abc import Iterable

from .models import CutRange, WordCaption

EPSILON = 1e-7


def normalize_cuts(cuts: Iterable[CutRange]) -> list[CutRange]:
    """Ordena e funde cortes sobrepostos ou encostados."""
    ordered = sorted(cuts, key=lambda cut: (cut.start, cut.end))
    if not ordered:
        return []
    normalized = [ordered[0]]
    for current in ordered[1:]:
        previous = normalized[-1]
        if current.start <= previous.end + EPSILON:
            normalized[-1] = CutRange(previous.start, max(previous.end, current.end))
        else:
            normalized.append(current)
    return normalized


def validate_cut_selection(start: float, end: float, duration: float) -> CutRange:
    if duration <= 0:
        raise ValueError("A duração do vídeo não está disponível.")
    cut = CutRange(start, end)
    if cut.start >= duration or cut.end > duration:
        raise ValueError("O trecho selecionado está fora do vídeo.")
    if cut.end - cut.start >= duration - EPSILON:
        raise ValueError("Não é possível excluir o vídeo inteiro.")
    return cut


def remaining_segments(duration: float, cuts: Iterable[CutRange]) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for cut in normalize_cuts(cuts):
        if cut.start > cursor + EPSILON:
            segments.append((cursor, cut.start))
        cursor = max(cursor, cut.end)
    if cursor < duration - EPSILON:
        segments.append((cursor, duration))
    return segments


def remap_time(seconds: float, cuts: Iterable[CutRange]) -> float | None:
    """Retorna a posição no vídeo cortado, ou None se estiver removida."""
    removed_before = 0.0
    for cut in normalize_cuts(cuts):
        if cut.start <= seconds < cut.end:
            return None
        if cut.end <= seconds:
            removed_before += cut.end - cut.start
        else:
            break
    return max(0.0, seconds - removed_before)


def remap_captions(captions: Iterable[WordCaption], cuts: Iterable[CutRange]) -> list[WordCaption]:
    normalized = normalize_cuts(cuts)
    result: list[WordCaption] = []
    for caption in captions:
        if any(caption.start < cut.end and caption.end > cut.start for cut in normalized):
            continue
        start = remap_time(caption.start, normalized)
        end = remap_time(caption.end, normalized)
        if start is not None and end is not None and end > start:
            result.append(WordCaption(caption.text, start, end))
    return result