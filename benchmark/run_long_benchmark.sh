#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script runs a series of long-duration benchmarks to evaluate the stability and
# performance of the system over an extended period.
#
# It executes benchmarks for single-process pub/sub, client/server, and actions, as well
# as memory benchmarks.
#
# This script is typically called by `run_all_benchmarks.sh`, but it can also be run
# manually for targeted long-duration testing.
#
# =================================================================================================

# The absolute path where this script is located
THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"

# Default values for optional arguments
test_duration=600 # 10 minutes
output_path=""
generate_results=true

# Function to display help
print_help() {
    echo "Usage: $0 [options]"
    echo
    echo "This script runs a series of long-duration benchmarks to test system stability."
    echo
    echo "Options:"
    echo "  -h, --help             Display this help message and exit"
    echo "  -t <duration>          Specify the duration (in seconds) of each test."
    echo "                         Must be an integer >= 1. Defaults to 600 seconds (10 minutes)."
    echo "  --output <path>        Specify the output path where to write tests results."
    echo "                         If empty, a new directory will be created."
    echo "  --no-results           This flag is included for compatibility but is not used, as this"
    echo "                         script does not generate reports."
    echo
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            print_help
            exit 0
            ;;
        -t)
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                test_duration="$2"
                shift
            else
                echo "Error: -t requires a duration value."
                exit 1
            fi
            ;;
        --output)
            if [[ -n "$2" && ! "$2" =~ ^- ]]; then
                output_path="$2"
                shift
            else
                echo "Error: --output requires a path."
                exit 1
            fi
            ;;
          --no-results)
            # This script doesn't generate results, but we parse the arg to avoid errors.
            generate_results=false
            ;;
        *)
            echo "Error: Unknown option $1"
            print_help
            exit 1
            ;;
    esac
    shift
done

# Check required variables
if [ -z "${PERF_FRAMEWORK_INSTALL_DIR}" ]; then
  echo "You must provide the \`PERF_FRAMEWORK_INSTALL_DIR\` env variable"
  echo "This must point to the directory where the ROS 2 performance framework has been installed"
  exit 1
fi
if [ ! -d "${PERF_FRAMEWORK_INSTALL_DIR}" ]; then
  echo "The \`PERF_FRAMEWORK_INSTALL_DIR\` env variable points to a non-existent directory"
  echo "${PERF_FRAMEWORK_INSTALL_DIR}"
  exit 1
fi

# Check if the script is run as root
if [[ $EUID -ne 0 ]]; then
  echo "You must run $0 with sudo or as root."
  exit 1
fi

# Ensure test duration is valid
if [[ "$test_duration" -lt 1 ]]; then
    echo "Error: Duration must be at least 1 second."
    exit 1
fi

# Set output path if not provided
if [[ -z "$output_path" ]]; then
    current_date=$(date +"%d_%m_%y_%Hh%M")
    output_path="/benchmark_results/results_${current_date}"
fi
mkdir -p "$output_path"
echo "Storing results in $output_path"

run_benchmark() {
  local script=$1
  local config=$2

  # Fix relative paths pre-pending default prefix
  if [[ ! "${script}" =~ ^/ ]]; then
    script="${THIS_DIR}/scripts/${script}"
  fi
  if [[ ! "${config}" =~ ^/ ]]; then
    config="${THIS_DIR}/test-matrix/${config}"
  fi

  echo "Running: $script with config: $config and test duration=$test_duration"
  bash "$script" "$config"
  local exit_code=$?

  if [ $exit_code -ne 0 ]; then
    echo -e "\033[31m[ERROR] $script $config failed with exit code $exit_code\033[0m"
    exit $exit_code
  else
    echo -e "\033[32m[SUCCESS] $script $config completed successfully\033[0m"
  fi
}

# These env variables are used by the various scripts
export ROS2_BENCHMARK_SCRIPTS_DIR=${THIS_DIR}/scripts
export ROS2_BENCHMARK_OUTPUT_DIR=${output_path}
export ROS2_BENCHMARK_TEST_DURATION=${test_duration}

RUNNERS_DIR=${ROS2_BENCHMARK_SCRIPTS_DIR}/runners

# === Long-Duration Benchmarks ===

# Run a long-duration test for single-process pub/sub communication.
echo "Starting long-duration single-process pub/sub benchmark..."
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_pub_sub_long.conf"

# Run a long-duration test for single-process client/server communication.
echo "Starting long-duration single-process client/server benchmark..."
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_cli_srv_long.conf"

# Run a long-duration test for single-process action communication.
echo "Starting long-duration single-process actions benchmark..."
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_actions_long.conf"

# Run memory benchmarks.
echo "Starting memory benchmarks..."
run_benchmark "${RUNNERS_DIR}/run_memory_benchmark.sh" "memory_test.conf"

echo "All long-duration benchmarks completed successfully."
echo "Results saved in ${output_path}"
echo "To generate the PDF report, run 'generate_all_metrics.sh' on the results directory."

