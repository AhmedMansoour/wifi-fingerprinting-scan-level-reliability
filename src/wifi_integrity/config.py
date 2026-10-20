"""Configuration loading and scientific-configuration validation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_CONFIGS = (
    "datasets.yaml",
    "estimators.yaml",
    "indicators.yaml",
    "analysis.yaml",
    "cases.yaml",
    "figures.yaml",
    "harmonization.yaml",
)


class ConfigurationError(ValueError):
    """Raised when a configuration is incomplete or inconsistent."""


def load_yaml(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if not isinstance(content, dict):
        raise ConfigurationError(f"Expected a mapping in {file_path}")
    return content


def load_config_bundle(config_dir: str | Path) -> dict[str, dict[str, Any]]:
    directory = Path(config_dir)
    missing = [name for name in REQUIRED_CONFIGS if not (directory / name).is_file()]
    if missing:
        raise ConfigurationError(f"Missing configuration files: {missing}")
    bundle = {Path(name).stem: load_yaml(directory / name) for name in REQUIRED_CONFIGS}
    validate_config_bundle(bundle)
    return bundle


def validate_config_bundle(bundle: dict[str, dict[str, Any]]) -> None:
    datasets = bundle["datasets"]
    units = datasets.get("units", [])
    if len(units) != 10:
        raise ConfigurationError(f"Expected exactly 10 evaluation units, found {len(units)}")
    unit_ids = [unit.get("id") for unit in units]
    if len(unit_ids) != len(set(unit_ids)):
        raise ConfigurationError("Dataset unit IDs must be unique")

    estimators = bundle["estimators"].get("estimators", [])
    estimator_ids = [item.get("id") for item in estimators]
    if len(estimators) != 8 or len(estimator_ids) != len(set(estimator_ids)):
        raise ConfigurationError("Expected eight unique reference estimators")

    indicators = bundle["indicators"].get("indicators", [])
    indicator_ids = [item.get("id") for item in indicators]
    if len(indicators) != 18 or len(indicator_ids) != len(set(indicator_ids)):
        raise ConfigurationError("Expected 18 unique empirical indicators")

    sqs = bundle["indicators"].get("sqs", {})
    components = sqs.get("components", {})
    total_weight = sum(float(spec["weight"]) for spec in components.values())
    if abs(total_weight - 1.0) > 1e-12:
        raise ConfigurationError(f"SQS component weights sum to {total_weight}, not 1")

    analysis = bundle["analysis"]
    if analysis.get("adaptive_gross_error", {}).get("tail_quantile") != 0.75:
        raise ConfigurationError("Primary adaptive tail quantile must remain 0.75")
    if analysis.get("adaptive_gross_error", {}).get("multiplier") != 1.5:
        raise ConfigurationError("Primary adaptive multiplier must remain 1.5")
