#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script runs multi-process benchmarks for the ROS 2 performance testing framework.
#
# It is designed to launch two concurrent performance test processes, making it suitable
# for inter-process communication benchmarks on a single host or distributed tests
# involving a remote host.
#
# The script takes a configuration file that defines the test matrix, including:
# - `RMW_LIST`: A list of RMW implementations to test.
# - `TOPOLOGY1`, `TOPOLOGY2`: Paired lists of topology files. For each test, one
#   process is launched with a topology from TOPOLOGY1 and another with the
#   corresponding one from TOPOLOGY2.
# - `COMMS_<RMW>`: Communication modes to test for each RMW (e.g., ipc_off, loaned).
#
# It also supports a `--remote-host-mode` for distributed testing.
#
# =================================================================================================

# --- Argument Validation ---
if [ $# -lt 1 ]; then
  echo "Usage: $0 <config_file> [options]"
  echo "  <config_file>: Path to the configuration file defining the test matrix."
  echo "  --remote-host-mode <mode>: 'publisher' or 'subscriber' to run one part of the test on a remote machine."
  exit 1
fi

# Set default timeout for how long the script should wait after spawning the router
# before running the benchmarks.
if [[ -z "$ZENOH_ROUTER_WAIT_TIMEOUT" ]]; then
  ZENOH_ROUTER_WAIT_TIMEOUT=1.0
fi


CONFIG_FILE=$1
shift # Shift arguments to parse options

if [ ! -f "$CONFIG_FILE" ]; then
  echo -e "\033[31m[ERROR] Configuration file '$CONFIG_FILE' not found!\033[0m"
  exit 1
fi

# Ensure scripts directory is set if not provided externally.
if [ -z "${ROS2_BENCHMARK_SCRIPTS_DIR}" ]; then
  THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
  ROS2_BENCHMARK_SCRIPTS_DIR="${THIS_DIR}/.."
fi

# Set default output path if not provided externally.
if [[ -z "$ROS2_BENCHMARK_OUTPUT_DIR" ]]; then
  current_date=$(date +"%d_%m_%y_%Hh%M")
  ROS2_BENCHMARK_OUTPUT_DIR="/benchmark_results/results_${current_date}"
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
if [[ -z "${RMW_LIST}" || -z "${TOPOLOGY1}" ]]; then
  echo -e "\033[31m[ERROR] Required test matrix variables 'RMW_LIST' or 'TOPOLOGY1' are not defined in '$CONFIG_FILE'!\033[0m"
  exit 1
fi

RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"

# --- Output Directory Setup ---
OUTPUT_DIR="${ROS2_BENCHMARK_OUTPUT_DIR}/${OUTPUT_DIR_NAME}"
echo "Results will be stored in: $OUTPUT_DIR"
rm -rf "$OUTPUT_DIR" && mkdir -p "$OUTPUT_DIR"

# --- Benchmark Execution Loop ---
for RMW in "${RMW_LIST[@]}"; do
  echo -e "\n\033[1;34mProcessing RMW: $RMW\033[0m"

  # Dynamically get the COMMS and LOANED_ENV_VARS arrays for the current RMW.
  declare -n COMMS="COMMS_${RMW}"
  declare -n LOANED_ENV_VARS="LOANED_ENV_VARS_${RMW}"
  echo "  COMMS for $RMW: ${COMMS[@]}"
  echo "  LOANED_ENV_VARS for $RMW: ${LOANED_ENV_VARS[@]}"

  for COMM in "${COMMS[@]}"; do
    echo -e "\n  \033[1;32mTesting COMM: $COMM\033[0m"

    # Set the RMW_IMPLEMENTATION for the benchmark processes.
    export RMW_IMPLEMENTATION="rmw_${RMW}_cpp"

    # Export specific environment variables if running a 'loaned' message test.
    if [[ "$COMM" == "loaned" ]]; then
      for VAR in "${LOANED_ENV_VARS[@]}"; do
        eval "$VAR"
      done
    fi

    # Loop through the paired topologies defined in the config file.
    for i in "${!TOPOLOGY1[@]}"; do
      if [[ "$RMW" == "zenoh" ]]; then
        # Automatically start the router in the background
        echo "Detected that $RMW is being benchmarked. Spawning router..."

        ${RUNNER_DIR}/run_zenoh_router.sh ${ZENOH_ROUTER_CONFIG_URI} &

        # Wait for the router to come online
        sleep ${ZENOH_ROUTER_WAIT_TIMEOUT}

        ROUTER_PID=$(pgrep zenohd)
        echo "Spawned zenoh router with PID ${ROUTER_PID}"
      fi

      T1="${TOPOLOGY1[i]}"
      T2="${TOPOLOGY2[i]}"
      RES="${RESULTS[i]}"

      echo -e "    \033[32m-> Running topology pair: ($T1, $T2)\033[0m"

      RESULT_FOLDER="${OUTPUT_DIR}/${RES}/${RMW}_${COMM}"
      mkdir -p "$RESULT_FOLDER"

      # Select the correct topology file based on the communication mode.
      if [[ "$COMM" == "loaned" ]]; then
        TOP1_PATH="${TOPOLOGIES_DIR}/${T1}_loaned.json"
      else
        TOP1_PATH="${TOPOLOGIES_DIR}/${T1}.json"
      fi
      TOP2_PATH="${TOPOLOGIES_DIR}/${T2}.json"

      # --- Remote Host Logic ---
      if [[ "$REMOTE_HOST_MODE" != "none" ]]; then
        if [[ "$REMOTE_HOST_MODE" == "publisher" ]]; then
          SCRIPT_FOR_REMOTE_HOST="set -e; source $PWD/install/setup.bash; sleep 5; echo 'Publishing...'; ros2 topic pub /test irobot_interfaces_plugin/msg/Stamped1mb -r 1 --times 5; echo 'Done.'; exit"
        elif [[ "$REMOTE_HOST_MODE" == "subscriber" ]]; then
          SCRIPT_FOR_REMOTE_HOST="set -e; source /root/install/setup.bash; sleep 5; for topic in \$(ros2 topic list | grep -E '^/test(_[0-9]+)?$'); do echo \"Subscribing to \$topic...\"; ros2 topic echo \"\$topic\" > /dev/null & done; wait; echo 'Done subscribing.';"
        else
          echo "Error: Unknown remote host mode '$REMOTE_HOST_MODE'"
          exit 1
        fi
        echo "Running remote process in '$REMOTE_HOST_MODE' mode..."
        RUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"
        "${RUNNER_DIR}/run_remote_process.sh" "$RMW_IMPLEMENTATION" "$SCRIPT_FOR_REMOTE_HOST"
      fi

      # --- Local Benchmark Execution ---
      # Construct and execute the main benchmark command.
      # This launches two processes concurrently using the specified topologies.
      COMMAND="${IROBOT_BENCHMARK} ${TOP1_PATH} ${TOP2_PATH} --executor ${EXECUTOR_ARG} --ipc off -t ${ROS2_BENCHMARK_TEST_DURATION} -s 1000 --csv-out on"
      echo -e "     Command: \n       $COMMAND"

      eval "$COMMAND"

      if [[ -n ${ROUTER_PID} ]]; then 
        echo "Stopping zenoh router with PID $ROUTER_PID"
        kill ${ROUTER_PID}
        while kill -0 "${ROUTER_PID}">/dev/null 2>&1; do
            echo "Waiting for zenoh router to exit.,,"
            sleep 0.1
        done        
        echo "Stopped zenoh router with PID $ROUTER_PID"
        unset $ROUTER_PID
      fi


      if [ $? -ne 0 ]; then
        echo -e "\033[31m[ERROR] Command failed: $COMMAND\033[0m"
        exit 1
      fi

      # Move the generated log files to the appropriate results folder.
      echo "     Moving log files to $RESULT_FOLDER"
      mv ./*log "$RESULT_FOLDER"
    done
        # Unset environment variables at the end of the loop to avoid side effects.
    unset FASTRTPS_DEFAULT_PROFILES_FILE
    unset RMW_FASTRTPS_USE_QOS_FROM_XML
    unset CYCLONEDDS_URI
    unset ZENOH_ROUTER_CONFIG_URI
    unset ZENOH_SESSION_CONFIG_URI
  done
done

echo -e "\n\033[1;32mMulti-process benchmark run completed successfully.\033[0m"
