"""Gera os ícones raster do Glimo Editor a partir da geometria da marca."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def draw_icon(size: int) -> Image.Image:
    scale = size / 1024

    def box(values: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return tuple(round(value * scale) for value in values)

    def points(values: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(round(x * scale), round(y * scale)) for x, y in values]

    image = Image.new("RGBA", (size, size), "#111111")
    draw = ImageDraw.Draw(image)
    draw.rectangle(box((64, 64, 960, 960)), fill="#F7C600")
    draw.polygon(points([(326, 244), (760, 512), (326, 780)]), fill="#111111")
    draw.rectangle(box((511, 250, 569, 774)), fill="#F7C600")
    draw.rectangle(box((180, 830, 844, 878)), fill="#111111")
    draw.rectangle(box((236, 808, 266, 900)), fill="#F7C600")
    draw.rectangle(box((758, 808, 788, 900)), fill="#F7C600")
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = draw_icon(1024)
    master.save(ASSETS / "glimo-editor.png")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    master.save(ASSETS / "glimo-editor.ico", sizes=[(size, size) for size in sizes])
    print("Ícones criados em assets/glimo-editor.png e assets/glimo-editor.ico")


if __name__ == "__main__":
    main()

