"""Biopolymer model — polymer chains and inter-chain connections.

A :class:`Biopolymer` is the v0.6 model for macromolecule drawings. It
consists of one or more :class:`PolymerChain` instances (peptide, RNA,
DNA, or chemical linker chains) connected by :class:`Connection` objects
(e.g. disulfide bonds, hydrogen bonds, branch links).

The biopolymer sits alongside the small-molecule :class:`Document` in the
scene — a typical BioDraw use case has an antibody template plus small
molecules around it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum

from bondforge.core.model.monomer import MonomerResidue, PolymerType


class ConnectionType(Enum):
    """Type of inter- or intra-chain connection."""

    PAIR = "pair"           # generic covalent bond (e.g. disulfide S-S)
    HYDROGEN = "hydrogen"   # hydrogen bond (display only, not covalent)
    BRANCH = "branch"       # side-chain attachment


@dataclass
class PolymerChain:
    """An ordered sequence of monomer residues forming a single chain.

    Attributes:
        id: Unique chain identifier within the biopolymer (e.g. ``"A"``).
        polymer_type: PEPTIDE, RNA, DNA, or CHEM.
        residues: Ordered list of monomers.
        x: Scene x origin for layout.
        y: Scene y origin for layout.
    """

    id: str
    polymer_type: PolymerType
    residues: list[MonomerResidue] = field(default_factory=list)
    x: float = 0.0
    y: float = 0.0

    @property
    def sequence(self) -> str:
        """One-letter sequence string."""
        return "".join(r.symbol for r in self.residues)

    def __len__(self) -> int:
        return len(self.residues)


@dataclass
class Connection:
    """A connection between two residues (possibly on different chains).

    Attributes:
        id: Unique connection identifier within the biopolymer.
        connection_type: What kind of linkage.
        source_chain_id: Chain ID of the first residue.
        source_position: 1-based residue index on the source chain.
        target_chain_id: Chain ID of the second residue.
        target_position: 1-based residue index on the target chain.
    """

    id: int
    connection_type: ConnectionType
    source_chain_id: str
    source_position: int
    target_chain_id: str
    target_position: int


@dataclass
class Biopolymer:
    """A complete biopolymer drawing (one or more chains + connections).

    The ``chains`` dict is keyed by chain ID (e.g. ``"A"``, ``"B"``).
    """

    id: int
    chains: dict[str, PolymerChain] = field(default_factory=dict)
    connections: dict[int, Connection] = field(default_factory=dict)
    _next_connection_id: int = 1
    x: float = 0.0
    y: float = 0.0

    def add_chain(
        self,
        chain_id: str,
        polymer_type: PolymerType,
        residues: list[MonomerResidue] | None = None,
    ) -> PolymerChain:
        """Create and register a new chain."""
        chain = PolymerChain(
            id=chain_id,
            polymer_type=polymer_type,
            residues=residues or [],
        )
        self.chains[chain_id] = chain
        return chain

    def remove_chain(self, chain_id: str) -> None:
        if chain_id not in self.chains:
            raise KeyError(f"Chain {chain_id!r} not found")
        del self.chains[chain_id]
        # Remove connections that reference this chain.
        to_remove = [
            cid for cid, c in self.connections.items()
            if c.source_chain_id == chain_id or c.target_chain_id == chain_id
        ]
        for cid in to_remove:
            del self.connections[cid]

    def add_connection(
        self,
        connection_type: ConnectionType,
        source_chain_id: str,
        source_position: int,
        target_chain_id: str,
        target_position: int,
    ) -> Connection:
        """Create and register an inter/intra-chain connection."""
        conn = Connection(
            id=self._next_connection_id,
            connection_type=connection_type,
            source_chain_id=source_chain_id,
            source_position=source_position,
            target_chain_id=target_chain_id,
            target_position=target_position,
        )
        self.connections[conn.id] = conn
        self._next_connection_id += 1
        return conn

    def remove_connection(self, connection_id: int) -> None:
        if connection_id not in self.connections:
            raise KeyError(f"Connection {connection_id} not found")
        del self.connections[connection_id]

    def iter_chains(self) -> Iterable[PolymerChain]:
        return self.chains.values()

    def iter_connections(self) -> Iterable[Connection]:
        return self.connections.values()


__all__ = [
    "ConnectionType",
    "PolymerChain",
    "Connection",
    "Biopolymer",
]
