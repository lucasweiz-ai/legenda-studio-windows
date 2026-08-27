"""Baixa FFmpeg e a fonte da legenda durante a montagem no Windows."""

from __future__ import annotations

import shutil
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
FONT_DIR = ROOT / "assets" / "fonts"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/static/Poppins-ExtraBold.ttf"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"Baixando {url}")
    urllib.request.urlretrieve(url, destination)


def main() -> None:
    RUNTIME.mkdir(exist_ok=True)
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg_zip = RUNTIME / "ffmpeg.zip"
    download(FFMPEG_URL, ffmpeg_zip)
    extract_dir = RUNTIME / "_ffmpeg"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()
    with zipfile.ZipFile(ffmpeg_zip) as archive:
        archive.extractall(extract_dir)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        matches = list(extract_dir.rglob(name))
        if not matches:
            raise FileNotFoundError(f"{name} não foi encontrado no pacote FFmpeg.")
        shutil.copy2(matches[0], RUNTIME / name)
    ffmpeg_zip.unlink()
    shutil.rmtree(extract_dir)
    download(FONT_URL, FONT_DIR / "Poppins-ExtraBold.ttf")


if __name__ == "__main__":
    main()