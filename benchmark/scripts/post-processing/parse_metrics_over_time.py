#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze CPU Metrics Over Time for Specific Scenarios.

This script processes CPU usage data from `resources.txt` files for specific
benchmark scenarios, namely 'multiple_topics' and 'idle' tests. Its primary
purpose is to visualize how CPU usage evolves over the duration of these tests,
especially for comparing performance between a local setup and one involving a
remote host.

The script performs the following tasks:
1.  **Data Extraction**: It finds all `resources.txt` files within a results
    directory that correspond to the included test types.
2.  **Grouping**: It groups the extracted CPU percentage data by the RMW middleware
    and by the host mode ('local' or 'remote').
3.  **Plotting**: For each host mode, it generates a plot showing CPU usage over
    time for all tested middlewares, allowing for direct comparison.
4.  **Output**: The generated plots are saved as PNG files (e.g.,
    `cpu_usage_over_time_multiple_topics_local_test.png`) in the `parsed_results`
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

# Defines the specific test scenarios this script is interested in
INCLUDED_TESTS = ["multiple_topics", "idle"]


def process_directory(directory: str) -> Dict[str, Dict[str, List[float]]]:
    """
    Parses `resources.txt` files to extract CPU usage data for specific tests.

    Args:
        directory: The root directory to search for result files.

    Returns:
        A dictionary where keys are host modes (e.g., 'multiple_topics_local')
        and values are another dictionary mapping middleware names to lists of
        CPU usage percentages over time.
    """
    processed_results = defaultdict(dict)
    sorted_files = get_sorted_files_by_mtime(directory, "resources.txt")

    for file_path in sorted_files:
        # Process only files that are relevant to the included tests
        if file_path.endswith("resources.txt") and any(
            key in file_path for key in INCLUDED_TESTS
        ):
            root = os.path.dirname(file_path)
            clean_root = root.lstrip("./")
            path_parts = clean_root.split("/")
            middleware = path_parts[-1] if "single_process" in root else path_parts[-2]

            # Determine if the test involved a remote host
            host_mode = "remote" if "remote_host" in file_path else "local"
            matching_test = next(
                (key for key in INCLUDED_TESTS if key in file_path), None
            )
            if matching_test:
                # Create a unique key for the test scenario and host mode
                scenario_key = f"{matching_test}_{host_mode}"

            try:
                resources_df = pd.read_csv(file_path)
                # Extract the 'cpu_perc' column, convert to float, and skip the summary row
                cpu_data = resources_df["cpu_perc"].astype(float).to_list()[1:]
                processed_results[scenario_key][middleware] = cpu_data
            except (FileNotFoundError, KeyError, ValueError) as e:
                print(f"Warning: Could not process file {file_path}. Error: {e}")
                continue

    return processed_results


def plot_metrics(
    processed_results: Dict[str, List[float]],
    output_file: str,
    host_mode: str,
    show_plot: bool,
):
    """
    Generates and saves a plot of CPU usage over time for a specific test scenario.

    Args:
        processed_results: A dictionary mapping middleware to CPU usage data lists.
        output_file: The path prefix for the saved plot image.
        host_mode: A string describing the test scenario (e.g., 'multiple_topics_local').
        show_plot: If True, displays the plot interactively.
    """
    plt.figure(figsize=(10, 5))

    for middleware, data in processed_results.items():
        # Trim the first and last elements to avoid noise from startup/shutdown
        trimmed_values = np.array(data)[1:-1]
        time_axis = np.arange(0, len(trimmed_values))

        plt.plot(time_axis, trimmed_values, label=middleware)

    # Configure plot labels, title, and legend
    plt.xlabel("Time (s)")
    plt.ylabel("CPU Usage (%)")
    plt.title(f"CPU Usage Over Time - {host_mode.replace('_', ' ').title()}")
    plt.xticks(
        np.arange(0, len(trimmed_values), step=max(1, len(trimmed_values) // 10))
    )  # Dynamic ticks
    plt.legend(title="Middleware", loc="center left", bbox_to_anchor=(1, 0.5))
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout(rect=[0, 0, 0.85, 1])  # Adjust layout for legend

    # Save the plot to a file
    plot_output_file = f"{output_file}_test.png"
    plt.savefig(plot_output_file)
    print(f"✅ Plot saved to: {plot_output_file}")

    if show_plot:
        plt.show()

    plt.close()


def main():
    """Main function to parse arguments and trigger the CPU-over-time analysis."""
    parser = argparse.ArgumentParser(
        description="""
Analyze CPU usage over time for specific benchmark scenarios (e.g., 'idle',
'multiple_topics'). This script processes `resources.txt` files and generates
plots to visualize CPU stability and performance, distinguishing between local
and remote host setups.
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
    parser.add_argument(
        "--output",
        type=str,
        default="cpu_usage_over_time",
        help="Base name for the output plot files (default: cpu_usage_over_time).",
    )
    args = parser.parse_args()

    results_directory = args.results_directory
    if not os.path.isdir(results_directory):
        print(f"Error: '{results_directory}' is not a valid directory.")
        sys.exit(1)

    parsed_results_directory = os.path.join(results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    print("Processing CPU usage over time...")
    cpu_usage_results = process_directory(results_directory)

    if not cpu_usage_results:
        print(
            "Info: No valid data found for 'idle' or 'multiple_topics' tests. Skipping."
        )
        sys.exit(0)

    # Generate a separate plot for each scenario (e.g., idle_local, multiple_topics_remote)
    output_base = os.path.join(parsed_results_directory, args.output)
    for host_mode, scenario_data in cpu_usage_results.items():
        output_plot_prefix = f"{output_base}_{host_mode}"
        plot_metrics(scenario_data, output_plot_prefix, host_mode, args.show_plot)


if __name__ == "__main__":
    main()
