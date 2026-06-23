from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generators import baseline, malformed, metadata, minimal_headers, mismatch, pdf_structures, polyglots, recipes, stress
from .manifest import load_manifest, write_manifest
from .models import GeneratorConfig
from .registry import FamilyRegistry
from .utils import sha256_file


CATEGORY_HANDLERS = {
    "baseline": baseline.generate,
    "mismatch": mismatch.generate,
    "minimal-headers": minimal_headers.generate,
    "malformed": malformed.generate,
    "metadata": metadata.generate,
    "filenames": recipes.generate_filenames,
    "multipart-recipes": recipes.generate_multipart,
    "stress-bounded": stress.generate,
    "pdf-structures": pdf_structures.generate,
    "polyglots": polyglots.generate,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upload_samples")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(generate_parser: argparse.ArgumentParser) -> None:
        generate_parser.add_argument("--out", type=Path, required=True)
        generate_parser.add_argument("--category", action="append", choices=sorted(CATEGORY_HANDLERS), help="Generate only selected categories.")
        generate_parser.add_argument("--family", action="append", help="Limit generation to selected canonical families.")
        generate_parser.add_argument("--extension", action="append", help="Limit generation to selected logical extensions.")
        generate_parser.add_argument("--seed", type=int, default=1337)
        generate_parser.add_argument("--max-file-size-mb", type=int, default=10)
        generate_parser.add_argument("--max-total-output-mb", type=int, default=250)
        generate_parser.add_argument("--max-pixels", type=int, default=25_000_000)
        generate_parser.add_argument("--max-tiff-pages", type=int, default=5)
        generate_parser.add_argument("--skip-existing", action="store_true")
        generate_parser.add_argument("--overwrite", action="store_true")
        generate_parser.add_argument("--format", choices=("json", "csv", "both"), default="both")
        generate_parser.add_argument("--mitra-path", type=Path)

    add_common(subparsers.add_parser("generate"))
    subparsers.add_parser("list-categories")
    subparsers.add_parser("list-families")

    manifest_parser = subparsers.add_parser("manifest")
    manifest_parser.add_argument("--out", type=Path, required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--out", type=Path, required=True)
    return parser


def build_registry() -> tuple[FamilyRegistry, list[str]]:
    registry = FamilyRegistry()
    registry.load_builtins()
    warnings = registry.load_entry_points()
    return registry, warnings


def config_from_args(args: argparse.Namespace, registry: FamilyRegistry) -> GeneratorConfig:
    selection = registry.select(args.family, args.extension)
    categories = tuple(args.category or CATEGORY_HANDLERS.keys())
    return GeneratorConfig(
        out_dir=args.out,
        categories=categories,
        selected_families=selection.families,
        selected_extensions=selection.extensions,
        seed=args.seed,
        max_file_size_mb=args.max_file_size_mb,
        max_total_output_mb=args.max_total_output_mb,
        max_pixels=args.max_pixels,
        max_tiff_pages=args.max_tiff_pages,
        overwrite=args.overwrite,
        skip_existing=args.skip_existing,
        format=args.format,
        mitra_path=args.mitra_path,
    )


def cmd_generate(args: argparse.Namespace) -> int:
    registry, warnings = build_registry()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    config = config_from_args(args, registry)
    entries = []
    for category in config.categories:
        entries.extend(CATEGORY_HANDLERS[category](config, registry))
    write_manifest(config.out_dir, config, entries)
    print(f"generated {len(entries)} manifest entries in {config.out_dir}")
    return 0


def cmd_list_categories() -> int:
    for category in sorted(CATEGORY_HANDLERS):
        print(category)
    return 0


def cmd_list_families() -> int:
    registry, warnings = build_registry()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for family in registry.families():
        plugin = registry.get_plugin(family)
        extensions = ",".join(plugin.default_extensions)
        print(f"{family}: {extensions}")
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    manifest_path = args.out / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    payload = load_manifest(manifest_path)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    csv_path = args.out / "manifest.csv"
    entries = payload.get("entries", [])
    if entries:
        from .utils import write_csv

        rows = []
        for entry in entries:
            row = dict(entry)
            row["provenance_json"] = json.dumps(row.pop("provenance", {}), sort_keys=True)
            rows.append(row)
        write_csv(csv_path, rows)
    print(f"rewrote manifest in {args.out}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    manifest_path = args.out / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")
    registry, warnings = build_registry()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    payload = load_manifest(manifest_path)
    entries = payload["entries"]
    failures: list[str] = []
    for entry in entries:
        file_path = args.out / entry["relative_path"]
        if not file_path.exists():
            failures.append(f"missing file: {file_path}")
            continue
        if file_path.stat().st_size != entry["size_bytes"]:
            failures.append(f"size mismatch: {file_path}")
        if sha256_file(file_path) != entry["sha256"]:
            failures.append(f"sha256 mismatch: {file_path}")
        magic = bytes.fromhex(entry["expected_magic_hex"])
        if not file_path.read_bytes().startswith(magic):
            failures.append(f"magic mismatch: {file_path}")
        expected_mismatch = registry.family_for_extension(entry["logical_extension"]) != entry["generated_content_family"]
        if expected_mismatch != entry["mismatch"]:
            failures.append(f"mismatch flag incorrect: {file_path}")
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print(f"verified {len(entries)} manifest entries in {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "generate":
        return cmd_generate(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "manifest":
        return cmd_manifest(args)
    if args.command == "list-categories":
        return cmd_list_categories()
    if args.command == "list-families":
        return cmd_list_families()
    parser.error(f"unsupported command: {args.command}")
    return 2
