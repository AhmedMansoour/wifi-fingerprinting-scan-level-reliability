from __future__ import annotations

import json
from pathlib import Path

import typer

from wifi_integrity.config import load_config_bundle
from wifi_integrity.data.extract import extract_member
from wifi_integrity.data.harmonize import harmonize_combined_table
from wifi_integrity.data.registry import load_registry
from wifi_integrity.data.validate import validate_unit_audit, write_validation_report
from wifi_integrity.freeze import inventory_directory, inventory_zip
from wifi_integrity.reporting.manifests import build_release_manifest
from wifi_integrity.regression import validate_frozen_results, write_frozen_result_report
from wifi_integrity.benchmark.replay import materialize_published_benchmark
from wifi_integrity.benchmark.native import run_native_benchmark
from wifi_integrity.ui.build import build_dashboard
from wifi_integrity.ui.server import serve as serve_dashboard
from wifi_integrity.reliability.indicators import build_reliability_features
from wifi_integrity.reliability.analysis import run_reliability_analysis
from wifi_integrity.reliability.cases import build_case_registry

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Wi-Fi fingerprinting integrity reproducibility tools."""


@app.command("validate-config")
def validate_config(config_dir: Path = Path("config")) -> None:
    bundle = load_config_bundle(config_dir)
    typer.echo(
        f"Configuration valid: {len(bundle['datasets']['units'])} units, "
        f"{len(bundle['estimators']['estimators'])} estimators, "
        f"{len(bundle['indicators']['indicators'])} indicators."
    )


@app.command("freeze-inventory")
def freeze_inventory(
    archive: Path = Path("legacy_release/data/scratch_start.zip"),
    inventory_dir: Path = Path("inventory"),
) -> None:
    inventory_dir.mkdir(parents=True, exist_ok=True)
    archive_count = inventory_zip(archive, inventory_dir / "legacy_archive_inventory.csv")
    directory_count = inventory_directory(
        Path("legacy_release"), inventory_dir / "legacy_release_inventory.csv"
    )
    typer.echo(f"Inventoried {archive_count} archive members and {directory_count} frozen files.")


@app.command("extract-source")
def extract_source(
    config_dir: Path = Path("config"),
) -> None:
    bundle = load_config_bundle(config_dir)
    source = bundle["datasets"]["frozen_source"]
    output = extract_member(source["archive"], source["combined_member"], source["extracted_csv"])
    typer.echo(f"Extracted frozen combined table to {output}")


@app.command("harmonize")
def harmonize(
    config_dir: Path = Path("config"),
    output_dir: Path = Path("data/processed"),
) -> None:
    bundle = load_config_bundle(config_dir)
    source = Path(bundle["datasets"]["frozen_source"]["extracted_csv"])
    if not source.is_file():
        extracted = bundle["datasets"]["frozen_source"]
        extract_member(extracted["archive"], extracted["combined_member"], source)
    units = load_registry(config_dir / "datasets.yaml")
    manifest = harmonize_combined_table(source, units, output_dir)
    typer.echo(
        f"Harmonized {manifest['selected_rows']:,} scans: "
        f"{manifest['training_rows']:,} train and {manifest['test_rows']:,} test."
    )


@app.command("validate-data")
def validate_data(
    config_dir: Path = Path("config"),
    audit: Path = Path("data/processed/unit_harmonization_audit.csv"),
    report: Path = Path("results/logs/data_regression_report.json"),
) -> None:
    units = load_registry(config_dir / "datasets.yaml")
    validation = validate_unit_audit(audit, units)
    write_validation_report(validation, report)
    typer.echo(json.dumps(validation, indent=2))


@app.command("validate-frozen-results")
def validate_frozen(
    root: Path = Path("."),
    report: Path = Path("results/logs/frozen_result_regression_report.json"),
) -> None:
    validation = validate_frozen_results(root)
    write_frozen_result_report(validation, report)
    typer.echo(json.dumps(validation, indent=2))


@app.command("build-release-manifest")
def release_manifest(
    root: Path = Path("."),
    output: Path = Path("results/release_manifest.json"),
) -> None:
    manifest = build_release_manifest(root, output)
    typer.echo(f"Release manifest contains {manifest['file_count']} files.")


@app.command("stage-data")
def stage_data(config_dir: Path = Path("config")) -> None:
    """Run extraction, harmonization, and data regression validation."""
    bundle = load_config_bundle(config_dir)
    source_cfg = bundle["datasets"]["frozen_source"]
    source = Path(source_cfg["extracted_csv"])
    if not source.is_file():
        extract_member(source_cfg["archive"], source_cfg["combined_member"], source)
    units = load_registry(config_dir / "datasets.yaml")
    harmonize_combined_table(source, units, Path("data/processed"))
    validation = validate_unit_audit("data/processed/unit_harmonization_audit.csv", units)
    write_validation_report(validation, "results/logs/data_regression_report.json")
    frozen = validate_frozen_results(Path("."))
    write_frozen_result_report(frozen, "results/logs/frozen_result_regression_report.json")
    typer.echo(json.dumps({"data": validation, "frozen_results": frozen}, indent=2))


@app.command("benchmark-published")
def benchmark_published(root: Path = Path(".")) -> None:
    """Materialize and regression-test the exact published estimator benchmark."""
    report = materialize_published_benchmark(root)
    typer.echo(json.dumps(report, indent=2))


@app.command("benchmark-native")
def benchmark_native(
    root: Path = Path("."),
    units: str = "U10",
    estimators: str = "knn,wknn",
    output_name: str = "estimator_predictions_native.csv.gz",
) -> None:
    """Retrain supported estimators through the common interface."""
    unit_ids = [item.strip() for item in units.split(",") if item.strip()]
    estimator_ids = [item.strip() for item in estimators.split(",") if item.strip()]
    report = run_native_benchmark(
        root, unit_ids=unit_ids, estimator_ids=estimator_ids, output_name=output_name
    )
    typer.echo(json.dumps(report, indent=2))


@app.command("build-ui")
def build_ui(root: Path = Path("."), output: Path = Path("site")) -> None:
    """Build the offline HTML research dashboard."""
    report = build_dashboard(root, root / output)
    typer.echo(json.dumps(report, indent=2))


@app.command("serve-ui")
def serve_ui(
    root: Path = Path("."), host: str = "127.0.0.1", port: int = 8000
) -> None:
    """Serve the repository and dashboard locally."""
    index = root / "site/index.html"
    if not index.is_file():
        build_dashboard(root, root / "site")
    typer.echo(f"Open http://{host}:{port}/site/index.html")
    serve_dashboard(root, host=host, port=port)


@app.command("stage-estimators")
def stage_estimators(root: Path = Path(".")) -> None:
    """Build the published estimator benchmark and HTML dashboard."""
    benchmark = materialize_published_benchmark(root)
    dashboard = build_dashboard(root, root / "site")
    typer.echo(json.dumps({"benchmark": benchmark, "dashboard": dashboard}, indent=2))


@app.command("reliability-features")
def reliability_features(root: Path = Path(".")) -> None:
    """Regenerate the diagnostic candidate probe and scan-level indicators."""
    report = build_reliability_features(root)
    typer.echo(json.dumps(report, indent=2))


@app.command("reliability-analysis")
def reliability_analysis(root: Path = Path(".")) -> None:
    """Regenerate association and gross-error discrimination tables."""
    report = run_reliability_analysis(root)
    typer.echo(json.dumps(report, indent=2))


@app.command("build-cases")
def build_cases(root: Path = Path("."), n_cases: int = 24) -> None:
    """Build the deterministic gross-error case registry and atlas data."""
    report = build_case_registry(root, n_cases=n_cases)
    typer.echo(json.dumps(report, indent=2))


@app.command("stage-reliability")
def stage_reliability(root: Path = Path("."), n_cases: int = 24) -> None:
    """Run reliability features, analysis, cases, and dashboard generation."""
    features = build_reliability_features(root)
    analysis = run_reliability_analysis(root)
    cases = build_case_registry(root, n_cases=n_cases)
    dashboard = build_dashboard(root, root / "site")
    typer.echo(json.dumps({"features": features, "analysis": analysis, "cases": cases, "dashboard": dashboard}, indent=2))


if __name__ == "__main__":
    app()
