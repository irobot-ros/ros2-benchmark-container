#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
Utility Functions for Benchmark Post-Processing.

This module provides common helper functions used across the different parsing
and analysis scripts in the `post-processing` directory. These functions handle
repetitive tasks such as finding files, parsing file sections, and processing
raw metric data.
"""

import os
from typing import List, Dict, Tuple, Any

import pandas as pd

# Define a threshold for maximum acceptable latency in microseconds (1,000,000,000 us = 1,000 s).
# Latency values above this are considered erroneous and are reset to 0.
MAX_LATENCY_US = 1_000_000_000

# Defines the maximum number of vendors to display in a single plot figure.
# This is used by the `split_vendors` function to chunk vendor lists.
MAX_VENDORS_PER_FIG = 8


def get_sorted_files_by_mtime(directory: str, file_name: str) -> List[str]:
    """
    Finds all files with a specific name within a directory and its subdirectories,
    then sorts them by their last modification time in ascending order.

    Args:
        directory: The root directory to search within.
        file_name: The name of the file to search for (e.g., 'resources.txt').

    Returns:
        A list of full file paths, sorted from oldest to newest.
    """
    files = [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files
        if file == file_name
    ]
    return sorted(files, key=lambda f: os.path.getmtime(f))


def extract_sections(file_path: str) -> Dict[str, List[str]]:
    """
    Extracts content from different sections within a `latency_all.txt` file.

    The file is expected to be structured with section headers like
    '-- Subscriptions stats --' or '-- Publishers stats --'. This function
    parses the file and groups the lines under their respective section.

    Args:
        file_path: The path to the file to be processed.

    Returns:
        A dictionary where keys are section names (e.g., 'subscriptions',
        'publishers') and values are lists of the lines belonging to that section.
    """
    sections = {
        "subscriptions": [],
        "publishers": [],
        "clients": [],
        "services": [],
        "action_clients": [],
        "action_servers": [],
    }
    current_section = None

    with open(file_path, "r") as f:
        for line in f:
            line_lower = line.lower()
            if "action clients stats:" in line_lower:
                current_section = "action_clients"
            elif "action servers stats:" in line_lower:
                current_section = "action_servers"
            elif "clients stats:" in line_lower:
                current_section = "clients"
            elif "services stats:" in line_lower:
                current_section = "services"
            elif "subscriptions stats:" in line_lower:
                current_section = "subscriptions"
            elif "publishers stats:" in line_lower:
                current_section = "publishers"
            elif current_section and line.strip():
                sections[current_section].append(line)

    return sections


def process_metrics_in_directory(
    directory: str,
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Reads a 'resources.txt' file from a directory and extracts key performance metrics.

    Args:
        directory: The path to the directory containing the 'resources.txt' file.

    Returns:
        A tuple of pandas Series containing:
        - Time in milliseconds (time_ms)
        - CPU usage percentage (cpu_perc)
        - Resident Set Size in kilobytes (rss_KB)
        - Virtual Memory Size in kilobytes (vsz_KB)
        - Latency in microseconds (latency_us), with outliers filtered.
    """
    file_path = os.path.join(directory, "resources.txt")
    resources_data = pd.read_csv(file_path)

    # Extract metrics into pandas Series
    cpu_perc = resources_data["cpu_perc"].astype(float)
    rss_KB = resources_data["rss_KB"].astype(float)
    vsz_KB = resources_data["vsz_KB"].astype(float)
    time_ms = resources_data["time_ms"]

    # Filter out exceptionally large latency values, which are likely errors
    resources_data["latency_us"] = resources_data["latency_us"].apply(
        lambda x: 0 if x > MAX_LATENCY_US else x
    )
    latency_us = resources_data["latency_us"].astype(float)

    return time_ms, cpu_perc, rss_KB, vsz_KB, latency_us


def split_vendors(vendor_data: Dict[str, Any]) -> List[List[str]]:
    """
    Splits a list of vendor names into smaller chunks for plotting.

    This is used to prevent plots from becoming too cluttered by limiting the
    number of vendors displayed on a single figure.

    Args:
        vendor_data: A dictionary with vendor names as keys.

    Returns:
        A list of lists, where each inner list is a chunk of vendor names.
    """
    vendors = list(vendor_data.keys())
    return [
        vendors[i : i + MAX_VENDORS_PER_FIG]
        for i in range(0, len(vendors), MAX_VENDORS_PER_FIG)
    ]
