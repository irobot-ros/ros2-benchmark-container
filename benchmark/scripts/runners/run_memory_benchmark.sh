#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script runs memory benchmarks for the ROS 2 performance testing framework.
#
# It takes a single configuration file as an argument. This file defines the
# test matrix, including the list of RMW implementations to test (`RMW_LIST`)
# and the memory benchmark binaries to run (`MEMORY_TOPOLOGIES`).
#
# For each RMW and binary combination, it executes the corresponding memory
# benchmark and saves the CSV output to a results directory.
#
# =================================================================================================

# --- Argument Validation ---
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <config_file>"
  echo "  <config_file>: Path to the configuration file defining the test matrix."
  exit 1
fi

# --- Configuration Loading ---
CONFIG_FILE=$1
if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "\033[31m[ERROR] Configuration file '$CONFIG_FILE' not found!\033[0m"
  exit 1
fi

echo "Loading configuration from: $CONFIG_FILE"
source "$CONFIG_FILE"

# --- Path and Test Matrix Validation ---
MEMORY_BENCHMARK_DIR="${PERF_FRAMEWORK_INSTALL_DIR}/memory_benchmark"
if [ ! -d "${MEMORY_BENCHMARK_DIR}" ]; then
  echo -e "\033[31m[ERROR] Memory benchmark directory '$MEMORY_BENCHMARK_DIR' not found!\033[0m"
  echo "Please ensure 'PERF_FRAMEWORK_INSTALL_DIR' is set correctly."
  exit 1
fi

if [[ -z "${RMW_LIST}" || -z "${MEMORY_TOPOLOGIES}" ]]; then
  echo -e "\033[31m[ERROR] Required test matrix variables 'RMW_LIST' or 'MEMORY_TOPOLOGIES' are not defined in '$CONFIG_FILE'!\033[0m"
  exit 1
fi

# --- Output Directory Setup ---
OUTPUT_DIR="${ROS2_BENCHMARK_OUTPUT_DIR}/${OUTPUT_DIR_NAME}"
echo "Results will be stored in: $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR" && mkdir -p "$OUTPUT_DIR"

# --- Benchmark Execution Loop ---
# Iterate through each specified RMW implementation.
for RMW in "${RMW_LIST[@]}"; do
  echo -e "\n\033[1;34mProcessing RMW: $RMW\033[0m"

  # Set the RMW_IMPLEMENTATION environment variable for the child processes.
  export RMW_IMPLEMENTATION="rmw_${RMW}_cpp"

  # Iterate through each specified memory benchmark binary.
  for BINARY in "${MEMORY_TOPOLOGIES[@]}"; do
    echo -e "\033[32m  -> Running memory test: $BINARY\033[0m"

    # Define the output file path for the current test run.
    RESULTS_FILE="${OUTPUT_DIR}/${RMW}_${BINARY}.csv"

    # Construct and execute the benchmark command.
    COMMAND="${MEMORY_BENCHMARK_DIR}/${BINARY}"
    echo "     Command: $COMMAND > $RESULTS_FILE"

    # Run the command and redirect output to the results file.
    eval "$COMMAND > $RESULTS_FILE"

    # Check for errors.
    if [ $? -ne 0 ]; then
      echo -e "\033[31m[ERROR] Command failed: $COMMAND\033[0m"
      exit 1
    fi
  done
done

echo -e "\n\033[1;32mMemory benchmark run completed successfully.\033[0m"
