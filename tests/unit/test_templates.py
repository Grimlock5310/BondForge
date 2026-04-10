"""Tests for biopolymer templates."""

from __future__ import annotations

from bondforge.core.model.templates import (
    dna_strand,
    igg_antibody,
    linear_peptide,
    rna_strand,
)


def test_igg_antibody_default() -> None:
    bp = igg_antibody()
    assert len(bp.chains) == 4  # 2 heavy + 2 light
    assert len(bp.connections) >= 3  # at least 3 disulfide bonds
    for chain in bp.iter_chains():
        assert len(chain.residues) > 0


def test_igg_antibody_full_length() -> None:
    bp = igg_antibody(full_length=True)
    heavy = bp.chains["PEPTIDE1"]
    light = bp.chains["PEPTIDE3"]
    # Full-length heavy chain should be much longer than short version.
    assert len(heavy.residues) > 100
    assert len(light.residues) > 100


def test_linear_peptide() -> None:
    bp = linear_peptide("ACDEFG")
    assert len(bp.chains) == 1
    chain = bp.chains["PEPTIDE1"]
    assert chain.sequence == "ACDEFG"


def test_dna_strand() -> None:
    bp = dna_strand("ACGT")
    assert len(bp.chains) == 1
    chain = bp.chains["DNA1"]
    assert len(chain.residues) == 4
    # DNA monomers use dA, dC, dG, dT symbols.
    symbols = [r.symbol for r in chain.residues]
    assert symbols == ["dA", "dC", "dG", "dT"]


def test_rna_strand() -> None:
    bp = rna_strand("ACGU")
    assert len(bp.chains) == 1
    chain = bp.chains["RNA1"]
    assert chain.sequence == "ACGU"
