#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze Resource Metrics from Long-Duration Benchmark Tests.

This script is designed to process resource usage data (`cpu_perc` and `rss_KB`)
from long-duration benchmark runs. The primary goal is to visualize the stability
of CPU and RAM usage over time to identify potential issues like memory leaks or
performance degradation in extended-run scenarios.

The script performs the following tasks:
1.  **Data Extraction**: It finds all `resources.txt` files within a given results
    directory that correspond to long-duration tests (i.e., their path contains
    '_long' or '_scalability').
2.  **Data Processing**: For each test, it reads the specified metric data over time.
    To focus on the steady-state performance, it trims the first and last 30
    seconds of data to exclude startup and shutdown noise.
3.  **Binning**: The trimmed data is then binned into 10-second intervals, and the
    mean of each bin is calculated. This helps to smooth out short-term fluctuations
    and reveal the underlying trend.
4.  **Plotting**: It generates plots showing the binned resource usage over time
    for different RMW implementations, allowing for easy comparison of their
    long-term stability.
5.  **Output**: The generated plots are saved as PNG files in the `parsed_results`
    directory.
"""

import argparse
import csv
import os
import sys
from collections import defaultdict
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Append the parent directory to sys.path to allow imports from the 'utils' module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import get_sorted_files_by_mtime

csv.field_size_limit(sys.maxsize)

# Labels for the plots based on the metric being analyzed
PLOT_LABELS = {
    "cpu_perc": ("CPU Usage [%]", "CPU Usage"),
    "rss_KB": ("RAM Usage [MB]", "RAM Usage"),
}


def process_directory(
    directory: str, ros_interface: str, metric: str
) -> Dict[str, List[float]]:
    """
    Parses `resources.txt` files to extract time-series data for a specific metric.

    Args:
        directory: The root directory to search for result files.
        ros_interface: The ROS interface to filter by (e.g., 'pub-sub', 'cli-srv').
        metric: The resource metric to extract (e.g., 'cpu_perc', 'rss_KB').

    Returns:
        A dictionary where keys are middleware names and values are lists of the
        metric's value over time.
    """
    processed_results = defaultdict(list)
    sorted_files = get_sorted_files_by_mtime(directory, "resources.txt")

    for file_path in sorted_files:
        # Process only files that match the ROS interface and are from a long test
        if (
            file_path.endswith("resources.txt")
            and ros_interface in file_path
            and any(x in file_path for x in ["_long", "_scalability"])
        ):
            root = os.path.dirname(file_path)  # Get root directory for cleaned path
            # Remove leading "./" from the directory path
            clean_root = root[2:] if root.startswith("./") else root
            path = clean_root.split("/")
            middleware = path[-1] if "single_process" in root else path[-2]

            try:
                resources_df = pd.read_csv(file_path)
                # Extract the metric column, convert to float, and skip the first summary row
                metric_data = resources_df[metric].astype(float).to_list()[1:]
                processed_results[middleware] = metric_data
            except (FileNotFoundError, KeyError, ValueError) as e:
                print(f"Warning: Could not process file {file_path}. Error: {e}")
                continue

    return processed_results


def plot_metrics(
    processed_results: Dict[str, List[float]],
    ros_interface: str,
    metric: str,
    output_file: str,
    show_plot: bool,
):
    """
    Generates and saves a plot of a resource metric over time for long-duration tests.

    Args:
        processed_results: A dictionary containing the processed time-series data.
        ros_interface: The ROS interface type being plotted (e.g., 'pub-sub').
        metric: The specific resource metric being plotted (e.g., 'cpu_perc').
        output_file: The path prefix for the saved plot image.
        show_plot: If True, displays the plot interactively.
    """
    plt.figure(figsize=(10, 5))

    for middleware, data in processed_results.items():
        # A long test should last for at least 60 seconds
        if len(data) < 60:
            print(
                f"Warning: Test duration for '{middleware}' ({len(data)}s) is too short for long-test analysis. Skipping plot."
            )
            continue

        # Trim the first 30s (initialization) and last 30s (shutdown) to focus on steady state
        init_time = 30
        values = np.array(data)
        trimmed_values = values[init_time + 1 : -30]

        # Bin the data into 10-second averages to smooth out noise
        num_bins = len(trimmed_values) // 10
        if num_bins == 0:
            continue
        bin_means = [
            np.mean(trimmed_values[i * 10 : (i + 1) * 10]) for i in range(num_bins)
        ]
        # X-axis represents the center time of each bin
        bin_centers = np.arange(init_time, init_time + num_bins * 10, 10)

        # Convert RAM from KB to MB if needed
        if metric == "rss_KB":
            bin_means = np.array(bin_means) / 1024

        plt.plot(bin_centers, bin_means, label=middleware)

    # Labels, title and legend
    ylabel, title = PLOT_LABELS.get(metric)
    plt.xlabel("Time [s]")
    plt.ylabel(ylabel)
    plt.title(f"{title} ({ros_interface})")
    plt.legend(title="Middleware", loc="center right", bbox_to_anchor=(1.25, 0.5))
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()

    # Save the plot to a file
    metric_output_file = f"{output_file}_{ros_interface}_long_test.png"
    plt.savefig(metric_output_file)
    print(f"✅ Plot saved to: {metric_output_file}")

    if show_plot:
        plt.show()

    plt.close()


def main():
    """Main function to parse arguments and trigger the long-duration metrics analysis."""
    parser = argparse.ArgumentParser(
        description="""
Analyze resource usage (CPU, RAM) from long-duration benchmark tests.
This script processes `resources.txt` files, trims and bins the data to show
steady-state performance, and generates plots to visualize stability over time.
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "results_directory",
        type=str,
        help="Path to the main results directory containing the raw benchmark data.",
    )
    parser.add_argument(
        "--show-plot",
        action="store_true",
        help="Display the generated plots interactively.",
    )
    args = parser.parse_args()

    results_directory = args.results_directory
    if not os.path.isdir(results_directory):
        print(f"Error: '{results_directory}' is not a valid directory.")
        sys.exit(1)

    parsed_results_directory = os.path.join(results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    # Iterate through each ROS interface and resource metric to generate plots
    for ros_interface in ["pub-sub", "cli-srv", "actions"]:
        for metric in ["cpu_perc", "rss_KB"]:
            print(f"\nProcessing '{metric}' for '{ros_interface}' long tests...")
            metric_usage_results = process_directory(
                results_directory, ros_interface, metric
            )

            if not metric_usage_results:
                print(
                    f"Info: No valid data found for '{metric}' in '{ros_interface}' long tests. Skipping."
                )
                continue

            output_prefix = os.path.join(parsed_results_directory, metric)
            plot_metrics(
                metric_usage_results,
                ros_interface,
                metric,
                output_prefix,
                args.show_plot,
            )


if __name__ == "__main__":
    main()
