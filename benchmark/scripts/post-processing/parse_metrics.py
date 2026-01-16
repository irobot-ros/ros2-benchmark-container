#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze General Performance Metrics (CPU, Memory).

This script processes `resources.txt` files from benchmark runs to analyze
CPU and memory usage across various test scenarios. It calculates average metrics,
performs linear regression analysis on CPU usage, and generates plots to
visualize the results.

The script's main functionalities are:
1.  **Data Aggregation**: It finds all `resources.txt` files in a given directory
    and calculates the average CPU percentage, RSS (Resident Set Size) in MB, and
    VSZ (Virtual Memory Size) in MB for each test run.
2.  **CSV Generation**:
    - `average_metrics.csv`: A summary file with the average metrics for each
      test configuration.
    - `all_cpu_usage.csv`: A file containing the complete time-series data for
      CPU usage, used by other analysis scripts.
3.  **CPU Usage Analysis**: It groups CPU usage data by ROS interface (pub-sub,
    cli-srv, actions), process type (single-process, multi-process), and RMW vendor.
4.  **Plotting and Regression**:
    - For `pub-sub` tests, it plots CPU usage vs. payload size.
    - For `cli-srv` and `actions` tests, it plots CPU usage vs. the number of clients.
    - It generates box plots to show the distribution of CPU usage and overlays a
      linear regression line to visualize the trend.
5.  **Report Data**: The results of the linear regression (R-squared and slope)
    are saved to `report_metrics.csv`, which provides quantitative insights for
    the final PDF report.
"""

import argparse
import math
import os
import sys
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import linregress
from utils import process_metrics_in_directory, split_vendors

# Constants for mapping and filtering
PAYLOAD_MAPPING = {"10b": 10, "100kb": 100e3, "1mb": 1e6, "4mb": 4e6}
PROCESS_TYPE = {
    "single_process": "Single Process",
    "multi_process": "Multi Process",
}


def get_sorted_directories_by_mtime(directories: List[str]) -> List[str]:
    """
    Sorts the given list of directories by the modification time of the 'resources.txt' file in ascending order.

    Args:
        directories (list): List of directory paths to sort.

    Returns:
        list: Sorted list of directory paths based on the modification time of 'resources.txt'.
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


def compute_average_metrics(
    cpu_perc: pd.Series, rss_KB: pd.Series, vsz_KB: pd.Series, latency_us: pd.Series
) -> Dict[str, float]:
    """
    Computes the average CPU, RSS memory, VSZ memory, and latency values.

    Args:
        cpu_perc: A pandas Series with CPU usage percentages.
        rss_KB: A pandas Series with RSS memory data in kilobytes.
        vsz_KB: A pandas Series with VSZ memory data in kilobytes.
        latency_us: A pandas Series with latency data in microseconds.

    Returns:
        A dictionary containing the average metrics values.
    """
    return {
        "CPU": round(np.mean(cpu_perc), 2),
        "RSS_MB": round(np.mean(rss_KB) / 1024, 2),  # Convert KB to MB
        "VSZ_MB": round(np.mean(vsz_KB) / 1024, 2),  # Convert KB to MB
        "Latency_us": round(np.mean(latency_us), 2),
    }


def generate_summary_csv(
    directories: List[str], csv_output_file: str, show_console: bool = False
):
    """
    Generates CSV files containing average and full time-series metrics.

    Args:
        directories: List of directory paths with benchmark data.
        csv_output_file: Base path for the output CSV files.
        show_console: If True, prints the average metrics to the console.
    """
    metric = os.path.basename(csv_output_file).removesuffix(".csv").replace("_", " ")
    print(f"Writing {metric} results to {csv_output_file}")

    with open(csv_output_file, "w") as csv_file:
        csv_header = "Directory;CPU;RSS_MB;VSZ_MB;Latency_us"
        csv_file.write(f"{csv_header}\n")
        if show_console:
            print(f"{csv_header}")

        for directory in directories:
            time_ms, cpu_perc, rss_KB, vsz_KB, latency_us = (
                process_metrics_in_directory(directory)
            )
            averages = compute_average_metrics(cpu_perc, rss_KB, vsz_KB, latency_us)

            # Write average metrics
            csv_line = f"{directory.lstrip('./')};{averages['CPU']};{averages['RSS_MB']};{averages['VSZ_MB']};{averages['Latency_us']}"
            csv_file.write(f"{csv_line}\n")
            if show_console:
                print(f"{csv_line}")


