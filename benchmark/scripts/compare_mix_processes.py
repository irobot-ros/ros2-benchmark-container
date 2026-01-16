#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Compare "Mixed-Process" Benchmark Scenarios.

This script analyzes and compares the performance of two different communication
scenarios involving a mix of intra-process and inter-process communication:

1.  **Single Publisher, Multiple Topics**: A single publisher node sends messages
    on multiple distinct topics to three subscribers:
    - One in the same process (intra-process).
    - One in a different process on the same host (inter-process).
    - One on a remote host.

2.  **Multiple Publishers, Multiple Topics**: Three separate publisher nodes are used,
    each dedicated to one of the subscribers mentioned above.

The script compares these two scenarios based on two key metrics:
- **Latency**: It performs a t-test to determine if there is a statistically
  significant difference in message latency.
- **CPU Usage**: It performs a z-test to check for significant differences in
  CPU consumption.

The results of these comparisons are saved to CSV files.
"""

import argparse
import ast
import csv
import os
import re
import sys
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from scipy import stats
from tabulate import tabulate

from utils import perform_z_test

csv.field_size_limit(sys.maxsize)


def read_csv(file_path: str, delimiter: str = ";") -> List[List[str]]:
    """
    Reads a CSV file and returns its content as a list of rows, skipping the header.

    Args:
        file_path: The path to the CSV file.
        delimiter: The delimiter used in the CSV file.

    Returns:
        A list of rows, where each row is a list of string values.
    """
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        sys.exit(1)

    with open(file_path, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter=delimiter)
        next(reader)  # Skip the header
        return list(reader)


def print_comparison_table(rows: List[List[Any]], metric_name: str):
    """
    Prints a formatted table comparing single vs. multiple publisher scenarios.

    Args:
        rows: A list of rows, with each row containing the comparison data for a middleware.
        metric_name: The name of the metric being displayed (e.g., "Latency", "CPU Usage").
    """
    headers = [
        "Middleware",
        f"Multiple Publishers ({metric_name})",
        "",
        f"Single Publisher ({metric_name})",
        "",
        "Statistical Test",
    ]
    sub_headers = ["", "Std Dev", "Average", "Std Dev", "Average", "p-value"]
    print(
        tabulate([headers] + [sub_headers] + rows, headers="firstrow", tablefmt="grid")
    )


def build_latency_table(results: Dict[str, Any], mode: str) -> List[List[Any]]:
    """
    Builds a table of latency metrics, comparing single vs. multiple publisher results.

    Args:
        results: A dictionary containing latency results grouped by middleware.
        mode: The latency mode, either 'pub' (for publisher) or 'sub' (for subscriber).

    Returns:
        A list of rows formatted for the comparison table.
    """
    table = []

    for middleware, topic_data in results.items():
        multi_pub_data = topic_data.get(f"multi_{mode}", [])
        single_pub_data = topic_data.get(f"single_{mode}", [])

        p_value = None
        if single_pub_data and multi_pub_data:
            # Perform a t-test to see if the means are significantly different.
            # 'less' alternative: tests if mean of multi_pub_data is less than single_pub_data.
            t_test_result = stats.ttest_ind(
                multi_pub_data, single_pub_data, alternative="less", equal_var=False
            )
            p_value = t_test_result.pvalue

        row = [
            f"{mode.capitalize()} Latency/{middleware}",
            np.std(multi_pub_data) if multi_pub_data else "N/A",
            np.mean(multi_pub_data) if multi_pub_data else "N/A",
            np.std(single_pub_data) if single_pub_data else "N/A",
            np.mean(single_pub_data) if single_pub_data else "N/A",
            p_value if p_value is not None else "N/A",
        ]
        table.append(row)
    return table


def compare_latency(
    results_file: str, show_console: bool = False
) -> Dict[str, List[List[Any]]]:
    """
    Parses latency data and compares single-publisher vs. multi-publisher scenarios.

    Args:
        results_file: The path to the CSV file containing all latency results.
        show_console: If True, prints the comparison tables to the console.

    Returns:
        A dictionary containing the formatted table rows for publisher and subscriber latency.
    """
    df = pd.read_csv(results_file, delimiter=";")

    # Group results by middleware and by scenario (single_topic vs. multi_topic)
    results = {}

    for _, row in df.iterrows():
        path = row["Directory"]
        if "mix_process" not in path:
            continue

        pub_lat = ast.literal_eval(row["PubDur"]) if pd.notna(row["PubDur"]) else []
        pub_lat = ast.literal_eval(row["SubLat"]) if pd.notna(row["SubLat"]) else []

        match = re.search(r"pub-sub_mix_process_(single|multi)_topic/([^/]+)/", path)
        if match:
            topic_type, middleware = match.groups()

            if middleware not in results:
                results[middleware] = {}

            # Aggregate latencies for each scenario type and middleware
            for key, latencies in [
                (f"{topic_type}_pub", pub_lat),
                (f"{topic_type}_sub", pub_lat),
            ]:
                if key not in results[middleware]:
                    results[middleware][key] = []
                results[middleware][key].extend(latencies)

    # Build formatted tables for publisher and subscriber latency
    pub_table = build_latency_table(results, "pub")
    sub_table = build_latency_table(results, "sub")

    if show_console:
        print("\nPublisher Latency Comparison:")
        print_comparison_table(pub_table, "Latency (ns)")
        print("\nSubscriber Latency Comparison:")
        print_comparison_table(sub_table, "Latency (ns)")

    return {"publishers": pub_table, "subscriber": sub_table}


def build_cpu_usage_table(results: Dict[str, Any]) -> List[List[Any]]:
    """
    Builds a table of CPU usage metrics, comparing single vs. multiple publisher results.

    Args:
        results: A dictionary containing CPU usage data grouped by middleware.

    Returns:
        A list of rows formatted for the comparison table.
    """
    table = []

    for middleware, topic_data in results.items():
        # Data from the "single publisher, multiple topics" scenario
        single_pub_data = topic_data.get("single", [])
        # Data from the "multiple publishers, multiple topics" scenario
        multi_pub_data = topic_data.get("multi", [])

        if not single_pub_data or not multi_pub_data:
            continue

        # Perform a z-test to check for a statistically significant difference
        p_left, mean_multi, mean_single, std_dev_multi, std_dev_single = perform_z_test(
            multi_pub_data, single_pub_data, middleware
        )

        row = [
            middleware,
            std_dev_multi,
            mean_multi,
            std_dev_single,
            mean_single,
            p_left if p_left is not None else "N/A",
        ]
        table.append(row)
    return table


def compare_cpu_usage(
    results_file: str, show_console: bool = False
) -> Dict[str, List[List[Any]]]:
    """
    Parses CPU usage data and compares single-publisher vs. multi-publisher scenarios.

    Args:
        results_file: The path to the CSV file containing all CPU usage results.
        show_console: If True, prints the comparison table to the console.

    Returns:
        A dictionary containing the formatted table rows for CPU usage.
    """
    df = pd.read_csv(results_file, delimiter=";")

    # Group results by middleware and scenario type
    results = {}

    for _, row in df.iterrows():
        path = row["Directory"]
        if "mix_process" not in path:
            continue

        cpu_usage = ast.literal_eval(row["CPU"])[1:] if pd.notna(row["CPU"]) else []
        if not isinstance(cpu_usage, list):
            raise ValueError("CPU usage values must be a list")

        match = re.search(r"(single|multi)_topic/([^/]+)/", path)
        if match:
            scenario_type, middleware = match.groups()  # 'single' or 'multi'

            if middleware not in results:
                results[middleware] = {"single": [], "multi": []}

            # The CPU usage is a list of values over time.
            # We sum the values from different runs of the same scenario.
            if not results[middleware][scenario_type]:
                results[middleware][scenario_type] = [0] * len(cpu_usage)
            results[middleware][scenario_type] = [
                sum(x) for x in zip(results[middleware][scenario_type], cpu_usage)
            ]

    # Build the formatted table for CPU usage
    cpu_usage_table = build_cpu_usage_table(results)

    if show_console:
        print("\nCPU Usage Comparison:")
        print_comparison_table(cpu_usage_table, "CPU %")

    return {"cpu_usage": cpu_usage_table}


def write_results_to_csv(data: Dict[str, List[List[Any]]], output_file_path: str):
    """
    Writes the summarized comparison results to a CSV file.

    Args:
        data: A dictionary where keys are test cases (e.g., 'publishers') and
              values are the formatted data rows.
        output_file_path: The path for the output CSV file.
    """
    metric = os.path.basename(output_file_path).removesuffix(".csv").replace("_", " ")
    print(f"✅ Writing {metric} results to {output_file_path}")

    with open(output_file_path, mode="w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "test_case",
                "multi_pub_std_dev",
                "multi_pub_mean",
                "single_pub_std_dev",
                "single_pub_mean",
                "p_value",
            ]
        )
        for _, rows in data.items():
            for row in rows:
                writer.writerow(row)


def main():
    """Main function to parse arguments and run the comparison."""
    parser = argparse.ArgumentParser(
        description="""
