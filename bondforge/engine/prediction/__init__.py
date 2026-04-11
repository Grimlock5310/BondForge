"""Spectrum prediction engines (NMR, IR, MS).

All predictors take a BondForge :class:`~bondforge.core.model.molecule.Molecule`
and return a :class:`~bondforge.core.model.spectrum.Spectrum`. Predictions
are heuristic — they're meant for teaching, quick sanity checks, and
populating the viewer when no experimental data is available. The viewer
always shows the ``origin`` field ("predicted") so users know the data is
computed.
"""

from bondforge.engine.prediction.ir import predict_ir
from bondforge.engine.prediction.ms import predict_ms
from bondforge.engine.prediction.nmr import predict_1h_nmr, predict_13c_nmr

__all__ = ["predict_1h_nmr", "predict_13c_nmr", "predict_ir", "predict_ms"]
