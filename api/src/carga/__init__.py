"""Demonstration load and production start of the GestNow base (ISSUE-008).

The mechanism lives here: :mod:`registro` holds the registered parts and the
date shift, :mod:`runner` decides between demonstration and production by the
app mode, :mod:`plataforma` writes the platform part converted from the
prototype mocks and :mod:`producao` starts the empty production base with the
first Admin. Each module adds its own part through a ``seed.py`` that calls
``src.carga.register``; the LEIA-ME in this folder explains the contract.
"""

from src.carga.prototipo import prototype_collection
from src.carga.registro import DEMO_ANCHOR, register, registered, shift_date
from src.carga.runner import (
    ProductionStartError,
    run_demonstration,
    run_for_mode,
    run_production,
)

__all__ = [
    "DEMO_ANCHOR",
    "ProductionStartError",
    "prototype_collection",
    "register",
    "registered",
    "run_demonstration",
    "run_for_mode",
    "run_production",
    "shift_date",
]
