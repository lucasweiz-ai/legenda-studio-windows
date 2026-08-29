from __future__ import annotations

import ctypes
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..cuts import normalize_cuts, validate_cut_selection
from ..media import MediaError, MediaInfo, probe_media
from ..models import CutRange, WordCaption
from ..project import ProjectState, SessionStore, load_project, save_project
from ..themes import (
    THEME_DARK,
    THEME_LIGHT,
    THEME_SYSTEM,
    application_stylesheet,
    resolved_theme,
)
from ..timecode import format_timecode, parse_timecode
from ..workers import ExportWorker, SilenceWorker, TranscriptionWorker
from .timeline import TimelineWidget


APP_NAME = "Glimo Editor"


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / relative


def app_icon() -> QIcon:
    return QIcon(str(resource_path("assets/glimo-editor.ico")))


class PreviewPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("surface")
        self.video = QVideoWidget()
        self.video.setStyleSheet("background: #101010; border: 0;")
        video_palette = self.video.palette()
        video_palette.setColor(QPalette.ColorRole.Window, QColor("#101010"))
        self.video.setPalette(video_palette)
        self.video.setAutoFillBackground(True)
        self.caption = QLabel("")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setStyleSheet(
            "color: white; background: transparent; padding: 8px; border: 0; "
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


class RecentProjectsDialog(QDialog):
    def __init__(self, store: SessionStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.selected_project: Path | None = None
        self.setWindowTitle("Continuar de onde parou")
        self.setWindowIcon(app_icon())
        self.resize(720, 430)

        layout = QVBoxLayout(self)
        title = QLabel("Seus vídeos recentes")
        title.setProperty("heading", True)
        description = QLabel("Selecione um vídeo para recuperar legendas, cortes e a última posição reproduzida.")
        description.setProperty("muted", True)
        description.setWordWrap(True)
        self.list = QListWidget()
        self.list.setAccessibleName("Vídeos e projetos recentes")
        self.list.itemDoubleClicked.connect(lambda _item: self._continue())
        self.list.currentItemChanged.connect(lambda *_args: self._update_buttons())

        actions = QHBoxLayout()
        self.remove_button = QPushButton("Remover da lista")
        self.continue_button = QPushButton("Continuar")
        self.continue_button.setProperty("primary", True)
        new_button = QPushButton("Começar vazio")
        actions.addWidget(self.remove_button)
        actions.addStretch()
        actions.addWidget(new_button)
        actions.addWidget(self.continue_button)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.list, 1)
        layout.addLayout(actions)
        self.remove_button.clicked.connect(self._remove)
        self.continue_button.clicked.connect(self._continue)
        new_button.clicked.connect(self.reject)
        self._populate()

    @staticmethod
    def _date_label(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
            return parsed.strftime("%d/%m/%Y às %H:%M")
        except ValueError:
            return "data não disponível"

    def _populate(self) -> None:
        self.list.clear()
        for entry in self.store.recent():
            source = Path(str(entry.get("source", "")))
            available = source.is_file()
            state = "Disponível" if available else "Arquivo de vídeo não encontrado"
            item = QListWidgetItem(
                f"{entry.get('name') or source.name}\n{source}\n{state} • Última edição: {self._date_label(str(entry.get('updated_at', '')))}"
            )
            item.setData(Qt.ItemDataRole.UserRole, str(entry.get("project", "")))
            item.setData(Qt.ItemDataRole.UserRole + 1, available)
            item.setSizeHint(QSize(0, 68))
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self._update_buttons()

    def _update_buttons(self) -> None:
        item = self.list.currentItem()
        self.remove_button.setEnabled(item is not None)
        self.continue_button.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole + 1)))

    def _remove(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        self.store.remove(Path(str(item.data(Qt.ItemDataRole.UserRole))))
        self._populate()

    def _continue(self) -> None:
        item = self.list.currentItem()
        if not item or not item.data(Qt.ItemDataRole.UserRole + 1):
            return
        self.selected_project = Path(str(item.data(Qt.ItemDataRole.UserRole)))
        self.accept()


class MainWindow(QMainWindow):
    statusMessage = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1060, 720)
        self.source: Path | None = None
        self.info: MediaInfo | None = None
        self.captions: list[WordCaption] = []
        self.cuts: list[CutRange] = []
        self.cut_history: list[list[CutRange]] = []
        self.current_project: Path | None = None
        self.worker_thread: QThread | None = None
        self.worker = None
        self._worker_label = ""
        self._last_worker_message = ""
        self._updating_table = False
        self.settings = QSettings("Glimo", APP_NAME)
        self.session_store = SessionStore()
        self.theme_preference = str(self.settings.value("theme", THEME_SYSTEM))
        self._resolved_theme = ""

        self._autosave_debounce = QTimer(self)
        self._autosave_debounce.setSingleShot(True)
        self._autosave_debounce.setInterval(500)
        self._autosave_debounce.timeout.connect(self._auto_save)
        self._periodic_save = QTimer(self)
        self._periodic_save.setInterval(15_000)
        self._periodic_save.timeout.connect(self._auto_save)
        self._periodic_save.start()
        self._theme_timer = QTimer(self)
        self._theme_timer.setInterval(1_500)
        self._theme_timer.timeout.connect(self._refresh_system_theme)
        self._theme_timer.start()

        self._build_ui()
        self._connect_shortcuts()
        self._apply_theme()
        self._set_status("Abra um vídeo ou continue um projeto recente.")

    def _build_ui(self) -> None:
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 10)
        outer.setSpacing(10)

        brand_row = QHBoxLayout()
        brand_icon = QLabel()
        brand_icon.setPixmap(app_icon().pixmap(30, 30))
        brand_icon.setFixedSize(34, 34)
        brand_name = QLabel(APP_NAME)
        brand_name.setProperty("heading", True)
        self.file_label = QLabel("Nenhum vídeo aberto")
        self.file_label.setProperty("muted", True)
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        theme_label = QLabel("Tema")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Automático (Windows)", THEME_SYSTEM)
        self.theme_combo.addItem("Claro", THEME_LIGHT)
        self.theme_combo.addItem("Escuro", THEME_DARK)
        index = self.theme_combo.findData(self.theme_preference)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.theme_combo.setAccessibleName("Tema da interface")
        brand_row.addWidget(brand_icon)
        brand_row.addWidget(brand_name)
        brand_row.addSpacing(12)
        brand_row.addWidget(self.file_label, 1)
        brand_row.addWidget(theme_label)
        brand_row.addWidget(self.theme_combo)
        outer.addLayout(brand_row)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.open_button = QPushButton("Abrir vídeo")
        self.open_button.setProperty("primary", True)
        self.open_project_button = QPushButton("Abrir projeto")
        self.save_project_button = QPushButton("Salvar projeto")
        self.caption_button = QPushButton("Gerar legenda")
        self.silence_button = QPushButton("Cortar silêncios")
        self.export_button = QPushButton("Exportar MP4")
        self.save_project_button.setEnabled(False)
        self.caption_button.setEnabled(False)
        self.silence_button.setEnabled(False)
        self.export_button.setEnabled(False)
        for button in (
            self.open_button,
            self.open_project_button,
            self.save_project_button,
            self.caption_button,
            self.silence_button,
            self.export_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch()
        outer.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        editor = QWidget()
        left = QVBoxLayout(editor)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        self.preview = PreviewPanel()
        self.preview.setMinimumSize(580, 330)
        left.addWidget(self.preview, 1)
        self.timeline = TimelineWidget()
        left.addWidget(self.timeline)

        cut_toolbar = QHBoxLayout()
        self.mark_start = QPushButton("Marcar início")
        self.mark_end = QPushButton("Marcar fim")
        self.delete_cut = QPushButton("Excluir seleção")
        self.delete_cut.setProperty("danger", True)
        self.undo_cut = QPushButton("Desfazer corte")
        self.selection_label = QLabel("Nenhum trecho selecionado")
        self.selection_label.setProperty("muted", True)
        for button in (self.mark_start, self.mark_end, self.delete_cut, self.undo_cut):
            button.setEnabled(False)
            cut_toolbar.addWidget(button)
        cut_toolbar.addWidget(self.selection_label, 1, Qt.AlignmentFlag.AlignRight)
        left.addLayout(cut_toolbar)

        playback = QHBoxLayout()
        self.play_button = QPushButton("▶  Reproduzir")
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_label = QLabel("00:00:00.000")
        self.position_label.setStyleSheet("font-family: Consolas, monospace;")
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

        captions_panel = QFrame()
        captions_panel.setObjectName("surface")
        right = QVBoxLayout(captions_panel)
        table_title = QLabel("Legenda palavra a palavra")
        table_title.setProperty("heading", True)
        table_help = QLabel("Clique para ir até a palavra. Clique duas vezes para editar.")
        table_help.setProperty("muted", True)
        table_help.setWordWrap(True)
        self.caption_table = QTableWidget(0, 3)
        self.caption_table.setHorizontalHeaderLabels(["Legenda", "Início", "Fim"])
        self.caption_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.caption_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.caption_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.caption_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked | QTableWidget.EditTrigger.EditKeyPressed
        )
        self.caption_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right.addWidget(table_title)
        right.addWidget(table_help)
        right.addWidget(self.caption_table, 1)
        splitter.addWidget(editor)
        splitter.addWidget(captions_panel)
        splitter.setSizes([920, 430])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        bottom = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMinimumWidth(260)
        self.progress.hide()
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.hide()
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
        self.open_project_button.clicked.connect(self.open_project)
        self.save_project_button.clicked.connect(self.save_project)
        self.caption_button.clicked.connect(self.generate_captions)
        self.silence_button.clicked.connect(self.cut_silences)
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
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_playback)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_video)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, activated=self.open_project)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_project)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_mp4)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self._undo_cut)
        QShortcut(QKeySequence("Delete"), self, activated=self._delete_cut)

    def _theme_changed(self) -> None:
        self.theme_preference = str(self.theme_combo.currentData())
        self.settings.setValue("theme", self.theme_preference)
        self._apply_theme()

    def _refresh_system_theme(self) -> None:
        if self.theme_preference == THEME_SYSTEM and resolved_theme(THEME_SYSTEM) != self._resolved_theme:
            self._apply_theme()

    def _apply_theme(self) -> None:
        self._resolved_theme = resolved_theme(self.theme_preference)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(application_stylesheet(self._resolved_theme))
        self.timeline.set_theme(self._resolved_theme)

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _update_window_title(self) -> None:
        self.setWindowTitle(f"{APP_NAME} — {self.source.name}" if self.source else APP_NAME)

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir vídeo",
            "",
            "Vídeos (*.mp4 *.mov *.mkv *.avi *.webm *.m4v)",
        )
        if path:
            self._open_source(Path(path))

    def _open_source(self, selected: Path) -> bool:
        try:
            info = probe_media(selected)
        except (MediaError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível abrir o vídeo", str(exc))
            return False
        self.source = selected
        self.info = info
        self.current_project = None
        self.captions.clear()
        self.cuts.clear()
        self.cut_history.clear()
        self._populate_table()
        self._prepare_loaded_media(0)
        self._schedule_auto_save()
        return True

    def _prepare_loaded_media(self, position_ms: int) -> None:
        if not self.source or not self.info:
            return
        self.player.setSource(QUrl.fromLocalFile(str(self.source)))
        self.timeline.set_duration(self.info.duration)
        self.timeline.set_cuts(self.cuts)
        self.timeline.set_selection(None, None)
        self.caption_button.setEnabled(self.info.has_audio)
        self.silence_button.setEnabled(self.info.has_audio)
        self.export_button.setEnabled(True)
        self.save_project_button.setEnabled(True)
        for button in (self.mark_start, self.mark_end, self.delete_cut):
            button.setEnabled(True)
        self.undo_cut.setEnabled(False)
        self.file_label.setText(str(self.source))
        self._update_window_title()
        QTimer.singleShot(150, lambda: self.player.setPosition(min(position_ms, int(self.info.duration * 1000))))
        if self.info.has_audio:
            self._set_status(f"Vídeo aberto • {format_timecode(self.info.duration)}")
        else:
            self._set_status("Vídeo aberto sem áudio • legenda e corte de silêncios indisponíveis.")

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir projeto", "", "Projeto Glimo (*.glimo)")
        if path:
            self._load_project_file(Path(path), manual_project=True)

    def _load_project_file(self, path: Path, manual_project: bool) -> bool:
        try:
            state = load_project(path)
            if not state.source.is_file():
                raise ValueError(f"O vídeo usado por este projeto não foi encontrado:\n{state.source}")
            info = probe_media(state.source)
        except (ValueError, MediaError, OSError) as exc:
            QMessageBox.critical(self, "Não foi possível abrir o projeto", str(exc))
            return False
        self.source = state.source
        self.info = info
        self.captions = state.captions
        self.cuts = normalize_cuts(state.cuts)
        self.cut_history.clear()
        self.current_project = path if manual_project else None
        self._populate_table()
        self._prepare_loaded_media(state.position_ms)
        self._set_status("Projeto recuperado. Você pode continuar de onde parou.")
        self._schedule_auto_save()
        return True

    def show_recovery_dialog(self) -> None:
        if not self.session_store.recent():
            return
        dialog = RecentProjectsDialog(self.session_store, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_project:
            self._load_project_file(dialog.selected_project, manual_project=False)

    def _project_state(self) -> ProjectState | None:
        if not self.source:
            return None
        return ProjectState(
            source=self.source,
            captions=list(self.captions),
            cuts=list(self.cuts),
            position_ms=self.player.position(),
        )

    def save_project(self) -> None:
        state = self._project_state()
        if not state:
            return
        destination = self.current_project
        if destination is None:
            suggested = self.source.with_suffix(".glimo") if self.source else Path("projeto.glimo")
            path, _ = QFileDialog.getSaveFileName(self, "Salvar projeto", str(suggested), "Projeto Glimo (*.glimo)")
            if not path:
                return
            destination = Path(path)
            if destination.suffix.lower() != ".glimo":
                destination = destination.with_suffix(".glimo")
        try:
            save_project(destination, state)
            self.current_project = destination
            self.session_store.save(state)
            self._set_status(f"Projeto salvo em {destination.name}.")
        except OSError as exc:
            QMessageBox.critical(self, "Não foi possível salvar", str(exc))

    def _schedule_auto_save(self) -> None:
        if self.source:
            self._autosave_debounce.start()

    def _auto_save(self) -> None:
        state = self._project_state()
        if not state:
            return
        try:
            self.session_store.save(state)
            if self.current_project:
                save_project(self.current_project, state)
        except OSError:
            self._set_status("Não foi possível criar o salvamento automático desta sessão.")

    def toggle_playback(self) -> None:
        if not self.source:
            return
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
            self._schedule_auto_save()
        except ValueError as exc:
            QMessageBox.warning(self, "Horário inválido", str(exc))
            self._populate_table()

    def _range_selected(self, start: float, end: float) -> None:
        duration = max(0, end - start)
        self.selection_label.setText(f"Selecionado: {format_timecode(duration)}")
        self._set_status(f"Trecho selecionado: {format_timecode(start)} – {format_timecode(end)}")

    def _mark_start(self) -> None:
        self.timeline.selection_start = self.player.position() / 1000
        self.timeline.update()
        self._set_status("Início marcado no cursor de reprodução.")

    def _mark_end(self) -> None:
        self.timeline.selection_end = self.player.position() / 1000
        self.timeline.update()
        if self.timeline.selection_start is not None:
            self._range_selected(*sorted((self.timeline.selection_start, self.timeline.selection_end)))
        else:
            self._set_status("Fim marcado no cursor de reprodução.")

    def _delete_cut(self) -> None:
        if not self.info or self.timeline.selection_start is None or self.timeline.selection_end is None:
            if self.source:
                QMessageBox.information(self, "Selecione um trecho", "Arraste na linha do tempo ou marque o início e o fim.")
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
            self.selection_label.setText("Nenhum trecho selecionado")
            self.undo_cut.setEnabled(True)
            self._set_status("Trecho marcado em vermelho para remoção. O vídeo original permanece intacto.")
            self._schedule_auto_save()
        except ValueError as exc:
            QMessageBox.warning(self, "Corte inválido", str(exc))

    def _undo_cut(self) -> None:
        if self.cut_history:
            self.cuts = self.cut_history.pop()
            self.timeline.set_cuts(self.cuts)
            self.undo_cut.setEnabled(bool(self.cut_history))
            self._set_status("Último corte desfeito.")
            self._schedule_auto_save()

    def generate_captions(self) -> None:
        if not self.source or self.worker_thread:
            return
        worker = TranscriptionWorker(self.source, self.info.duration if self.info else None)
        self._start_worker(worker, "Gerando legenda", self._transcription_done)

    def cut_silences(self) -> None:
        if not self.source or not self.info or not self.info.has_audio or self.worker_thread:
            return
        worker = SilenceWorker(self.source, self.info.duration)
        self._start_worker(worker, "Analisando e cortando silêncios", self._silences_done)

    def _silences_done(self, detected: list[CutRange]) -> None:
        if not self.info:
            return
        if not detected:
            self._set_status("Nenhum silêncio longo foi encontrado com segurança.")
            return
        previous = list(self.cuts)
        combined = normalize_cuts([*self.cuts, *detected])
        if sum(cut.end - cut.start for cut in combined) >= self.info.duration:
            QMessageBox.warning(self, "Cortes não aplicados", "A detecção removeria o vídeo inteiro.")
            return
        self.cut_history.append(previous)
        self.cuts = combined
        self.timeline.set_cuts(self.cuts)
        self.undo_cut.setEnabled(True)
        self._set_status(f"{len(detected)} silêncios marcados em vermelho. Revise a linha do tempo antes de exportar.")
        self._schedule_auto_save()

    def export_mp4(self) -> None:
        if not self.source or not self.info or self.worker_thread:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar MP4",
            str(self.source.with_name(f"{self.source.stem}_editado.mp4")),
            "MP4 (*.mp4)",
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
            "Exportando MP4",
        )

    def _start_worker(self, worker, label: str, completion_handler=None) -> None:
        self.worker = worker
        self._worker_label = label
        self._last_worker_message = label
        self.worker_thread = QThread(self)
        worker.moveToThread(self.worker_thread)
        worker.progress.connect(self._worker_progress)
        worker.failed.connect(self._worker_failed)
        worker.canceled.connect(self._worker_canceled)
        if completion_handler:
            worker.completed.connect(completion_handler)
        worker.completed.connect(self._worker_completed)
        self.worker_thread.started.connect(worker.run)
        self.worker_thread.finished.connect(self._worker_thread_finished)
        self.worker_thread.start()
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Aguarde…")
        self.progress.show()
        self.cancel_button.show()
        self._set_status(f"{label}…")
        QTimer.singleShot(3_000, self._show_long_wait_message)

    def _set_busy(self, busy: bool) -> None:
        self.open_button.setEnabled(not busy)
        self.open_project_button.setEnabled(not busy)
        self.save_project_button.setEnabled(bool(self.source) and not busy)
        self.caption_button.setEnabled(bool(self.info and self.info.has_audio) and not busy)
        self.silence_button.setEnabled(bool(self.info and self.info.has_audio) and not busy)
        self.export_button.setEnabled(bool(self.source) and not busy)
        self.cancel_button.setEnabled(busy)

    def _show_long_wait_message(self) -> None:
        if self.worker:
            detail = self._last_worker_message.rstrip(". …")
            self._set_status(f"{detail}. Aguarde — esta ação pode levar vários minutos.")

    def _worker_progress(self, value, message: str) -> None:
        self._last_worker_message = message
        if isinstance(value, int):
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(value, 100)))
            self.progress.setFormat("%p%")
            self._set_status(f"{message} {max(0, min(value, 100))}%")
        else:
            self.progress.setRange(0, 0)
            self.progress.setFormat("Aguarde…")
            self._set_status(message)

    def _transcription_done(self, captions: list[WordCaption]) -> None:
        self.captions = captions
        self._populate_table()
        self._set_status(f"{len(captions)} palavras transcritas.")
        self._schedule_auto_save()

    def _worker_completed(self) -> None:
        if self.worker and isinstance(self.worker, ExportWorker):
            self._set_status("MP4 exportado com sucesso.")
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
        self._set_busy(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("Concluído")
        self.cancel_button.hide()
        QTimer.singleShot(1_500, lambda: self.progress.hide() if not self.worker else None)
        if self.worker_thread:
            self.worker_thread.quit()

    def closeEvent(self, event) -> None:
        self._auto_save()
        if self.worker:
            self.worker.cancel()
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(3_000)
        super().closeEvent(event)


def run() -> int:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Glimo.Editor")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setOrganizationName("Glimo")
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    QTimer.singleShot(0, window.show_recovery_dialog)
    return app.exec()