def generate_all_cpu_usage_csv(
    directories: list, csv_output_file: str, show_console: bool = False
):
    """
    Processes multiple directories and writes all the CPU usage metrics to a CSV file.

    Args:
        directories (list): List of directory paths containing benchmark result data.
        csv_output_file (str): Path to the output CSV file where the results will be written.
        show_console (bool): If True, print the data to the console. Defaults to False.
    """
    print(f"Writing metrics to {csv_output_file}")

    with open(csv_output_file, "w") as csv_file:
        csv_header = "Directory;CPU"
        csv_file.write(f"{csv_header}\n")
        if show_console:
            print(f"{csv_header}")

        for directory in directories:
            _, cpu_perc, _, _, _ = process_metrics_in_directory(directory)
            csv_line = f"{directory};{cpu_perc.to_list()[1:]}"
            csv_file.write(f"{csv_line}\n")
            if show_console:
                print(f"{csv_line}")


def generate_report_csv(
    data: Dict[str, Any], csv_report_file: str, first_write: bool = False
):
    """
    Writes linear regression results to a CSV file for the final report.

    Args:
        data: A dictionary containing the slope and r-squared values for each test case.
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


def extract_key_and_vendor(directory: str, ros_interface: str, process: str):
    """
    Extracts the vendor and the independent variable (key) from a directory path.

    The key can be payload size for pub-sub tests or number of clients for others.

    Args:
        directory: The directory path for a test run.
        ros_interface: The ROS interface used ('pub-sub', 'cli-srv', 'actions').
        process_type: The process type ('single_process', 'multi_process').

    Returns:
        A tuple (vendor, key) or (None, None) if not applicable.
    """
    interface_process = f"{ros_interface}_{process}"
    if interface_process not in directory:
        return None, None

    parts = directory.split("/")
    vendor_idx = -1 if process == "single_process" else -2
    vendor = parts[vendor_idx]

    if ros_interface == "pub-sub":
        key = next(
            (PAYLOAD_MAPPING[size] for size in PAYLOAD_MAPPING if size in directory),
            None,
        )
        return vendor, key
    elif ros_interface in ["cli-srv", "actions"] and "multiple_clients" in directory:
        clients_idx = -2 if process == "single_process" else -3
        num_clients_folder = parts[clients_idx]

        match = re.match(r"(\d+)_cli_srv", num_clients_folder) or re.match(
            r"(\d+)_actions", num_clients_folder
        )
        key = int(match.group(1)) if match else 1
        return vendor, key
    return None, None


def collect_cpu_usage_by_type(
    directories: List[str], ros_interface: str, process_type: str
) -> Dict[str, Dict[Any, List[float]]]:
    """
    Collects and groups CPU usage data by vendor and a secondary key (payload or client count).

    Args:
        directories: A list of all result directories.
        ros_interface: The ROS interface to filter for.
        process_type: The process type to filter for.

    Returns:
        A nested dictionary: {vendor: {key: [cpu_usage_list]}}.
    """
    cpu_usage_by_vendor = defaultdict(dict)
    for directory in directories:
        vendor, key = extract_key_and_vendor(directory, ros_interface, process_type)

        if vendor is not None and key is not None:
            _, cpu_perc, _, _, _ = process_metrics_in_directory(directory)
            cpu_usage_by_vendor[vendor][key] = cpu_perc.to_list()[1:]
    return cpu_usage_by_vendor


def plot_cpu_usage(
    cpu_usage_by_vendor: Dict[str, Any],
    process_type: str,
    output_file_prefix: str,
    csv_report_file: str,
    ros_interface: str,
    show_plot: bool = False,
):
    """
    Generates and saves box plots of CPU usage with linear regression overlays.

    Args:
        cpu_usage_by_vendor: Grouped CPU usage data.
        process_type: The process type being plotted.
        output_file_prefix: The base path and name for the output plot file.
        csv_report_file: Path to the CSV file for saving regression data.
        ros_interface: The ROS interface being plotted.
        show_plot: If True, displays the plots interactively.
    """
    chunks = split_vendors(cpu_usage_by_vendor)

    for fig_idx, vendors_chunk in enumerate(chunks):
        n_rows = math.ceil(len(vendors_chunk) / 2)

        fig, axis = plt.subplots(n_rows, 2, figsize=(12, 4 * n_rows))
        fig.suptitle(
            f"CPU Usage - {ros_interface} - {PROCESS_TYPE[process_type]}", fontsize=14
        )
        axis = axis.flatten()

        # Hide unused subplots
        for i in range(len(cpu_usage_by_vendor), len(axis)):
            axis[i].axis("off")

        # Limit the y-axis to 10% above the maximum value to all plots
        max_y_limit = 1.1 * max(
            value
            for vendor in cpu_usage_by_vendor
            for cpu in cpu_usage_by_vendor[vendor].values()
            for value in cpu
        )

        report_data = defaultdict()

        for vendor, ax in zip(cpu_usage_by_vendor, axis):
            cpu_usages = list(cpu_usage_by_vendor[vendor].values())
            x_values = np.array(list(cpu_usage_by_vendor[vendor].keys()))

            max_cpu_usage_len = max([len(c) for c in cpu_usages])
            for i in range(len(cpu_usages)):
                pad_len = max_cpu_usage_len - len(cpu_usages[i])
                cpu_usages[i] = np.pad(cpu_usages[i], (0, pad_len), mode="edge")

            if ros_interface == "pub-sub":
                x_label = "Payload Size [bytes]"
                ax.set_xscale("log")
                ax.set_xlim(0.4e1, 1e7)
                widths = x_values
            else:
                x_label = "Number of Clients"
                ax.set_xscale("linear")
                ax.set_xlim(0, 21)
                widths = 1

            ax.boxplot(
                cpu_usages,
                positions=x_values,
                widths=widths,
                patch_artist=True,
                boxprops=dict(facecolor="lightgray"),
                medianprops=dict(color="blue"),
            )

            # Compute and plot the linear regression for all the values
            cpu_usages_array = np.array(cpu_usages)
            x_values_expanded = np.repeat(x_values, cpu_usages_array.shape[1])
            y_values = cpu_usages_array.flatten()

            try:
                slope, intercept, r_value, _, _ = linregress(
                    x_values_expanded, y_values
                )

                # Calculate and save the value of R-squared
                r_squared = r_value**2
                report_data[f"{ros_interface}/{process_type}/{vendor}"] = {
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
            ax.set_ylabel("CPU Usage (%)")
            ax.set_ylim(0, max_y_limit)
            ax.set_title(f"{vendor}")
            ax.grid(True)
            ax.legend()

        plt.tight_layout()
        suffix = f"_{fig_idx}" if fig_idx > 0 else ""
        plt.savefig(f"{output_file_prefix}{suffix}.png")

        if show_plot:
            plt.show()
        plt.close(fig)

        # Generate the CSV for the report with the processed data
        generate_report_csv(report_data, csv_report_file)


def main():
    """Main function to orchestrate the metrics parsing and plotting."""
    parser = argparse.ArgumentParser(
        description="""
