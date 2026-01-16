#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Parse and Analyze Latency Benchmark Results.

This script processes raw latency data from benchmark runs. It recursively finds
all `latency_all.txt` files in a given results directory, parses them to extract
latency metrics for publishers, subscribers, clients, and services.

The script performs the following main tasks:
1.  **Data Extraction**: Reads latency data (mean, min, max, and all individual values)
    from different sections (publishers, subscribers, etc.) within the raw text files.
2.  **Aggregation**: Calculates the average of the mean, min, and max latencies across
    all runs for each specific test configuration (e.g., for a given RMW, payload, etc.).
3.  **CSV Generation**:
    - Creates `average_latency.csv` with the aggregated mean, min, and max values.
    - Creates `all_latency.csv` containing every single latency measurement, which is
      used by other analysis scripts.
4.  **Plotting**: Generates plots visualizing latency vs. payload size for different
    RMW vendors and process types (single-process vs. multi-process). It also creates
    a summary plot comparing the mean latencies of all vendors.
5.  **Linear Regression**: For the latency vs. payload plots, it computes and plots
    a linear regression to show the trend. The R-squared value and slope are calculated.
6.  **Report CSV**: Saves the linear regression results (R-squared and slope) to
    `report_latency.csv`, which is later used to generate the final PDF report.
"""


import argparse
import csv
import math
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from scipy.stats import linregress
from typing import List, Optional, Dict, Any, Tuple, Union

from utils import extract_sections, get_sorted_files_by_mtime, split_vendors

csv.field_size_limit(sys.maxsize)

# Constants for filtering and mapping
EXCLUDED_TESTS = ["multiple_topics", "idle"]
PAYLOAD_MAPPING = {"10b": 10, "100kb": 100e3, "1mb": 1e6, "4mb": 4e6}
PROCESS_MAPPING = {
    "single_process": "Single Process",
    "multi_process": "Multi Process",
    "mix_process": "Mix Process",
}
SECTIONS_MAPPING = {
    "PubDur": "Publishers",
    "SubLat": "Subscribers",
    "CliLat": "Clients",
    "SrvLat": "Services",
    "ActionCliLat": "Action Client",
    "ActionSrvLat": "Action Server",
}

# Maximum number of vendors to show in a single plot figure
VENDORS_PER_FIG = 8


class ProcessedResults:
    """
    A data structure to store processed results for the metrics:
    - mean: A list of mean values.
    - min: A list of minimum values.
    - max: A list of maximum values.
    - all_latency: A list of all the latency values.
    """

    def __init__(self):
        self.mean: List[float] = []
        self.min: List[float] = []
        self.max: List[float] = []
        self.all_latency: List[float] = []


@dataclass
class ComputedResults:
    """Stores the computed mean, min, max and all the latency values after processing."""

    mean: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    all_latency: Optional[List[float]] = None


def calculate_metrics_from_section(lines: list, result: ComputedResults):
    """
    Calculate the average, minimum, and maximum values from a section.

    Args:
        lines: A list of strings representing lines in a section.
        result: An object to store computed results.

    Returns:
        None. The computed values are stored in the provided result object.
    """
    if not lines:
        return

    reader = csv.DictReader(lines)
    raw_data = ProcessedResults()

    for row in reader:
        mean_us = row.get("mean_us")
        min_us = row.get("min_us")
        max_us = row.get("max_us")
        all_lat_str = row.get("all_lat")

        if mean_us and mean_us.strip():
            try:
                raw_data.mean.append(float(mean_us.strip()))
            except ValueError:
                raise ValueError(f"Invalid 'mean_us' value: {mean_us}")
        else:
            raise ValueError(f"Missing 'mean_us' in row: {row}")
        if min_us and min_us.strip():
            try:
                raw_data.min.append(float(min_us))
            except ValueError:
                raise ValueError(f"Invalid 'min_us' value: {min_us}")
        else:
            raise ValueError(f"Missing 'min_us' in row: {row}")
        if max_us and max_us.strip():
            try:
                raw_data.max.append(float(max_us))
            except ValueError:
                raise ValueError(f"Invalid 'max_us' value: {max_us}")
        else:
            raise ValueError(f"Missing 'max_us' in row: {row}")
        if all_lat_str and all_lat_str != "[]":
            result.all_latency = [int(x) for x in all_lat_str.strip("[]").split("; ")]

    # Compute summary statistics only if we have valid values
    result.mean = sum(raw_data.mean) / len(raw_data.mean) if raw_data.mean else None
    result.min = min(raw_data.min) if raw_data.min else None
    result.max = max(raw_data.max) if raw_data.max else None


def process_directory(directory: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process all `latency_all.txt` files in a directory to compute latency metrics.

    Args:
        directory: The root directory containing the benchmark result files.

    Returns:
        A dictionary containing lists of mean, min, max, and all latency values,
        with each list item being a dictionary representing a processed file.
    """
    processed_results = ProcessedResults()
    # Get sorted latency_all.txt files by modification time
    sorted_files = get_sorted_files_by_mtime(directory, "latency_all.txt")
    for file_path in sorted_files:
        if any(key in file_path for key in EXCLUDED_TESTS):
            # Skip files that are not relevant for this processing
            continue
        if file_path.endswith("latency_all.txt"):
            root = os.path.dirname(file_path)  # Get root directory for cleaned path
            sections = extract_sections(file_path)

            avg_pub = ComputedResults()
            avg_sub = ComputedResults()
            avg_client = ComputedResults()
            avg_service = ComputedResults()
            avg_action_cli = ComputedResults()
            avg_action_srv = ComputedResults()

            calculate_metrics_from_section(sections["publishers"], avg_pub)
            calculate_metrics_from_section(sections["subscriptions"], avg_sub)
            calculate_metrics_from_section(sections["clients"], avg_client)
            calculate_metrics_from_section(sections["services"], avg_service)
            calculate_metrics_from_section(sections["action_clients"], avg_action_cli)
            calculate_metrics_from_section(sections["action_servers"], avg_action_srv)

            # Remove leading "./" from the directory path
            clean_root = root[2:] if root.startswith("./") else root
            processed_results.mean.append(
                {
                    "Directory": clean_root,
                    "PubDur": avg_pub.mean,
                    "SubLat": avg_sub.mean,
                    "CliLat": avg_client.mean,
                    "SrvLat": avg_service.mean,
                    "ActionCliLat": avg_action_cli.mean,
                    "ActionSrvLat": avg_action_srv.mean,
                }
            )
            processed_results.min.append(
                {
                    "Directory": clean_root,
                    "PubDur": avg_pub.min,
                    "SubLat": avg_sub.min,
                    "CliLat": avg_client.min,
                    "SrvLat": avg_service.min,
                    "ActionCliLat": avg_action_cli.min,
                    "ActionSrvLat": avg_action_srv.min,
                }
            )
            processed_results.max.append(
                {
                    "Directory": clean_root,
                    "PubDur": avg_pub.max,
                    "SubLat": avg_sub.max,
                    "CliLat": avg_client.max,
                    "SrvLat": avg_service.max,
                    "ActionCliLat": avg_action_cli.max,
                    "ActionSrvLat": avg_action_srv.max,
                }
            )
            processed_results.all_latency.append(
                {
                    "Directory": clean_root,
                    "PubDur": avg_pub.all_latency,
                    "SubLat": avg_sub.all_latency,
                    "CliLat": avg_client.all_latency,
                    "SrvLat": avg_service.all_latency,
                    "ActionCliLat": avg_action_cli.all_latency,
                    "ActionSrvLat": avg_action_srv.all_latency,
                }
            )
    return processed_results


