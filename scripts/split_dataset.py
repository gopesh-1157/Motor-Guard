#!/usr/bin/env python3
"""
MotorGuard — Run-Based Dataset Preprocessing & Stratified Splitter

Features:
- Trims startup transients (discards initial N seconds of each run).
- Groups data strictly by 'run_id' to prevent data leakage across Train / Val / Test.
- Stratifies run allocations across mechanical fault classes.
- Generates both:
  1) Standard 3-feature format (temperature_C, vibration_g, current_A, health_status)
  2) Rich 8-feature format (temp, current, 3-axis RMS, total RMS, peak, crest factor, health_status)

Usage:
    python scripts/split_dataset.py --input data/raw_runs/session_*.csv --outdir data/processed
"""

import os
import glob
import random
import argparse
from typing import Dict, List, Tuple
import pandas as pd
import numpy as np


LABEL_MAP_3CLASS = {
    "h": "healthy",
    "o": "warning",
    "i": "critical",
    "l": "warning",
    "healthy": "healthy",
    "overload": "warning",
    "imbalance": "critical",
    "loose_mount": "warning",
}

LABEL_MAP_4CLASS = {
    "h": "healthy",
    "o": "overload",
    "i": "imbalance",
    "l": "loose_mount",
    "healthy": "healthy",
    "overload": "overload",
    "imbalance": "imbalance",
    "loose_mount": "loose_mount",
}


def load_raw_sessions(input_paths: List[str]) -> pd.DataFrame:
    dfs = []
    for p in input_paths:
        for f in glob.glob(p):
            if os.path.isfile(f):
                try:
                    df = pd.read_csv(f)
                    df["source_file"] = os.path.basename(f)
                    dfs.append(df)
                    print(f"Loaded {len(df)} rows from {os.path.basename(f)}")
                except Exception as e:
                    print(f"Error reading {f}: {e}")
    if not dfs:
        raise ValueError(f"No valid CSV files found matching: {input_paths}")
    return pd.concat(dfs, ignore_index=True)


def trim_run_transients(df: pd.DataFrame, trim_seconds: float = 3.5) -> pd.DataFrame:
    """Discards initial transient seconds of each run to capture steady-state dynamics."""
    trimmed_dfs = []
    trim_ms = trim_seconds * 1000.0

    for run_id, run_group in df.groupby("run_id"):
        min_ts = run_group["timestamp_ms"].min()
        steady = run_group[run_group["timestamp_ms"] >= (min_ts + trim_ms)]
        if len(steady) > 0:
            trimmed_dfs.append(steady)
        else:
            print(f"Warning: Run {run_id} has insufficient duration after trimming {trim_seconds}s")

    if not trimmed_dfs:
        return df
    return pd.concat(trimmed_dfs, ignore_index=True)


