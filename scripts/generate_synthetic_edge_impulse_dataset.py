#!/usr/bin/env python3
"""Generate physically bounded, run-isolated synthetic MotorGuard datasets.

This generator creates labelled *synthetic* data for exercising the Edge
Impulse pipeline. It does not calibrate the physical motor or replace real
bench measurements. Every generated row is bounded by the current firmware
rule bands: warning at 3.0 A / 0.100 g and critical at 4.0 A / 0.400 g.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


FEATURE_COLUMNS = ("temperature_C", "vibration_g", "current_A", "health_status")
RUN_COLUMNS = ("run_id", "sample_index", "split", "scenario", *FEATURE_COLUMNS)

WARNING_CURRENT_A = 3.0
CRITICAL_CURRENT_A = 4.0
WARNING_VIBRATION_G = 0.100
CRITICAL_VIBRATION_G = 0.400


@dataclass(frozen=True)
class Scenario:
    """Run-level feature ranges for one safe synthetic operating scenario."""

    name: str
    label: str
    temperature_range: tuple[float, float]
    vibration_range: tuple[float, float]
    current_range: tuple[float, float]


SCENARIOS = (
    Scenario("healthy_no_load", "healthy", (26.0, 32.0), (0.015, 0.055), (0.30, 0.75)),
    Scenario("healthy_rated_load", "healthy", (29.0, 38.0), (0.030, 0.090), (1.10, 2.70)),
    Scenario("warning_high_vibration", "warning", (28.0, 40.0), (0.115, 0.280), (0.35, 2.70)),
    Scenario("warning_high_current", "warning", (30.0, 42.0), (0.035, 0.095), (3.05, 3.75)),
    Scenario("critical_overcurrent", "critical", (30.0, 44.0), (0.035, 0.120), (4.05, 4.70)),
    Scenario("critical_vibration", "critical", (30.0, 46.0), (0.420, 0.650), (0.45, 3.20)),
)


def clamp(value: float, bounds: tuple[float, float]) -> float:
    """Keep a generated value inside its physical scenario band."""
    return max(bounds[0], min(value, bounds[1]))


def classify(current_a: float, vibration_g: float) -> str:
    """Apply the same current/vibration bands used by the synthetic labels."""
    if current_a >= CRITICAL_CURRENT_A or vibration_g >= CRITICAL_VIBRATION_G:
        return "critical"
    if current_a >= WARNING_CURRENT_A or vibration_g >= WARNING_VIBRATION_G:
        return "warning"
    return "healthy"


def generate_run(
    scenario: Scenario,
    run_id: str,
    rows_per_run: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    """Generate a correlated feature sequence instead of independent rows."""
    temperature_base = rng.uniform(*scenario.temperature_range)
    vibration_base = rng.uniform(*scenario.vibration_range)
    current_base = rng.uniform(*scenario.current_range)
    phase = rng.uniform(0.0, math.tau)
    records: list[dict[str, str]] = []

    for sample_index in range(rows_per_run):
        wave = math.sin((sample_index / 24.0) + phase)
        temperature = clamp(
            temperature_base + wave * 0.35 + rng.gauss(0.0, 0.15),
            scenario.temperature_range,
        )
        vibration = clamp(
            vibration_base + wave * 0.006 + rng.gauss(0.0, 0.004),
            scenario.vibration_range,
        )
        current = clamp(
            current_base + wave * 0.08 + rng.gauss(0.0, 0.035),
            scenario.current_range,
        )
        observed_label = classify(current, vibration)
        if observed_label != scenario.label:
            raise ValueError(
                f"{scenario.name} generated {observed_label} at run {run_id}, sample {sample_index}"
            )
        records.append(
            {
                "run_id": run_id,
                "sample_index": str(sample_index),
                "scenario": scenario.name,
                "temperature_C": f"{temperature:.2f}",
                "vibration_g": f"{vibration:.4f}",
                "current_A": f"{current:.3f}",
                "health_status": scenario.label,
            }
        )
    return records


def split_run_ids(run_ids: list[str], rng: random.Random) -> dict[str, set[str]]:
    """Split one label's run IDs into deterministic 70/15/15 partitions."""
    shuffled = list(run_ids)
    rng.shuffle(shuffled)
    count = len(shuffled)
    train_count = max(1, round(count * 0.70))
    validation_count = max(1, round(count * 0.15))
    if train_count + validation_count >= count:
        validation_count = 1
        train_count = count - 2
    return {
        "train": set(shuffled[:train_count]),
        "validation": set(shuffled[train_count : train_count + validation_count]),
        "test": set(shuffled[train_count + validation_count :]),
    }


def write_csv(path: Path, columns: Iterable[str], records: Iterable[dict[str, str]]) -> None:
    """Write a deterministic UTF-8 CSV with the supplied columns."""
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def build_dataset(output_dir: Path, runs_per_class: int, rows_per_run: int, seed: int) -> dict[str, int]:
    """Create full metadata and Edge Impulse split CSVs, returning row counts."""
    if runs_per_class < 3:
        raise ValueError("runs_per_class must be at least 3 for train/validation/test splits")
    if rows_per_run < 1:
        raise ValueError("rows_per_run must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    generation_rng = random.Random(seed)
    split_rng = random.Random(seed + 1)
    records: list[dict[str, str]] = []
    run_ids_by_label: dict[str, list[str]] = {"healthy": [], "warning": [], "critical": []}
    scenarios_by_label: dict[str, list[Scenario]] = {
        label: [scenario for scenario in SCENARIOS if scenario.label == label]
        for label in run_ids_by_label
    }

    for label, scenarios in scenarios_by_label.items():
        for run_number in range(1, runs_per_class + 1):
            scenario = scenarios[(run_number - 1) % len(scenarios)]
            run_id = f"SYN-{label[:1].upper()}-{run_number:03d}"
            run_ids_by_label[label].append(run_id)
            records.extend(generate_run(scenario, run_id, rows_per_run, generation_rng))

    partitions: dict[str, set[str]] = {"train": set(), "validation": set(), "test": set()}
    for run_ids in run_ids_by_label.values():
        for partition, ids in split_run_ids(run_ids, split_rng).items():
            partitions[partition].update(ids)

    partition_by_run = {
        run_id: partition
        for partition, run_ids in partitions.items()
        for run_id in run_ids
    }
    for record in records:
        record["split"] = partition_by_run[record["run_id"]]

    write_csv(output_dir / "motorguard_synthetic_v2_runs.csv", RUN_COLUMNS, records)
    write_csv(output_dir / "motorguard_synthetic_v2_edge_impulse.csv", FEATURE_COLUMNS, records)
    counts: dict[str, int] = {"all": len(records)}
    for partition, ids in partitions.items():
        split_records = [record for record in records if record["run_id"] in ids]
        write_csv(output_dir / f"{partition}_edge_impulse.csv", FEATURE_COLUMNS, split_records)
        counts[partition] = len(split_records)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a bounded synthetic MotorGuard Edge Impulse dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/synthetic_v2"))
    parser.add_argument("--runs-per-class", type=int, default=30)
    parser.add_argument("--rows-per-run", type=int, default=200)
    parser.add_argument("--seed", type=int, default=775)
    args = parser.parse_args()
    counts = build_dataset(args.output_dir, args.runs_per_class, args.rows_per_run, args.seed)
    print(
        "Created synthetic-v2 dataset: "
        f"{counts['all']} rows (train={counts['train']}, validation={counts['validation']}, test={counts['test']})."
    )


if __name__ == "__main__":
    main()
