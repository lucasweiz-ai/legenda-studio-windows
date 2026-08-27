from __future__ import annotations

from collections.abc import Iterable

from .models import WordCaption

PLAY_RES_X = 478
PLAY_RES_Y = 850
CAPTION_X = PLAY_RES_X // 2
CAPTION_Y = PLAY_RES_Y - 225


def _ass_time(seconds: float) -> str:
    centiseconds = int(round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", " ")


def generate_ass(captions: Iterable[WordCaption]) -> str:
    """Gera duas camadas por palavra: glow preto discreto e texto branco sem borda."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Legenda,Poppins ExtraBold,80,&H00FFFFFF,&H00FFFFFF,&H00000000,"
        "&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,0,0,225,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for caption in captions:
        text = _escape_ass(caption.text.strip())
        start, end = _ass_time(caption.start), _ass_time(caption.end)
        glow = (
            r"{\an2\pos("
            f"{CAPTION_X},{CAPTION_Y}"
            r")\1c&H000000&\1a&H88&\bord0\shad0\blur7}"
        )
        foreground = (
            r"{\an2\pos("
            f"{CAPTION_X},{CAPTION_Y}"
            r")\1c&HFFFFFF&\1a&H00&\bord0\shad0}"
        )
        lines.append(f"Dialogue: 0,{start},{end},Legenda,,0,0,0,,{glow}{text}")
        lines.append(f"Dialogue: 1,{start},{end},Legenda,,0,0,0,,{foreground}{text}")
    return "\n".join(lines) + "\n"