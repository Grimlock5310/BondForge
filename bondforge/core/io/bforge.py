"""Native ``.bforge`` JSON serialization format.

A ``.bforge`` file is a UTF-8 JSON document that losslessly round-trips
every field of the :class:`Document` model — atoms, bonds, arrows, text
annotations, and their associated metadata.

Schema (v1)::

    {
        "format": "bforge",
        "version": 1,
        "document": {
            "molecule": {
                "atoms": [ {id, element, x, y, ...}, ... ],
                "bonds": [ {id, begin_atom_id, end_atom_id, order, stereo}, ... ]
            },
            "arrows": [ {id, kind, x1, y1, x2, y2, curvature, label}, ... ],
            "texts":  [ {id, text, x, y, font_family, font_size, bold, italic}, ... ]
        }
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from bondforge.core.model.arrow import Arrow, ArrowKind
from bondforge.core.model.atom import Atom
from bondforge.core.model.bond import Bond, BondOrder, BondStereo
from bondforge.core.model.document import Document
from bondforge.core.model.molecule import Molecule
from bondforge.core.model.text_annotation import TextAnnotation

FORMAT_VERSION = 1


# ---- serialization --------------------------------------------------------


def _atom_to_dict(atom: Atom) -> dict:
    d: dict = {
        "id": atom.id,
        "element": atom.element,
        "x": atom.x,
        "y": atom.y,
    }
    if atom.charge != 0:
        d["charge"] = atom.charge
    if atom.isotope != 0:
        d["isotope"] = atom.isotope
    if atom.radical_electrons != 0:
        d["radical_electrons"] = atom.radical_electrons
    if atom.explicit_hydrogens is not None:
        d["explicit_hydrogens"] = atom.explicit_hydrogens
    if atom.map_number != 0:
        d["map_number"] = atom.map_number
    if atom.label is not None:
        d["label"] = atom.label
    if atom.is_query:
        d["is_query"] = True
    return d


def _bond_to_dict(bond: Bond) -> dict:
    return {
        "id": bond.id,
        "begin_atom_id": bond.begin_atom_id,
        "end_atom_id": bond.end_atom_id,
        "order": bond.order.name,
        "stereo": bond.stereo.name,
    }


def _arrow_to_dict(arrow: Arrow) -> dict:
    return {
        "id": arrow.id,
        "kind": arrow.kind.name,
        "x1": arrow.x1,
        "y1": arrow.y1,
        "x2": arrow.x2,
        "y2": arrow.y2,
        "curvature": arrow.curvature,
        "label": arrow.label,
    }


def _text_to_dict(ann: TextAnnotation) -> dict:
    return {
        "id": ann.id,
        "text": ann.text,
        "x": ann.x,
        "y": ann.y,
        "font_family": ann.font_family,
        "font_size": ann.font_size,
        "bold": ann.bold,
        "italic": ann.italic,
    }


def document_to_json(doc: Document) -> str:
    """Serialize a :class:`Document` to a JSON string."""
    mol = doc.molecule
    payload = {
        "format": "bforge",
        "version": FORMAT_VERSION,
        "document": {
            "molecule": {
                "atoms": [_atom_to_dict(a) for a in mol.iter_atoms()],
                "bonds": [_bond_to_dict(b) for b in mol.iter_bonds()],
            },
            "arrows": [_arrow_to_dict(a) for a in doc.iter_arrows()],
            "texts": [_text_to_dict(t) for t in doc.iter_texts()],
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def save_bforge(doc: Document, path: str | Path) -> None:
    """Write a ``.bforge`` file to disk."""
    Path(path).write_text(document_to_json(doc) + "\n", encoding="utf-8")


# ---- deserialization ------------------------------------------------------


def _atom_from_dict(d: dict) -> Atom:
    return Atom(
        id=d["id"],
        element=d["element"],
        x=d["x"],
        y=d["y"],
        charge=d.get("charge", 0),
        isotope=d.get("isotope", 0),
        radical_electrons=d.get("radical_electrons", 0),
        explicit_hydrogens=d.get("explicit_hydrogens"),
        map_number=d.get("map_number", 0),
        label=d.get("label"),
        is_query=d.get("is_query", False),
    )


def _bond_from_dict(d: dict) -> Bond:
    return Bond(
        id=d["id"],
        begin_atom_id=d["begin_atom_id"],
        end_atom_id=d["end_atom_id"],
        order=BondOrder[d["order"]],
        stereo=BondStereo[d["stereo"]],
    )


def _arrow_from_dict(d: dict) -> Arrow:
    return Arrow(
        id=d["id"],
        kind=ArrowKind[d["kind"]],
        x1=d["x1"],
        y1=d["y1"],
        x2=d["x2"],
        y2=d["y2"],
        curvature=d.get("curvature", 0.0),
        label=d.get("label", ""),
    )


def _text_from_dict(d: dict) -> TextAnnotation:
    return TextAnnotation(
        id=d["id"],
        text=d["text"],
        x=d["x"],
        y=d["y"],
        font_family=d.get("font_family", "Arial"),
        font_size=d.get("font_size", 12.0),
        bold=d.get("bold", False),
        italic=d.get("italic", False),
    )


def json_to_document(text: str) -> Document:
    """Deserialize a JSON string into a :class:`Document`."""
    data = json.loads(text)
    if data.get("format") != "bforge":
        raise ValueError("Not a .bforge file (missing 'format' key)")
    version = data.get("version", 0)
    if version > FORMAT_VERSION:
        raise ValueError(
            f"File version {version} is newer than this BondForge "
            f"(supports up to version {FORMAT_VERSION})"
        )

    doc_data = data["document"]
    mol_data = doc_data["molecule"]

    # Rebuild molecule with correct ID counters.
    mol = Molecule()
    for ad in mol_data.get("atoms", []):
        atom = _atom_from_dict(ad)
        mol.atoms[atom.id] = atom
        if atom.id >= mol._next_atom_id:
            mol._next_atom_id = atom.id + 1

    for bd in mol_data.get("bonds", []):
        bond = _bond_from_dict(bd)
        mol.bonds[bond.id] = bond
        if bond.id >= mol._next_bond_id:
            mol._next_bond_id = bond.id + 1

    doc = Document(molecule=mol)

    for ad in doc_data.get("arrows", []):
        arrow = _arrow_from_dict(ad)
        doc.arrows[arrow.id] = arrow
        if arrow.id >= doc._next_arrow_id:
            doc._next_arrow_id = arrow.id + 1

    for td in doc_data.get("texts", []):
        ann = _text_from_dict(td)
        doc.texts[ann.id] = ann
        if ann.id >= doc._next_text_id:
            doc._next_text_id = ann.id + 1

    return doc


def load_bforge(path: str | Path) -> Document:
    """Read a ``.bforge`` file from disk."""
    text = Path(path).read_text(encoding="utf-8")
    return json_to_document(text)


__all__ = [
    "document_to_json",
    "json_to_document",
    "save_bforge",
    "load_bforge",
    "FORMAT_VERSION",
]
