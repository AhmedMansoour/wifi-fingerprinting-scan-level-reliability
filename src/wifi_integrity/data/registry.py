"""Dataset registry objects and lookup helpers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from wifi_integrity.config import load_yaml


@dataclass(frozen=True)
class UnitSpec:
    id: str
    label: str
    dataset: str
    group: str
    expected_train: int
    expected_test: int
    floor_labels_available: bool
    source_url: str | None = None
    license: str | None = None
    redistribution: str = "pending"

    @property
    def legacy_label(self) -> str:
        return f"{self.dataset} / {self.group}"


def load_registry(path: str | Path) -> list[UnitSpec]:
    content = load_yaml(path)
    units: list[UnitSpec] = []
    for item in content.get("units", []):
        units.append(
            UnitSpec(
                id=str(item["id"]),
                label=str(item["label"]),
                dataset=str(item["dataset"]),
                group=str(item["group"]),
                expected_train=int(item["expected_train"]),
                expected_test=int(item["expected_test"]),
                floor_labels_available=bool(item.get("floor_labels_available", True)),
                source_url=item.get("source_url"),
                license=item.get("license"),
                redistribution=str(item.get("redistribution", "pending")),
            )
        )
    return units


def registry_lookup(units: Iterable[UnitSpec]) -> dict[tuple[str, str], UnitSpec]:
    return {(unit.dataset, unit.group): unit for unit in units}
