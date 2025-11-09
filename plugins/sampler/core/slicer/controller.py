"""Orchestrates the auto-slicer pipeline for field recorder drops."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

import audioop
import showlog

from . import config
from .converter import AudioConverter, ConversionError
from .detector import DetectionResult, detect_transients
from .models import SliceSet, SliceSummary

Listener = Callable[[SliceSet], None]


class AutoSlicerController:
    """Manage conversion and slicing of field recorder drops."""

    def __init__(
        self,
        *,
        input_root: Optional[Path] = None,
        processed_root: Optional[Path] = None,
        max_slices: Optional[int] = None,
        min_slice_ms: Optional[float] = None,
        min_gap_ms: Optional[float] = None,
        converter: Optional[AudioConverter] = None,
    ) -> None:
        self.input_root = Path(input_root or config.FIELD_RECORDER_ROOT)
        self.processed_root = Path(processed_root or config.PROCESSED_ROOT)
        self.max_slices = int(max_slices or config.MAX_SLICES)
        self.min_slice_ms = float(min_slice_ms or config.MIN_SLICE_MS)
        self.min_gap_ms = float(min_gap_ms or config.MIN_GAP_MS)

        self.converter = converter or AudioConverter()
        self._listeners: list[Listener] = []
        self._last_sets: dict[str, SliceSet] = {}
        self._errors: dict[str, str] = {}
        self._last_error_id: str | None = None

        self.processed_root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Listener support
    # ------------------------------------------------------------------
    def add_listener(self, callback: Listener) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Listener) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify(self, slice_set: SliceSet) -> None:
        for callback in list(self._listeners):
            try:
                callback(slice_set)
            except Exception as exc:  # pragma: no cover - defensive
                showlog.debug(f"[AutoSlicer] Listener failed: {exc}")

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------
    def discover_pending(self) -> List[Path]:
        pending: List[Path] = []
        if not self.input_root.exists():
            return pending

        for path in sorted(self.input_root.glob("*.m4a")):
            rec_id = path.stem
            meta_path = self.processed_root / rec_id / config.METADATA_FILENAME
            if meta_path.exists():
                continue
            pending.append(path)
        return pending

    def discover_processed(self) -> List[SliceSet]:
        results: List[SliceSet] = []
        if not self.processed_root.exists():
            return results
        for meta_path in sorted(self.processed_root.glob(f"*/{config.METADATA_FILENAME}")):
            try:
                slice_set = self._load_metadata(meta_path)
            except Exception as exc:
                showlog.warn(f"[AutoSlicer] Failed to load metadata {meta_path}: {exc}")
                continue
            if slice_set:
                results.append(slice_set)
        return results

    # ------------------------------------------------------------------
    # Processing pipeline
    # ------------------------------------------------------------------
    def process_pending(self, *, limit: Optional[int] = None) -> List[SliceSet]:
        results: List[SliceSet] = []
        for path in self.discover_pending():
            try:
                result = self.process_recording(path)
            except Exception as exc:
                showlog.error(f"[AutoSlicer] Failed to process {path}: {exc}")
                continue
            results.append(result)
            if limit is not None and len(results) >= limit:
                break
        return results

    def process_recording(self, recording_path: Path) -> SliceSet:
        recording_path = Path(recording_path)
        if not recording_path.exists():
            raise FileNotFoundError(f"Recording not found: {recording_path}")

        recording_id = recording_path.stem
        work_dir = self.processed_root / recording_id
        work_dir.mkdir(parents=True, exist_ok=True)

        converted_path = work_dir / f"{recording_id}.wav"
        metadata_path = work_dir / config.METADATA_FILENAME
        slices_dir = work_dir / "slices"
        slices_dir.mkdir(parents=True, exist_ok=True)

        try:
            converted = self.converter.convert(recording_path, converted_path)
        except ConversionError as exc:
            message = str(exc)
            self._errors[recording_id] = message
            self._last_error_id = recording_id
            self._write_failure_metadata(
                recording_id=recording_id,
                source_path=recording_path,
                metadata_path=metadata_path,
                message=message,
            )
            raise

        detection = detect_transients(
            converted,
            max_slices=self.max_slices,
            min_slice_ms=self.min_slice_ms,
            min_gap_ms=self.min_gap_ms,
        )

        slice_summaries = self._export_slices(converted, slices_dir, detection, recording_id)

        slice_set = SliceSet(
            recording_id=recording_id,
            source_path=recording_path,
            converted_path=converted,
            metadata_path=metadata_path,
            sample_rate=detection.sample_rate,
            channels=detection.channels,
            sample_width=detection.sample_width,
            slices=slice_summaries,
            created_at=datetime.now(timezone.utc),
        )

        self._write_metadata(slice_set)
        self._errors.pop(recording_id, None)
        if self._last_error_id == recording_id:
            self._last_error_id = None
        self._last_sets[recording_id] = slice_set
        self._notify(slice_set)
        return slice_set

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def load_slice_set(self, recording_id: str) -> SliceSet | None:
        meta_path = self.processed_root / recording_id / config.METADATA_FILENAME
        return self._load_metadata(meta_path)

    def _load_metadata(self, meta_path: Path) -> SliceSet | None:
        meta_path = Path(meta_path)
        if not meta_path.exists():
            return None
        try:
            with meta_path.open("r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception as exc:
            raise RuntimeError(f"Failed to read metadata {meta_path}: {exc}") from exc
        status = str(data.get("status", "ok") or "ok").lower()
        recording_id = str(data.get("recording_id") or meta_path.parent.name)
        if status != "ok":
            message = data.get("error_message") or data.get("message") or f"Processing failed ({status})"
            if recording_id:
                self._errors[recording_id] = message
                self._last_error_id = recording_id
            return None
        slice_set = SliceSet.from_dict(data)
        self._last_sets[slice_set.recording_id] = slice_set
        return slice_set

    def _write_metadata(self, slice_set: SliceSet) -> Path:
        path = slice_set.metadata_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            json.dump(slice_set.to_dict(), fp, indent=2)
        return path

    def _write_failure_metadata(
        self,
        *,
        recording_id: str,
        source_path: Path,
        metadata_path: Path,
        message: str,
    ) -> Path:
        payload = {
            "status": "error",
            "recording_id": recording_id,
            "source_path": str(source_path),
            "metadata_path": str(metadata_path),
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error_message": message,
        }
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with metadata_path.open("w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
        return metadata_path

    def get_last_error(self, recording_id: str | None = None) -> Optional[str]:
        if recording_id is not None:
            return self._errors.get(recording_id)
        if self._last_error_id and self._last_error_id in self._errors:
            return self._errors[self._last_error_id]
        if not self._errors:
            return None
        try:
            last_key = next(reversed(self._errors))
        except StopIteration:
            return None
        return self._errors.get(last_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _export_slices(
        self,
        converted: Path,
        slices_dir: Path,
        detection: DetectionResult,
        recording_id: str,
    ) -> List[SliceSummary]:
        if not detection.candidates:
            showlog.info(f"[AutoSlicer] No transients detected for {recording_id}")
            return []

        import wave

        summaries: List[SliceSummary] = []
        with wave.open(str(converted), "rb") as reader:
            params = reader.getparams()
            total_frames = reader.getnframes()

            for index, candidate in enumerate(detection.candidates[: self.max_slices]):
                start = max(0, min(candidate.start_frame, total_frames))
                end = max(start, min(candidate.end_frame, total_frames))
                candidate_frames = candidate.frame_count
                if candidate_frames <= 0:
                    candidate_frames = end - start
                frame_count = max(0, min(candidate_frames, end - start))
                if frame_count <= 0:
                    continue

                reader.setpos(start)
                frames = reader.readframes(frame_count)

                slice_path = slices_dir / f"{recording_id}_slice_{index + 1:02d}.wav"
                with wave.open(str(slice_path), "wb") as writer:
                    writer.setparams(params)
                    writer.writeframes(frames)

                peak, rms = _measure_levels(
                    frames,
                    detection.sample_width,
                    detection.channels,
                )

                start_ms = (start / detection.sample_rate) * 1000.0
                end_ms = (end / detection.sample_rate) * 1000.0
                duration_ms = (frame_count / detection.sample_rate) * 1000.0
                peak_db = _to_dbfs(peak, detection.sample_width)
                rms_db = _to_dbfs(rms, detection.sample_width)
                peak_norm = _normalize_peak(peak, detection.sample_width)

                summaries.append(
                    SliceSummary(
                        index=index,
                        path=slice_path,
                        start_ms=start_ms,
                        end_ms=end_ms,
                        duration_ms=duration_ms,
                        peak_amplitude=float(peak),
                        peak_db=peak_db,
                        rms_db=rms_db,
                        peak_normalized=peak_norm,
                    )
                )

        return summaries


# ----------------------------------------------------------------------
# Audio helpers
# ----------------------------------------------------------------------

def _measure_levels(frames: bytes, sample_width: int, channels: int) -> tuple[int, int]:
    if not frames:
        return 0, 0
    mono = frames
    if channels > 1:
        try:
            mono = audioop.tomono(frames, sample_width, 0.5, 0.5)
        except Exception:
            mono = frames
    try:
        peak = audioop.max(mono, sample_width)
    except Exception:
        peak = 0
    try:
        rms = audioop.rms(mono, sample_width)
    except Exception:
        rms = 0
    return peak, rms


def _to_dbfs(value: int, sample_width: int) -> float | None:
    if value <= 0:
        return None
    max_amplitude = _max_amplitude(sample_width)
    if max_amplitude <= 0:
        return None
    return 20.0 * math.log10(value / max_amplitude)


def _normalize_peak(value: int, sample_width: int) -> float:
    max_amplitude = _max_amplitude(sample_width)
    if max_amplitude <= 0:
        return 0.0
    ratio = value / max_amplitude
    return max(0.0, min(1.0, ratio))


def _max_amplitude(sample_width: int) -> float:
    bits = max(1, sample_width) * 8
    return float((1 << (bits - 1)) - 1)
