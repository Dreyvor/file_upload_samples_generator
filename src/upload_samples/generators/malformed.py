from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from ..utils import append_tail, truncated
from .common import build_entry, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    families_seen: set[str] = set()
    for extension in config.selected_extensions:
        family_id = registry.family_for_extension(extension)
        if family_id in families_seen:
            continue
        families_seen.add(family_id)
        plugin = registry.get_plugin(family_id)
        sample = plugin.generate_valid(plugin.default_extensions[0])
        truncated_data = truncated(sample.data, max(1, len(sample.data) // 2))
        truncated_path = f"malformed/truncated-valid.{plugin.default_extensions[0]}"
        write_artifact(config, truncated_path, truncated_data)
        entries.append(
            build_entry(
                config=config,
                category="malformed",
                relative_path=truncated_path,
                logical_extension=plugin.default_extensions[0],
                generated_content_family=family_id,
                expected_magic=sample.expected_magic,
                expected_mime=sample.mime,
                mismatch=False,
                risk_level="low",
                generator="malformed.generate",
                description=f"Truncated valid {family_id.upper()} file.",
                expected_behavior="Strict validators should reject the file because parser validation should fail on truncation.",
                data=truncated_data,
            )
        )
        tailed_data = append_tail(sample.expected_magic, config.seed + len(entries), 64)
        tail_path = f"malformed/random-tail-after-valid-header.{plugin.default_extensions[0]}"
        write_artifact(config, tail_path, tailed_data)
        entries.append(
            build_entry(
                config=config,
                category="malformed",
                relative_path=tail_path,
                logical_extension=plugin.default_extensions[0],
                generated_content_family=family_id,
                expected_magic=sample.expected_magic,
                expected_mime=sample.mime,
                mismatch=False,
                risk_level="low",
                generator="malformed.generate",
                description=f"Valid {family_id.upper()} header followed by deterministic random tail bytes.",
                expected_behavior="Header-only validation may accept the file, but strict parsers should reject it safely.",
                data=tailed_data,
            )
        )
    return entries
