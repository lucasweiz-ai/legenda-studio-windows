from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ..cuts import normalize_cuts, validate_cut_selection
from ..media import MediaError, MediaInfo, find_binary, probe_media
from ..models import CutRange, WordCaption
from ..timecode import format_timecode, parse_timecode
from ..workers import ExportWorker, TranscriptionWorker
from .timeline import TimelineWidget


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


class PreviewPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.video = QVideoWidget()
        self.video.setStyleSheet("background: #101318;")
        self.caption = QLabel("")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setStyleSheet(
            "color: white; background: transparent; padding: 8px; "
            "font-family: 'Poppins ExtraBold'; font-size: 28px; font-weight: 800;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video)
        self.caption.setParent(self.video)
        self.caption.raise_()

    def position_caption(self) -> None:
        self.caption.adjustSize()
        self.caption.move(
            max(0, (self.video.width() - self.caption.width()) // 2),
            max(0, self.video.height() * 3 // 5),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.position_caption()


class MainWindow(QMainWindow):
    statusMessage = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Legenda Studio")
        self.resize(1360, 820)
        self.source: Path | None = None
        self.info: MediaInfo | None = None
        self.captions: list[WordCaption] = []
        self.cuts: list[CutRange] = []
        self.cut_history: list[list[CutRange]] = []
        self.worker_thread: QThread | None = None
        self.worker = None
        self._updating_table = False
        self._build_ui()
        self._connect_shortcuts()
        self._set_status("Abra um vídeo para começar.")

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f7f8fa; color: #182230; font-size: 13px; }
            QPushButton { background: #ffffff; border: 1px solid #d0d5dd; border-radius: 6px; padding: 8px 14px; }
            QPushButton:hover { background: #eff6ff; border-color: #93c5fd; }
            QPushButton:disabled { color: #98a2b3; background: #f2f4f7; }
            QTableWidget { background: #ffffff; border: 1px solid #d0d5dd; border-radius: 6px; gridline-color: #eaecf0; }
            QHeaderView::section { background: #f2f4f7; color: #475467; padding: 9px; border: 0; border-bottom: 1px solid #d0d5dd; }
            QSlider::groove:horizontal { height: 4px; background: #d0d5dd; border-radius: 2px; }
            QSlider::handle:horizontal { width: 12px; margin: -5px 0; background: #2563eb; border-radius: 6px; }
            """
        )
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 12)
        outer.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.open_button = QPushButton("Abrir vídeo")
        self.caption_button = QPushButton("Gerar legenda")
        self.export_button = QPushButton("Exportar MP4")
        self.caption_button.setEnabled(False)
        self.export_button.setEnabled(False)
        toolbar.addWidget(self.open_button)
        toolbar.addWidget(self.caption_button)
        toolbar.addWidget(self.export_button)
        toolbar.addStretch()
        self.file_label = QLabel("Nenhum vídeo aberto")
        self.file_label.setStyleSheet("color: #667085;")
        toolbar.addWidget(self.file_label)
        outer.addLayout(toolbar)

        content = QHBoxLayout()
        content.setSpacing(14)
        left = QVBoxLayout()
        self.preview = PreviewPanel()
        self.preview.setMinimumSize(580, 420)
        left.addWidget(self.preview, 1)
        self.timeline = TimelineWidget()
        left.addWidget(self.timeline)
        cut_toolbar = QHBoxLayout()
        self.mark_start = QPushButton("Marcar início")
        self.mark_end = QPushButton("Marcar fim")
        self.delete_cut = QPushButton("Excluir trecho")
        self.undo_cut = QPushButton("Desfazer")
        for button in (self.mark_start, self.mark_end, self.delete_cut, self.undo_cut):
            button.setEnabled(False)
            cut_toolbar.addWidget(button)
        cut_toolbar.addStretch()
        left.addLayout(cut_toolbar)
        playback = QHBoxLayout()
        self.play_button = QPushButton("▶  Reproduzir")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_label = QLabel("00:00:00.000")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setMaximumWidth(110)
        playback.addWidget(self.play_button)
        playback.addWidget(self.position_slider, 1)
        playback.addWidget(self.position_label)
        playback.addWidget(QLabel("Volume"))
        playback.addWidget(self.volume_slider)
        left.addLayout(playback)
        content.addLayout(left, 3)

        right = QVBoxLayout()
        right.addWidget(QLabel("<b>Legenda palavra a palavra</b>"))
        self.caption_table = QTableWidget(0, 3)
        self.caption_table.setHorizontalHeaderLabels(["Legenda", "Início", "Fim"])
        self.caption_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.caption_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.caption_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.caption_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.caption_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right.addWidget(self.caption_table, 1)
        content.addLayout(right, 2)
        outer.addLayout(content, 1)

        bottom = QHBoxLayout()
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setEnabled(False)
        self.status_label = QLabel()
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        bottom.addWidget(self.status_label, 2)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.cancel_button)
        outer.addLayout(bottom)
        self.setCentralWidget(root)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.preview.video)
        self.audio.setVolume(0.8)
        self.open_button.clicked.connect(self.open_video)
        self.caption_button.clicked.connect(self.generate_captions)
        self.export_button.clicked.connect(self.export_mp4)
        self.play_button.clicked.connect(self.toggle_playback)
        self.position_slider.sliderMoved.connect(self.player.setPosition)
        self.volume_slider.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(lambda value: self.position_slider.setRange(0, value))
        self.player.playbackStateChanged.connect(self._playback_state_changed)
        self.caption_table.cellClicked.connect(self._caption_clicked)
        self.caption_table.itemChanged.connect(self._caption_edited)
        self.timeline.seekRequested.connect(lambda seconds: self.player.setPosition(int(seconds * 1000)))
        self.timeline.rangeSelected.connect(self._range_selected)
        self.mark_start.clicked.connect(self._mark_start)
        self.mark_end.clicked.connect(self._mark_end)
        self.delete_cut.clicked.connect(self._delete_cut)
        self.undo_cut.clicked.connect(self._undo_cut)
        self.cancel_button.clicked.connect(self._cancel_worker)

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_playback)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_video)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_mp4)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo_cut)

    def _set_status(self, message: str, progress: int | None = None) -> None:
        self.status_label.setText(message)
        if progress is not None:
            self.progress.setValue(max(0, min(progress, 100)))

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir vídeo",
            "",
            "Vídeos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        if not path:
            return
        try:
            selected = Path(path)
            self.info = probe_media(selected)
            self.source = selected
            self.captions.clear()
            self.cuts.clear()
            self.cut_history.clear()
            self._populate_table()
            self.player.setSource(QUrl.fromLocalFile(str(selected)))
            self.timeline.set_duration(self.info.duration)
            self.timeline.set_cuts([])
            self.timeline.set_selection(None, None)
            self.caption_button.setEnabled(self.info.has_audio)
            self.export_button.setEnabled(True)
            for button in (self.mark_start, self.mark_end, self.delete_cut):
                button.setEnabled(True)
            self.undo_cut.setEnabled(False)
            self.file_label.setText(selected.name)
            if self.info.has_audio:
                self._set_status(f"Vídeo aberto · {format_timecode(self.info.duration)}")
            else:
                self._set_status("Vídeo aberto sem áudio · não é possível gerar legenda.")
        except (MediaError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível abrir o vídeo", str(exc))

    def toggle_playback(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _playback_state_changed(self, state) -> None:
        self.play_button.setText("❚❚  Pausar" if state == QMediaPlayer.PlaybackState.PlayingState else "▶  Reproduzir")

    def _position_changed(self, position: int) -> None:
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position)
        self.position_slider.blockSignals(False)
        seconds = position / 1000
        self.position_label.setText(format_timecode(seconds))
        self.timeline.set_position(seconds)
        active = next((caption.text for caption in self.captions if caption.start <= seconds <= caption.end), "")
        self.preview.caption.setText(active)
        self.preview.position_caption()

    def _populate_table(self) -> None:
        self._updating_table = True
        self.caption_table.setRowCount(len(self.captions))
        for row, caption in enumerate(self.captions):
            self.caption_table.setItem(row, 0, QTableWidgetItem(caption.text))
            self.caption_table.setItem(row, 1, QTableWidgetItem(format_timecode(caption.start)))
            self.caption_table.setItem(row, 2, QTableWidgetItem(format_timecode(caption.end)))
        self._updating_table = False

    def _caption_clicked(self, row: int, _column: int) -> None:
        if row < len(self.captions):
            self.player.setPosition(int(self.captions[row].start * 1000))

    def _caption_edited(self, item: QTableWidgetItem) -> None:
        if self._updating_table or item.row() >= len(self.captions):
            return
        row = item.row()
        original = self.captions[row]
        try:
            if item.column() == 0:
                updated = WordCaption(item.text(), original.start, original.end)
            else:
                start = parse_timecode(self.caption_table.item(row, 1).text())
                end = parse_timecode(self.caption_table.item(row, 2).text())
                updated = WordCaption(original.text, start, end)
                if self.info and end > self.info.duration:
                    raise ValueError("O horário está além do fim do vídeo.")
            self.captions[row] = updated
        except ValueError as exc:
            QMessageBox.warning(self, "Horário inválido", str(exc))
            self._populate_table()

    def _range_selected(self, start: float, end: float) -> None:
        self._set_status(
            f"Trecho selecionado: {format_timecode(start)} – {format_timecode(end)}"
        )

    def _mark_start(self) -> None:
        self.timeline.selection_start = self.player.position() / 1000
        self.timeline.update()
        self._set_status("Início marcado no playhead.")

    def _mark_end(self) -> None:
        self.timeline.selection_end = self.player.position() / 1000
        self.timeline.update()
        self._set_status("Fim marcado no playhead.")

    def _delete_cut(self) -> None:
        if not self.info or self.timeline.selection_start is None or self.timeline.selection_end is None:
            QMessageBox.information(self, "Selecione um trecho", "Arraste no timeline ou marque início e fim.")
            return
        start, end = sorted((self.timeline.selection_start, self.timeline.selection_end))
        try:
            selected = validate_cut_selection(start, end, self.info.duration)
            self.cut_history.append(list(self.cuts))
            self.cuts = normalize_cuts([*self.cuts, selected])
            if sum(cut.end - cut.start for cut in self.cuts) >= self.info.duration:
                self.cuts = self.cut_history.pop()
                raise ValueError("Não é possível excluir o vídeo inteiro.")
            self.timeline.set_cuts(self.cuts)
            self.timeline.set_selection(None, None)
            self.undo_cut.setEnabled(True)
            self._set_status("Trecho marcado para remoção. O original continua intacto.")
        except ValueError as exc:
            QMessageBox.warning(self, "Corte inválido", str(exc))

    def _undo_cut(self) -> None:
        if self.cut_history:
            self.cuts = self.cut_history.pop()
            self.timeline.set_cuts(self.cuts)
            self.undo_cut.setEnabled(bool(self.cut_history))
            self._set_status("Último corte desfeito.")

    def generate_captions(self) -> None:
        if not self.source or self.worker_thread:
            return
        self._start_worker(TranscriptionWorker(self.source, self.info.duration if self.info else None), "transcrição")
        self.worker.completed.connect(self._transcription_done)

    def export_mp4(self) -> None:
        if not self.source or not self.info or self.worker_thread:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self, "Exportar MP4", str(self.source.with_name(f"{self.source.stem}_legendado.mp4")), "MP4 (*.mp4)"
        )
        if not destination:
            return
        if Path(destination).resolve() == self.source.resolve():
            QMessageBox.warning(self, "Destino inválido", "Escolha um arquivo diferente do vídeo original.")
            return
        font_dir = resource_path("assets/fonts")
        self._start_worker(
            ExportWorker(
                self.source,
                Path(destination),
                list(self.captions),
                list(self.cuts),
                self.info.duration,
                self.info.has_audio,
                font_dir,
            ),
            "exportação",
        )

    def _start_worker(self, worker, label: str) -> None:
        self.worker = worker
        self.worker_thread = QThread(self)
        worker.moveToThread(self.worker_thread)
        worker.progress.connect(self._worker_progress)
        worker.failed.connect(self._worker_failed)
        worker.canceled.connect(self._worker_canceled)
        worker.completed.connect(self._worker_completed)
        self.worker_thread.started.connect(worker.run)
        self.worker_thread.finished.connect(self._worker_thread_finished)
        self.worker_thread.start()
        self.open_button.setEnabled(False)
        self.caption_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setEnabled(True)
        self._set_status(f"Executando {label}…", 0)

    def _worker_progress(self, value, message: str) -> None:
        self._set_status(message, value if isinstance(value, int) else None)

    def _transcription_done(self, captions: list[WordCaption]) -> None:
        self.captions = captions
        self._populate_table()
        self._set_status(f"{len(captions)} palavras transcritas.", 100)

    def _worker_completed(self) -> None:
        if self.worker and isinstance(self.worker, ExportWorker):
            self._set_status("MP4 exportado com sucesso.", 100)
            QMessageBox.information(self, "Exportação concluída", "O MP4 foi exportado com sucesso.")
        self._finish_worker()

    def _worker_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Operação não concluída", message)
        self._set_status("A operação falhou.")
        self._finish_worker()

    def _worker_canceled(self) -> None:
        self._set_status("Operação cancelada.")
        self._finish_worker()

    def _cancel_worker(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.cancel_button.setEnabled(False)
            self._set_status("Cancelando…")

    def _worker_thread_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.worker_thread:
            self.worker_thread.deleteLater()
        self.worker = None
        self.worker_thread = None

    def _finish_worker(self) -> None:
        self.open_button.setEnabled(True)
        self.caption_button.setEnabled(bool(self.info and self.info.has_audio))
        self.export_button.setEnabled(bool(self.source))
        self.cancel_button.setEnabled(False)
        self.progress.setEnabled(False)
        if self.worker_thread:
            self.worker_thread.quit()

    def closeEvent(self, event) -> None:
        if self.worker:
            self.worker.cancel()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
        super().closeEvent(event)


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Legenda Studio")
    window = MainWindow()
    window.show()
    return app.exec()