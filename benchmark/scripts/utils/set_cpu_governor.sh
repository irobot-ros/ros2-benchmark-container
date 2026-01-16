#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# Sets the CPU frequency scaling governor for all available CPU policies.
#
# This script is crucial for creating a stable and reproducible environment for
# performance benchmarking. By setting the governor to 'performance', it ensures
# that the CPU operates at its maximum frequency, minimizing variance in test
# results caused by dynamic frequency scaling.
#
# It requires `sudo` privileges to write to the system's `scaling_governor` files.
#
# =================================================================================================

# --- Help Function ---
print_help() {
  echo "Usage: $0 <governor>"
  echo
  echo "This script sets the CPU governor to the specified value for all CPU policies."
  echo "It requires sudo privileges."
  echo
  echo "Common governors:"
  echo "  performance: Locks the CPU at its maximum frequency."
  echo "  powersave:   Locks the CPU at its minimum frequency."
  echo "  ondemand:    Scales frequency based on CPU load (default on many systems)."
  echo
  echo "Example:"
  echo "  sudo $0 performance"
  echo
  exit 0
}

# --- Argument Validation ---
if [[ $# -ne 1 || "$1" == "--help" || "$1" == "-h" ]]; then
  print_help
fi

# The desired governor setting (e.g., "performance").
desired_governor="$1"

# --- Prerequisite Check ---
# Ensure the CPU frequency scaling sysfs directory exists.
if [ ! -d "/sys/devices/system/cpu/cpufreq/" ]; then
  echo -e "\033[31m[ERROR] CPU frequency scaling is not supported or the 'cpufreq' sysfs interface is not available on this system.\033[0m"
  exit 1
fi

# --- Apply Governor ---
echo "Attempting to set CPU governor to '$desired_governor' for all CPU policies..."

# Iterate over all available CPU policies and write the desired governor.
# Using a loop ensures the setting is applied to all cores/clusters.
for policy_file in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do
  # Use 'tee' with sudo to handle permission redirection properly.
  if ! echo "$desired_governor" | sudo tee "$policy_file" > /dev/null; then
    echo -e "\033[31m[ERROR] Failed to set governor for $policy_file.\033[0m"
    echo "Please ensure the script is run with sudo privileges."
    exit 1
  fi
done

# --- Verification ---
# Read back the governor from the first policy to verify the change.
current_governor=$(cat /sys/devices/system/cpu/cpufreq/policy0/scaling_governor)
if [ "$current_governor" != "$desired_governor" ]; then
  echo -e "\033[31m[ERROR] Failed to set CPU governor to '$desired_governor'. Current value is still '$current_governor'.\033[0m"
  exit 1
fi

echo -e "\033[32m[SUCCESS] CPU governor for all policies is now set to '$desired_governor'.\033[0m"
