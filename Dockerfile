# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

# =================================================================================================
#
# This Dockerfile defines the environment for running the ROS 2 benchmarks.
#
# The build is divided into the following stages:
#
# 1. `base`:         Specifies the base ROS 2 image to use.
# 2. `dependencies`: Installs system dependencies and sets up the workspace.
# 3. `ros2-benchmark-container`: Builds the ROS 2 packages and configures the final image.
#
# =================================================================================================

# Stage 1: Base Image
# This allows specifying the base ROS 2 image at build time. Defaults to `ros:jazzy`.
ARG BASE_IMAGE=ros:jazzy
FROM ${BASE_IMAGE} AS base

# Stage 2: Dependencies
# Installs all the necessary system packages and Python modules.
FROM base AS dependencies

# Argument for the ROS distribution, passed from the docker-bake.hcl file.
ARG ROS_DISTRO

USER root

# Set the timezone to avoid interactive prompts during package installation.
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Los_Angeles
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install system dependencies, including different RMW implementations and Python packages for data analysis.
RUN \
    apt update && \
    apt install -y \
        ros-${ROS_DISTRO}-rmw-cyclonedds-cpp \
        ros-${ROS_DISTRO}-rmw-zenoh-cpp \
        docker.io \
        python3-pip \
        python3-tk \
        python3-numpy \
        python3-matplotlib \
        python3-pandas \
        python3-reportlab \
        python3-scipy \
        python3-tabulate

# Setup environment variables for the ROS workspace.
ENV ROS_INSTALL_DIR=/opt/ros/${ROS_DISTRO}
ENV COLCON_WS_DIR=/ws
ENV COLCON_SRC_DIR=${COLCON_WS_DIR}/src
ENV COLCON_INSTALL_DIR=${COLCON_WS_DIR}/install
WORKDIR ${COLCON_WS_DIR}

# Copy the external ROS 2 packages into the workspace.
COPY ./external ${COLCON_SRC_DIR}/ros2_benchmark_container/
# Source rosdeps and build everything placed in the "external" directory. 
RUN /bin/bash -c "rosdep install --from-paths ${COLCON_SRC_DIR} --ignore-src --rosdistro ${ROS_DISTRO} -y"

FROM dependencies AS builder
# Stage 3: Builder
# Build the ROS 2 workspace using colcon.
WORKDIR ${COLCON_WS_DIR}

# Copy the external ROS 2 packages into the workspace.
RUN /bin/bash -c "source ${ROS_INSTALL_DIR}/setup.bash; colcon build --merge-install"

FROM dependencies AS ros2-benchmark-container
ENV PERF_FRAMEWORK_INSTALL_DIR=${COLCON_INSTALL_DIR}/lib

# Stage 4: ROS 2 Benchmark Container
# Copy only the install folder for a lighter image
COPY --from=builder ${COLCON_INSTALL_DIR} ${COLCON_INSTALL_DIR}
# Automatically source environment variables on login
RUN echo 'source ${COLCON_INSTALL_DIR}/setup.bash' >> ~/.bashrc
# Add aliases for the main benchmark scripts.
RUN echo 'alias run_single_process_benchmark="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/runners/run_single_process_benchmark.sh"' >> ~/.bashrc
RUN echo 'alias run_multi_process_benchmark="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/runners/run_multi_process_benchmark.sh"' >> ~/.bashrc
RUN echo 'alias run_memory_benchmark="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/runners/run_memory_benchmark.sh"' >> ~/.bashrc
RUN echo 'alias run_remote_process="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/runners/run_remote_process.sh"' >> ~/.bashrc
RUN echo 'alias run_all_benchmarks="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/run_all_benchmarks.sh"' >> ~/.bashrc
RUN echo 'alias run_long_benchmark="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/run_long_benchmark.sh"' >> ~/.bashrc
RUN echo 'alias generate_all_metrics="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/generate_all_metrics.sh"' >> ~/.bashrc
RUN echo 'alias run_zenoh_router="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/runners/run_zenoh_router.sh"' >> ~/.bashrc
RUN echo 'alias set_cpu_governor="${COLCON_SRC_DIR}/ros2_benchmark_container/benchmark/scripts/utils/set_cpu_governor.sh"' >> ~/.bashrc
CMD ["bash"]
