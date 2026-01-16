#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze RAM Scalability Benchmark Results.

This script is dedicated to analyzing how Resident Set Size (RSS) memory usage
scales as the number of processes in the system increases. It processes data
from benchmark runs specifically designed to test scalability.

The script's workflow includes:
1.  **Data Extraction**: It finds all `resources.txt` files within result directories
    that are marked as 'scalability' tests.
2.  **Data Aggregation**: It collects the RSS memory usage data (in MB) for each test run.
3.  **CSV Generation**:
    - `all_ram_usage.csv`: A file containing the complete time-series data for RAM
      usage, which can be used for more detailed analysis.
    - `scalability_metrics.csv`: A report file containing the results of the
      linear regression (R-squared and slope) for each RMW vendor.
4.  **Grouping**: It groups the collected RAM usage data by RMW vendor and by the
    number of processes in the test (e.g., 1, 2, 5, 10).
5.  **Plotting and Regression**:
    - It generates box plots to visualize the distribution of RAM usage for each
      number of processes.
    - It calculates and overlays a linear regression line on the plot to provide a
      clear trend of how RAM usage scales. The R-squared value is included to
      indicate the quality of the linear fit.
6.  **Output**: The final plot is saved as `ram_scalability.png` in the
    `parsed_results` directory.
"""

import argparse
import math
import os
import sys
from collections import defaultdict
from typing import List, Dict, Any, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import linregress

# Append the parent directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from utils import process_metrics_in_directory, split_vendors

# The number of processes used in the scalability tests
NUMBER_OF_PROCESSES = [1, 2, 5, 10]


def get_sorted_directories_by_mtime(directories: list) -> List[str]:
    """
    Sorts a list of directories based on the modification time of their 'resources.txt' file.

    Args:
        directories: A list of directory paths.

    Returns:
        A list of directory paths sorted by the modification time of 'resources.txt'.
    """
    return sorted(
        directories, key=lambda d: os.path.getmtime(os.path.join(d, "resources.txt"))
    )


def find_directories_with_resources(root_dirs: list):
    """
    Finds and collects directories that contain a 'resources.txt' file.

    Args:
        root_dirs (list): List of root directory paths to search under.

    Returns:
        list: A list of directory paths that contain a 'resources.txt' file.
    """
    directories = []
    for root_dir in root_dirs:
        for root, _, files in os.walk(root_dir):
            if "resources.txt" in files:
                # Remove ./ prefix from the path
                clean_path = root[2:] if root.startswith("./") else root
                directories.append(clean_path)
    return directories


def generate_all_ram_usage_csv(
    directories: List[str], csv_output_file: str, show_console: bool = False
):
    """
    Processes scalability test directories and writes the full RAM usage time-series data to a CSV file.

    Args:
        directories: List of directory paths with benchmark data.
        csv_output_file: Path for the output CSV file.
        show_console: If True, prints the data to the console.
    """
    print(f"✅ Writing full RAM usage metrics to {csv_output_file}")
    with open(csv_output_file, "w") as csv_file:
        csv_header = "Directory;RAM_MB"
        csv_file.write(f"{csv_header}\n")
        if show_console:
            print(f"{csv_header}")

        for directory in directories:
            # Filter for scalability tests only
            if "scalability" not in directory or "debug" in directory:
                continue
            _, _, rss_kb, _, _ = process_metrics_in_directory(directory)
            csv_line = f"{directory};{rss_kb.to_list()[1:]}"
            csv_file.write(f"{csv_line}\n")
            if show_console:
                print(f"{csv_line}")


def generate_report_csv(
    data: Dict[str, Any], csv_report_file: str, first_write: bool = False
):
    """
    Writes linear regression results to a CSV file for the final report.

    Args:
        data: A dictionary containing the slope and r-squared values for each vendor.
        csv_report_file: Path to the CSV file to save the data.
        first_write: If True, overwrites the file and writes the header.
    """
    mode = "w" if first_write else "a"

    # Write to CSV
    with open(csv_report_file, mode=mode, newline="") as report_csv:
        if first_write:
            csv_header = "RMW;r-squared;slope"
            report_csv.write(f"{csv_header}\n")

        for vendor, metrics in data.items():
            report_csv.write(f"{vendor};{metrics['r_squared']:4f};{metrics['slope']}\n")


def extract_key_and_vendor(directory: str) -> Tuple[str, int]:
    """
    Extracts the vendor and the number of processes from the directory path.

    Args:
        directory: The directory path for a scalability test run.

    Returns:
        A tuple (vendor, num_processes) or (None, None).
    """
    vendor = directory.split("/")[-2]
    num_processes = next(
        (p for p in NUMBER_OF_PROCESSES if f"/{str(p)}_" in directory),
        None,
    )
    return vendor, num_processes


def collect_rss_usage_by_type(
    directories: List[str],
) -> Dict[str, Dict[int, List[float]]]:
    """
    Collects and groups RSS memory usage data by vendor and number of processes.

    Args:
        directories: A list of all result directories.

    Returns:
        A nested dictionary: {vendor: {num_processes: [ram_usage_list_mb]}}.
    """
    ram_usage_by_vendor = defaultdict(dict)
    for directory in directories:
        if "scalability" not in directory or "debug" in directory:
            continue
        vendor, key = extract_key_and_vendor(directory)
        if vendor and key is not None:
            _, _, rss_kb, _, _ = process_metrics_in_directory(directory)
            rss_mb = (rss_kb / 1024).to_list()[1:]  # Convert to MB
            ram_usage_by_vendor[vendor][key] = rss_mb
    return ram_usage_by_vendor


def plot_ram_usage(
    ram_usage_by_vendor: Dict[str, Dict[int, List[float]]],
    output_file_prefix: str,
    csv_report_file: str,
    show_plot: bool = False,
):
    """
    Generates box plots of RAM usage vs. number of processes with regression lines.

    Args:
        ram_usage_by_vendor: Grouped RAM usage data.
        output_file_prefix: The base path and name for the output plot file.
        csv_report_file: Path to the CSV file for saving regression data.
        show_plot: If True, displays the plots interactively.
    """
    chunks = split_vendors(ram_usage_by_vendor)

    for fig_idx, vendors_chunk in enumerate(chunks):

        n_rows = math.ceil(len(vendors_chunk) / 2)

        fig, axis = plt.subplots(n_rows, 2, figsize=(12, 4 * n_rows))
        fig.suptitle("RAM Usage Scalability", fontsize=14)
        axis = axis.flatten()

        # Hide unused subplots
        for i in range(len(ram_usage_by_vendor), len(axis)):
            axis[i].axis("off")

        # Limit the y-axis to 10% above the maximum value to all plots
        max_y_limit = 1.1 * max(
            value
            for vendor in ram_usage_by_vendor
            for ram in ram_usage_by_vendor[vendor].values()
            for value in ram
        )

        report_data = defaultdict()

        for vendor, ax in zip(ram_usage_by_vendor, axis):
            if vendor is None:
                continue
            ram_usage = list(ram_usage_by_vendor[vendor].values())
            x_values = np.array([float(k) for k in ram_usage_by_vendor[vendor].keys()])

            max_ram_usage_len = max([len(c) for c in ram_usage])
            for i in range(len(ram_usage)):
                pad_len = max_ram_usage_len - len(ram_usage[i])
                ram_usage[i] = np.pad(ram_usage[i], (0, pad_len), mode="edge")

            x_label = "Number of Processes"
            ax.set_xscale("linear")
            ax.set_xlim(0, 11)
            widths = 1

            # Plot the RAM usage data as a boxplot
            ax.boxplot(
                ram_usage,
                positions=x_values,
                widths=widths,
                patch_artist=True,
                boxprops=dict(facecolor="lightgray"),
                medianprops=dict(color="blue"),
            )

            # Compute and plot the linear regression for all the values
            ram_usage_array = np.array(ram_usage)
            x_values_expanded = np.repeat(x_values, ram_usage_array.shape[1])
            y_values = ram_usage_array.flatten()

            try:
                slope, intercept, r_value, _, _ = linregress(
                    x_values_expanded, y_values
                )

                # Calculate and save the value of R-squared
                r_squared = r_value**2
                report_data[vendor] = {
                    "r_squared": r_squared,
                    "slope": slope,
                }

                # Plot the linear regression
                x_reg = np.linspace(0, int(1e7), 1000)
                y_reg = intercept + slope * x_reg
                ax.plot(
                    x_reg,
                    y_reg,
                    label="Linear Regression",
                    color="red",
                    linestyle="--",
                )
            except ValueError as ve:
                print("Error when plotting linear regression. ", ve)

            ax.set_xlabel(x_label)
            ax.set_ylabel("RAM usage [MB]")
            ax.set_ylim(0, max_y_limit)
            ax.set_title(f"{vendor}")
            ax.grid(True)
            ax.legend()

        plt.tight_layout()
        suffix = f"_{fig_idx}" if fig_idx > 0 else ""
        plt.savefig(f"{output_file_prefix}{suffix}.png")
        if show_plot:
            plt.show()

        # Generate the CSV for the report with the processed data
        generate_report_csv(report_data, csv_report_file)


def main():
    """Main function to orchestrate the RAM scalability analysis."""
    parser = argparse.ArgumentParser(
        description="""
