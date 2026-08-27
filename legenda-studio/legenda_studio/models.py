from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WordCaption:
    text: str
    start: float
    end: float

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("A legenda não pode estar vazia.")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("O início deve ser menor que o fim.")


@dataclass(frozen=True, order=True)
class CutRange:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError("O trecho precisa ter início e fim válidos.")