"""Pre-built biopolymer templates for common macromolecules.

Provides factory functions that return ready-to-use :class:`Biopolymer`
instances for common structures like antibodies. Templates use
representative sequences (human IgG1 consensus) shortened for
display purposes.
"""

from __future__ import annotations

from bondforge.core.model.biopolymer import Biopolymer, ConnectionType
from bondforge.core.model.monomer import MonomerResidue, PolymerType

# Short representative sequences for IgG antibody templates.
# Real antibody chains are ~450 (heavy) and ~215 (light) residues.
# We use abbreviated sequences that capture the domain architecture.

_IGG_HEAVY_VH = "EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEWVSAISGSGGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYCAK"
_IGG_HEAVY_CH1 = "ASTKGPSVFPLAPSSKSTSGGTAALGCLVKDYFPEPVTVSWNSGALTSGVHTFPAVLQSSGLYSLSSVVTVPSSSLGTQTYICNVNHKPSNTKVDK"
_IGG_HEAVY_HINGE = "EPKSCDKTHTCPPCP"
_IGG_HEAVY_CH2 = "APELLGGPSVFLFPPKPKDTLMISRTPEVTCVVVDVSHEDPEVKFNWYVDGVEVHNAK"
_IGG_HEAVY_CH3 = "TKPREEQYNSTYRVVSVLTVLHQDWLNGKEYKCKVSNKALPAPIEKTISKAK"
_IGG_LIGHT_VL = "DIQMTQSPSSLSASVGDRVTITCRASQGIRNDLGWYQQKPGKAPKLLIYAASSLQSGVPSRFSGSGSGTDFTLTISSLQPEDFATYYCQQSYSTPLT"
_IGG_LIGHT_CL = "FGQGTKVEIKRTVAAPSVFIFPPSDEQLKSGTASVVCLLNNFYPREAKVQWKVDNALQSGNSQESVTEQDSKDSTYSLSSTLTLSKADYEKHKVYACEVTHQGLSSPVTKSFNRGEC"

_IGG_HEAVY = _IGG_HEAVY_VH + _IGG_HEAVY_CH1 + _IGG_HEAVY_HINGE + _IGG_HEAVY_CH2 + _IGG_HEAVY_CH3
_IGG_LIGHT = _IGG_LIGHT_VL + _IGG_LIGHT_CL

# Shortened versions for display (first 30 residues of each domain).
_SHORT_HEAVY = "EVQLVESGGGLVQPGGSLRLSCAASGFTFS"
_SHORT_LIGHT = "DIQMTQSPSSLSASVGDRVTITCRASQGI"


def _make_residues(sequence: str, ptype: PolymerType) -> list[MonomerResidue]:
    return [
        MonomerResidue(position=i + 1, symbol=aa, polymer_type=ptype)
        for i, aa in enumerate(sequence)
    ]


def igg_antibody(*, full_length: bool = False) -> Biopolymer:
    """Create an IgG1 antibody template with two heavy and two light chains.

    Args:
        full_length: If True, use full-length representative sequences
            (~450 heavy, ~215 light). If False (default), use shortened
            30-residue versions for display.

    Returns:
        A :class:`Biopolymer` with chains HC1, HC2, LC1, LC2 and four
        disulfide connections (HC1-LC1, HC2-LC2, HC1-HC2 x2 at hinge).
    """
    heavy_seq = _IGG_HEAVY if full_length else _SHORT_HEAVY
    light_seq = _IGG_LIGHT if full_length else _SHORT_LIGHT

    bp = Biopolymer(id=1)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, _make_residues(heavy_seq, PolymerType.PEPTIDE))
    bp.add_chain("PEPTIDE2", PolymerType.PEPTIDE, _make_residues(heavy_seq, PolymerType.PEPTIDE))
    bp.add_chain("PEPTIDE3", PolymerType.PEPTIDE, _make_residues(light_seq, PolymerType.PEPTIDE))
    bp.add_chain("PEPTIDE4", PolymerType.PEPTIDE, _make_residues(light_seq, PolymerType.PEPTIDE))

    # Disulfide bonds: HC1-LC1, HC2-LC2 (Cys near position 22 in heavy, 23 in light).
    h_cys = min(22, len(heavy_seq))
    l_cys = min(23, len(light_seq))
    bp.add_connection(ConnectionType.PAIR, "PEPTIDE1", h_cys, "PEPTIDE3", l_cys)
    bp.add_connection(ConnectionType.PAIR, "PEPTIDE2", h_cys, "PEPTIDE4", l_cys)
    # Hinge disulfides: HC1-HC2 (positions 11, 14 in the hinge region).
    hinge_pos = min(11, len(heavy_seq))
    bp.add_connection(ConnectionType.PAIR, "PEPTIDE1", hinge_pos, "PEPTIDE2", hinge_pos)

    return bp


def linear_peptide(sequence: str) -> Biopolymer:
    """Create a single-chain linear peptide from a one-letter sequence."""
    bp = Biopolymer(id=1)
    bp.add_chain("PEPTIDE1", PolymerType.PEPTIDE, _make_residues(sequence, PolymerType.PEPTIDE))
    return bp


def dna_strand(sequence: str) -> Biopolymer:
    """Create a single-chain DNA strand from a base sequence (A/C/G/T)."""
    # DNA monomers use dA, dC, dG, dT symbols.
    _DNA_MAP = {"A": "dA", "C": "dC", "G": "dG", "T": "dT"}
    residues = [
        MonomerResidue(
            position=i + 1,
            symbol=_DNA_MAP.get(base.upper(), base),
            polymer_type=PolymerType.DNA,
        )
        for i, base in enumerate(sequence)
    ]
    bp = Biopolymer(id=1)
    bp.add_chain("DNA1", PolymerType.DNA, residues)
    return bp


def rna_strand(sequence: str) -> Biopolymer:
    """Create a single-chain RNA strand from a base sequence (A/C/G/U)."""
    bp = Biopolymer(id=1)
    bp.add_chain("RNA1", PolymerType.RNA, _make_residues(sequence.upper(), PolymerType.RNA))
    return bp


TEMPLATES: dict[str, tuple[str, callable]] = {
    "IgG Antibody": ("Full IgG1 antibody (2 heavy + 2 light chains)", igg_antibody),
    "Linear Peptide": ("Single-chain peptide from sequence", linear_peptide),
    "DNA Strand": ("Single-stranded DNA from base sequence", dna_strand),
    "RNA Strand": ("Single-stranded RNA from base sequence", rna_strand),
}


__all__ = [
    "TEMPLATES",
    "igg_antibody",
    "linear_peptide",
    "dna_strand",
    "rna_strand",
]
