"""Standalone runner for sampler core tests."""

from __future__ import annotations

import unittest


def main() -> None:
    """Execute the sampler core test suite."""

    unittest.main("plugins.sampler.core.tests", exit=False, verbosity=2)


if __name__ == "__main__":  # pragma: no cover
    main()
