#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script is the main entrypoint for running all the ROS 2 benchmarks.
# It executes a series of single-process, multi-process, and mixed-process benchmarks.
# It also runs long-duration benchmarks and memory benchmarks.
#
# This script is typically called by `run_all_benchmarks.sh`, but it can also be run
# manually for targeted testing.
#
# =================================================================================================

# The absolute path where this script is located
THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
# The absolute path where this script is being called from
CALLER_DIR="$(pwd)"

# Default values for optional arguments
test_duration=20
output_path=""
generate_results=true
skip_long_tests=false
skip_remote_host_tests=false

# Function to display help
print_help() {
  echo "Usage: $0 [options]"
  echo
  echo "Options:"
  echo "  -h, --help             Display this help message and exit"
  echo "  -t <duration>          Specify the duration (in seconds) of each test."
  echo "                         Must be an integer >= 1. Defaults to 20 seconds"
  echo "  --output <path>        Specify the output path where to write tests results."
  echo "                         If empty, a new directory will be created where the script is called."
  echo "  --no-results           Skip generating the results. By default, results are generated."
  echo "  --skip-long-tests      Skip long-duration test. By default, these tests are executed and each test lasts 15 minutes."
  echo
  echo "This script runs a collection of benchmarks for ROS 2, including single-process,"
  echo "multi-process, and memory benchmarks. It generates CSV files and a PDF summary report."
  echo
  echo "To add a new test:"
  echo "1. Add a topology JSON file in 'benchmark/topologies'."
  echo "2. Add a test matrix '.conf' file in 'benchmark/test-matrix'."
  echo "3. Add a 'run_benchmark' call in this script."
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
  -h | --help)
    print_help
    exit 0
    ;;
  -t)
    if [[ -n "$2" && ! "$2" =~ ^- ]]; then
      test_duration="$2"
      # Skip long tests if duration is less than 60 seconds
      if [[ "$2" -gt 60 ]]; then
        PASS_TIME_ARG="-t $test_duration" # Prepare argument for script for long tests
      else
        echo "test duration ($2 s) is less than 60 seconds. Skipping long tests."
        skip_long_tests=true
      fi
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
    generate_results=false # Set flag to skip result generation
    ;;
  --skip-long-tests)
    skip_long_tests=true # Set flag to skip long-duration tests
    ;;
  --skip-remote-host-tests)
    skip_remote_host_tests=true # Set flag to skip remote host tests
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
  echo "The \`PERF_FRAMEWORK_INSTALL_DIR\` env variable points to a non-existant directory"
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
  shift 2
  local args=("$@")

  # Fix relative paths pre-pending default prefix
  if [[ ! "${script}" =~ ^/ ]]; then
    script="${THIS_DIR}/scripts/${script}"
  fi
  if [[ ! "${config}" =~ ^/ ]]; then
    config="${THIS_DIR}/test-matrix/${config}"
  fi

  echo "Running: $script with config: $config and test duration=$test_duration"
  bash "$script" "$config" "${args[@]}"
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

# Single-process benchmarks
echo "Starting single-process benchmarks..."
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_pub_sub.conf"

# Multi-process benchmarks
echo "Starting multi-process benchmarks..."
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "multi_process_pub_sub.conf"

# Mix-process benchmarks
echo "Starting mix-process benchmarks..."
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "mix_process_pub_sub.conf"
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "mix_process_pub_sub_multiple_topics.conf"

# Remote host benchmarks
if [ "$skip_remote_host_tests" = false ]; then
  echo "Starting mix-process benchmark with remote host test..."
  run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "mix_process_pub_sub_remote_host.conf" --remote-host-mode "publisher"

  echo "Starting single-process multi-topic benchmark with remote host disabled test..."
  run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_pub_sub_multiple_topics.conf"
  echo "Starting single-process multi-topic benchmark with remote host enabled test..."
  run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_pub_sub_multiple_topics.conf" --remote-host-mode "subscriber"
fi

run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "mix_process_cli_srv.conf"
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "mix_process_actions.conf"

# Memory benchmarks
echo "Starting memory benchmarks..."
run_benchmark "${RUNNERS_DIR}/run_memory_benchmark.sh" "memory_test.conf"

# Long-duration benchmark (15 minutes by default for each test)
if [ "$skip_long_tests" = false ]; then
  echo "Running long test..."
  ${THIS_DIR}/run_long_benchmark.sh --output ${output_path} ${PASS_TIME_ARG}
fi

# Single-process benchmark for Client/Service and ActionCli/ActionSrv interface with multiple clients
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_cli_srv_multiple_clients.conf"
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_actions_multiple_clients.conf"

# Multi-process benchmark for Client/Service and ActionCli/ActionSrv interface with multiple clients
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "multi_process_cli_srv_multiple_clients.conf"

# Run benchmark with very slow publishing (1h period) to measure idle RAM/CPU usage over 60s
export ROS2_BENCHMARK_TEST_DURATION=60
run_benchmark "${RUNNERS_DIR}/run_single_process_benchmark.sh" "single_process_pub_sub_idle.conf"
# Run multi-process scalability benchmark for pub/sub
run_benchmark "${RUNNERS_DIR}/run_multi_process_benchmark.sh" "multi_process_scalability_pub_sub.conf"

# Parse results
if [ "$generate_results" = true ]; then
  echo "Generating results csv..."
  if [ "$skip_long_tests" = false ]; then
    ${THIS_DIR}/generate_all_metrics.sh ${output_path}
  else
    ${THIS_DIR}/generate_all_metrics.sh ${output_path} --skip-long-tests
  fi
else
  echo "Results generation was disabled. To manually generate results csv run the following script:"
  echo "  ${THIS_DIR}/generate_all_metrics.sh ${output_path}"
fi
