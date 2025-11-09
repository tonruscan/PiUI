"""Unit tests for sampler core utility helpers."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.sampler.core.utils import (
    extract_sample_tokens,
    match_device_by_name,
    normalize_bank,
    parse_bool,
    parse_int,
)


class UtilsTests(unittest.TestCase):
    """Ensure shared helpers mirror the legacy Drumbo behaviour."""

    def test_normalize_bank_pads_and_truncates(self) -> None:
        self.assertEqual(normalize_bank([1, 2, 3]), [1, 2, 3, 0, 0, 0, 0, 0])
        self.assertEqual(normalize_bank(range(10)), [0, 1, 2, 3, 4, 5, 6, 7])

    def test_parse_int_reads_environment(self) -> None:
        with patch.dict(os.environ, {"DRUMBO_SAMPLE_RATE": " 48000 "}, clear=False):
            self.assertEqual(parse_int("DRUMBO_SAMPLE_RATE"), 48000)

    def test_parse_int_invalid_returns_none(self) -> None:
        with patch.dict(os.environ, {"DRUMBO_SAMPLE_RATE": "forty"}, clear=False):
            self.assertIsNone(parse_int("DRUMBO_SAMPLE_RATE"))

    def test_parse_bool_recognises_truthy_and_falsy(self) -> None:
        with patch.dict(os.environ, {"DRUMBO_FORCE": "Yes"}, clear=False):
            self.assertTrue(parse_bool("DRUMBO_FORCE"))
        with patch.dict(os.environ, {"DRUMBO_FORCE": "0"}, clear=False):
            self.assertFalse(parse_bool("DRUMBO_FORCE"))

    def test_parse_bool_invalid_returns_none(self) -> None:
        with patch.dict(os.environ, {"DRUMBO_FORCE": "maybe"}, clear=False):
            self.assertIsNone(parse_bool("DRUMBO_FORCE"))

    def test_match_device_by_name_exact_and_partial(self) -> None:
        devices = ["Primary Output", b"USB Audio", "Headphones"]
        self.assertEqual(match_device_by_name("primary output", devices), "Primary Output")
        self.assertEqual(match_device_by_name("usb", devices), "USB Audio")
        self.assertIsNone(match_device_by_name("nonexistent", devices))

    def test_extract_sample_tokens_matches_legacy_logic(self) -> None:
        label, sequence = extract_sample_tokens(Path("kit/snare_mics/MIC-03.wav"))
        self.assertEqual(label, "MIC")
        self.assertEqual(sequence, 3)

        label, sequence = extract_sample_tokens("snare_set_A_M1-09_take.wav")
        self.assertEqual(label, "M1")
        self.assertEqual(sequence, 9)

        label, sequence = extract_sample_tokens("set_snare_Mic 1.wav")
        self.assertEqual(label, "MIC1")
        self.assertEqual(sequence, 1)

        label, sequence = extract_sample_tokens("drum_loop.wav")
        self.assertEqual(label, "LOOP")
        self.assertIsNone(sequence)


if __name__ == "__main__":  # pragma: no cover
    unittest.main(exit=False)
