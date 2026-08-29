from __future__ import annotations

import tempfile
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from .ass import generate_ass
from .cuts import remap_captions
from .export import ExportCancelled, export_video
from .models import CutRange, WordCaption
from .silence import SilenceDetectionCancelled, detect_silences
from .transcription import transcribe_brazilian_portuguese


class TranscriptionWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self, source: Path, duration: float | None = None) -> None:
        super().__init__()
        self.source = source
        self.duration = duration
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            captions = transcribe_brazilian_portuguese(
                self.source,
                self.cancel_event,
                self.duration,
                lambda value, message: self.progress.emit(value, message),
            )
            if self.cancel_event.is_set():
                self.canceled.emit()
            else:
                self.completed.emit(captions)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self.cancel_event.set()


class ExportWorker(QObject):
    progress = Signal(object, str)
    completed = Signal()
    failed = Signal(str)
    canceled = Signal()

    def __init__(
        self,
        source: Path,
        destination: Path,
        captions: list[WordCaption],
        cuts: list[CutRange],
        duration: float,
        has_audio: bool,
        font_dir: Path,
    ) -> None:
        super().__init__()
        self.source = source
        self.destination = destination
        self.captions = captions
        self.cuts = cuts
        self.duration = duration
        self.has_audio = has_audio
        self.font_dir = font_dir
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            remapped = remap_captions(self.captions, self.cuts)
            with tempfile.TemporaryDirectory(prefix="glimo-editor-") as temporary:
                ass_path = Path(temporary) / "legendas.ass"
                ass_path.write_text(generate_ass(remapped), encoding="utf-8")
                export_video(
                    self.source,
                    self.destination,
                    ass_path,
                    self.font_dir,
                    self.duration,
                    self.cuts,
                    self.has_audio,
                    self.cancel_event,
                    lambda value, message: self.progress.emit(value, message),
                )
            if self.cancel_event.is_set():
                self.canceled.emit()
            else:
                self.completed.emit()
        except ExportCancelled:
            self.canceled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self.cancel_event.set()


class SilenceWorker(QObject):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)
    canceled = Signal()

    def __init__(self, source: Path, duration: float) -> None:
        super().__init__()
        self.source = source
        self.duration = duration
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            cuts = detect_silences(
                self.source,
                self.duration,
                self.cancel_event,
                lambda value, message: self.progress.emit(value, message),
            )
            if self.cancel_event.is_set():
                self.canceled.emit()
            else:
                self.completed.emit(cuts)
        except SilenceDetectionCancelled:
            self.canceled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self.cancel_event.set()

