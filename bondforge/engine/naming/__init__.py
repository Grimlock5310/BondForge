"""Chemistry naming: name↔structure translation.

v0.3 ships the *name → structure* direction via OPSIN (through the
``py2opsin`` wrapper) and leaves *structure → name* for a later
release — STOUT (the ML option) is too heavy to bundle by default and
needs an explicit "experimental" toggle.
"""

from bondforge.engine.naming.opsin_client import (
    OpsinError,
    OpsinUnavailable,
    is_opsin_available,
    name_to_molecule,
    name_to_smiles,
)

__all__ = [
    "OpsinError",
    "OpsinUnavailable",
    "is_opsin_available",
    "name_to_molecule",
    "name_to_smiles",
]
