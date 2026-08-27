from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..models import CutRange


class TimelineWidget(QWidget):
    rangeSelected = Signal(float, float)
    seekRequested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(58)
        self.duration = 0.0
        self.position = 0.0
        self.cuts: list[CutRange] = []
        self.selection_start: float | None = None
        self.selection_end: float | None = None
        self._drag_start: float | None = None
        self.setMouseTracking(True)

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
        return QRectF(10, 19, max(1, self.width() - 20), 22)

    def _time_at(self, point: QPointF) -> float:
        rect = self._track_rect()
        fraction = max(0.0, min(1.0, (point.x() - rect.left()) / rect.width()))
        return fraction * self.duration

    def _x_at(self, seconds: float) -> float:
        rect = self._track_rect()
        return rect.left() + (seconds / self.duration) * rect.width() if self.duration else rect.left()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._track_rect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e4e7ec"))
        painter.drawRoundedRect(rect, 5, 5)
        painter.setBrush(QColor("#cdd5df"))
        for cut in self.cuts:
            start = self._x_at(cut.start)
            end = self._x_at(cut.end)
            cut_rect = QRectF(start, rect.top(), max(2, end - start), rect.height())
            painter.setBrush(QBrush(QColor("#fecaca"), Qt.BrushStyle.BDiagPattern))
            painter.drawRect(cut_rect)
        if self.selection_start is not None and self.selection_end is not None:
            start, end = sorted((self.selection_start, self.selection_end))
            painter.setBrush(QColor(37, 99, 235, 90))
            painter.drawRect(QRectF(self._x_at(start), rect.top(), max(2, self._x_at(end) - self._x_at(start)), rect.height()))
        playhead_x = self._x_at(self.position)
        painter.setPen(QPen(QColor("#1d4ed8"), 2))
        painter.drawLine(playhead_x, 10, playhead_x, 51)
        painter.setBrush(QColor("#1d4ed8"))
        painter.drawEllipse(QPointF(playhead_x, 13), 4, 4)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._track_rect().contains(event.position()):
            self._drag_start = self._time_at(event.position())
            self.set_selection(self._drag_start, self._drag_start)
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None:
            current = self._time_at(event.position())
            self.set_selection(min(self._drag_start, current), max(self._drag_start, current))
            self.rangeSelected.emit(self.selection_start or 0, self.selection_end or 0)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is not None and event.button() == Qt.MouseButton.LeftButton:
            current = self._time_at(event.position())
            start, end = sorted((self._drag_start, current))
            self.set_selection(start, end)
            self.rangeSelected.emit(start, end)
            self.seekRequested.emit(start)
            self._drag_start = None
            event.accept()