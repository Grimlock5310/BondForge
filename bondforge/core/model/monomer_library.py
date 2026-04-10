"""Built-in monomer library — standard amino acids and nucleotides.

Provides :data:`MONOMER_LIBRARY`, a dict mapping ``(PolymerType, symbol)``
to :class:`MonomerDef`. Also provides convenience lookup functions.
"""

from __future__ import annotations

from bondforge.core.model.monomer import MonomerDef, PolymerType

# ---- Standard amino acids (20 natural + selenocysteine) ------------------

_AMINO_ACIDS: list[tuple[str, str, str, str]] = [
    # (symbol, name, SMILES, natural_analog)
    ("G", "Glycine", "NCC(=O)O", "G"),
    ("A", "Alanine", "N[C@@H](C)C(=O)O", "A"),
    ("V", "Valine", "N[C@@H](CC(C)C)C(=O)O", "V"),
    ("L", "Leucine", "N[C@@H](CC(C)C)C(=O)O", "L"),
    ("I", "Isoleucine", "N[C@@H]([C@@H](C)CC)C(=O)O", "I"),
    ("P", "Proline", "OC(=O)[C@@H]1CCCN1", "P"),
    ("F", "Phenylalanine", "N[C@@H](Cc1ccccc1)C(=O)O", "F"),
    ("W", "Tryptophan", "N[C@@H](Cc1c[nH]c2ccccc12)C(=O)O", "W"),
    ("M", "Methionine", "N[C@@H](CCSC)C(=O)O", "M"),
    ("S", "Serine", "N[C@@H](CO)C(=O)O", "S"),
    ("T", "Threonine", "N[C@@H]([C@@H](O)C)C(=O)O", "T"),
    ("C", "Cysteine", "N[C@@H](CS)C(=O)O", "C"),
    ("Y", "Tyrosine", "N[C@@H](Cc1ccc(O)cc1)C(=O)O", "Y"),
    ("H", "Histidine", "N[C@@H](Cc1cnc[nH]1)C(=O)O", "H"),
    ("D", "Aspartic acid", "N[C@@H](CC(=O)O)C(=O)O", "D"),
    ("E", "Glutamic acid", "N[C@@H](CCC(=O)O)C(=O)O", "E"),
    ("N", "Asparagine", "N[C@@H](CC(=O)N)C(=O)O", "N"),
    ("Q", "Glutamine", "N[C@@H](CCC(=O)N)C(=O)O", "Q"),
    ("K", "Lysine", "N[C@@H](CCCCN)C(=O)O", "K"),
    ("R", "Arginine", "N[C@@H](CCCNC(=N)N)C(=O)O", "R"),
    ("U", "Selenocysteine", "N[C@@H](C[Se])C(=O)O", "U"),
]

# ---- RNA nucleotides -----------------------------------------------------

_RNA_NUCLEOTIDES: list[tuple[str, str, str, str]] = [
    ("A", "Adenosine", "OC[C@H]1OC(n2cnc3c(N)ncnc23)[C@H](O)[C@@H]1O", "A"),
    ("C", "Cytidine", "OC[C@H]1OC(n2ccc(N)nc2=O)[C@H](O)[C@@H]1O", "C"),
    ("G", "Guanosine", "OC[C@H]1OC(n2cnc3c(=O)[nH]c(N)nc23)[C@H](O)[C@@H]1O", "G"),
    ("U", "Uridine", "OC[C@H]1OC(n2ccc(=O)[nH]c2=O)[C@H](O)[C@@H]1O", "U"),
]

# ---- DNA nucleotides -----------------------------------------------------

_DNA_NUCLEOTIDES: list[tuple[str, str, str, str]] = [
    ("dA", "Deoxyadenosine", "OC[C@H]1OC(n2cnc3c(N)ncnc23)C[C@@H]1O", "A"),
    ("dC", "Deoxycytidine", "OC[C@H]1OC(n2ccc(N)nc2=O)C[C@@H]1O", "C"),
    ("dG", "Deoxyguanosine", "OC[C@H]1OC(n2cnc3c(=O)[nH]c(N)nc23)C[C@@H]1O", "G"),
    ("dT", "Thymidine", "OC[C@H]1OC(n2cc(C)c(=O)[nH]c2=O)C[C@@H]1O", "T"),
]

# ---- Build the combined library ------------------------------------------

MONOMER_LIBRARY: dict[tuple[PolymerType, str], MonomerDef] = {}

for sym, name, smi, analog in _AMINO_ACIDS:
    MONOMER_LIBRARY[(PolymerType.PEPTIDE, sym)] = MonomerDef(
        symbol=sym, name=name, polymer_type=PolymerType.PEPTIDE,
        smiles=smi, natural_analog=analog,
    )

for sym, name, smi, analog in _RNA_NUCLEOTIDES:
    MONOMER_LIBRARY[(PolymerType.RNA, sym)] = MonomerDef(
        symbol=sym, name=name, polymer_type=PolymerType.RNA,
        smiles=smi, natural_analog=analog,
    )

for sym, name, smi, analog in _DNA_NUCLEOTIDES:
    MONOMER_LIBRARY[(PolymerType.DNA, sym)] = MonomerDef(
        symbol=sym, name=name, polymer_type=PolymerType.DNA,
        smiles=smi, natural_analog=analog,
    )


def lookup(polymer_type: PolymerType, symbol: str) -> MonomerDef | None:
    """Look up a monomer definition by type and symbol."""
    return MONOMER_LIBRARY.get((polymer_type, symbol))


def symbols_for_type(polymer_type: PolymerType) -> list[str]:
    """Return all known symbols for a polymer type, sorted."""
    return sorted(
        sym for (pt, sym) in MONOMER_LIBRARY if pt == polymer_type
    )


__all__ = ["MONOMER_LIBRARY", "lookup", "symbols_for_type"]
