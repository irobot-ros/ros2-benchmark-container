#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Compare Benchmark Metrics from Two Different Result Sets.

This script takes two benchmark result directories as input, reads the
`average_metrics.csv` file from each, and computes the percentage change
for key metrics (CPU, RSS, VSZ).

The primary use case is to compare the performance impact of a change by
running the benchmarks before and after the change and then using this script
to quantify the difference.

The script generates a `comparison_metrics.csv` file with the percentage
differences for all test cases. Additionally, it can display in the console
only the test cases where the change exceeds a certain percentage threshold,
making it easy to spot significant performance regressions or improvements.
"""

import sys
import os
import pandas as pd
from typing import Union


def print_help():
    """Prints the detailed usage and help information for the script."""
    print(
        """
Usage:
    python3 compare_all_metrics.py <results_dir1> <results_dir2> [--threshold <percentage>]

Description:
    Compares the `average_metrics.csv` from two benchmark result directories.
    It calculates the percentage change for CPU, RSS, and VSZ metrics between
    the two result sets and saves the comparison to `comparison_metrics.csv`.

Arguments:
    <results_dir1>       Path to the first results directory (baseline).
    <results_dir2>       Path to the second results directory (to compare against baseline).
    --threshold <number> Optional percentage threshold. If provided, the script will
                         print the metrics for test cases where the percentage change
                         is greater than the threshold or less than its negative.

Example:
    # Compare results from two directories
    python3 compare_all_metrics.py /path/to/results_before /path/to/results_after

    # Compare and show only differences greater than 10%
    python3 compare_all_metrics.py results_A results_B --threshold 10

Output:
    - A CSV file named 'comparison_metrics.csv' in the current directory,
      containing the percentage differences for all metrics.
    - Console output of metrics that exceed the specified threshold, including
      the original values for context.
"""
    )
    sys.exit(0)


def calculate_percentage_change(value1: float, value2: float) -> Union[float, str]:
    """
    Calculates the percentage change from value1 to value2.

    Args:
        value1: The baseline value.
        value2: The new value.

    Returns:
        The percentage change as a float, or a string ('Infinity' or '0')
        if the baseline value is zero.
    """
    if value1 == 0:
        return "Infinity" if value2 != 0 else "0"
    return ((value2 - value1) / value1) * 100


def main():
    """Main function to run the comparison."""
    # Handle help flag
    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()

    # Check command-line arguments
    if len(sys.argv) < 3 or len(sys.argv) > 5:
        print("Error: Invalid arguments.")
        print("Use --help or -h for usage instructions.")
        sys.exit(1)

    results_dir1 = sys.argv[1]
    results_dir2 = sys.argv[2]

    # Parse the optional threshold argument
    threshold = None
    if "--threshold" in sys.argv:
        try:
            threshold_index = sys.argv.index("--threshold") + 1
            threshold = float(sys.argv[threshold_index])
        except (IndexError, ValueError):
            print(
                "Error: Invalid threshold value. Provide a valid number after --threshold."
            )
            sys.exit(1)

    # Construct paths to the metrics files
    metrics_file1 = os.path.join(results_dir1, "average_metrics.csv")
    metrics_file2 = os.path.join(results_dir2, "average_metrics.csv")

    if not os.path.exists(metrics_file1):
        print(f"Error: average_metrics.csv not found in '{results_dir1}'")
        sys.exit(1)
    if not os.path.exists(metrics_file2):
        print(f"Error: average_metrics.csv not found in '{results_dir2}'")
        sys.exit(1)

    # Load the data from the CSV files
    df1 = pd.read_csv(metrics_file1)
    df2 = pd.read_csv(metrics_file2)

    # Merge the two dataframes on the 'Directory' column, which identifies the test case
    merged_df = pd.merge(df1, df2, on="Directory", suffixes=("_1", "_2"))

    # Calculate percentage change for each metric
    merged_df["Average_CPU %"] = merged_df.apply(
        lambda row: round(
            calculate_percentage_change(row["Average_CPU1"], row["Average_CPU2"]), 2
        ),
        axis=1,
    )
    merged_df["Average_RSS_MB %"] = merged_df.apply(
        lambda row: round(
            calculate_percentage_change(row["Average_RSS_MB1"], row["Average_RSS_MB2"]),
            2,
        ),
        axis=1,
    )
    merged_df["Average_VSZ_MB %"] = merged_df.apply(
        lambda row: round(
            calculate_percentage_change(row["Average_VSZ_MB1"], row["Average_VSZ_MB2"]),
            2,
        ),
        axis=1,
    )

    # Create the final result DataFrame with the desired columns
    result_df = merged_df[
        ["Directory", "Average_CPU %", "Average_RSS_MB %", "Average_VSZ_MB %"]
    ].copy()

    # Save the full comparison to a CSV file
    output_file = "comparison_metrics.csv"
    result_df.to_csv(output_file, index=False)
    print(f"✅ Comparison completed. Full results saved to '{output_file}'")

    # If a threshold is provided, print metrics with differences exceeding it
    if threshold is not None:
        print(
            f"\n📊 Metrics with percentage differences exceeding {threshold}% or below {-threshold}%:\n"
        )
        # Filter the merged dataframe to find rows exceeding the threshold for any metric
        filtered_df = merged_df[
            (merged_df["Average_CPU %"].abs() > threshold)
            | (merged_df["Average_RSS_MB %"].abs() > threshold)
            | (merged_df["Average_VSZ_MB %"].abs() > threshold)
        ]

        if not filtered_df.empty:
            for _, row in filtered_df.iterrows():
                print(f"Directory: {row['Directory']}")
                if abs(row["Average_CPU %"]) > threshold:
                    print(
                        f"  - Average_CPU %: {row['Average_CPU %']}% (Before: {row['Average_CPU1']}, After: {row['Average_CPU2']})"
                    )
                if abs(row["Average_RSS_MB %"]) > threshold:
                    print(
                        f"  - Average_RSS_MB %: {row['Average_RSS_MB %']}% (Before: {row['Average_RSS_MB1']}, After: {row['Average_RSS_MB2']})"
                    )
                if abs(row["Average_VSZ_MB %"]) > threshold:
                    print(
                        f"  - Average_VSZ_MB %: {row['Average_VSZ_MB %']}% (Before: {row['Average_VSZ_MB1']}, After: {row['Average_VSZ_MB2']})"
                    )
                print("-" * 50)
        else:
            print("✅ No metrics exceeded the specified threshold.")


if __name__ == "__main__":
    main()
