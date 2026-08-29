import sys
import traceback
from pathlib import Path


def self_test() -> int:
    """Valida dependências críticas dentro do pacote portátil."""
    from legenda_studio.media import find_binary

    log_path = Path("GlimoEditor-self-test.log")
    log_path.write_text("Iniciando autoteste.\n", encoding="utf-8")
    find_binary("ffmpeg")
    find_binary("ffprobe")
    with log_path.open("a", encoding="utf-8") as log:
        log.write("FFmpeg e FFprobe encontrados.\n")
    from faster_whisper import WhisperModel

    with log_path.open("a", encoding="utf-8") as log:
        log.write("Motor de transcrição importado.\n")
    if WhisperModel is None:
        raise RuntimeError("O motor de transcrição não pôde ser carregado.")
    log_path.unlink(missing_ok=True)
    return 0


def startup_test() -> int:
    """Abre e fecha a janela principal para detectar falhas de inicialização."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from legenda_studio.ui.main_window import APP_NAME, MainWindow, app_icon

    app = QApplication(sys.argv)
    app.setOrganizationName("Glimo")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    QTimer.singleShot(1000, app.quit)
    return app.exec()


def main() -> int:
    if "--self-test" in sys.argv:
        try:
            return self_test()
        except Exception:
            Path("GlimoEditor-self-test.log").write_text(traceback.format_exc(), encoding="utf-8")
            return 1
    if "--startup-test" in sys.argv:
        try:
            return startup_test()
        except Exception:
            Path("GlimoEditor-startup-test.log").write_text(traceback.format_exc(), encoding="utf-8")
            return 1
    from legenda_studio.ui.main_window import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())

