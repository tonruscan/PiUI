"""Audio conversion utilities for the auto-slicer pipeline."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import showlog

from . import config


class ConversionError(RuntimeError):
    """Raised when audio conversion fails."""


class AudioConverter:
    """Convert source recordings to the sampler's target PCM format."""

    def __init__(self, ffmpeg_binary: Optional[str] = None) -> None:
        self.ffmpeg_binary = ffmpeg_binary or _guess_ffmpeg_binary()

    def convert(self, source_path: Path, dest_path: Path) -> Path:
        """Convert `source_path` into `dest_path` using ffmpeg."""

        source_path = Path(source_path)
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if not source_path.exists():
            raise ConversionError(f"Source audio not found: {source_path}")

        cmd = [
            self.ffmpeg_binary,
            "-y",
            "-i",
            str(source_path),
            "-ac",
            str(config.TARGET_CHANNELS),
            "-ar",
            str(config.TARGET_SAMPLE_RATE),
            "-sample_fmt",
            _sample_format_flag(config.TARGET_SAMPLE_WIDTH),
            str(dest_path),
        ]

        showlog.debug(f"[AutoSlicer] ffmpeg convert: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if result.returncode != 0:
            error_text = result.stderr.decode(errors="ignore")
            showlog.debug(f"[AutoSlicer] ffmpeg stderr ({result.returncode}): {error_text}")
            summary = _summarize_ffmpeg_error(error_text)
            raise ConversionError(f"ffmpeg failed ({result.returncode}): {summary}")

        if not dest_path.exists():
            raise ConversionError(f"ffmpeg reported success but file missing: {dest_path}")

        return dest_path


class PassthroughConverter(AudioConverter):
    """Fallback converter that simply copies the source file."""

    def __init__(self) -> None:
        super().__init__(ffmpeg_binary="ffmpeg")

    def convert(self, source_path: Path, dest_path: Path) -> Path:  # type: ignore[override]
        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        return dest_path


def _guess_ffmpeg_binary() -> str:
    candidates = [
        os.environ.get("FFMPEG"),
        os.environ.get("FFMPEG_BINARY"),
        "ffmpeg",
        "ffmpeg.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        probe = shutil.which(candidate) if not Path(candidate).exists() else candidate
        if probe:
            return str(probe)
    return "ffmpeg"


def _sample_format_flag(sample_width_bytes: int) -> str:
    if sample_width_bytes >= 4:
        return "s32"
    if sample_width_bytes == 3:
        return "s24"
    if sample_width_bytes == 2:
        return "s16"
    return "s8"


def _summarize_ffmpeg_error(stderr_text: str) -> str:
    lines = [line.strip() for line in stderr_text.splitlines() if line.strip()]
    if not lines:
        return "unknown error"
    for line in lines:
        lower = line.lower()
        if "moov atom not found" in lower:
            return "moov atom not found (file appears incomplete or truncated)"
        if "invalid data" in lower and "when processing input" in lower:
            return "invalid data found while parsing input"
        if lower.startswith("error:"):
            return line[6:].strip() or "ffmpeg error"
    return lines[-1]
