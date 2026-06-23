from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import GeneratorConfig, ManifestEntry
from .utils import manifest_to_rows, to_json, write_csv


def write_manifest(out_dir: Path, config: GeneratorConfig, entries: list[ManifestEntry]) -> tuple[Path, Path]:
    payload = {
        "schema_version": "1.0",
        "generated_at": entries[0].created_at if entries else "",
        "tool_version": "0.1.0",
        "config": {
            "categories": list(config.categories),
            "selected_families": list(config.selected_families),
            "selected_extensions": list(config.selected_extensions),
            "seed": config.seed,
            "max_file_size_mb": config.max_file_size_mb,
            "max_total_output_mb": config.max_total_output_mb,
            "max_pixels": config.max_pixels,
            "max_tiff_pages": config.max_tiff_pages,
        },
        "entries": [asdict(entry) for entry in entries],
    }
    json_path = out_dir / "manifest.json"
    csv_path = out_dir / "manifest.csv"
    if config.format in {"json", "both"}:
        json_path.write_text(to_json(payload) + "\n", encoding="utf-8")
    if config.format in {"csv", "both"}:
        write_csv(csv_path, manifest_to_rows(entries))
    return json_path, csv_path


def load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
