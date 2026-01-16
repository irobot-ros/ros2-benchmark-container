#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze Latency from Long-Duration Benchmark Tests.

This script is designed to process latency data from long-duration benchmark runs. The primary goal is to visualize the stability of latency over time to identify potential issues like performance degradation in extended-run scenarios.

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
import os
import csv
import math
import sys
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from typing import List, Optional, Dict
from utils import extract_sections, get_sorted_files_by_mtime, split_vendors

csv.field_size_limit(sys.maxsize)

ROS_INTERFACES = [
    "PubDur",
    "SubLat",
    "CliLat",
    "SrvLat",
    "ActionCliLat",
    "ActionSrvLat",
]


class RawResults:
    """
    A data structure to store raw results for the metrics:
    - node: The name of the node.
    - topic: The name of the topic.
    - freq_hz: The frequency of the topic.
    - all_latency: A list of all the latency values.
    """

    def __init__(self):
        self.node: str = ""
        self.topic: str = ""
        self.freq_hz: float = 0
        self.all_latency: List[float] = []


def get_data_from_section(lines: List[str]) -> Optional[List[RawResults]]:
    """
    Parse latency data from a section of a CSV file.

    This function takes a list of strings, where each string is a line from a
    CSV file, and parses it to extract latency data. It populates a list of
    RawResults objects with the parsed data.

    Args:
        lines: A list of strings, each representing a line in a CSV section.

    Returns:
        A list of RawResults objects containing the parsed data, or None if the
        input is empty.
    """
    if not lines:
        return None

    reader = csv.DictReader(lines)
    result = []

    for row in reader:
        raw_result = RawResults()
        node = row.get("node")
        topic = row.get("topic")
        freq_hz = row.get("freq_hz")
        all_lat_str = row.get("all_lat")

        if freq_hz and freq_hz.strip():
            try:
                raw_result.freq_hz = float(freq_hz)
            except ValueError:
                raise ValueError(f"Invalid 'freq_hz' value: {freq_hz}")
        else:
            raise ValueError(f"Missing 'freq_hz' in row: {row}")

        raw_result.node = node
        raw_result.topic = topic

        if all_lat_str and all_lat_str != "[]":
            raw_result.all_latency = [
                int(x) for x in all_lat_str.strip("[]").split("; ")
            ]

        result.append(raw_result)

    return result


def process_directory(directory: str, test_case: str) -> Dict[str, dict]:
    """
    Process all files with latency results in a directory, extracting data and computing necessary metrics.

    Args:
        directory: The root directory containing the files to be processed.
        test_case: The test case to be processed (e.g., pub-sub, cli-srv, actions).

    Returns:
        A dictionary with the computed results from the processed files.
    """
    processed_results = defaultdict(dict)

    # Get sorted latency_all.txt files by modification time
    sorted_files = get_sorted_files_by_mtime(directory, "latency_all.txt")
    for file_path in sorted_files:
        # Process only files that match the specified test case
        if (
            file_path.endswith("latency_all.txt")
            and "_long" in file_path
            and test_case in file_path
        ):
            root = os.path.dirname(file_path)  # Get root directory for cleaned path
            sections = extract_sections(file_path)

            # Remove leading "./" from the directory path
            clean_root = root[2:] if root.startswith("./") else root
            path = clean_root.split("/")
            middleware = path[-1]
            publisher_data = get_data_from_section(sections["publishers"])
            subscriber_data = get_data_from_section(sections["subscriptions"])
            client_data = get_data_from_section(sections["clients"])
            service_data = get_data_from_section(sections["services"])
            action_client_data = get_data_from_section(sections["action_clients"])
            action_server_data = get_data_from_section(sections["action_servers"])

            processed_results[middleware] = {
                "Directory": clean_root,
                "PubDur": publisher_data,
                "SubLat": subscriber_data,
                "CliLat": client_data,
                "SrvLat": service_data,
                "ActionCliLat": action_client_data,
                "ActionSrvLat": action_server_data,
            }
    return processed_results


