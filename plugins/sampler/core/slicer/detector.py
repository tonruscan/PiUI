"""Transient detection utilities for the sampler auto-slicer."""

from __future__ import annotations

import audioop
import math
import statistics
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import showlog

from . import config


@dataclass
class SliceCandidate:
    """Represents a detected transient slice in frame coordinates."""

    start_frame: int
    end_frame: int
    peak_rms: float
    energy_sq_sum: float
    frame_total: int

    @property
    def frame_count(self) -> int:
        return max(0, self.frame_total)

    @property
    def avg_rms(self) -> float:
        if self.frame_total <= 0:
            return 0.0
        try:
            return math.sqrt(self.energy_sq_sum / self.frame_total)
        except (ValueError, ZeroDivisionError):
            return 0.0


@dataclass
class DetectionResult:
    """Container for transient detection results."""

    sample_rate: int
    channels: int
    sample_width: int
    total_frames: int
    candidates: List[SliceCandidate]


def detect_transients(
    wav_path: Path,
    *,
    max_slices: int | None = None,
    min_slice_ms: float | None = None,
    min_gap_ms: float | None = None,
) -> DetectionResult:
    """Detect transient slices within a PCM WAV file."""

    wav_path = Path(wav_path)
    if not wav_path.exists():
        raise FileNotFoundError(f"PCM file not found: {wav_path}")

    limit = max_slices or config.MAX_SLICES
    min_slice_ms = min_slice_ms or config.MIN_SLICE_MS
    min_gap_ms = min_gap_ms or config.MIN_GAP_MS

    with wave.open(str(wav_path), "rb") as reader:
        sample_rate = reader.getframerate()
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        total_frames = reader.getnframes()

        hop_frames = max(1, int(sample_rate * 0.01))
        min_slice_frames = max(1, int(sample_rate * (min_slice_ms / 1000.0)))
        min_gap_frames = max(1, int(sample_rate * (min_gap_ms / 1000.0)))

        energies: list[int] = []
        positions: list[int] = []
        chunk_frames: list[int] = []
        frame_cursor = 0

        while True:
            chunk = reader.readframes(hop_frames)
            if not chunk:
                break
            actual_frames = len(chunk) // (sample_width * channels)
            if actual_frames <= 0:
                break

            mono_chunk = chunk
            if channels > 1:
                try:
                    mono_chunk = audioop.tomono(chunk, sample_width, 0.5, 0.5)
                except Exception:
                    mono_chunk = chunk

            try:
                energy = audioop.rms(mono_chunk, sample_width)
            except Exception:
                energy = 0

            energies.append(energy)
            positions.append(frame_cursor)
            chunk_frames.append(actual_frames)
            frame_cursor += actual_frames

            if actual_frames < hop_frames:
                break

        # Determine adaptive threshold
        non_zero = [value for value in energies if value > 0]
        if non_zero:
            median_energy = statistics.median(non_zero)
            peak_energy = max(non_zero)
        else:
            median_energy = 0.0
            peak_energy = 0.0

        if peak_energy <= 0.0:
            threshold = 0.0
        else:
            dynamic_floor = median_energy * 1.5 if median_energy > 0 else peak_energy * 0.08
            threshold = max(dynamic_floor, peak_energy * 0.25, 300.0)
            threshold = min(threshold, peak_energy * 0.95)

        showlog.debug(
            f"[AutoSlicer] Transient detect: median={median_energy:.1f} peak={peak_energy:.1f} threshold={threshold:.1f}"
        )

        candidates: list[SliceCandidate] = []
        state = "idle"
        current_start = 0
        current_peak = 0.0
        current_energy_sq = 0.0
        current_frame_total = 0
        silence_frames = 0

        for idx, energy in enumerate(energies):
            position = positions[idx]
            frames_in_chunk = chunk_frames[idx]
            if energy >= threshold and threshold > 0:
                if state == "idle":
                    state = "slice"
                    current_start = position
                    current_peak = float(energy)
                    current_energy_sq = float(energy) ** 2 * frames_in_chunk
                    current_frame_total = frames_in_chunk
                    silence_frames = 0
                else:
                    current_peak = max(current_peak, float(energy))
                    current_energy_sq += float(energy) ** 2 * frames_in_chunk
                    current_frame_total += frames_in_chunk
                    silence_frames = 0
            elif state == "slice":
                silence_frames += frames_in_chunk
                current_energy_sq += float(energy) ** 2 * frames_in_chunk
                current_frame_total += frames_in_chunk
                if silence_frames >= min_gap_frames:
                    end_frame = position
                    if end_frame <= current_start:
                        end_frame = current_start + hop_frames
                    if (end_frame - current_start) >= min_slice_frames:
                        candidates.append(
                            SliceCandidate(
                                start_frame=current_start,
                                end_frame=min(end_frame, total_frames),
                                peak_rms=current_peak,
                                energy_sq_sum=current_energy_sq,
                                frame_total=current_frame_total,
                            )
                        )
                        if len(candidates) >= limit:
                            break
                    state = "idle"
                    silence_frames = 0
                    current_energy_sq = 0.0
                    current_frame_total = 0
                    current_peak = 0.0

        if state == "slice" and len(candidates) < limit:
            candidates.append(
                SliceCandidate(
                    start_frame=current_start,
                    end_frame=total_frames,
                    peak_rms=current_peak,
                    energy_sq_sum=current_energy_sq,
                    frame_total=current_frame_total,
                )
            )

        merged = _merge_short_candidates(candidates, min_slice_frames)

        return DetectionResult(
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            total_frames=total_frames,
            candidates=merged[:limit],
        )


def _merge_short_candidates(candidates: Iterable[SliceCandidate], min_frames: int) -> List[SliceCandidate]:
    merged: List[SliceCandidate] = []
    buffer_candidate: SliceCandidate | None = None

    for candidate in candidates:
        if candidate.frame_count >= min_frames:
            if buffer_candidate:
                combined = _merge_two(buffer_candidate, candidate)
                merged.append(combined)
                buffer_candidate = None
            else:
                merged.append(candidate)
            continue

        if buffer_candidate is None:
            buffer_candidate = candidate
        else:
            buffer_candidate = _merge_two(buffer_candidate, candidate)

    if buffer_candidate:
        merged.append(buffer_candidate)

    return merged


def _merge_two(first: SliceCandidate, second: SliceCandidate) -> SliceCandidate:
    start = min(first.start_frame, second.start_frame)
    end = max(first.end_frame, second.end_frame)
    peak = max(first.peak_rms, second.peak_rms)
    energy_sq = first.energy_sq_sum + second.energy_sq_sum
    frame_total = first.frame_total + second.frame_total
    return SliceCandidate(
        start_frame=start,
        end_frame=end,
        peak_rms=peak,
        energy_sq_sum=energy_sq,
        frame_total=frame_total,
    )
