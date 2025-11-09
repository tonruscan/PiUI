"""Smoke tests for the sampler instrument registry."""

from __future__ import annotations

import unittest

from plugins.sampler.core.engine import InstrumentDescriptor
from plugins.sampler.core.services import instrument_registry


class InstrumentRegistryTests(unittest.TestCase):
    """Ensure the scaffolding registry exposes the expected behaviour."""

    def setUp(self) -> None:
        instrument_registry.clear_registry()

    def tearDown(self) -> None:
        instrument_registry.clear_registry()

    def test_dummy_drumbo_registration(self) -> None:
        descriptor = InstrumentDescriptor(
            id="drumbo",
            display_name="Drumbo",
            category="drums",
            version="0.1.0",
            entry_module="plugins.sampler.instruments.drumbo.module",
        )
        instrument_registry.register_instrument(descriptor)
        registered = instrument_registry.get_instrument("drumbo")
        self.assertIsNotNone(registered)
        self.assertEqual(registered.display_name, "Drumbo")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(exit=False)
