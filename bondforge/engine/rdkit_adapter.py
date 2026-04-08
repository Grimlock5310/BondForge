"""Round-trip between :class:`bondforge.core.model.Molecule` and RDKit ``RWMol``.

The display ``Molecule`` is the source of truth. RDKit is used for:

- sanitization, aromaticity perception, and stereo perception,
- file IO of community formats (MOL, SDF, SMILES, InChI),
- property and descriptor calculation.

The conversion preserves a one-to-one mapping between display atoms and RDKit
atoms via the atom index, so callers can copy perceived properties back onto
the display model after a round trip.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import AllChem

from bondforge.core.model.atom import Atom
from bondforge.core.model.bond import Bond, BondOrder, BondStereo
from bondforge.core.model.molecule import Molecule

_BOND_ORDER_TO_RDKIT = {
    BondOrder.SINGLE: Chem.BondType.SINGLE,
    BondOrder.DOUBLE: Chem.BondType.DOUBLE,
    BondOrder.TRIPLE: Chem.BondType.TRIPLE,
    BondOrder.AROMATIC: Chem.BondType.AROMATIC,
    BondOrder.DATIVE: Chem.BondType.DATIVE,
    BondOrder.ANY: Chem.BondType.UNSPECIFIED,
}
_RDKIT_TO_BOND_ORDER = {v: k for k, v in _BOND_ORDER_TO_RDKIT.items()}

_BOND_STEREO_TO_RDKIT_DIR = {
    BondStereo.WEDGE_UP: Chem.BondDir.BEGINWEDGE,
    BondStereo.WEDGE_DOWN: Chem.BondDir.BEGINDASH,
    BondStereo.EITHER: Chem.BondDir.UNKNOWN,
}


def molecule_to_rwmol(mol: Molecule) -> Chem.RWMol:
    """Build an ``RWMol`` from a display :class:`Molecule`.

    The returned mol carries 2D coordinates and atom map numbers but is
    *not* sanitized — callers should run :func:`Chem.SanitizeMol` if they
    need aromaticity or implicit valence perception.
    """
    rw = Chem.RWMol()
    index_by_id: dict[int, int] = {}
    for atom in mol.iter_atoms():
        rd_atom = Chem.Atom(atom.element)
        rd_atom.SetFormalCharge(atom.charge)
        if atom.isotope:
            rd_atom.SetIsotope(atom.isotope)
        if atom.radical_electrons:
            rd_atom.SetNumRadicalElectrons(atom.radical_electrons)
        if atom.explicit_hydrogens is not None:
            rd_atom.SetNumExplicitHs(atom.explicit_hydrogens)
            rd_atom.SetNoImplicit(True)
        if atom.map_number:
            rd_atom.SetAtomMapNum(atom.map_number)
        idx = rw.AddAtom(rd_atom)
        index_by_id[atom.id] = idx

    for bond in mol.iter_bonds():
        bidx = rw.AddBond(
            index_by_id[bond.begin_atom_id],
            index_by_id[bond.end_atom_id],
            _BOND_ORDER_TO_RDKIT[bond.order],
        )
        rd_bond = rw.GetBondWithIdx(bidx - 1)
        if bond.stereo in _BOND_STEREO_TO_RDKIT_DIR:
            rd_bond.SetBondDir(_BOND_STEREO_TO_RDKIT_DIR[bond.stereo])

    if mol.atoms:
        conf = Chem.Conformer(rw.GetNumAtoms())
        for atom_id, idx in index_by_id.items():
            atom = mol.atoms[atom_id]
            # Qt scene Y grows downward; flip into chemistry-style Y-up.
            conf.SetAtomPosition(idx, (float(atom.x), float(-atom.y), 0.0))
        rw.AddConformer(conf, assignId=True)

    return rw


def rwmol_to_molecule(rw: Chem.Mol) -> Molecule:
    """Build a display :class:`Molecule` from an RDKit mol.

    If the mol carries no 2D conformer, one is generated via
    :func:`AllChem.Compute2DCoords` so the result is always renderable.
    """
    if rw.GetNumConformers() == 0 and rw.GetNumAtoms() > 0:
        AllChem.Compute2DCoords(rw)

    out = Molecule()
    rd_idx_to_id: dict[int, int] = {}
    conf = rw.GetConformer(0) if rw.GetNumConformers() else None

    for rd_atom in rw.GetAtoms():
        x = y = 0.0
        if conf is not None:
            pos = conf.GetAtomPosition(rd_atom.GetIdx())
            x = float(pos.x)
            y = float(-pos.y)  # flip back to Qt scene Y-down
        atom = out.add_atom(
            element=rd_atom.GetSymbol(),
            x=x,
            y=y,
            charge=rd_atom.GetFormalCharge(),
            isotope=rd_atom.GetIsotope(),
        )
        atom.radical_electrons = rd_atom.GetNumRadicalElectrons()
        if rd_atom.GetNoImplicit():
            atom.explicit_hydrogens = rd_atom.GetNumExplicitHs()
        atom.map_number = rd_atom.GetAtomMapNum()
        rd_idx_to_id[rd_atom.GetIdx()] = atom.id

    for rd_bond in rw.GetBonds():
        order = _RDKIT_TO_BOND_ORDER.get(rd_bond.GetBondType(), BondOrder.SINGLE)
        stereo = BondStereo.NONE
        bdir = rd_bond.GetBondDir()
        if bdir == Chem.BondDir.BEGINWEDGE:
            stereo = BondStereo.WEDGE_UP
        elif bdir == Chem.BondDir.BEGINDASH:
            stereo = BondStereo.WEDGE_DOWN
        elif bdir == Chem.BondDir.UNKNOWN and order == BondOrder.SINGLE:
            stereo = BondStereo.EITHER
        out.add_bond(
            rd_idx_to_id[rd_bond.GetBeginAtomIdx()],
            rd_idx_to_id[rd_bond.GetEndAtomIdx()],
            order=order,
            stereo=stereo,
        )

    return out


def sanitized(mol: Molecule) -> Chem.Mol:
    """Build a sanitized RDKit copy of ``mol`` for chemistry queries.

    Use this whenever you need aromaticity, implicit Hs, or canonical
    SMILES. The sanitized mol is *not* fed back into the display model
    automatically; callers can convert via :func:`rwmol_to_molecule`
    if they want to.
    """
    rw = molecule_to_rwmol(mol)
    Chem.SanitizeMol(rw)
    return rw.GetMol()


__all__ = [
    "Atom",
    "Bond",
    "Molecule",
    "molecule_to_rwmol",
    "rwmol_to_molecule",
    "sanitized",
]
