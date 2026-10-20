"""Targeted tests for the bounded synthetic MotorGuard dataset generator."""

import csv
import importlib.util
import sys
from pathlib import Path

import pytest


GENERATOR_PATH = Path(__file__).parents[2] / "scripts" / "generate_synthetic_edge_impulse_dataset.py"
SPEC = importlib.util.spec_from_file_location("synthetic_dataset_generator", GENERATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generator
SPEC.loader.exec_module(generator)


def test_generated_labels_match_declared_threshold_bands(tmp_path: Path) -> None:
    counts = generator.build_dataset(tmp_path, runs_per_class=3, rows_per_run=4, seed=775)
    assert counts == {"all": 36, "train": 12, "validation": 12, "test": 12}

    with (tmp_path / "motorguard_synthetic_v2_runs.csv").open(newline="", encoding="utf-8") as csv_file:
        records = list(csv.DictReader(csv_file))
    assert {record["health_status"] for record in records} == {"healthy", "warning", "critical"}
    for record in records:
        observed = generator.classify(float(record["current_A"]), float(record["vibration_g"]))
        assert observed == record["health_status"]


def test_edge_impulse_splits_do_not_share_runs(tmp_path: Path) -> None:
    generator.build_dataset(tmp_path, runs_per_class=6, rows_per_run=2, seed=775)
    with (tmp_path / "motorguard_synthetic_v2_runs.csv").open(newline="", encoding="utf-8") as csv_file:
        records = list(csv.DictReader(csv_file))

    run_ids = {record["run_id"] for record in records}
    assert len(run_ids) == 18
    split_run_ids = {
        split: {record["run_id"] for record in records if record["split"] == split}
        for split in ("train", "validation", "test")
    }
    assert set.union(*split_run_ids.values()) == run_ids
    assert split_run_ids["train"].isdisjoint(split_run_ids["validation"])
    assert split_run_ids["train"].isdisjoint(split_run_ids["test"])
    assert split_run_ids["validation"].isdisjoint(split_run_ids["test"])
    assert all((tmp_path / f"{split}_edge_impulse.csv").exists() for split in ("train", "validation", "test"))


@pytest.mark.parametrize("current,vibration,expected", [
    (0.75, 0.050, "healthy"),
    (3.00, 0.050, "warning"),
    (0.75, 0.100, "warning"),
    (4.00, 0.050, "critical"),
    (0.75, 0.400, "critical"),
])
def test_classify_respects_threshold_boundaries(current: float, vibration: float, expected: str) -> None:
    assert generator.classify(current, vibration) == expected
