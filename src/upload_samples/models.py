from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


RISK_INFO = "info"
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_DISABLED = "disabled"


@dataclass(frozen=True)
class GeneratorConfig:
    out_dir: Path
    categories: tuple[str, ...]
    selected_families: tuple[str, ...]
    selected_extensions: tuple[str, ...]
    seed: int = 1337
    max_file_size_mb: int = 10
    max_total_output_mb: int = 250
    max_pixels: int = 25_000_000
    max_tiff_pages: int = 5
    overwrite: bool = False
    skip_existing: bool = False
    format: str = "both"
    mitra_path: Path | None = None
    init_reporting: bool = False
    debug: bool = False


@dataclass
class ManifestEntry:
    id: str
    category: str
    relative_path: str
    filename: str
    logical_extension: str
    generated_content_family: str
    expected_mime: str
    expected_magic_hex: str
    mismatch: bool
    risk_level: str
    generator: str
    description: str
    expected_behavior: str
    sha256: str
    size_bytes: int
    created_at: str
    provenance: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FamilySample:
    content_family: str
    logical_extension: str
    data: bytes
    expected_magic: bytes
    mime: str


class FileFamilyPlugin(Protocol):
    family_id: str
    default_extensions: tuple[str, ...]
    magic_prefixes: tuple[bytes, ...]
    mime_type: str

    def supports(self, capability: str) -> bool:
        ...

    def generate_valid(self, logical_extension: str) -> FamilySample:
        ...

    def generate_metadata_samples(self) -> list[tuple[str, bytes, str]]:
        ...

    def generate_stress_samples(self, max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]:
        ...

    def generate_structure_samples(self) -> list[tuple[str, bytes, str]]:
        ...
