"""TextItem — QGraphicsTextItem subclass for text annotations on the canvas.

Renders a :class:`TextAnnotation` as an editable rich-text item that can
be repositioned by dragging. Double-click to enter edit mode.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem

from bondforge.core.model.text_annotation import TextAnnotation


class TextItem(QGraphicsTextItem):
    """Visual representation of a :class:`TextAnnotation`."""

    def __init__(self, annotation: TextAnnotation, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._annotation = annotation
        self.setPos(annotation.x, annotation.y)
        self.setPlainText(annotation.text)
        font = QFont(annotation.font_family, int(annotation.font_size))
        font.setBold(annotation.bold)
        font.setItalic(annotation.italic)
        self.setFont(font)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setZValue(4.0)

    @property
    def annotation(self) -> TextAnnotation:
        return self._annotation

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """Enter inline edit mode on double-click."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        """Leave edit mode and sync text back to the model."""
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._annotation.text = self.toPlainText()
        self._annotation.x = self.x()
        self._annotation.y = self.y()
        super().focusOutEvent(event)
