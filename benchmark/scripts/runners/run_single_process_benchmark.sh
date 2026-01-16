#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script runs single-process benchmarks for the ROS 2 performance testing framework.
#
# It is designed to launch a single performance test process that contains all the
# nodes defined in a given topology file. This makes it ideal for measuring
# intra-process communication performance.
#
# The script takes a configuration file that defines the test matrix, including:
# - `RMW_LIST`: A list of RMW implementations to test.
# - `TOPOLOGIES`: A list of topology files to run.
# - `COMMS_<RMW>`: Communication modes to test for each RMW (e.g., ipc_on, ipc_off, loaned).
#
# It also supports a `--remote-host-mode` for testing discovery with remote nodes.
#
# =================================================================================================

# --- Argument Validation ---
if [ $# -lt 1 ]; then
  echo "Usage: $0 <config_file> [options]"
  echo "  <config_file>: Path to the configuration file defining the test matrix."
  echo "  --remote-host-mode <mode>: 'publisher' or 'subscriber' to add a remote process to the test."
  exit 1
fi

CONFIG_FILE=$1
shift # Shift arguments to parse options

if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "\033[31m[ERROR] Configuration file '$CONFIG_FILE' not found!\033[0m"
  exit 1
fi

# Set default test duration if not provided externally.
if [ -z "${ROS2_BENCHMARK_TEST_DURATION}" ]; then
  ROS2_BENCHMARK_TEST_DURATION=1
fi

# --- Option Parsing ---
REMOTE_HOST_MODE="none"
while [[ $# -gt 0 ]]; do
  case "$1" in
  --remote-host-mode)
    if [[ -n "$2" && ! "$2" =~ ^- ]]; then
      REMOTE_HOST_MODE="$2"
      shift
    else
      echo "Error: --remote-host-mode requires a value (e.g., 'publisher' or 'subscriber')"
      exit 1
    fi
    ;;
  *)
    echo "Error: Unknown option $1"
    exit 1
    ;;
  esac
  shift
done

echo "Loading configuration from: $CONFIG_FILE"
source "$CONFIG_FILE"

# --- Environment Setup & Validation ---
GOVERNOR_SCRIPT="${ROS2_BENCHMARK_SCRIPTS_DIR}/utils/set_cpu_governor.sh"
IROBOT_BENCHMARK="${PERF_FRAMEWORK_INSTALL_DIR}/irobot_benchmark/irobot_benchmark"

# Possible args for different executor types
declare -A EXECUTOR_ARGS=( ["SingleThreadedExecutor"]="1" ["EventsExecutor"]="2" ["MultiThreadedExecutor"]="3")

# Configure system executor, using the EventsExecutor by default. 
if [[ -z "${SYSTEM_EXECUTOR}" ]]; then
  SYSTEM_EXECUTOR="EventsExecutor"
fi

if [[ -v EXECUTOR_ARGS[${SYSTEM_EXECUTOR}] ]]; then
    EXECUTOR_ARG="${EXECUTOR_ARGS[${SYSTEM_EXECUTOR}]}"
else 
  echo -e "Invalid executor ${SYSTEM_EXECUTOR}. Please choose from SingleThreadedExecutor, MultiThreadedExecutor or EventsExecutor."
  exit 1
fi

# Set CPU governor to 'performance' mode for consistent results.
original_governor=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor)
echo "Setting CPU governor to 'performance'."
$GOVERNOR_SCRIPT performance
if [ $? -ne 0 ]; then
  echo -e "\033[31m[ERROR] Failed to set CPU governor. Exiting.\033[0m"
  exit 1
fi
# Ensure the original governor is restored when the script exits.
trap "$GOVERNOR_SCRIPT $original_governor" EXIT

# Validate that essential variables are defined in the config file.
if [[ -z "${RMW_LIST}" || -z "${TOPOLOGIES}" ]]; then
  echo -e "\033[31m[ERROR] Required test matrix variables 'RMW_LIST' or 'TOPOLOGIES' are not defined in '$CONFIG_FILE'!\033[0m"
  exit 1
fi

# --- Output Directory Setup ---
# Append a suffix to the output directory if running in remote host mode.
OUTPUT_DIR="${ROS2_BENCHMARK_OUTPUT_DIR}/${OUTPUT_DIR_NAME}"
if [[ "$REMOTE_HOST_MODE" != "none" ]]; then
  OUTPUT_DIR="${ROS2_BENCHMARK_OUTPUT_DIR}/${OUTPUT_DIR_NAME}_remote_host"
fi
echo "Results will be stored in: $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR" && mkdir -p "$OUTPUT_DIR"

