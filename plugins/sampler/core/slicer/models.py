"""Data models used by the sampler auto-slicer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class SliceSummary:
    """Metadata describing a single auto-detected slice."""

    index: int
    path: Path
    start_ms: float
    end_ms: float
    duration_ms: float
    peak_amplitude: float
    peak_db: Optional[float]
    rms_db: Optional[float]
    peak_normalized: float
    status: str = "pending"
    label: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "path": str(self.path),
            "start_ms": round(self.start_ms, 3),
            "end_ms": round(self.end_ms, 3),
            "duration_ms": round(self.duration_ms, 3),
            "peak_amplitude": float(self.peak_amplitude),
            "peak_db": None if self.peak_db is None else float(self.peak_db),
            "rms_db": None if self.rms_db is None else float(self.rms_db),
            "peak_normalized": float(self.peak_normalized),
            "status": self.status,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SliceSummary":
        return cls(
            index=int(data.get("index", 0)),
            path=Path(data.get("path", "")),
            start_ms=float(data.get("start_ms", 0.0)),
            end_ms=float(data.get("end_ms", 0.0)),
            duration_ms=float(data.get("duration_ms", 0.0)),
            peak_amplitude=float(data.get("peak_amplitude", 0.0)),
            peak_db=data.get("peak_db"),
            rms_db=data.get("rms_db"),
            peak_normalized=float(data.get("peak_normalized", 0.0)),
            status=str(data.get("status", "pending")),
            label=data.get("label"),
        )


@dataclass
class SliceSet:
    """Container describing all slices derived from a single recording."""

    recording_id: str
    source_path: Path
    converted_path: Path
    metadata_path: Path
    sample_rate: int
    channels: int
    sample_width: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    slices: list[SliceSummary] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recording_id": self.recording_id,
            "source_path": str(self.source_path),
            "converted_path": str(self.converted_path),
            "metadata_path": str(self.metadata_path),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "sample_width": self.sample_width,
            "created_at": self.created_at.isoformat().replace("+00:00", "Z"),
            "status": "ok",
            "slice_count": len(self.slices),
            "slices": [slice_summary.to_dict() for slice_summary in self.slices],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SliceSet":
        created_raw = data.get("created_at")
        created_at = None
        if isinstance(created_raw, str):
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except ValueError:
                created_at = datetime.now(timezone.utc)
        if created_at is None:
            created_at = datetime.now(timezone.utc)

        slices = [SliceSummary.from_dict(item) for item in data.get("slices", [])]
        return cls(
            recording_id=str(data.get("recording_id", "")),
            source_path=Path(data.get("source_path", "")),
            converted_path=Path(data.get("converted_path", "")),
            metadata_path=Path(data.get("metadata_path", "")),
            sample_rate=int(data.get("sample_rate", 44100)),
            channels=int(data.get("channels", 1)),
            sample_width=int(data.get("sample_width", 2)),
            created_at=created_at,
            slices=slices,
        )
