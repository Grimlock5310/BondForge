"""Tests for the biopolymer model, monomer library, and commands."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from bondforge.core.commands import (  # noqa: E402
    AddBiopolymerCommand,
    DeleteBiopolymerCommand,
)
from bondforge.core.model.biopolymer import (  # noqa: E402
    Biopolymer,
    ConnectionType,
)
from bondforge.core.model.document import Document  # noqa: E402
from bondforge.core.model.molecule import Molecule  # noqa: E402
from bondforge.core.model.monomer import MonomerResidue, PolymerType  # noqa: E402
from bondforge.core.model.monomer_library import (  # noqa: E402
    lookup,
    symbols_for_type,
)


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


# ---- monomer library tests -----------------------------------------------


def test_amino_acids_present() -> None:
    standard = "ACDEFGHIKLMNPQRSTVWY"
    for aa in standard:
        assert lookup(PolymerType.PEPTIDE, aa) is not None, f"Missing amino acid {aa}"


def test_rna_nucleotides_present() -> None:
    for base in "ACGU":
        assert lookup(PolymerType.RNA, base) is not None, f"Missing RNA base {base}"


def test_dna_nucleotides_present() -> None:
    for base in ["dA", "dC", "dG", "dT"]:
        assert lookup(PolymerType.DNA, base) is not None, f"Missing DNA base {base}"


def test_symbols_for_type() -> None:
    peptide_syms = symbols_for_type(PolymerType.PEPTIDE)
    assert "A" in peptide_syms
    assert "G" in peptide_syms
    assert len(peptide_syms) >= 20


def test_lookup_missing_returns_none() -> None:
    assert lookup(PolymerType.PEPTIDE, "ZZZ") is None


# ---- biopolymer model tests ----------------------------------------------


def test_biopolymer_add_chain() -> None:
    bp = Biopolymer(id=1)
    residues = [
        MonomerResidue(position=1, symbol="A", polymer_type=PolymerType.PEPTIDE),
        MonomerResidue(position=2, symbol="G", polymer_type=PolymerType.PEPTIDE),
    ]
    chain = bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, residues)
    assert chain.id == "PEPTIDE1"
    assert len(chain) == 2
    assert chain.sequence == "AG"


def test_biopolymer_remove_chain() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("A", PolymerType.PEPTIDE)
    bp.remove_chain("A")
    assert "A" not in bp.chains


def test_biopolymer_remove_chain_not_found() -> None:
    bp = Biopolymer(id=1)
    with pytest.raises(KeyError):
        bp.remove_chain("MISSING")


def test_biopolymer_add_connection() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("A", PolymerType.PEPTIDE)
    bp.add_chain("B", PolymerType.PEPTIDE)
    conn = bp.add_connection(ConnectionType.PAIR, "A", 5, "B", 10)
    assert conn.id == 1
    assert conn.source_chain_id == "A"
    assert conn.target_position == 10


def test_remove_chain_cascades_connections() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("A", PolymerType.PEPTIDE)
    bp.add_chain("B", PolymerType.PEPTIDE)
    bp.add_connection(ConnectionType.PAIR, "A", 1, "B", 1)
    bp.remove_chain("A")
    assert len(bp.connections) == 0


# ---- document integration ------------------------------------------------


def test_document_add_biopolymer() -> None:
    doc = Document()
    bp = Biopolymer(id=0)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE)
    doc.add_biopolymer(bp)
    assert bp.id == 1
    assert 1 in doc.biopolymers


def test_document_remove_biopolymer() -> None:
    doc = Document()
    bp = Biopolymer(id=0)
    doc.add_biopolymer(bp)
    doc.remove_biopolymer(bp.id)
    assert bp.id not in doc.biopolymers


def test_document_remove_biopolymer_not_found() -> None:
    doc = Document()
    with pytest.raises(KeyError):
        doc.remove_biopolymer(999)


# ---- command tests -------------------------------------------------------


def test_add_biopolymer_command_round_trip() -> None:
    scene = _FakeScene()
    bp = Biopolymer(id=0)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, [
        MonomerResidue(1, "A", PolymerType.PEPTIDE),
        MonomerResidue(2, "G", PolymerType.PEPTIDE),
    ])
    cmd = AddBiopolymerCommand(scene, bp)
    cmd.redo()
    assert len(scene.document.biopolymers) == 1
    assert cmd.created_bp_id == 1

    cmd.undo()
    assert len(scene.document.biopolymers) == 0


def test_add_biopolymer_preserves_id_across_redo() -> None:
    scene = _FakeScene()
    bp = Biopolymer(id=0)
    cmd = AddBiopolymerCommand(scene, bp)
    cmd.redo()
    original_id = cmd.created_bp_id
    cmd.undo()
    cmd.redo()
    assert cmd.created_bp_id == original_id
    assert original_id in scene.document.biopolymers


def test_delete_biopolymer_command_round_trip() -> None:
    scene = _FakeScene()
    bp = Biopolymer(id=0)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, [
        MonomerResidue(1, "K", PolymerType.PEPTIDE),
    ])
    scene.document.add_biopolymer(bp)
    cmd = DeleteBiopolymerCommand(scene, bp.id)
    cmd.redo()
    assert bp.id not in scene.document.biopolymers
    cmd.undo()
    restored = scene.document.biopolymers[bp.id]
    assert "PEPTIDE1" in restored.chains
