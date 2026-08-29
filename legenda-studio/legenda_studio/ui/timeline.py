from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..models import CutRange


class TimelineWidget(QWidget):
    """Linha do tempo com seleção por arraste, alças e cortes persistentes."""

    rangeSelected = Signal(float, float)
    seekRequested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(158)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Linha do tempo de edição")
        self.setToolTip("Clique para mover o cursor. Arraste para selecionar um trecho e use Excluir seleção.")
        self.duration = 0.0
        self.position = 0.0
        self.cuts: list[CutRange] = []
        self.selection_start: float | None = None
        self.selection_end: float | None = None
        self._press_time: float | None = None
        self._drag_mode: str | None = None
        self._theme = "light"
        self.setMouseTracking(True)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def set_duration(self, duration: float) -> None:
        self.duration = max(0.0, duration)
        self.update()

    def set_position(self, position: float) -> None:
        self.position = max(0.0, min(position, self.duration or position))
        self.update()

    def set_cuts(self, cuts: Iterable[CutRange]) -> None:
        self.cuts = list(cuts)
        self.update()

    def set_selection(self, start: float | None, end: float | None) -> None:
        self.selection_start = start
        self.selection_end = end
        self.update()

    def _track_rect(self) -> QRectF:
        return QRectF(18, 43, max(1, self.width() - 36), 84)

    def _video_rect(self) -> QRectF:
        track = self._track_rect()
        return QRectF(track.left(), track.top(), track.width(), 45)

    def _audio_rect(self) -> QRectF:
        track = self._track_rect()
        return QRectF(track.left(), track.top() + 51, track.width(), 33)

    def _time_at(self, point: QPointF) -> float:
        rect = self._track_rect()
        fraction = max(0.0, min(1.0, (point.x() - rect.left()) / rect.width()))
        return fraction * self.duration

    def _x_at(self, seconds: float) -> float:
        rect = self._track_rect()
        return rect.left() + (seconds / self.duration) * rect.width() if self.duration else rect.left()

    def _tick_interval(self) -> float:
        if self.duration <= 0:
            return 1.0
        target = self.duration / max(4, self.width() // 110)
        power = 10 ** math.floor(math.log10(max(target, 0.001)))
        for multiplier in (1, 2, 5, 10):
            if multiplier * power >= target:
                return multiplier * power
        return 10 * power

    @staticmethod
    def _short_time(seconds: float) -> str:
        total = max(0, int(round(seconds)))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        dark = self._theme == "dark"
        ink = QColor("#F5F5F5" if dark else "#111111")
        muted = QColor("#B9B9B9" if dark else "#5F6874")
        border = QColor("#4B4B4B" if dark else "#C9CED6")
        surface = QColor("#202020" if dark else "#FFFFFF")
        lane = QColor("#303030" if dark else "#E8EBEF")
        clip = QColor("#414141" if dark else "#D6DBE2")
        yellow = QColor("#F7C600")
        red = QColor("#DC3B3B")

        painter.fillRect(self.rect(), surface)
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(ink)
        painter.drawText(QRectF(18, 5, 120, 20), Qt.AlignmentFlag.AlignVCenter, "LINHA DO TEMPO")
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(muted)
        painter.drawText(
            QRectF(138, 5, max(10, self.width() - 156), 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "Clique para posicionar • Arraste para selecionar • Arraste as alças para ajustar",
        )

        track = self._track_rect()
        painter.setPen(QPen(border, 1))
        interval = self._tick_interval()
        tick = 0.0
        painter.setFont(QFont("Segoe UI", 8))
        while tick <= self.duration + 1e-6:
            x = self._x_at(tick)
            painter.drawLine(QPointF(x, 27), QPointF(x, 39))
            painter.setPen(muted)
            painter.drawText(QRectF(x - 28, 25, 56, 15), Qt.AlignmentFlag.AlignHCenter, self._short_time(tick))
            painter.setPen(QPen(border, 1))
            tick += interval

        video_rect = self._video_rect()
        audio_rect = self._audio_rect()
        painter.fillRect(video_rect, clip)
        painter.fillRect(audio_rect, lane)
        painter.setPen(QPen(border, 1))
        painter.drawRect(video_rect)
        painter.drawRect(audio_rect)
        painter.setPen(muted)
        painter.drawText(video_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, "VÍDEO")

        painter.setPen(QPen(muted, 1))
        center_y = audio_rect.center().y()
        x = int(audio_rect.left()) + 5
        while x < int(audio_rect.right()) - 4:
            amplitude = 3 + int(abs(math.sin(x * 0.071) + math.sin(x * 0.019)) * 5)
            painter.drawLine(QPointF(x, center_y - amplitude), QPointF(x, center_y + amplitude))
            x += 8

        for cut in self.cuts:
            start_x = self._x_at(cut.start)
            end_x = self._x_at(cut.end)
            cut_rect = QRectF(start_x, track.top(), max(3, end_x - start_x), track.height())
            painter.fillRect(cut_rect, QBrush(QColor(red.red(), red.green(), red.blue(), 150), Qt.BrushStyle.BDiagPattern))
            painter.setPen(QPen(red, 1))
            painter.drawRect(cut_rect)
            if cut_rect.width() >= 62:
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(cut_rect, Qt.AlignmentFlag.AlignCenter, "REMOVER")

        if self.selection_start is not None and self.selection_end is not None:
            start, end = sorted((self.selection_start, self.selection_end))
            start_x, end_x = self._x_at(start), self._x_at(end)
            selection = QRectF(start_x, track.top(), max(2, end_x - start_x), track.height())
            painter.fillRect(selection, QColor(yellow.red(), yellow.green(), yellow.blue(), 100))
            painter.setPen(QPen(yellow, 2))
            painter.drawRect(selection)
            for handle_x in (start_x, end_x):
                handle = QRectF(handle_x - 5, track.top() - 3, 10, track.height() + 6)
                painter.fillRect(handle, yellow)
                painter.setPen(QPen(QColor("#111111"), 1))
                painter.drawRect(handle)
                painter.drawLine(QPointF(handle_x - 2, track.center().y() - 7), QPointF(handle_x - 2, track.center().y() + 7))
                painter.drawLine(QPointF(handle_x + 2, track.center().y() - 7), QPointF(handle_x + 2, track.center().y() + 7))

        playhead_x = self._x_at(self.position)
        painter.setPen(QPen(QColor("#FFFFFF") if dark else QColor("#111111"), 4))
        painter.drawLine(QPointF(playhead_x, 31), QPointF(playhead_x, 133))
        painter.setPen(QPen(yellow, 2))
        painter.drawLine(QPointF(playhead_x, 31), QPointF(playhead_x, 133))
        painter.fillRect(QRectF(playhead_x - 5, 29, 10, 8), yellow)

        painter.setPen(muted)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(18, 133, self.width() - 36, 18), Qt.AlignmentFlag.AlignVCenter, "Amarelo: seleção  •  Vermelho: trecho removido na exportação")

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self._track_rect().contains(event.position()):
            return
        pressed = self._time_at(event.position())
        tolerance = max(self.duration * 8 / max(self._track_rect().width(), 1), 0.03)
        if self.selection_start is not None and abs(pressed - self.selection_start) <= tolerance:
            self._drag_mode = "start"
        elif self.selection_end is not None and abs(pressed - self.selection_end) <= tolerance:
            self._drag_mode = "end"
        else:
            self._drag_mode = "new"
            self.set_selection(pressed, pressed)
        self._press_time = pressed
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_mode is None or self._press_time is None:
            return
        current = self._time_at(event.position())
        if self._drag_mode == "start":
            self.selection_start = current
        elif self._drag_mode == "end":
            self.selection_end = current
        else:
            self.selection_start, self.selection_end = sorted((self._press_time, current))
        self.update()
        if self.selection_start is not None and self.selection_end is not None:
            start, end = sorted((self.selection_start, self.selection_end))
            self.rangeSelected.emit(start, end)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_mode is None or self._press_time is None or event.button() != Qt.MouseButton.LeftButton:
            return
        released = self._time_at(event.position())
        moved_pixels = abs(self._x_at(released) - self._x_at(self._press_time))
        if self._drag_mode == "new" and moved_pixels < 4:
            self.set_selection(None, None)
            self.seekRequested.emit(released)
        elif self.selection_start is not None and self.selection_end is not None:
            start, end = sorted((self.selection_start, self.selection_end))
            self.selection_start, self.selection_end = start, end
            self.rangeSelected.emit(start, end)
            self.seekRequested.emit(start)
        self._drag_mode = None
        self._press_time = None
        self.update()
        event.accept()

