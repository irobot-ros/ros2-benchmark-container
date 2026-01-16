#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Compare Single-Process vs. Multi-Process Benchmark Performance.

This script analyzes and compares the performance of single-process versus
multi-process applications using data from benchmark runs. It focuses on
pub-sub communication patterns across different payload sizes (10b, 100kb, 1mb, 4mb).

The script performs the following comparisons:
- **Latency**: It uses a t-test to determine if there is a statistically
  significant difference in message latency (PubDur and SubLat) between
  single-process and multi-process setups.
- **CPU Usage**: It uses a z-test to check for significant differences in
  CPU consumption. For multi-process tests, the CPU usage of the publisher
  and subscriber nodes is summed to allow for a fair comparison with the
  single-process equivalent.

The results of these comparisons are saved to `latency_comparison.csv` and
`cpu_usage_comparison.csv`.
"""

import argparse
import ast
import csv
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats
from tabulate import tabulate

from utils import perform_z_test

csv.field_size_limit(sys.maxsize)

PAYLOADS = ["10b", "100kb", "1mb", "4mb"]
PROCESSES = ["single_process", "multi_process"]
EXCLUDED_TESTS = [
    "ipc_on",
    "long",
    "mix_process",
    "multiple_topics",
    "idle",
    "scalability",
]
INCLUDED_TESTS = ["pub-sub"]


def read_csv(file_path: str, delimiter: str = ";") -> list[list[str]]:
    """
    Reads a CSV file and returns its content as a list of rows.

    Args:
        file_path: The path to the CSV file.
        delimiter: The delimiter used in the CSV file. Defaults to ";".

    Returns:
        A list of rows, where each row is a list of string values from the CSV, excluding the header.
    """
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        sys.exit(1)

    with open(file_path, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file, delimiter=delimiter)
        next(reader)  # Skip the header
        return list(reader)


def extract_process_payload(directory: str) -> tuple[str, str]:
    """
    Extracts the process type and payload size from the directory name.

    Args:
        directory: The directory name containing the process type and payload size.

    Returns:
        A tuple containing the type of process and the payload size found in the directory name.
    """
    process_type = next(
        (process for process in PROCESSES if process in directory), None
    )
    payload = next((payload for payload in PAYLOADS if payload in directory), None)

    if not process_type:
        raise ValueError(f"Process type not found in directory: {directory}")
    if not payload:
        raise ValueError(f"Payload not found in directory: {directory}")

    return process_type, payload


def print_table(title: str, data: list[list]):
    """
    Prints a comparison table with a title.

    Args:
        title: The title of the table.
        data: List of rows to display.
    """
    headers = [
        "Payload",
        "Multi - Std Dev",
        "Multi - Mean",
        "Single - Std Dev",
        "Single - Mean",
        "P-Value",
    ]
    print(f"\n{title}")
    print(tabulate(data, headers=headers, tablefmt="grid"))
    print("\n")


def should_process_directory(directory: str) -> bool:
    """
    Determine if a directory should be processed based on an exclusion test list.

    Args:
        directory: The directory path.

    Returns:
        True if the directory should be processed, False otherwise.
    """
    if any(test not in directory for test in INCLUDED_TESTS) or any(
        test in directory for test in EXCLUDED_TESTS
    ):
        return False
    return True


def compare_latency(results_file: str, show_console: bool = False) -> dict:
    """
    Compare latency results by calculating the percentage change between different values.

    Args:
        results_file: The directory containing the latency result files.
        show_console: Whether to print the comparison results to the console. Defaults to False.

    Returns:
        A dictionary containing the mean and standard deviation of each process and the comparison results.
    """
    rows = read_csv(results_file)

    grouped_data = {
        "PubDur": defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None))),
        "SubLat": defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None))),
    }

    for row in rows:
        directory, pubdur, sublat = row[0], row[1], row[2]
        middleware = directory.split("/")[5]

        # Skip processing for directories that contain any excluded test types
        if not should_process_directory(directory):
            continue

        process_type, payload = extract_process_payload(directory)
        # Determine if single or multi process
        process_type = next(
            (process for process in PROCESSES if process in directory), None
        )

        # Skip the directory if the process type is not single or multi process
        if process_type is None:
            continue

        # If it's single-process, store both values directly
        if process_type == "single_process":
            grouped_data["PubDur"][middleware][payload][process_type] = pubdur
            grouped_data["SubLat"][middleware][payload][process_type] = sublat

        # If it's multi-process, determine if it's PubDur or SubLat
        else:
            topic_type = directory.split("/")[-1]
            if "pub" in topic_type:
                grouped_data["PubDur"][middleware][payload][process_type] = pubdur
            elif "sub" in topic_type:
                grouped_data["SubLat"][middleware][payload][process_type] = sublat

    # Calculate the percentage change for each metric
    results = defaultdict(dict)
    for topic, middleware in grouped_data.items():
        for rmw, data in middleware.items():
            results_data = []
            for payload, processes in data.items():
                multi_process_data = ast.literal_eval(processes["multi_process"])
                single_process_data = ast.literal_eval(processes["single_process"])
                pvalue = None

                # Perform a t-test to determine if the multi-process latency is less than the single-process latency
                t_test_result = stats.ttest_ind(
                    multi_process_data,
                    single_process_data,
                    alternative="less",
                    equal_var=False,
                )
                pvalue = t_test_result.pvalue

                results_data.append(
                    [
                        payload,
                        round(float(np.std(multi_process_data)), 3),
                        round(float(np.mean(multi_process_data)), 3),
                        round(float(np.std(single_process_data)), 3),
                        round(float(np.mean(single_process_data)), 3),
                        float(pvalue) if pvalue is not None else "N/A",
                    ]
                )
                results[f"{topic}/{rmw}"] = results_data

            if show_console:
                print_table(f"Latency Comparison - {topic} - {rmw}", results_data)

    return results


def compare_cpu_usage(results_file: str, show_console: bool = False) -> dict:
    """
    Compare CPU usage results by calculating the percentage change between different values.

    Args:
        results_file: The directory containing the CPU usage result files.
        show_console: Whether to print the comparison results to the console. Defaults to False.

    Returns:
        A dictionary containing the mean and standard deviation of each process and the comparison results.
    """
    rows = read_csv(results_file)

    grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: None)))

    for row in rows:
        directory, cpu_usage = row[0], row[1]
        middleware = directory.split("/")[5]

        # Skip processing for directories that contain any excluded test types
        if not should_process_directory(directory):
            continue

        # Determine if the process tpye is single or multi process
        process_type = next(
            (process for process in PROCESSES if process in directory), None
        )
        # Skip the directory if the process type is not single or multi process
        if process_type is None:
            continue

        process_type, payload = extract_process_payload(directory)

        if process_type in grouped_data[middleware][payload]:
            # Sum element-wise if an entry already exists
            grouped_data[middleware][payload][process_type] = [
                a + b
                for a, b in zip(
                    grouped_data[middleware][payload][process_type],
                    ast.literal_eval(cpu_usage),
                )
            ]
        else:
            # Store the first array if no previous entry
            grouped_data[middleware][payload][process_type] = ast.literal_eval(
                cpu_usage
            )

    # Calculate the percentage change for each metric
    results = defaultdict(dict)
    for rmw, data in grouped_data.items():
        results_data = []
        for payload, processes in data.items():
            multi_process_data = processes["multi_process"]
            single_process_data = processes["single_process"]

            p_left, mean_x1, mean_x2, std_dev_x1, std_dev_x2 = perform_z_test(
                multi_process_data, single_process_data, middleware
            )

            results_data.append(
                [
                    payload,
                    round(float(std_dev_x1), 3),
                    round(float(mean_x1), 3),
                    round(float(std_dev_x2), 3),
                    round(float(mean_x2), 3),
                    float(p_left) if p_left is not None else "N/A",
                ]
            )
        results[f"{rmw}"] = results_data

        if show_console:
            print_table(f"CPU Usage Comparison - {rmw}", results_data)

    return results


def generate_comparison_csv(data: dict, output_file_path: str):
    """
    Generate a CSV file containing the comparison results.

    Args:
        data: The comparison results.
        output_file_path: The path where the CSV file will be saved.
    """
    metric = os.path.basename(output_file_path).removesuffix(".csv").replace("_", " ")
    print(f"Writing {metric} results to {output_file_path}")

    # Write to CSV
    with open(output_file_path, mode="w", newline="") as comparison_csv:
        header = "test_case;payload;multi_std_dev;multi_mean;single_std_dev;single_mean;p_value"
        comparison_csv.write(f"{header}\n")

        for key, values in data.items():
            for value in values:
                comparison_csv.write(f"{key};" + ";".join(map(str, value)) + "\n")


def main():
    """
    Compare single-process and multi-process benchmark performance.

    This script analyzes benchmark data to compare the performance of
    single-process versus multi-process applications. It processes latency and
    CPU usage data from a specified results directory, performs statistical
    comparisons (t-test for latency, z-test for CPU), and generates CSV
    reports with the findings.
    """
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="""
This script processes all 'latency_all.txt' files in the specified directory (and its subdirectories),
calculates average latency metrics (for publishers, subscriptions, clients, services, action clients, and
action servers), and generates a CSV file (average_latency.csv) with these metrics.
If the --show-plot flag is provided, it also generates plots for the metrics.                                 
"""
    )

    # Add a required positional argument for the results directory path
    parser.add_argument(
        "results_directory",
        type=str,
        help="The path where the results files will be searched and the output will be saved.",
    )

    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Show the generated latency plots (optional).",
    )

    parser.add_argument(
        "--show-console",
        action="store_true",
        help="Show the generated latency data in the console (optional).",
    )

    # Parse the arguments
    args = parser.parse_args()

    if not os.path.isdir(args.results_directory):
        print(f"Error: '{args.results_directory}' is not a valid directory.")
        sys.exit(1)

    parsed_results_directory = os.path.join(args.results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    # Compare latency results for multi-process vs single-process
    latency_comparison_results = compare_latency(
        os.path.join(parsed_results_directory, "all_latency.csv"), args.show_console
    )

    # Generate CSV for the comparison results
    csv_latency_file = os.path.join(parsed_results_directory, "latency_comparison.csv")
    generate_comparison_csv(latency_comparison_results, csv_latency_file)

    # Compare CPU usage results for multi-process vs single-process
    cpu_comparison_results = compare_cpu_usage(
        os.path.join(parsed_results_directory, "all_cpu_usage.csv"), args.show_console
    )

    # Generate CSV for the comparison results
    csv_cpu_usage_file = os.path.join(
        parsed_results_directory, "cpu_usage_comparison.csv"
    )
    generate_comparison_csv(cpu_comparison_results, csv_cpu_usage_file)


if __name__ == "__main__":
    main()
