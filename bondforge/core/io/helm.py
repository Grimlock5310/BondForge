"""HELM (Hierarchical Editing Language for Macromolecules) IO.

Supports a practical subset of HELM v2.0 notation:

- Simple polymer chains: ``PEPTIDE1{A.G.K.L}$$$$V2.0``
- Inter-chain connections: ``PEPTIDE1,PEPTIDE2,1:R3-1:R3``
- Multiple chains of any type (PEPTIDE, RNA, DNA, CHEM)

Limitations (v0.6):

- No inline SMILES monomers (``[*]...``)
- No polymer groups (third section always empty)
- No extended annotations (fourth section always empty)

Reference: https://pistoiaalliance.atlassian.net/wiki/spaces/PUB/pages/8716297/HELM+Notation
"""

from __future__ import annotations

import re

from bondforge.core.model.biopolymer import (
    Biopolymer,
    ConnectionType,
)
from bondforge.core.model.monomer import MonomerResidue, PolymerType


class HelmError(Exception):
    """Raised on invalid or unsupported HELM notation."""


# ---- parsing ---------------------------------------------------------------

_CHAIN_RE = re.compile(r"^(PEPTIDE|RNA|DNA|CHEM)(\d+)\{([^}]*)\}$")
_CONN_RE = re.compile(
    r"^(\w+),(\w+),(\d+):R(\d+)-(\d+):R(\d+)$"
)

_TYPE_MAP = {
    "PEPTIDE": PolymerType.PEPTIDE,
    "RNA": PolymerType.RNA,
    "DNA": PolymerType.DNA,
    "CHEM": PolymerType.CHEM,
}


def parse_helm(helm: str) -> Biopolymer:
    """Parse a HELM string into a :class:`Biopolymer`.

    The HELM string is split on ``$`` into sections. Only sections 1
    (simple polymers) and 2 (connections) are interpreted.

    Returns a biopolymer with auto-generated integer ID 1.
    """
    # Strip trailing V2.0 version tag and whitespace.
    helm = helm.strip()
    if not helm:
        raise HelmError("Empty HELM string")
    if helm.endswith("V2.0"):
        helm = helm[:-4].rstrip("$").rstrip()

    sections = helm.split("$")
    if not sections or not sections[0].strip():
        raise HelmError("Empty HELM string")

    # Section 1: simple polymers, separated by |
    polymer_section = sections[0].strip()
    # Section 2: connections (may be empty)
    connection_section = sections[1].strip() if len(sections) > 1 else ""

    bp = Biopolymer(id=1)

    # Parse chains.
    if polymer_section:
        for chain_str in polymer_section.split("|"):
            chain_str = chain_str.strip()
            if not chain_str:
                continue
            m = _CHAIN_RE.match(chain_str)
            if m is None:
                raise HelmError(f"Cannot parse polymer: {chain_str!r}")
            type_str, num, residues_str = m.group(1), m.group(2), m.group(3)
            chain_id = f"{type_str}{num}"
            ptype = _TYPE_MAP[type_str]
            residues = _parse_residues(residues_str, ptype)
            bp.add_chain(chain_id, ptype, residues)

    # Parse connections.
    if connection_section:
        for conn_str in connection_section.split("|"):
            conn_str = conn_str.strip()
            if not conn_str:
                continue
            cm = _CONN_RE.match(conn_str)
            if cm is None:
                raise HelmError(f"Cannot parse connection: {conn_str!r}")
            src_chain = cm.group(1)
            tgt_chain = cm.group(2)
            src_pos = int(cm.group(3))
            tgt_pos = int(cm.group(5))
            bp.add_connection(
                ConnectionType.PAIR, src_chain, src_pos, tgt_chain, tgt_pos
            )

    return bp


def _parse_residues(text: str, ptype: PolymerType) -> list[MonomerResidue]:
    """Parse a dot-separated residue list like ``A.G.K.L``."""
    residues: list[MonomerResidue] = []
    for i, sym in enumerate(text.split("."), start=1):
        sym = sym.strip()
        if not sym:
            continue
        residues.append(MonomerResidue(position=i, symbol=sym, polymer_type=ptype))
    return residues


# ---- writing ---------------------------------------------------------------


def write_helm(bp: Biopolymer) -> str:
    """Serialize a :class:`Biopolymer` to HELM v2.0 notation."""
    # Section 1: simple polymers.
    chain_parts: list[str] = []
    for chain in bp.iter_chains():
        residues = ".".join(r.symbol for r in chain.residues)
        chain_parts.append(f"{chain.id}{{{residues}}}")
    polymers = "|".join(chain_parts)

    # Section 2: connections.
    conn_parts: list[str] = []
    for conn in bp.iter_connections():
        # Default to R3 attachment points for inter-chain bonds.
        conn_parts.append(
            f"{conn.source_chain_id},{conn.target_chain_id},"
            f"{conn.source_position}:R3-{conn.target_position}:R3"
        )
    connections = "|".join(conn_parts)

    # Sections 3 and 4 are empty; append V2.0 version tag.
    return f"{polymers}${connections}$$$V2.0"


def read_helm_file(path: str) -> Biopolymer:
    """Read a HELM file (one HELM string per line, first line used)."""
    from pathlib import Path

    text = Path(path).read_text(encoding="utf-8").strip()
    first_line = text.split("\n")[0].strip()
    return parse_helm(first_line)


def write_helm_file(bp: Biopolymer, path: str) -> None:
    """Write a HELM string to a file."""
    from pathlib import Path

    Path(path).write_text(write_helm(bp) + "\n", encoding="utf-8")


__all__ = [
    "HelmError",
    "parse_helm",
    "write_helm",
    "read_helm_file",
    "write_helm_file",
]
