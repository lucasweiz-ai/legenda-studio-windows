from __future__ import annotations

import re

_TIMECODE = re.compile(r"^(?P<h>\d{1,3}):(?P<m>[0-5]\d):(?P<s>[0-5]\d)\.(?P<ms>\d{1,3})$")


def parse_timecode(value: str) -> float:
    """Converte HH:MM:SS.mmm em segundos, rejeitando valores ambíguos."""
    match = _TIMECODE.fullmatch(value.strip())
    if not match:
        raise ValueError("Use o formato HH:MM:SS.mmm.")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    milliseconds = int(match.group("ms").ljust(3, "0"))
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def format_timecode(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("O tempo não pode ser negativo.")
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"