def plot_latency_metrics(
    processed_results: dict,
    output_file: str,
    show_plot: bool,
):
    """
    Plot the latency metrics for all directories in a single horizontal plot with different symbols.

    Args:
        processed_results: The processed data containing latency metrics.
        output_file: Path where the plot image will be saved.
        show_plot: If True, display the plot after generating it.
    """
    # Limit the number of vendors per figure
    chunks = split_vendors(processed_results)

    # Iterate over chunks of vendors
    # Each chunk will create a separate figure
    for fig_idx, vendors_chunk in enumerate(chunks):
        n_rows = math.ceil(len(vendors_chunk) / 2)

        for ros_interface in ROS_INTERFACES:
            fig, axes = plt.subplots(n_rows, 2, figsize=(12, 4 * n_rows))
            axes = axes.flatten()
            handles = []
            labels = []

            for ax, (middleware, raw_data) in zip(axes, processed_results.items()):
                # Skip if this middleware does not include the current ros_interface
                # (some applications may not support all interface types)
                if raw_data[ros_interface] is None:
                    continue
                for rows in raw_data[ros_interface]:
                    # Compute time values for each frequency sample
                    sample_times = np.cumsum([1 / rows.freq_hz] * len(rows.all_latency))

                    # Stop execution if total duration is less than 60 seconds
                    if sample_times[-1] < 60:
                        print(
                            f"Error: Test duration for {middleware} ({rows.node}/{rows.topic}) is too short ({sample_times[-1]:.2f}s). It should be more than 60 seconds. Exiting."
                        )
                        continue

                    # Find max time and ignore first and last 30 seconds
                    max_time = sample_times[-1] if len(sample_times) > 0 else 0
                    valid_indices = (sample_times >= 30) & (
                        sample_times <= max_time - 30
                    )

                    sample_times = sample_times[valid_indices]
                    latencies = np.array(rows.all_latency)[valid_indices]

                    # Skip if no valid data
                    if len(sample_times) == 0:
                        continue

                    # Define 10-second bins starting from 30s
                    bin_edges = np.arange(30, max_time - 30, 10)
                    bin_means = []

                    # Compute mean latency per bin
                    for i in range(len(bin_edges) - 1):
                        start, end = bin_edges[i], bin_edges[i + 1]
                        mask = (sample_times >= start) & (sample_times < end)
                        mean_latency = (
                            np.mean(latencies[mask]) if np.any(mask) else np.nan
                        )
                        bin_means.append(mean_latency)

                    ax.plot(
                        bin_edges[:-1], bin_means, label=f"{rows.node}/{rows.topic}"
                    )

                # Store the legend from the last subplot
                handles, labels = ax.get_legend_handles_labels()

                ax.set_xlabel("Time [s]")
                ax.set_ylabel("Latency [us]")
                ax.set_title(f"{middleware}")
                ax.grid(True, linestyle="--", alpha=0.7)

            fig.suptitle(f"Latency - {ros_interface}", fontsize=14)
            fig.tight_layout()
            fig.legend(handles, labels, title="Node/interface", loc="center", ncol=2)

            # Optionally show the plot
            if show_plot:
                plt.show()

            # Save the plot as a PNG file
            suffix = f"_{fig_idx}" if fig_idx > 0 else ""
            metric_output_file = f"{output_file}_{ros_interface}_long_test{suffix}.png"
            fig.savefig(metric_output_file)

            # Close the current figure to avoid overlap with next plot
            plt.close()


def main():
    """
    Main function to parse arguments and execute the latency processing for long duration tests and plotting.
    """
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

    # Parse the arguments
    args = parser.parse_args()

    if not os.path.isdir(args.results_directory):
        print(f"Error: '{args.results_directory}' is not a valid directory.")
        sys.exit(1)

    parsed_results_directory = os.path.join(args.results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    for test_case in ["pub-sub", "cli-srv", "actions"]:

        # Process the results directory to gather the data from the tests
        latency_results = process_directory(args.results_directory, test_case)

        # Validate that all metrics (mean, min, max) contain data
        if not latency_results:
            print("Error: no valid data found to process.")
            sys.exit(1)

        # Generate plots for latency metrics
        output_plot = os.path.join(parsed_results_directory, f"latency_{test_case}")
        plot_latency_metrics(latency_results, output_plot, args.show_plot)


if __name__ == "__main__":
    main()
