"""Tests for the sampler auto-slicer detection and controller pipeline."""

from __future__ import annotations

import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from ..slicer.controller import AutoSlicerController  # type: ignore[import]
from ..slicer.converter import AudioConverter, ConversionError  # type: ignore[import]
from ..slicer.detector import detect_transients  # type: ignore[import]


def _write_wave(path: Path, *, hits: int = 3, sample_rate: int = 44100) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    silence_frames = int(sample_rate * 0.1)
    hit_frames = int(sample_rate * 0.05)
    amplitude = 20000
    frequency = 220.0

    frames = bytearray()
    frames.extend(b"\x00\x00" * silence_frames)
    for _ in range(hits):
        for n in range(hit_frames):
            value = int(amplitude * math.sin(2.0 * math.pi * frequency * (n / sample_rate)))
            frames.extend(struct.pack("<h", value))
        frames.extend(b"\x00\x00" * silence_frames)

    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(frames)


class _StubConverter(AudioConverter):
    """Test double that copies the source file instead of invoking ffmpeg."""

    def __init__(self) -> None:
        # Do not call super().__init__ to avoid ffmpeg discovery in tests
        pass

    def convert(self, source_path: Path, dest_path: Path):  # type: ignore[override]
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        data = Path(source_path).read_bytes()
        dest_path.write_bytes(data)
        return dest_path


class AutoSlicerDetectionTests(unittest.TestCase):
    def test_detect_transients_on_synthetic_wave(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wav_path = Path(tmp_dir) / "sample.wav"
            _write_wave(wav_path, hits=4)

            result = detect_transients(wav_path, max_slices=8)

            self.assertGreaterEqual(len(result.candidates), 4)
            first = result.candidates[0]
            start_seconds = first.start_frame / result.sample_rate
            self.assertLess(start_seconds, 0.2)

    def test_controller_process_recording_outputs_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            input_root = Path(tmp_dir) / "fieldrecorder"
            processed_root = Path(tmp_dir) / "processed"
            input_root.mkdir(parents=True, exist_ok=True)

            recording_path = input_root / "rec_1234567890123.m4a"
            _write_wave(recording_path)

            controller = AutoSlicerController(
                input_root=input_root,
                processed_root=processed_root,
                converter=_StubConverter(),
                max_slices=6,
            )

            slice_set = controller.process_recording(recording_path)

            meta_path = processed_root / "rec_1234567890123" / "metadata.json"
            self.assertTrue(meta_path.exists(), "metadata.json should be written")
            self.assertGreater(len(slice_set.slices), 0)

            for summary in slice_set.slices:
                self.assertTrue(summary.path.exists())
                self.assertGreater(summary.duration_ms, 0.0)
                self.assertGreaterEqual(summary.peak_normalized, 0.0)
                self.assertLessEqual(summary.peak_normalized, 1.0)

    def test_controller_records_failed_conversion(self) -> None:
        class _FailingConverter(AudioConverter):
            def __init__(self) -> None:
                pass

            def convert(self, source_path: Path, dest_path: Path):  # type: ignore[override]
                raise ConversionError("ffmpeg failed (1): moov atom not found (file appears incomplete or truncated)")

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_root = Path(tmp_dir) / "fieldrecorder"
            processed_root = Path(tmp_dir) / "processed"
            input_root.mkdir(parents=True, exist_ok=True)

            recording_path = input_root / "rec_9999999999999.m4a"
            recording_path.write_bytes(b"")

            controller = AutoSlicerController(
                input_root=input_root,
                processed_root=processed_root,
                converter=_FailingConverter(),
            )

            results = controller.process_pending()
            self.assertEqual(results, [])

            meta_path = processed_root / "rec_9999999999999" / "metadata.json"
            self.assertTrue(meta_path.exists(), "Failure metadata should be written")

            payload = json.loads(meta_path.read_text())
            self.assertEqual(payload.get("status"), "error")
            self.assertIn("moov atom not found", payload.get("error_message", ""))

            self.assertIn("moov atom not found", controller.get_last_error("rec_9999999999999") or "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main(exit=False)
