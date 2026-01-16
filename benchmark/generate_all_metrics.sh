#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script processes the raw results from the benchmark runs and generates summarized metrics.
# It calls a series of Python scripts to parse the data, create plots, and generate a final
# PDF report.
#
# This script is typically called by `run_all_benchmarks.sh`, but it can also be run manually
# on an existing results directory.
#
# =================================================================================================

# The absolute path where this script is located
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"

# Default values for optional arguments
skip_long_tests=false
skip_remote_tests=false

# Display help/usage instructions
print_help() {
  echo "Usage: $0 RESULTS_DIRECTORY [OPTIONS]"
  echo
  echo "This script extracts metrics data from a results directory, generates plots,"
  echo "and creates a PDF report summarizing the benchmark results."
  echo
  echo "Options:"
  echo "  --help, -h        Display this help message."
  echo "  --skip-long-tests Skip processing of long-duration test data."
  echo
  echo "Arguments:"
  echo "  RESULTS_DIRECTORY Required directory where the raw benchmark results are located."
  echo
  exit 0
}

# Select results directory
if [ -z "$1" ]; then
  echo "You must provide the benchmark results directory as argument"
  exit 1
fi

# Argument parsing
while [[ $# -gt 0 ]]; do
  case "$1" in
  --help | -h)
    print_help
    ;;
  --skip-long-tests)
    skip_long_tests=true
    shift
    ;;
  --skip-remote-tests)
    skip_remote_tests=true
    shift
    ;;
  -*)
    echo "Unknown option: $1"
    exit 1
    ;;
  *)
    if [ -z "$RESULTS_DIRECTORY" ]; then
      RESULTS_DIRECTORY="$1"
      shift
    else
      echo "Unexpected extra argument: $1"
      exit 1
    fi
    ;;
  esac
done

if [[ ! -d "${RESULTS_DIRECTORY}" ]]; then
  echo "The provided results directory does not exist: ${RESULTS_DIRECTORY}"
  exit 1
fi

PARSING_SCRIPTS_DIR="${THIS_DIR}/scripts/post-processing"

# Parse the main benchmark results.
# These scripts generate CSV files and plots from the raw data.
echo "Parsing main benchmark results..."
python3 ${PARSING_SCRIPTS_DIR}/parse_latency.py ${RESULTS_DIRECTORY}
python3 ${PARSING_SCRIPTS_DIR}/parse_memory_scalability.py ${RESULTS_DIRECTORY}
python3 ${PARSING_SCRIPTS_DIR}/parse_metrics.py ${RESULTS_DIRECTORY}
python3 ${PARSING_SCRIPTS_DIR}/parse_ram_scalability.py ${RESULTS_DIRECTORY}

# Compare the multi-process and single-process metrics.
echo "Comparing single vs. multi-process metrics..."
python3 ${PARSING_SCRIPTS_DIR}/../compare_processes.py ${RESULTS_DIRECTORY}

# Compare the mixed-process metrics.
echo "Comparing mixed-process metrics..."
python3 ${PARSING_SCRIPTS_DIR}/../compare_mix_processes.py ${RESULTS_DIRECTORY}

# Parse metrics for remote host tests if not skipped.
if [ "${skip_remote_tests}" = false ]; then
  echo "Parsing remote host metrics..."
  python3 ${PARSING_SCRIPTS_DIR}/parse_metrics_over_time.py ${RESULTS_DIRECTORY}
fi

# Parse metrics for long-duration tests and generate the final report.
if [ "${skip_long_tests}" = false ]; then
  echo "Parsing long-duration test results..."
  # Parse data for long tests.
  python3 ${PARSING_SCRIPTS_DIR}/parse_latency_long_test.py ${RESULTS_DIRECTORY}
  python3 ${PARSING_SCRIPTS_DIR}/parse_metrics_long_test.py ${RESULTS_DIRECTORY}
  # Generate the PDF report including all metrics.
  echo "Generating PDF report..."
  python3 ${PARSING_SCRIPTS_DIR}/generate_report.py --output ${RESULTS_DIRECTORY} ${RESULTS_DIRECTORY}
else
  # Generate the PDF report without the long-duration test metrics.
  echo "Generating PDF report (skipping long tests)..."
  python3 ${PARSING_SCRIPTS_DIR}/generate_report.py --output ${RESULTS_DIRECTORY} ${RESULTS_DIRECTORY} --skip-long-tests
fi

echo "All metrics generated successfully in ${RESULTS_DIRECTORY}"
