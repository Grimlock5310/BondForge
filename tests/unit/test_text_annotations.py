"""Tests for text annotation model, commands, and document integration."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.core.commands import AddTextCommand, DeleteTextCommand  # noqa: E402
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402
from bondforge.core.model.text_annotation import TextAnnotation  # noqa: E402


class _FakeScene:
    def __init__(self) -> None:
        self._document = Document(molecule=Molecule())
        self.rebuilds = 0

    @property
    def document(self) -> Document:
        return self._document

    @property
    def molecule(self) -> Molecule:
        return self._document.molecule

    def rebuild(self) -> None:
        self.rebuilds += 1


# ---- model tests --------------------------------------------------------


def test_text_annotation_creation() -> None:
    ann = TextAnnotation(id=1, text="Hello", x=10.0, y=20.0)
    assert ann.text == "Hello"
    assert ann.font_family == "Arial"
    assert ann.font_size == 12.0
    assert ann.bold is False
    assert ann.italic is False


def test_document_add_text() -> None:
    doc = Document()
    ann = doc.add_text("reagent", 50, 100, bold=True)
    assert ann.id == 1
    assert ann.text == "reagent"
    assert ann.bold is True
    assert 1 in doc.texts


def test_document_remove_text() -> None:
    doc = Document()
    ann = doc.add_text("label", 0, 0)
    doc.remove_text(ann.id)
    assert ann.id not in doc.texts


def test_document_remove_text_not_found() -> None:
    doc = Document()
    with pytest.raises(KeyError):
        doc.remove_text(999)


def test_document_iter_texts() -> None:
    doc = Document()
    doc.add_text("a", 0, 0)
    doc.add_text("b", 10, 10)
    texts = list(doc.iter_texts())
    assert len(texts) == 2
    assert {t.text for t in texts} == {"a", "b"}


# ---- command tests ------------------------------------------------------


def test_add_text_command_round_trip() -> None:
    scene = _FakeScene()
    cmd = AddTextCommand(scene, "Hello", 100, 200)
    cmd.redo()
    assert len(scene.document.texts) == 1
    assert cmd.created_text_id == 1
    ann = scene.document.texts[1]
    assert ann.text == "Hello"
    assert ann.x == 100
    assert ann.y == 200

    cmd.undo()
    assert len(scene.document.texts) == 0


def test_add_text_preserves_id_across_redo() -> None:
    scene = _FakeScene()
    cmd = AddTextCommand(scene, "Test", 0, 0)
    cmd.redo()
    original_id = cmd.created_text_id
    cmd.undo()
    cmd.redo()
    assert cmd.created_text_id == original_id
    assert original_id in scene.document.texts


def test_add_text_with_font_options() -> None:
    scene = _FakeScene()
    cmd = AddTextCommand(
        scene, "Bold", 0, 0,
        font_family="Helvetica", font_size=14.0, bold=True, italic=True,
    )
    cmd.redo()
    ann = scene.document.texts[cmd.created_text_id]
    assert ann.font_family == "Helvetica"
    assert ann.font_size == 14.0
    assert ann.bold is True
    assert ann.italic is True


def test_delete_text_command_round_trip() -> None:
    scene = _FakeScene()
    ann = scene.document.add_text("label", 50, 50, font_size=18.0)
    cmd = DeleteTextCommand(scene, ann.id)
    cmd.redo()
    assert ann.id not in scene.document.texts
    cmd.undo()
    restored = scene.document.texts[ann.id]
    assert restored.text == "label"
    assert restored.font_size == 18.0
    assert restored.x == 50