def run_based_split(
    df: pd.DataFrame,
    train_pct: float = 0.70,
    val_pct: float = 0.15,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Partitions runs into Train / Val / Test strictly by run_id (zero row leakage)."""
    random.seed(seed)
    
    # Identify primary class per run
    run_classes: Dict[int, str] = {}
    for run_id, g in df.groupby("run_id"):
        primary_label = g["target_class"].mode()[0]
        run_classes[run_id] = primary_label

    # Group runs by label for stratified allocation
    class_to_runs: Dict[str, List[int]] = {}
    for run_id, label in run_classes.items():
        class_to_runs.setdefault(label, []).append(run_id)

    train_runs = []
    val_runs = []
    test_runs = []

    for label, runs in class_to_runs.items():
        random.shuffle(runs)
        n = len(runs)
        if n == 1:
            train_runs.extend(runs)
        elif n == 2:
            train_runs.append(runs[0])
            test_runs.append(runs[1])
        else:
            n_train = max(1, int(round(n * train_pct)))
            n_val = max(1, int(round(n * val_pct)))
            train_runs.extend(runs[:n_train])
            val_runs.extend(runs[n_train : n_train + n_val])
            test_runs.extend(runs[n_train + n_val :])

    train_df = df[df["run_id"].isin(train_runs)].copy()
    val_df = df[df["run_id"].isin(val_runs)].copy()
    test_df = df[df["run_id"].isin(test_runs)].copy()

    return train_df, val_df, test_df


def main():
    parser = argparse.ArgumentParser(description="MotorGuard Run-Based Dataset Splitter")
    parser.add_argument("--input", default="data/raw_runs/*.csv", help="Input CSV path or glob")
    parser.add_argument("--outdir", default="data/processed", help="Output directory")
    parser.add_argument("--trim", type=float, default=3.5, help="Seconds to trim from start of each run")
    parser.add_argument("--num_classes", type=int, choices=[3, 4], default=3, help="3-class or 4-class target")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    print("=" * 70)
    print("  MOTORGUARD RUN-BASED DATASET PREPROCESSING & STRATIFIED SPLIT")
    print(f"  Input Source:        {args.input}")
    print(f"  Transient Trim:      {args.trim} s per run")
    print(f"  Target Classes:      {args.num_classes} classes")
    print(f"  Output Directory:    {args.outdir}")
    print("=" * 70)

    try:
        df_raw = load_raw_sessions([args.input])
    except ValueError as e:
        print(f"\n{e}")
        print("Note: To collect real runs, execute 'python scripts/collect_dataset.py --port COMx'")
        return

    # Map target label
    label_map = LABEL_MAP_3CLASS if args.num_classes == 3 else LABEL_MAP_4CLASS
    df_raw["target_class"] = df_raw["label"].astype(str).str.lower().map(label_map)
    df_clean = df_raw.dropna(subset=["target_class"]).copy()

    # Trim start transients
    df_steady = trim_run_transients(df_clean, trim_seconds=args.trim)

    # Perform Run-Based Group Split
    train_df, val_df, test_df = run_based_split(df_steady, seed=args.seed)

    print("\n--- SPLIT SUMMARY (RUN-BASED ISOLATION) ---")
    print(f"Total Unique Runs:     {df_steady['run_id'].nunique()}")
    print(f"Train Runs:            {train_df['run_id'].nunique()} ({len(train_df)} rows)")
    print(f"Validation Runs:       {val_df['run_id'].nunique()} ({len(val_df)} rows)")
    print(f"Test Runs:             {test_df['run_id'].nunique()} ({len(test_df)} rows)")

    print("\nClass Distribution in Train Set:")
    print(train_df["target_class"].value_counts())
    print("\nClass Distribution in Test Set:")
    print(test_df["target_class"].value_counts())

    # Export 1: Standard 3-Feature Tabular Edge Impulse Format
    train_df_3col = train_df[["temp_c", "vib_rms_g", "current_a", "target_class"]].rename(
        columns={
            "temp_c": "temperature_C",
            "vib_rms_g": "vibration_g",
            "current_a": "current_A",
            "target_class": "health_status",
        }
    )
    test_df_3col = test_df[["temp_c", "vib_rms_g", "current_a", "target_class"]].rename(
        columns={
            "temp_c": "temperature_C",
            "vib_rms_g": "vibration_g",
            "current_a": "current_A",
            "target_class": "health_status",
        }
    )
    val_df_3col = val_df[["temp_c", "vib_rms_g", "current_a", "target_class"]].rename(
        columns={
            "temp_c": "temperature_C",
            "vib_rms_g": "vibration_g",
            "current_a": "current_A",
            "target_class": "health_status",
        }
    )

    p_train_3col = os.path.join(args.outdir, "train_3features.csv")
    p_val_3col = os.path.join(args.outdir, "val_3features.csv")
    p_test_3col = os.path.join(args.outdir, "test_3features.csv")

    train_df_3col.to_csv(p_train_3col, index=False)
    val_df_3col.to_csv(p_val_3col, index=False)
    test_df_3col.to_csv(p_test_3col, index=False)

    # Export 2: Rich 8-Feature Windowed Format
    rich_cols = [
        "temp_c",
        "current_a",
        "vib_x_rms",
        "vib_y_rms",
        "vib_z_rms",
        "vib_rms_g",
        "vib_peak_g",
        "crest_factor",
        "target_class",
    ]
    if all(c in train_df.columns for c in rich_cols):
        p_train_rich = os.path.join(args.outdir, "train_rich_features.csv")
        p_val_rich = os.path.join(args.outdir, "val_rich_features.csv")
        p_test_rich = os.path.join(args.outdir, "test_rich_features.csv")

        train_df[rich_cols].rename(columns={"target_class": "health_status"}).to_csv(p_train_rich, index=False)
        val_df[rich_cols].rename(columns={"target_class": "health_status"}).to_csv(p_val_rich, index=False)
        test_df[rich_cols].rename(columns={"target_class": "health_status"}).to_csv(p_test_rich, index=False)
        print(f"\n[SAVED] Rich 8-feature datasets saved to: {args.outdir}")

    print(f"[SAVED] Standard 3-feature datasets saved to: {args.outdir}")
    print("Files ready for direct upload to Edge Impulse!")


if __name__ == "__main__":
    main()
