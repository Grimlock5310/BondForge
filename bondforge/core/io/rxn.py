"""MDL RXN reaction-file writer.

v0.3 supports *writing* reaction files. Reading RXN is v0.4 (we'd need
to ingest multiple molecules and arrows as a unit, which is more work
than the display-side write path).

The write path is heuristic: given a :class:`Document` containing one
molecule with several disjoint connected components plus at least one
forward arrow, we:

1. Walk the molecule's connectivity to find each connected component.
2. Use the first forward arrow's midpoint as a separator: components
   whose centroid lies on the tail side are reactants, components on
   the head side are products.
3. Feed the resulting component molecules into an RDKit
   ``ChemicalReaction`` and serialize via ``ReactionToRxnBlock``.

Curved electron-pushing arrows are ignored by RXN export — they're a
display-only mechanism annotation.

The heuristic handles the common A + B → C layout. Multi-step schemes
with two or more forward arrows are written as a *single* reaction
using the first arrow and all components. Future work: emit one
``$RXN`` per arrow, or expand to an RD-file with multiple reactions.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem

from bondforge.core.model.arrow import ArrowKind
from bondforge.core.model.document import Document
from bondforge.core.model.molecule import Molecule
from bondforge.engine.rdkit_adapter import molecule_to_rwmol


class RxnExportError(RuntimeError):
    """The document cannot be exported as a reaction in its current form."""


def _connected_components(mol: Molecule) -> list[list[int]]:
    """Return a list of atom-id lists, one per connected component."""
    adjacency: dict[int, list[int]] = {a.id: [] for a in mol.iter_atoms()}
    for bond in mol.iter_bonds():
        adjacency.setdefault(bond.begin_atom_id, []).append(bond.end_atom_id)
        adjacency.setdefault(bond.end_atom_id, []).append(bond.begin_atom_id)

    seen: set[int] = set()
    components: list[list[int]] = []
    for start in adjacency:
        if start in seen:
            continue
        stack = [start]
        component: list[int] = []
        while stack:
            nid = stack.pop()
            if nid in seen:
                continue
            seen.add(nid)
            component.append(nid)
            stack.extend(adjacency[nid])
        components.append(component)
    return components


def _component_centroid(mol: Molecule, atom_ids: list[int]) -> tuple[float, float]:
    n = len(atom_ids)
    if n == 0:
        return 0.0, 0.0
    cx = sum(mol.atoms[a].x for a in atom_ids) / n
    cy = sum(mol.atoms[a].y for a in atom_ids) / n
    return cx, cy


def _sub_molecule(mol: Molecule, atom_ids: list[int]) -> Molecule:
    """Build a fresh :class:`Molecule` holding just the listed atoms and their bonds."""
    sub = Molecule()
    id_map: dict[int, int] = {}
    for old_id in atom_ids:
        atom = mol.atoms[old_id]
        new_atom = sub.add_atom(
            atom.element, atom.x, atom.y, charge=atom.charge, isotope=atom.isotope
        )
        new_atom.radical_electrons = atom.radical_electrons
        new_atom.explicit_hydrogens = atom.explicit_hydrogens
        new_atom.map_number = atom.map_number
        id_map[old_id] = new_atom.id
    atom_set = set(atom_ids)
    for bond in mol.iter_bonds():
        if bond.begin_atom_id in atom_set and bond.end_atom_id in atom_set:
            sub.add_bond(
                id_map[bond.begin_atom_id],
                id_map[bond.end_atom_id],
                bond.order,
                bond.stereo,
            )
    return sub


def document_to_rxn(document: Document) -> str:
    """Serialize a :class:`Document` to an MDL RXN V2000 block.

    Raises:
        RxnExportError: the document has no forward arrow, or no atoms,
            or the split produces zero reactants or zero products.
    """
    arrows = [a for a in document.iter_arrows() if a.kind == ArrowKind.FORWARD]
    if not arrows:
        raise RxnExportError(
            "RXN export requires at least one forward reaction arrow. "
            "Use the Arrow tool to draw one between reactants and products."
        )
    if not document.molecule.atoms:
        raise RxnExportError("No atoms to export.")

    arrow = arrows[0]
    ax = (arrow.x1 + arrow.x2) / 2
    # Use the arrow direction as the "reactant → product" axis so vertical
    # and slanted arrows work, not just horizontal ones.
    dx = arrow.x2 - arrow.x1
    dy = arrow.y2 - arrow.y1
    import math

    length = math.hypot(dx, dy)
    if length == 0:
        # Degenerate arrow: fall back to x-axis splitting.
        dx, dy, length = 1.0, 0.0, 1.0
    ux = dx / length
    uy = dy / length
    mx = (arrow.x1 + arrow.x2) / 2
    my = (arrow.y1 + arrow.y2) / 2

    def side(cx: float, cy: float) -> float:
        # Projection of (cx-mx, cy-my) onto the arrow direction: positive
        # means "past the midpoint" (i.e. on the product side).
        return (cx - mx) * ux + (cy - my) * uy

    reactants: list[Molecule] = []
    products: list[Molecule] = []
    for component in _connected_components(document.molecule):
        cx, cy = _component_centroid(document.molecule, component)
        sub = _sub_molecule(document.molecule, component)
        if side(cx, cy) >= 0:
            products.append(sub)
        else:
            reactants.append(sub)
    # Suppress unused-variable lint for the original chord x-center.
    del ax

    if not reactants:
        raise RxnExportError("No reactants found on the tail side of the arrow.")
    if not products:
        raise RxnExportError("No products found on the head side of the arrow.")

    rxn = AllChem.ChemicalReaction()
    for r in reactants:
        rw = molecule_to_rwmol(r)
        # Partial structures are allowed in a reaction file, so silently
        # skip sanitization failures.
        with contextlib.suppress(Exception):
            Chem.SanitizeMol(rw)
        rxn.AddReactantTemplate(rw)
    for p in products:
        rw = molecule_to_rwmol(p)
        with contextlib.suppress(Exception):
            Chem.SanitizeMol(rw)
        rxn.AddProductTemplate(rw)

    return AllChem.ReactionToRxnBlock(rxn)


def write_rxn_file(document: Document, path: str | Path) -> None:
    """Write a :class:`Document` to an ``.rxn`` file on disk."""
    Path(path).write_text(document_to_rxn(document), encoding="utf-8")


__all__ = ["document_to_rxn", "write_rxn_file", "RxnExportError"]
