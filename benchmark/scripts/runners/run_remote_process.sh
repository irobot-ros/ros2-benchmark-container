#!/bin/bash

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This script launches a "remote" ROS 2 process by starting a second Docker container.
#
# It is designed to be run from within the main benchmark container and requires the
# Docker socket to be mounted (`-v /var/run/docker.sock:/var/run/docker.sock`).
#
# The script launches a sibling container using the same Docker image as the main
# container. It passes through necessary ROS 2 and RMW environment variables to
# ensure the two containers can communicate over the host's network. This setup
# simulates a distributed system for testing inter-machine communication.
#
# Arguments:
#   $1: The RMW_IMPLEMENTATION to use (e.g., 'rmw_fastrtps_cpp'). Defaults to 'rmw_cyclonedds_cpp'.
#   $2: The shell command or script to execute inside the new container.
#
# =================================================================================================

# --- Argument Parsing ---
RMW_IMPLEMENTATION="${1:-rmw_cyclonedds_cpp}" # Default middleware if not provided.
CONTAINER_SCRIPT="${2:-}"                   # The script to run in the new container.
CONTAINER_NAME="remote-host-container"       # Name for the new container.

if [ -z "$CONTAINER_SCRIPT" ]; then
    echo "Error: No script provided to run in the container."
    echo "Usage: $0 [RMW_IMPLEMENTATION] [CONTAINER_SCRIPT]"
    exit 1
fi

# --- Prerequisite Checks ---
# Check if the Docker client is available within the current container.
if ! command -v docker &> /dev/null; then
    echo "Error: Docker client not found. Please install docker.io or ensure it's in the PATH."
    exit 1
fi

# Check if the Docker socket is mounted, which is necessary to control Docker.
if [ ! -e "/var/run/docker.sock" ]; then
    echo "Error: Docker socket not found at /var/run/docker.sock."
    echo "Please ensure the main container was run with the volume mount:"
    echo "  -v /var/run/docker.sock:/var/run/docker.sock"
    exit 1
fi

# --- Container Management ---
# Check if a container with the same name is already running and clean it up.
# This prevents naming conflicts on subsequent runs.
if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "Container '${CONTAINER_NAME}' is already running. Stopping and removing it..."
    docker stop "${CONTAINER_NAME}"
    docker rm "${CONTAINER_NAME}"
fi

# --- Container Launch ---
echo "Launching '$CONTAINER_NAME' container with RMW=$RMW_IMPLEMENTATION..."

# Launch the new container in detached mode.
# Important flags:
#   --network=host: Both containers share the host's network stack, allowing them to communicate as if they were on the same machine.
#   --privileged: Grants extended privileges, often needed for certain RMWs to function correctly.
#   --shm-size: Sets the size of /dev/shm (shared memory), crucial for some inter-process communication mechanisms.
#   -e VAR=...:   Passes environment variables from this container to the new one to ensure consistent ROS/RMW configuration.
#   --rm:         Automatically removes the container when it exits.
docker run -d --rm --network=host --privileged --shm-size=100mb \
    -e ROS_DOMAIN_ID=${ROS_DOMAIN_ID} \
    -e RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION} \
    -e FASTRTPS_DEFAULT_PROFILES_FILE=${FASTRTPS_DEFAULT_PROFILES_FILE} \
    -e RMW_FASTRTPS_USE_QOS_FROM_XML=${RMW_FASTRTPS_USE_QOS_FROM_XML} \
    -e CYCLONEDDS_URI=${CYCLONEDDS_URI} \
    --name "${CONTAINER_NAME}" \
    "${IMAGE_NAME}" \
    bash -c "$CONTAINER_SCRIPT"

if [ $? -eq 0 ]; then
    echo "✅ Container '${CONTAINER_NAME}' launched successfully."
else
    echo -e "\033[31m[ERROR] Failed to launch container '${CONTAINER_NAME}'.\033[0m"
    exit 1
fi