# --- Benchmark Execution Loop ---
for RMW in "${RMW_LIST[@]}"; do
  echo -e "\n\033[1;34mProcessing RMW: $RMW\033[0m"

  # Set the RMW_IMPLEMENTATION for the benchmark process.
  export RMW_IMPLEMENTATION="rmw_${RMW}_cpp"

  # Dynamically get the COMMS and LOANED_ENV_VARS arrays for the current RMW.
  declare -n COMMS="COMMS_${RMW}"
  declare -n LOANED_ENV_VARS="LOANED_ENV_VARS_${RMW}"
  echo "  COMMS for $RMW: ${COMMS[@]}"
  echo "  LOANED_ENV_VARS for $RMW: ${LOANED_ENV_VARS[@]}"

  for COMM in "${COMMS[@]}"; do
    echo -e "\n  \033[1;32mTesting COMM: $COMM\033[0m"

    # Export specific environment variables if running a 'loaned' message test.
    if [[ "$COMM" == "loaned" ]]; then
      for VAR in "${LOANED_ENV_VARS[@]}"; do
        eval "$VAR"
      done
    fi

    # Set the --ipc flag based on the communication mode.
    IPC_OPTION="--ipc off"
    if [[ "$COMM" == "ipc_on" ]]; then
      IPC_OPTION="--ipc on"
    fi

    # Loop through each topology defined in the config file.
    for TOPOLOGY in "${TOPOLOGIES[@]}"; do
      TEST_CASE_DIR="${OUTPUT_DIR}/${TOPOLOGY}"
      mkdir -p "${TEST_CASE_DIR}"

      # Select the correct topology file, using the '_loaned' version if required.
      if [[ "$COMM" == "loaned" ]]; then
        TOPOLOGY_PATH="${TOPOLOGIES_DIR}/${TOPOLOGY}_loaned.json"
      else
        TOPOLOGY_PATH="${TOPOLOGIES_DIR}/${TOPOLOGY}.json"
      fi

      RESULT_FOLDER="${TEST_CASE_DIR}/${RMW}_${COMM}"
      echo -e "    \033[32m-> Running topology: $TOPOLOGY\033[0m"
      echo "       Results will be in: $RESULT_FOLDER"

      # --- Remote Host Logic ---
      # If a remote mode is specified, launch a sibling container to act as a remote node.
      if [[ "$REMOTE_HOST_MODE" != "none" ]]; then
        if [[ "$REMOTE_HOST_MODE" == "publisher" ]]; then
            SCRIPT_FOR_REMOTE_HOST="set -e; source $PWD/install/setup.bash; sleep 5; echo 'Publishing...'; ros2 topic pub /test irobot_interfaces_plugin/msg/Stamped1mb -r 1 --times 5; echo 'Done.'; exit"
        elif [[ "$REMOTE_HOST_MODE" == "subscriber" ]]; then
            SCRIPT_FOR_REMOTE_HOST="set -e; source /root/install/setup.bash; sleep 5; for topic in \$(ros2 topic list | grep -E '^/test(_[0-9]+)?$'); do echo \"Subscribing to \$topic...\"; ros2 topic echo \"\$topic\" > /dev/null & done; wait; echo 'Done subscribing.';"
        else
            echo "Error: Unknown remote host mode '$REMOTE_HOST_MODE'"
            exit 1
        fi
        echo "       Running remote process in '$REMOTE_HOST_MODE' mode..."
        RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
        "${RUNNER_DIR}/run_remote_process.sh" "$RMW_IMPLEMENTATION" "$SCRIPT_FOR_REMOTE_HOST"
      fi

      # --- Local Benchmark Execution ---
      # Construct and execute the main benchmark command.
      COMMAND="${IROBOT_BENCHMARK} ${TOPOLOGY_PATH} --executor ${EXECUTOR_ARG}  ${IPC_OPTION} -t ${ROS2_BENCHMARK_TEST_DURATION} -s 1000 --csv-out on --results-dir ${RESULT_FOLDER}"
      echo -e "     Command: \n       $COMMAND"

      eval "$COMMAND"

      if [ $? -ne 0 ]; then
        echo -e "\033[31m[ERROR] Command failed: $COMMAND\033[0m"
        exit 1
      fi
    done

    # Unset environment variables at the end of the loop to avoid side effects.
    unset FASTRTPS_DEFAULT_PROFILES_FILE
    unset RMW_FASTRTPS_USE_QOS_FROM_XML
    unset CYCLONEDDS_URI
  done
done

echo -e "\n\033[1;32mSingle-process benchmark run completed successfully.\033[0m"