Analyze RAM scalability from benchmark results. This script processes `resources.txt`
files from scalability tests, calculates linear regressions for RAM usage vs.
number of processes, and generates plots to visualize the scaling behavior.
""",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "results_directory", type=str, help="Path to the main results directory."
    )
    parser.add_argument(
        "--show-plot", action="store_true", help="Display generated plots."
    )
    parser.add_argument(
        "--show-console", action="store_true", help="Print CSV data to console."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.results_directory):
        print(f"Error: Directory '{args.results_directory}' not found.")
        sys.exit(1)

    parsed_results_directory = os.path.join(args.results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    directories = find_directories_with_resources(args.results_directory)
    if not directories:
        print("No 'resources.txt' files found.")
        sys.exit(0)

    # Sort directories by modification time (oldest to newest)
    sorted_directories = get_sorted_directories_by_mtime(directories)

    # Generate CSV with all RAM usage data
    all_ram_csv = os.path.join(parsed_results_directory, "all_ram_usage.csv")
    generate_all_ram_usage_csv(sorted_directories, all_ram_csv, args.show_console)

    # Prepare for report generation
    report_csv_path = os.path.join(parsed_results_directory, "scalability_metrics.csv")
    generate_report_csv({}, report_csv_path, first_write=True)

    # Collect and plot RAM usage data
    print("\nProcessing RAM scalability data...")
    ram_data = collect_rss_usage_by_type(sorted_directories)
    if not ram_data:
        print("No RAM scalability data found to process. Skipping plots.")
        sys.exit(0)

    output_prefix = os.path.join(parsed_results_directory, "ram_scalability")
    plot_ram_usage(ram_data, output_prefix, report_csv_path, args.show_plot)

    print("✅ RAM scalability analysis complete.")


if __name__ == "__main__":
    main()
