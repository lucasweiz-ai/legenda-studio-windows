"""Gera o ICO multirresolução a partir da capivara oficial do Glimo Editor."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    source = ASSETS / "glimo-editor.png"
    master = Image.open(source).convert("RGBA")
    if master.size != (1024, 1024):
        master = master.resize((1024, 1024), Image.Resampling.LANCZOS)
        master.save(source)
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    master.save(ASSETS / "glimo-editor.ico", sizes=[(size, size) for size in sizes])
    print("ICO da capivara criado em assets/glimo-editor.ico")


if __name__ == "__main__":
    main()