Parse and analyze CPU and memory metrics from benchmark resource files.
This script generates summary CSV files, box plots with linear regressions for
CPU usage vs. payload/client count, and a CSV file with regression results
for the final report.
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
        "--show-console", action="store_true", help="Print average metrics to console."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.results_directory):
        print(f"Error: Directory '{args.results_directory}' not found.")
        sys.exit(1)

    parsed_results_directory = os.path.join(args.results_directory, "parsed_results")
    os.makedirs(parsed_results_directory, exist_ok=True)

    # Find directories with resources.txt in the specified directories
    directories = find_directories_with_resources([args.results_directory])

    if not directories:
        print("No directories with 'resources.txt' found in the provided directories.")
        sys.exit(0)

    # Sort directories by modification time (oldest to newest)
    sorted_directories = get_sorted_directories_by_mtime(directories)

    # Generate summary CSVs
    csv_output_file = os.path.join(parsed_results_directory, "average_metrics.csv")
    generate_summary_csv(sorted_directories, csv_output_file, args.show_console)
    # Generate CSV for all CPU and Memory usage metrics
    csv_output_file = os.path.join(parsed_results_directory, "all_cpu_usage.csv")
    generate_all_cpu_usage_csv(directories, csv_output_file, args.show_console)

    # Prepare for report generation
    report_csv_path = os.path.join(parsed_results_directory, "report_metrics.csv")
    generate_report_csv({}, report_csv_path, first_write=True)

    # Main loop to generate plots for each combination of interface and process type
    for ros_interface in ["pub-sub", "cli-srv", "actions"]:
        for process_type in PROCESS_TYPE.keys():
            cpu_data = collect_cpu_usage_by_type(
                directories, ros_interface, process_type
            )
            if not cpu_data:
                continue

            # Generate plot and CSV for the report
            output_plot = os.path.join(parsed_results_directory, "cpu_usage")
            output_file = f"{output_plot}_{ros_interface}_{process_type}"

            plot_cpu_usage(
                cpu_data,
                process_type,
                output_file,
                report_csv_path,
                ros_interface,
                args.show_plot,
            )


if __name__ == "__main__":
    main()