def generate_average_latency_csv(
    results: list, output_file_path: str, show_console: bool = False
):
    """
    Generate a CSV file containing average latency data and optionally print the content to the console.

    Args:
        results: A list of computed results to be written to the CSV.
        output_file_path: Path where the CSV file will be saved.
        show_console: If True, print the CSV content to the console.
    """
    metric = os.path.basename(output_file_path).removesuffix(".csv").replace("_", " ")
    print(f"Writing {metric} results to {output_file_path}")

    with open(output_file_path, "w", newline="") as csvfile:
        fieldnames = [
            "Directory",
            "PubDur",
            "SubLat",
            "CliLat",
            "SrvLat",
            "ActionCliLat",
            "ActionSrvLat",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        if show_console:
            print(";".join(fieldnames))

        for result in results:
            row = {
                "Directory": result["Directory"],
                "PubDur": format_data_for_csv(result["PubDur"]),
                "SubLat": format_data_for_csv(result["SubLat"]),
                "CliLat": format_data_for_csv(result["CliLat"]),
                "SrvLat": format_data_for_csv(result["SrvLat"]),
                "ActionCliLat": format_data_for_csv(result["ActionCliLat"]),
                "ActionSrvLat": format_data_for_csv(result["ActionSrvLat"]),
            }
            writer.writerow(row)

            if show_console:
                print(";".join(str(row[field]) for field in fieldnames))


def format_data_for_csv(value: Union[int, float, list]) -> str:
    """
    Processes the input value:
    - Rounds it to 2 decimal places if it's a number (int or float).
    - Leaves it unchanged if it's a valid list or other non-numeric type.

    Args:
        value: The value or list to be processed.

    Returns:
        The processed value, either a rounded number, the original value, or an empty string.
    """
    return (
        round(value, 2)
        if isinstance(value, (int, float))
        else value if value is not None else ""
    )


def group_by_vendor(
    dirs: List[str], values: List[List[float]], process_type: str
) -> Tuple[str, Dict, Dict, Dict, Dict]:
    """
    Group the data by vendor for the given process type.

    Args:
        dirs: A list of directory names containing the data.
        values: A list of associated values to be grouped.
        process_type: The type of process used for grouping.

    Returns:
        A dictionary containing the data grouped by vendor.
    """
    grouped_mean = defaultdict(list)
    grouped_min = defaultdict(list)
    grouped_max = defaultdict(list)
    grouped_all = defaultdict(list)
    test_case = None

    for dir, mean, min_val, max_val, all_vals in zip(dirs, *values):
        path = dir.split("/")

        # Processes directories that match the process type and don't correspond to long tests
        if f"pub-sub_{process_type}" in dir and "long" not in dir:
            if process_type == "single_process":
                vendor = path[-1]
            elif process_type == "multi_process" or process_type == "mix_process":
                vendor = path[-2]
            else:
                print(f"Process type: {process_type} not supported")
                continue
            test_case = path[3]
            payload = next(
                (size for size in PAYLOAD_MAPPING.keys() if size in dir), None
            )

            grouped_mean[vendor].append({payload: mean})
            grouped_min[vendor].append({payload: min_val})
            grouped_max[vendor].append({payload: max_val})
            grouped_all[vendor].append({payload: all_vals})

    return test_case, grouped_mean, grouped_min, grouped_max, grouped_all


def process_data(
    data: List[Dict[str, Any]],
) -> Tuple[List[float], List[float], List[Any]]:
    """
    Extracts payload sizes and corresponding latency values for plotting.

    Args:
        data: A list of dictionaries, where each entry contains payload-keyed data.

    Returns:
        A tuple of two lists: payload sizes (x-axis) and latency values (y-axis).
    """
    x_payloads, y_values, fixed_values = [], [], []

    for entry in data:
        for key, value in entry.items():
            if key is None:
                continue
            payload_key = next((size for size in PAYLOAD_MAPPING if size in key), None)

            # Store the fixed-size values separately
            if "fixed_size" in key:
                fixed_values.append(value)
            else:
                # Map the payload name to number
                x_payloads.append(PAYLOAD_MAPPING[payload_key])
                # Store the corresponding metric value
                y_values.append(value)

    x_payloads, y_values = zip(*sorted(zip(x_payloads, y_values)))

    return x_payloads, y_values, fixed_values


def compute_linear_regression(latency_values: List[Dict[str, Any]]):
    """
    Computes linear regression for a given latency metric vs. payload size.

    Args:
        latency_values: A list containing dictionaries of all latency measurements for each payload.

    Returns:
        A tuple containing the slope, intercept, and r-squared value.
    """
    x_values_expanded = []
    y_values_expanded = []

    for latency in latency_values:
        for key, values in latency.items():
            # Skip the cases with fixed payload size
            if key is None:
                continue
            # Use PAYLOAD_MAPPING to get the corresponding x value
            x_value = next(
                (
                    PAYLOAD_MAPPING[payload]
                    for payload in PAYLOAD_MAPPING
                    if payload in key
                ),
                None,
            )

            num_measurements = len(values)
            # Expand x_value to match the number of measurements
            x_values_expanded.extend(np.repeat(x_value, num_measurements))
            y_values_expanded.extend(values)

    # Convert the list to a numpy array
    x_values_array = np.array(x_values_expanded)
    y_values_array = np.array(y_values_expanded)

    return linregress(x_values_array, y_values_array)


def generate_report_csv(
    data: Dict[str, Any],
    csv_report_file: str,
    first_write: bool = False,
    show_console: bool = False,
):
    """
    Writes insights and relevant data to a CSV file to be used when generating the report.

    Args:
        data (dict): Dictionary containing the relevant data (e.g., {'r_squared': 0.98, 'slope': 2.5, 'intercept': 1.2}).
        csv_report_file (str): Path to the CSV file to save the report.
        first_write (bool): If True, overwrites the output file and writes the header.
        show_console (bool): If True, print the data to the console.
    """
    mode = "w" if first_write else "a"

    # Write to CSV
    with open(csv_report_file, mode=mode, newline="") as report_csv:
        if first_write:
            csv_header = "RMW;r-squared;slope"
            report_csv.write(f"{csv_header}\n")

        for vendor, metrics in data.items():
            report_csv.write(f"{vendor};{metrics['r_squared']:4f};{metrics['slope']}\n")

    if show_console:
        print("Report Data:")
        for key, value in data.items():
            print(f"{key}: {value}")


def plot_latency_metrics(
    processed_results: ProcessedResults,
    output_file: str,
    csv_report_file: str,
    show_plot: bool,
):
    """
    Plot the latency metrics for all directories in a single horizontal plot with different symbols.

    Args:
        processed_results: The processed data containing latency metrics.
        output_file: Path where the plot image will be saved.
        csv_report_file: Path to the CSV report file.
        show_plot: If True, display the plot after generating it.
    """
    directories = [result["Directory"] for result in processed_results.mean]
    metrics = {
        "PubDur": [
            [result["PubDur"] or 0 for result in results]
            for results in (
                processed_results.mean,
                processed_results.min,
                processed_results.max,
            )
        ],
        "SubLat": [
            [result["SubLat"] or 0 for result in results]
            for results in (
                processed_results.mean,
                processed_results.min,
                processed_results.max,
            )
        ],
    }
    # Add all latency values
    metrics["PubDur"].append(
        [result["PubDur"] or 0 for result in processed_results.all_latency]
    )
    metrics["SubLat"].append(
        [result["SubLat"] or 0 for result in processed_results.all_latency]
    )

    # Vendor colors for differentiation
    colors = ["b", "r", "g", "c", "m", "y", "k", "#ff7f0e"]

    # Iterate over process types
    for process_type in PROCESS_MAPPING.keys():
        # Skip the mix_process type. This case is handled separately.
        if process_type == "mix_process":
            continue

        report_data = defaultdict()
        # Plot each metric in a separate figure
        for metric, values in metrics.items():
            # Filter out zero values (if any)
            all_values_filtered = [
                [val for val in sublist if val > 0]
                for sublist in values[3]
                if isinstance(sublist, list)
            ]
            filtered_values = [
                [val for val in value_list if val > 0] for value_list in values[:-1]
            ] + [all_values_filtered]
            filtered_dirs = [
                directories[i] for i, val in enumerate(values[0]) if val > 0
            ]

            # Group the data by vendor
            (
                test_case,
                grouped_mean_metrics,
                grouped_min_metrics,
                grouped_max_metrics,
                grouped_all_metrics,
            ) = group_by_vendor(filtered_dirs, filtered_values, process_type)
            test_case_str = (
                next((v for k, v in PROCESS_MAPPING.items() if k in test_case), None)
                if test_case
                else ""
            )

            # Limit the number of vendors per figure
            chunks = split_vendors(grouped_mean_metrics)

            # Create plot to compare all vendors
            fig_all, ax_all = plt.subplots(figsize=(12, 8))
            fig_all.suptitle(
                f"{SECTIONS_MAPPING[metric]} Latency - {test_case_str} - Mean comparison",
                fontsize=14,
            )

            # Iterate over chunks of vendors. Each chunk will create a separate figure
            for fig_idx, vendors_chunk in enumerate(chunks):

                n_rows = math.ceil(len(vendors_chunk) / 2)

                # Create subplots for each vendor
                fig, axis = plt.subplots(n_rows, 2, figsize=(12, 4 * n_rows))
                fig.suptitle(
                    f"{SECTIONS_MAPPING[metric]} Latency - {test_case_str}", fontsize=14
                )

                axis = axis.flatten()

                # Find the highest max_y_value across all vendors to set the y scale
                max_y_limit = 0

                # Loop over the max values to find the highest max_y_value with 10% padding to max limit
                for _, max_data in grouped_max_metrics.items():
                    _, max_y_values, _ = process_data(max_data)
                    max_y_limit = 1.1 * max(max_y_limit, max(max_y_values))

                # Hide unused subplots
                for i in range(len(grouped_mean_metrics), len(axis.flatten())):
                    axis[i].axis("off")

                for i, vendor in enumerate(vendors_chunk):
                    ax = axis[i]
                    mean_data = grouped_mean_metrics[vendor]
                    min_data = grouped_min_metrics[vendor]
                    max_data = grouped_max_metrics[vendor]
                    all_data = grouped_all_metrics[vendor]
                    color = colors[i + fig_idx * VENDORS_PER_FIG - 1]

                    # Process the data to extract payloads and separate fixed-size values
                    x_payloads, mean_y_values, _ = process_data(mean_data)
                    _, min_y_values, _ = process_data(min_data)
                    _, max_y_values, _ = process_data(max_data)

                    # Create a plot for each metric
                    ax.plot(
                        x_payloads,
                        mean_y_values,
                        label="mean",
                        color="b",
                        marker="o",
                        linestyle="-",
                    )
                    ax.plot(
                        x_payloads,
                        min_y_values,
                        label="min",
                        color="r",
                        marker="o",
                        linestyle="-",
                    )
                    ax.plot(
                        x_payloads,
                        max_y_values,
                        label="max",
                        color="g",
                        marker="o",
                        linestyle="-",
                    )

                    # Create a plot for the overall mean comparison
                    ax_all.plot(
                        x_payloads,
                        mean_y_values,
                        label=vendor,
                        color=color,
                        marker="o",
                        linestyle="-",
                    )

                    # Compute and plot the linear regression for mean values
                    slope, intercept, r_value, _, _ = compute_linear_regression(
                        all_data
                    )
                    x_reg = np.linspace(10, int(1e7), 1000)
                    y_reg = intercept + slope * x_reg
                    ax.plot(
                        x_reg,
                        y_reg,
                        label="Linear Regression",
                        color="k",
                        linestyle="--",
                    )

                    # Calculate and save the value of R-squared
                    r_squared = r_value**2
                    report_data[process_type + "/" + vendor] = {
                        "r_squared": r_squared,
                        "slope": slope,
                    }

                    # Set the y-axis limit to the highest found
                    ax.set_ylim(0, max_y_limit)
                    # Set plot labels and title
                    ax.set_xlabel("Payload [bytes]")
                    ax.set_ylabel("Latency [us]")
                    ax.set_xscale("log")
                    ax.set_title(f"{vendor}")

                    # Add a grid and legend
                    ax.grid(True, linestyle="--", alpha=0.7)
                    ax.legend(title="Metric", loc="upper left", bbox_to_anchor=(0, 1))

                fig.tight_layout()

                # Save the plot as a PNG file with a unique name based on the metric
                suffix = f"_{fig_idx}" if fig_idx > 0 else ""
                metric_output_file = f"{output_file}_{test_case}_{metric}{suffix}.png"
                fig.savefig(metric_output_file)

            # Add legend for the overall comparison plot
            ax_all.set_xlabel("Payload [bytes]")
            ax_all.set_ylabel("Latency [us]")
            ax_all.set_xscale("log")
            ax_all.grid(True, linestyle="--", alpha=0.7)
            ax_all.legend(title="Vendor", loc="upper left", bbox_to_anchor=(0, 1))

            fig_all.tight_layout()
            fig_all.savefig(f"{output_file}_{test_case}_{metric}_comparison.png")

            # Optionally show the plot
            if show_plot:
                plt.show()

            # Close the current figure to avoid overlap with next plot
            plt.close()

        # Generate the CSV for the report with the processed data
        generate_report_csv(report_data, csv_report_file)


def main():
    # Create the argument parser
    parser = argparse.ArgumentParser(
        description="""
Parse and analyze latency data from benchmark results. This script extracts latency
metrics from `latency_all.txt` files, calculates aggregate statistics, generates
CSV summary files, and creates plots to visualize latency vs. payload size for
different RMW implementations and process configurations.
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

    csv_output_file = os.path.join(parsed_results_directory, "average_latency.csv")
    csv_all_lat_output_file = os.path.join(parsed_results_directory, "all_latency.csv")
    csv_report_file = os.path.join(parsed_results_directory, "report_latency.csv")
    generate_report_csv({}, csv_report_file, first_write=True)

    # Process the results directory to gather the data from the tests
    processed_results = ProcessedResults()
    processed_results = process_directory(args.results_directory)

    # Validate that all metrics (mean, min, max) contain data
    if (
        not processed_results.mean
        or not processed_results.min
        or not processed_results.max
    ):
        print("Error: no valid data found to process.")
        sys.exit(1)

    # Generate CSV
    generate_average_latency_csv(
        processed_results.mean, csv_output_file, args.show_console
    )
    generate_average_latency_csv(
        processed_results.all_latency, csv_all_lat_output_file, args.show_console
    )

    # Generate plots for latency metrics
    output_plot = os.path.join(parsed_results_directory, "latency")
    plot_latency_metrics(
        processed_results, output_plot, csv_report_file, args.show_plot
    )


if __name__ == "__main__":
    main()
