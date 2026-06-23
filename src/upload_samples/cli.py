from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .generators import baseline, malformed, metadata, minimal_headers, mismatch, pdf_structures, polyglots, recipes, stress
from .manifest import load_manifest, write_manifest
from .models import GeneratorConfig
from .registry import FamilyRegistry
from .reporting import export_report, init_reporting, reset_reporting, run_report_ui, status_summary
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
    parser = argparse.ArgumentParser(
        prog="upload_samples",
        description="Generate and verify benign file-upload security test samples.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(generate_parser: argparse.ArgumentParser) -> None:
        generate_parser.add_argument(
            "--out",
            type=Path,
            required=True,
            help="Output directory where samples, manifests, and recipe files will be written.",
        )
        generate_parser.add_argument(
            "--category",
            action="append",
            choices=sorted(CATEGORY_HANDLERS),
            help="Generate only the selected category. Repeat the option to include multiple categories.",
        )
        generate_parser.add_argument(
            "--family",
            action="append",
            help="Restrict generation to canonical content families such as pdf, jpg, png, or tiff.",
        )
        generate_parser.add_argument(
            "--extension",
            action="append",
            help="Restrict generation to logical filename extensions such as pdf, jpg, jpeg, png, or tiff.",
        )
        generate_parser.add_argument(
            "--seed",
            type=int,
            default=1337,
            help="Seed used for deterministic malformed tails and any other pseudo-random sample generation.",
        )
        generate_parser.add_argument(
            "--max-file-size-mb",
            type=int,
            default=10,
            help="Per-file safety limit in megabytes for bounded generators.",
        )
        generate_parser.add_argument(
            "--max-total-output-mb",
            type=int,
            default=250,
            help="Overall output budget in megabytes for a generation run.",
        )
        generate_parser.add_argument(
            "--max-pixels",
            type=int,
            default=25_000_000,
            help="Maximum pixel budget used by bounded image stress generators.",
        )
        generate_parser.add_argument(
            "--max-tiff-pages",
            type=int,
            default=5,
            help="Maximum page count target used by bounded TIFF stress generation.",
        )
        generate_parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip writing files that already exist instead of failing or replacing them.",
        )
        generate_parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Allow generated files to replace existing files in the output directory.",
        )
        generate_parser.add_argument(
            "--format",
            choices=("json", "csv", "both"),
            default="both",
            help="Manifest output format: JSON only, CSV only, or both.",
        )
        generate_parser.add_argument(
            "--mitra-path",
            type=Path,
            help="Path to a local Mitra script for optional polyglot generation.",
        )
        generate_parser.add_argument(
            "--init-reporting",
            action="store_true",
            help="Initialize reporting scaffolding after sample generation finishes.",
        )
        generate_parser.add_argument(
            "--debug",
            action="store_true",
            help="Keep intermediate debugging artifacts such as empty Mitra pair directories that would otherwise be cleaned up.",
        )

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate sample files, recipes, and manifests.",
        description="Generate benign file-upload test samples into the selected output directory.",
    )
    add_common(generate_parser)

    subparsers.add_parser(
        "list-categories",
        help="List supported generation categories.",
        description="Print all category names that can be passed to --category.",
    )
    subparsers.add_parser(
        "list-families",
        help="List supported file families and extensions.",
        description="Print all registered canonical families and the logical extensions they provide.",
    )

    manifest_parser = subparsers.add_parser(
        "manifest",
        help="Rewrite manifest files from the existing manifest.json.",
        description="Reformat manifest.json and regenerate manifest.csv from an existing output directory.",
    )
    manifest_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory containing an existing manifest.json file.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify generated files against manifest.json.",
        description="Check file existence, file size, SHA-256, magic bytes, and mismatch flags for an output directory.",
    )
    verify_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory containing generated files and manifest.json.",
    )

    report_init_parser = subparsers.add_parser(
        "report-init",
        help="Initialize the reporting database and local UI assets.",
        description="Create reporting/session.sqlite3 and reporting/ui assets from an existing manifest.json.",
    )
    report_init_parser.add_argument("--out", type=Path, required=True, help="Output directory containing an existing manifest.json file.")
    report_init_parser.add_argument(
        "--reset",
        action="store_true",
        help="WARNING: delete the current reporting SQLite database and rebuild it from manifest.json, losing saved reporting data.",
    )

    report_ui_parser = subparsers.add_parser(
        "report-ui",
        help="Run the local reporting web UI.",
        description="Serve a localhost-only reporting app with autosave backed by SQLite.",
    )
    report_ui_parser.add_argument("--out", type=Path, required=True, help="Output directory containing manifest.json and reporting assets.")
    report_ui_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind the local reporting server to. (default: 127.0.0.1)")
    report_ui_parser.add_argument("--port", type=int, default=8765, help="Port to bind the local reporting server to. (default: 8765)")

    report_export_parser = subparsers.add_parser(
        "report-export",
        help="Export the final HTML and summary reports.",
        description="Render final-report.html plus JSON and Markdown summaries from the saved reporting session.",
    )
    report_export_parser.add_argument("--out", type=Path, required=True, help="Output directory containing the reporting session database.")

    report_status_parser = subparsers.add_parser(
        "report-status",
        help="Show saved testing progress counts.",
        description="Print current status totals from the reporting session database.",
    )
    report_status_parser.add_argument("--out", type=Path, required=True, help="Output directory containing the reporting session database.")
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
        init_reporting=args.init_reporting,
        debug=args.debug,
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
    if config.init_reporting:
        init_reporting(config.out_dir)
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


def cmd_report_init(args: argparse.Namespace) -> int:
    summary = reset_reporting(args.out) if args.reset else init_reporting(args.out)
    print(
        f"{'reset and initialized' if args.reset else 'initialized'} reporting in {args.out / 'reporting'} "
        f"(entries={summary['total_entries']}, new_results={summary['new_results']}, retired_entries={summary['retired_entries']})"
    )
    return 0


def cmd_report_ui(args: argparse.Namespace) -> int:
    print(f"serving reporting UI on http://{args.host}:{args.port}")
    run_report_ui(args.out, args.host, args.port)
    return 0


def cmd_report_export(args: argparse.Namespace) -> int:
    outputs = export_report(args.out)
    print(f"exported report to {outputs['html']}")
    return 0


def cmd_report_status(args: argparse.Namespace) -> int:
    summary = status_summary(args.out)
    for key, value in summary.items():
        print(f"{key}: {value}")
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
    if args.command == "report-init":
        return cmd_report_init(args)
    if args.command == "report-ui":
        return cmd_report_ui(args)
    if args.command == "report-export":
        return cmd_report_export(args)
    if args.command == "report-status":
        return cmd_report_status(args)
    parser.error(f"unsupported command: {args.command}")
    return 2
