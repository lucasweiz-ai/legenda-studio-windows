"""Monta e valida a pasta portátil do Glimo Editor no Windows."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "GlimoEditor"
INTERNAL_DIR = DIST_DIR / "_internal"


def main() -> None:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "GlimoEditor",
        "--icon",
        "assets/glimo-editor.ico",
        "--collect-all",
        "faster_whisper",
        "--add-data",
        "assets;assets",
        "--add-data",
        "runtime;runtime",
        "app.py",
    ]
    subprocess.run(command, cwd=ROOT, check=True)

    # O Qt usa a ICU fornecida pelo Windows. Uma ICU externa encontrada no PATH
    # pode ser coletada pelo PyInstaller e causar "procedimento não encontrado".
    for pattern in ("icuuc.dll", "icudt*.dll"):
        for incompatible in INTERNAL_DIR.glob(pattern):
            incompatible.unlink()

    shutil.copy2(ROOT / "LEIA-ME.md", DIST_DIR / "LEIA-ME.md")
    required = [
        DIST_DIR / "GlimoEditor.exe",
        INTERNAL_DIR / "runtime" / "ffmpeg.exe",
        INTERNAL_DIR / "runtime" / "ffprobe.exe",
        INTERNAL_DIR / "assets" / "fonts" / "Poppins-ExtraBold.ttf",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Arquivos obrigatórios ausentes no pacote: " + ", ".join(missing))
    print(f"Aplicativo portátil montado em {DIST_DIR}")


if __name__ == "__main__":
    main()

