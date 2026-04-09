"""Tests for the :class:`Arrow` / :class:`Document` display models."""

from __future__ import annotations

from bondforge.core.model.arrow import ArrowKind
from bondforge.core.model.document import Document
from bondforge.core.model.molecule import Molecule


def test_document_starts_empty() -> None:
    doc = Document()
    assert doc.molecule is not None
    assert list(doc.iter_arrows()) == []


def test_add_arrow_assigns_sequential_ids() -> None:
    doc = Document(molecule=Molecule())
    a = doc.add_arrow(ArrowKind.FORWARD, 0, 0, 100, 0)
    b = doc.add_arrow(ArrowKind.EQUILIBRIUM, 0, 50, 100, 50)
    assert a.id == 1
    assert b.id == 2
    assert len(doc.arrows) == 2


def test_remove_arrow_raises_for_missing_id() -> None:
    doc = Document()
    doc.add_arrow(ArrowKind.FORWARD, 0, 0, 10, 0)
    doc.remove_arrow(1)
    try:
        doc.remove_arrow(1)
    except KeyError:
        pass
    else:
        raise AssertionError("expected KeyError")


def test_arrow_kind_classifications() -> None:
    assert ArrowKind.FORWARD.is_reaction
    assert ArrowKind.EQUILIBRIUM.is_reaction
    assert ArrowKind.RETROSYNTHETIC.is_reaction
    assert not ArrowKind.ELECTRON_PAIR.is_reaction
    assert ArrowKind.ELECTRON_PAIR.is_curved
    assert ArrowKind.SINGLE_ELECTRON.is_curved
    assert not ArrowKind.FORWARD.is_curved