Compares performance metrics (Latency and CPU Usage) between two 'mixed-process'
scenarios: a single publisher with multiple topics vs. multiple publishers
with multiple topics. The script generates CSV files with the statistical
comparison and can display summary tables in the console.
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "results_directory",
        type=str,
        help="Path to the main results directory. This script will look for the "
        "'parsed_results' subdirectory within this path.",
    )
    parser.add_argument(
        "--show-console",
        action="store_true",
        help="Print summary tables of the comparison results to the console.",
    )
    args = parser.parse_args()

    if not os.path.isdir(args.results_directory):
        print(f"Error: '{args.results_directory}' is not a valid directory.")
        sys.exit(1)

    parsed_results_dir = os.path.join(args.results_directory, "parsed_results")
    os.makedirs(parsed_results_dir, exist_ok=True)

    # --- Latency Comparison ---
    latency_csv_path = os.path.join(parsed_results_dir, "all_latency.csv")
    latency_comparison_results = compare_latency(latency_csv_path, args.show_console)

    output_latency_csv = os.path.join(
        parsed_results_dir, "latency_comparison_mix_process.csv"
    )
    write_results_to_csv(latency_comparison_results, output_latency_csv)

    # --- CPU Usage Comparison ---
    cpu_csv_path = os.path.join(parsed_results_dir, "all_cpu_usage.csv")
    cpu_comparison_results = compare_cpu_usage(cpu_csv_path, args.show_console)

    output_cpu_csv = os.path.join(
        parsed_results_dir, "cpu_usage_comparison_mix_process.csv"
    )
    write_results_to_csv(cpu_comparison_results, output_cpu_csv)


if __name__ == "__main__":
    main()
