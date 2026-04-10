"""Tests for the HELM notation parser and writer."""

from __future__ import annotations

import pytest

from bondforge.core.io.helm import HelmError, parse_helm, write_helm
from bondforge.core.model.biopolymer import Biopolymer, ConnectionType
from bondforge.core.model.monomer import MonomerResidue, PolymerType


def test_parse_simple_peptide() -> None:
    helm = "PEPTIDE1{A.G.K.L}$$$$V2.0"
    bp = parse_helm(helm)
    assert "PEPTIDE1" in bp.chains
    chain = bp.chains["PEPTIDE1"]
    assert chain.polymer_type == PolymerType.PEPTIDE
    assert chain.sequence == "AGKL"
    assert len(chain.residues) == 4


def test_parse_dna() -> None:
    helm = "DNA1{dA.dC.dG.dT}$$$$V2.0"
    bp = parse_helm(helm)
    assert "DNA1" in bp.chains
    chain = bp.chains["DNA1"]
    assert chain.polymer_type == PolymerType.DNA
    assert len(chain.residues) == 4


def test_parse_rna() -> None:
    helm = "RNA1{A.C.G.U}$$$$V2.0"
    bp = parse_helm(helm)
    chain = bp.chains["RNA1"]
    assert chain.polymer_type == PolymerType.RNA
    assert chain.sequence == "ACGU"


def test_parse_multiple_chains() -> None:
    helm = "PEPTIDE1{A.G}|PEPTIDE2{K.L}$$$$V2.0"
    bp = parse_helm(helm)
    assert len(bp.chains) == 2
    assert bp.chains["PEPTIDE1"].sequence == "AG"
    assert bp.chains["PEPTIDE2"].sequence == "KL"


def test_parse_with_connections() -> None:
    helm = "PEPTIDE1{A.C.G}|PEPTIDE2{K.C.L}$PEPTIDE1,PEPTIDE2,2:R3-2:R3$$$V2.0"
    bp = parse_helm(helm)
    assert len(bp.connections) == 1
    conn = list(bp.connections.values())[0]
    assert conn.source_chain_id == "PEPTIDE1"
    assert conn.target_chain_id == "PEPTIDE2"
    assert conn.source_position == 2
    assert conn.target_position == 2


def test_parse_empty_raises() -> None:
    with pytest.raises(HelmError):
        parse_helm("")


def test_parse_invalid_chain_raises() -> None:
    with pytest.raises(HelmError):
        parse_helm("INVALID{A.G}$$$$V2.0")


def test_write_simple_peptide() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, [
        MonomerResidue(1, "A", PolymerType.PEPTIDE),
        MonomerResidue(2, "G", PolymerType.PEPTIDE),
    ])
    result = write_helm(bp)
    assert "PEPTIDE1{A.G}" in result
    assert result.endswith("V2.0")


def test_write_with_connections() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, [
        MonomerResidue(1, "A", PolymerType.PEPTIDE),
        MonomerResidue(2, "C", PolymerType.PEPTIDE),
    ])
    bp.add_chain("PEPTIDE2", PolymerType.PEPTIDE, [
        MonomerResidue(1, "K", PolymerType.PEPTIDE),
        MonomerResidue(2, "C", PolymerType.PEPTIDE),
    ])
    bp.add_connection(ConnectionType.PAIR, "PEPTIDE1", 2, "PEPTIDE2", 2)
    result = write_helm(bp)
    assert "PEPTIDE1,PEPTIDE2,2:R3-2:R3" in result


def test_round_trip() -> None:
    bp = Biopolymer(id=1)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, [
        MonomerResidue(i, aa, PolymerType.PEPTIDE)
        for i, aa in enumerate("ACDEFG", 1)
    ])
    helm = write_helm(bp)
    restored = parse_helm(helm)
    assert restored.chains["PEPTIDE1"].sequence == "ACDEFG"
