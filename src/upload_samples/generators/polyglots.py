from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import GeneratorConfig
from ..registry import FamilyRegistry


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    if config.mitra_path is None:
        return []
    pairs = [("pdf", "jpg"), ("pdf", "png"), ("pdf", "tiff"), ("jpg", "pdf"), ("png", "pdf"), ("tiff", "pdf")]
    out_dir = config.out_dir / "polyglots"
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for left, right in pairs:
        if left not in registry.families() or right not in registry.families():
            continue
        left_plugin = registry.get_plugin(left)
        right_plugin = registry.get_plugin(right)
        left_seed = out_dir / f"seed-{left}.{left_plugin.default_extensions[0]}"
        right_seed = out_dir / f"seed-{right}.{right_plugin.default_extensions[0]}"
        left_seed.write_bytes(left_plugin.generate_valid(left_plugin.default_extensions[0]).data)
        right_seed.write_bytes(right_plugin.generate_valid(right_plugin.default_extensions[0]).data)
        try:
            subprocess.run(
                ["python3", str(config.mitra_path), str(left_seed), str(right_seed)],
                cwd=out_dir,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception:
            continue
    return entries
