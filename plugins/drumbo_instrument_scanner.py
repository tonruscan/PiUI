"""Utilities for discovering Drumbo instrument metadata and samples.

The scanner walks configured instrument roots (e.g. ``assets/samples/drums``)
and returns structured metadata ready for the Drumbo module to consume.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import showlog

META_FILENAME = "meta.json"
DEFAULT_MICS = 16
DEFAULT_RANGE = (0, 127)
DEFAULT_PRESET_NAME = "init.json"
AUTO_DIAL_DEFAULT = 100


@dataclass
class DialSpec:
    slot: int
    label: str
    variable: str
    range: Tuple[int, int] = DEFAULT_RANGE
    default: Optional[int] = None
    group: Optional[str] = None
    color: Optional[str] = None


@dataclass
class BankSpec:
    id: str
    label: Optional[str]
    dials: List[DialSpec]


@dataclass
class PresetSpec:
    namespace: str
    default: str = DEFAULT_PRESET_NAME
    include_global: bool = False


@dataclass
class InstrumentSpec:
    id: str
    display_name: str
    category: Optional[str]
    mics: int
    banks: List[BankSpec]
    round_robin: Dict[str, object]
    presets: PresetSpec
    meta_path: Path
    samples_path: Path
    audio_files: List[Path] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    instruments: Dict[str, InstrumentSpec]
    errors: List[str]


def _normalise_label_token(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    token = str(raw).strip()
    if not token:
        return None
    token = token.split("-")[0]
    token = token.split(".")[0]
    token = token.replace(" ", "")
    token = token.strip("-_ ")
    if not token:
        return None
    return token.upper()


def _derive_tokens_from_stem(stem: str) -> Tuple[str, Optional[str], Optional[str]]:
    parts = stem.split("_") if stem else []
    instrument = parts[0] if parts else stem
    category = parts[1] if len(parts) > 1 else None
    if len(parts) > 2:
        label_part = parts[2]
    elif len(parts) == 2:
        label_part = parts[1]
    else:
        label_part = parts[0]
    label = _normalise_label_token(label_part)
    return instrument, category, label


def _build_auto_meta(samples_path: Path, wav_paths: List[Path]) -> Optional[dict]:
    if not wav_paths:
        return None

    sorted_paths = sorted(wav_paths)
    first_stem = sorted_paths[0].stem
    instrument_token, category_token, _ = _derive_tokens_from_stem(first_stem)

    instrument_id = samples_path.name
    display_source = instrument_token or instrument_id
    display_name = display_source.replace("-", " ").replace("_", " ").strip().title() or instrument_id.title()
    category = (category_token or "").strip().lower() or None

    label_order: List[str] = []
    for wav_path in sorted_paths:
        _instrument, _category, label = _derive_tokens_from_stem(wav_path.stem)
        if not label:
            continue
        if label not in label_order:
            label_order.append(label)

    if not label_order:
        showlog.warn(f"[DrumboScanner] Could not derive mic labels for {samples_path}")
        return None

    trimmed_labels = label_order[:DEFAULT_MICS]
    if len(label_order) > DEFAULT_MICS:
        showlog.warn(
            f"[DrumboScanner] Trimming mic labels for {samples_path} to {DEFAULT_MICS} entries (found {len(label_order)})"
        )

    banks: List[dict] = []
    for bank_index in range(0, len(trimmed_labels), 8):
        chunk = trimmed_labels[bank_index : bank_index + 8]
        if not chunk:
            continue
        bank_id = chr(ord("A") + bank_index // 8)
        dials = []
        for idx, label in enumerate(chunk, start=1):
            global_index = bank_index + idx
            variable_name = f"mic_{global_index}_level"
            dials.append(
                {
                    "slot": idx,
                    "label": label,
                    "variable": variable_name,
                    "range": list(DEFAULT_RANGE),
                    "default": AUTO_DIAL_DEFAULT,
                }
            )
        banks.append({"id": bank_id, "dials": dials})

    return {
        "id": instrument_id,
        "display_name": display_name,
        "category": category,
        "banks": banks,
    }


def _auto_generate_missing_meta(root: Path, errors: List[str]) -> None:
    try:
        wav_map: Dict[Path, List[Path]] = {}
        for wav_path in root.rglob("*.wav"):
            wav_map.setdefault(wav_path.parent, []).append(wav_path)
    except Exception as exc:
        errors.append(f"failed to enumerate wav files in {root}: {exc}")
        showlog.warn(f"[DrumboScanner] Failed to enumerate WAVs in {root}: {exc}")
        return

    for samples_path, wav_paths in wav_map.items():
        meta_path = samples_path / META_FILENAME
        if meta_path.exists():
            continue
        meta_payload = _build_auto_meta(samples_path, wav_paths)
        if not meta_payload:
            continue
        try:
            meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")
            showlog.info(f"[DrumboScanner] Auto-created metadata: {meta_path}")
        except Exception as exc:
            message = f"auto-create failed for {samples_path}: {exc}"
            errors.append(message)
            showlog.warn(f"[DrumboScanner] {message}")

def _coerce_int(value, *, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_range(value) -> Tuple[int, int]:
    if not value:
        return DEFAULT_RANGE
    if isinstance(value, (list, tuple)) and len(value) == 2:
        lo = _coerce_int(value[0], default=DEFAULT_RANGE[0])
        hi = _coerce_int(value[1], default=DEFAULT_RANGE[1])
        return (lo if lo is not None else DEFAULT_RANGE[0], hi if hi is not None else DEFAULT_RANGE[1])
    showlog.warn(f"[DrumboScanner] Invalid range spec {value!r}; using default {DEFAULT_RANGE}")
    return DEFAULT_RANGE


def _normalise_display_name(instrument_id: str, explicit: Optional[str]) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return instrument_id.replace("_", " ").replace("-", " ").title()


def _load_json(meta_path: Path) -> Optional[dict]:
    try:
        raw = meta_path.read_text(encoding="utf-8")
        return json.loads(raw)
    except FileNotFoundError:
        showlog.warn(f"[DrumboScanner] Meta file missing: {meta_path}")
    except json.JSONDecodeError as exc:
        showlog.error(f"[DrumboScanner] Failed to parse {meta_path}: {exc}")
    except Exception as exc:
        showlog.error(f"[DrumboScanner] Unexpected error reading {meta_path}: {exc}")
    return None


def _build_dial_spec(raw_dial: dict, *, errors: List[str], context: str) -> Optional[DialSpec]:
    try:
        slot = _coerce_int(raw_dial.get("slot"))
        label = str(raw_dial.get("label", "")).strip()
        variable = str(raw_dial.get("variable", "")).strip()
        if slot is None or slot < 1:
            raise ValueError("slot must be a positive integer")
        if not label:
            raise ValueError("label is required")
        if not variable:
            raise ValueError("variable is required")
        dial_range = _coerce_range(raw_dial.get("range"))
        default = _coerce_int(raw_dial.get("default"))
        group = raw_dial.get("group")
        color = raw_dial.get("color")
        return DialSpec(
            slot=slot,
            label=label,
            variable=variable,
            range=dial_range,
            default=default,
            group=group,
            color=color,
        )
    except ValueError as exc:
        errors.append(f"{context}: {exc}")
        return None


def _build_bank_spec(raw_bank: dict, *, errors: List[str], instrument_id: str, index: int) -> Optional[BankSpec]:
    bank_id = str(raw_bank.get("id", "")).strip() or chr(ord("A") + index)
    label = raw_bank.get("label")
    raw_dials = raw_bank.get("dials")
    if not isinstance(raw_dials, list) or not raw_dials:
        errors.append(f"instrument '{instrument_id}' bank '{bank_id}': dials array is required")
        return None

    dials: List[DialSpec] = []
    seen_slots: set[int] = set()
    for dial_index, raw_dial in enumerate(raw_dials):
        if not isinstance(raw_dial, dict):
            errors.append(
                f"instrument '{instrument_id}' bank '{bank_id}': dial #{dial_index + 1} must be an object"
            )
            continue
        spec = _build_dial_spec(
            raw_dial,
            errors=errors,
            context=f"instrument '{instrument_id}' bank '{bank_id}' dial #{dial_index + 1}",
        )
        if spec is None:
            continue
        if spec.slot in seen_slots:
            errors.append(
                f"instrument '{instrument_id}' bank '{bank_id}': duplicate slot {spec.slot}"
            )
            continue
        seen_slots.add(spec.slot)
        dials.append(spec)

    if not dials:
        return None

    dials.sort(key=lambda d: d.slot)
    return BankSpec(id=bank_id, label=label, dials=dials)


def _build_preset_spec(instrument_id: str, raw_presets: Optional[dict]) -> PresetSpec:
    namespace_default = f"drumbo/{instrument_id}"
    if not isinstance(raw_presets, dict):
        return PresetSpec(namespace=namespace_default)
    namespace = str(raw_presets.get("namespace")) if raw_presets.get("namespace") else namespace_default
    default_name = str(raw_presets.get("default")) if raw_presets.get("default") else DEFAULT_PRESET_NAME
    include_global = bool(raw_presets.get("include_global", False))
    return PresetSpec(namespace=namespace, default=default_name, include_global=include_global)


def _gather_audio_files(samples_path: Path) -> List[Path]:
    audio_extensions = {".wav", ".wave", ".aiff", ".aif", ".flac"}
    files: List[Path] = []
    if not samples_path.exists():
        return files
    for candidate in samples_path.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in audio_extensions:
            try:
                files.append(candidate.relative_to(samples_path))
            except ValueError:
                files.append(candidate)
    files.sort()
    return files


def scan_instrument_roots(roots: Iterable[Path]) -> DiscoveryResult:
    """Scan instrument roots and return discovered metadata.

    Args:
        roots: Iterable of base directories to search for ``meta.json`` files.
    """
    instruments: Dict[str, InstrumentSpec] = {}
    errors: List[str] = []

    root_paths = [Path(root).resolve() for root in roots]
    for root in root_paths:
        if not root.exists():
            errors.append(f"instrument root missing: {root}")
            continue
        _auto_generate_missing_meta(root, errors)
        for meta_path in root.rglob(META_FILENAME):
            samples_path = meta_path.parent
            meta = _load_json(meta_path)
            if not isinstance(meta, dict):
                errors.append(f"invalid metadata: {meta_path}")
                continue

            instrument_id = str(meta.get("id", "")).strip() or samples_path.name
            if not instrument_id:
                errors.append(f"{meta_path}: missing instrument id")
                continue

            if instrument_id in instruments:
                errors.append(
                    f"duplicate instrument id '{instrument_id}' found at {meta_path} (already defined at {instruments[instrument_id].meta_path})"
                )
                continue

            display_name = _normalise_display_name(instrument_id, meta.get("display_name"))
            category = meta.get("category")
            mics = _coerce_int(meta.get("mics"), default=DEFAULT_MICS) or DEFAULT_MICS

            raw_banks = meta.get("banks")
            if not isinstance(raw_banks, list) or not raw_banks:
                errors.append(f"instrument '{instrument_id}' has no banks defined ({meta_path})")
                continue

            banks: List[BankSpec] = []
            for idx, raw_bank in enumerate(raw_banks):
                if not isinstance(raw_bank, dict):
                    errors.append(f"instrument '{instrument_id}': bank #{idx + 1} must be an object")
                    continue
                bank_spec = _build_bank_spec(
                    raw_bank,
                    errors=errors,
                    instrument_id=instrument_id,
                    index=idx,
                )
                if bank_spec:
                    banks.append(bank_spec)

            if not banks:
                errors.append(f"instrument '{instrument_id}' has no valid banks")
                continue

            round_robin = meta.get("round_robin") if isinstance(meta.get("round_robin"), dict) else {}
            presets = _build_preset_spec(instrument_id, meta.get("presets"))
            audio_files = _gather_audio_files(samples_path)
            if not audio_files:
                showlog.warn(f"[DrumboScanner] Instrument '{instrument_id}' at {samples_path} has no audio files")

            instruments[instrument_id] = InstrumentSpec(
                id=instrument_id,
                display_name=display_name,
                category=category,
                mics=mics,
                banks=banks,
                round_robin=round_robin,
                presets=presets,
                meta_path=meta_path,
                samples_path=samples_path,
                audio_files=audio_files,
            )

    return DiscoveryResult(instruments=instruments, errors=errors)