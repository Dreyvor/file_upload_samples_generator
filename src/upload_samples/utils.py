from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import ManifestEntry


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_within(base_dir: Path, target: Path) -> Path:
    base = base_dir.resolve()
    resolved = target.resolve()
    if base not in (resolved, *resolved.parents):
        raise ValueError(f"path escapes output directory: {target}")
    return resolved


def write_bytes(path: Path, data: bytes, overwrite: bool = False, skip_existing: bool = False) -> bool:
    if path.exists():
        if skip_existing:
            return False
        if not overwrite:
            raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def write_text(path: Path, text: str, overwrite: bool = False, skip_existing: bool = False) -> bool:
    return write_bytes(path, text.encode("utf-8"), overwrite=overwrite, skip_existing=skip_existing)


def deterministic_bytes(seed: int, length: int) -> bytes:
    rng = random.Random(seed)
    return bytes(rng.randrange(0, 256) for _ in range(length))


def truncated(data: bytes, keep_bytes: int) -> bytes:
    return data[: max(1, min(len(data), keep_bytes))]


def append_tail(data: bytes, seed: int, tail_bytes: int) -> bytes:
    return data + deterministic_bytes(seed, tail_bytes)


def to_json(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def manifest_to_rows(entries: Iterable[ManifestEntry]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in entries:
        row = asdict(entry)
        row["provenance_json"] = json.dumps(row.pop("provenance"), sort_keys=True)
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
