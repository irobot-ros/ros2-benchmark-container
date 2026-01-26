# ROS 2 Benchmark Container

A Dockerized environment for benchmarking the performance of various ROS 2 Middleware (RMW) implementations.

## Overview

This repository provides a framework to build and run performance tests for various ROS 2 middleware implementations. It uses Docker to create a consistent and reproducible environment for running benchmarks. The main goal is to compare the performance of different RMWs under various conditions, such as message sizes, communication patterns (pub/sub, client/server), and number of nodes.

The benchmark results can be used to:
-   Evaluate the performance of a specific RMW.
-   Compare the performance of different RMWs.
-   Identify performance bottlenecks in a ROS 2 system.

## Table of Contents

- [ROS 2 Benchmark Container](#ros-2-benchmark-container)
  - [Overview](#overview)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Setup](#setup)
    - [Supported ROS 2 Distributions](#supported-ros-2-distributions)
  - [Usage](#usage)
    - [Build the Docker container](#build-the-docker-container)
    - [Run the benchmarks](#run-the-benchmarks)
    - [Analyze the results](#analyze-the-results)
  - [Benchmark Environment](#benchmark-environment)
  - [Advanced Usage](#advanced-usage)
    - [Adding a new test matrix](#adding-a-new-test-matrix)
    - [Adding new topologies](#adding-new-topologies)
    - [Adding a new RMW](#adding-a-new-rmw)
    - [Deploying to a remote host](#deploying-to-a-remote-host)
  - [Repository Structure](#repository-structure)
  - [Contributing](#contributing)
  - [License](#license)

## Getting Started

### Prerequisites

-   Docker engine with [buildkit](https://docs.docker.com/build/buildkit/) capabilities.

### Setup

1.  **Clone the repository and initialize submodules:**

    ```bash
    git clone <repository-url>
    cd ros2_benchmark_container
    git submodule update --init --recursive
    ```

2.  **Set up the Buildkit builder:**

    It's recommended to use a Buildkit builder for faster and more efficient builds.

    ```bash
    docker buildx create --use
    ```
### Supported ROS 2 Distributions

The following ROS 2 distributions are supported:

-   `jazzy` (default)
-   `kilted`
-   `rolling`

## Usage

Convenience scripts are provided in the `docker/` directory to simplify the process of building, running, deploying and attaching to the benchmark container. Make sure they are executable:

```bash
chmod +x docker/build docker/run docker/attach docker/deploy
```

### Build the Docker container

The `docker/build` script automates the process of building the container, including all benchmarking packages and sourcing environment variables.

From the root of this repository, run:

```bash
docker/build
```

This will automatically build containers for the ROS 2 distributions specified in `docker-bake.hcl`. By default, this is `jazzy`.

To build for an alternate distro, use the `-d` flag:

```bash
docker/build -d rolling
```

By default, containers are built for the host architecture. To build a container compatible with `arm64` architecture, pass `arm64` as an argument to the `-a` flag:

```bash
docker/build -a arm64
```
Note that `arm64` builds are currently much slower than `amd64`, as buildkit makes use of QEMU for emulation based cross-building.

### Run the benchmarks

1.  **Attach to the container:**

    The `docker/run` script starts the container and attaches a shell to it. It also mounts the `benchmark_results/${ROS_DISTRO}` directory from your host into the container's `/benchmark_results` directory to persist the results.

    ```bash
    docker/run -d <ros-distro>
    ```
    For example, to run the `kilted` container:
    ```bash
    docker/run -d kilted
    ```
    If no distribution is specified, it defaults to `jazzy`.

2.  **Run all benchmarks:**

    Once inside the container, you can use the `run_all_benchmarks` alias to execute all benchmarks:

    ```bash
    run_all_benchmarks
    ```

    This will take a significant amount of time to complete. To perform a quick test run, you can specify a shorter duration with the `-t` flag (e.g., 1 second per test):

    ```bash
    run_all_benchmarks -t 1
    ```

    The script will create a new directory inside `/benchmark_results` (e.g., `results_07_01_25_00h25`) containing the raw results. By default, it will also automatically generate post-processed results. To disable this, use the `--no-results` flag.


    NOTE - At this time, if running benchmarks on rmw_zenoh (which is enabled by default), the router needs to be manually started inside the container before the benchmarks are run via
    
    ```bash
    run_zenoh_router
    ```

### Analyze the results

At the end of a successful benchmark run, the results are automatically processed. The output directory will contain:

-   `raw_results/`: The raw data from the performance tests.
-   `parsed_results/`: Generated plots (`.png` files) and summary data in CSV format.
-   `report_<date>.pdf`: A comprehensive PDF report summarizing the results with plots and analysis. For example: `report_06_01_26_13h11.pdf`.

If you run the benchmarks with `--no-results`, you can manually generate the analysis by running the `generate_all_metrics` alias:

```bash
generate_all_metrics /benchmark_results/<results-directory>
```

Replace `<results-directory>` with the actual directory name (e.g., `results_07_01_25_00h25`).

## Benchmark Environment

The Docker container provides a standardized environment with the following key components:

-   **ROS 2 Distributions:** `Jazzy Jalisco` (default). The supported distributions can be configured in `docker-bake.hcl`.
-   **RMW Implementations:**
    -   `rmw_fastrtps_cpp` (default in ROS 2)
    -   `rmw_cyclonedds_cpp`
    -   `rmw_zenoh_cpp`
-   **Benchmarking Tools:**
    -   [ros2-performance](https://github.com/irobot-ros/ros2-performance): The underlying framework used to create and run the performance tests. This is a public iRobot repository, and the code is included in this project as a git submodule in the `external/` folder.
-   **Analysis Tools:**
    -   `pandas`, `numpy`, `matplotlib`, `scipy`: For data manipulation, analysis, and plotting.
    -   `reportlab`: For generating the final PDF report.

## Advanced Usage

### Configuring the system executor

The executor implementation used for the benchmarks is configurable by the user when launching the container.
By default, the EventsExecutor is used, but you can specify an alternate executor via the `-x` flag, e.g.:

```bash
docker/run -x SingleThreadedExecutor
```

By default, available executors are the `SingleThreadedExecutor`, `EventsExecutor` and `MultiThreadedExecutor`. If you have an executor from a different package that you'd like to benchmark, add it as a submodule in `/external`, include it in the `package.xml` and `CMakeLists.txt` for `ros2-performance`, add it to the list of available executors and extend the list of executors in `run_single_process_benchmark` and `run_multi_process_benchmark`.

An example for how to modify `ros2-performance` to add a new executor can be found [here](https://github.com/irobot-ros/ros2-performance/commit/71335ba88f5196a02b06a197cf5cae32b4ffb607). 

### Adding a new test matrix

The `benchmark/test-matrix` directory contains configuration files that define the test matrices for the benchmarks. Each file specifies a set of tests to be run with different configurations.

To create a new test matrix, you can create a new `.conf` file in this directory. The file should define the following variables:

-   `OUTPUT_DIR_NAME`: The name of the directory where the benchmark results will be saved.
-   `TOPOLOGIES`: A list of topology files to be used in the benchmark.
-   `TOPOLOGIES_DIR`: The directory where the topology files are located.
-   `PROFILES_DIR`: The directory where the RMW profile files are located.
-   `RMW_LIST`: A list of the RMW implementations to be tested.
-   `COMMS_<rmw>`: For each RMW in `RMW_LIST`, this variable defines the communication modes to be tested (e.g., `ipc_on`, `ipc_off`, `loaned`).
-   `LOANED_ENV_VARS_<rmw>`: For each RMW, this variable can be used to export environment variables required for running with loaned messages.

For example, the `single_process_pub_sub.conf` file defines a test matrix for single-process pub/sub benchmarks. After creating a new test matrix, you need to add a call to `run_benchmark` in the `run_all_benchmarks.sh` script to execute it.

### Adding new topologies

The `benchmark/topologies` directory contains the JSON files that define the architecture of the nodes to be benchmarked.

A python script `generate_topology.py` is provided to generate new topologies.

For example, to generate a topology with 10 topics at 50Hz in a single process:

```bash
python3 benchmark/topologies/generate_topology.py --num-topics 10 --freq 50 --process-mode single --output my_new_topology
```

This will generate `my_new_topology.json` and `my_new_topology_loaned.json` files in the current directory. You can then move these files to the appropriate topology directory.

Once the topology is created, you need to add it to the desired test matrix configuration file in the `benchmark/test-matrix` directory to include it in the benchmarks.

### Adding a new RMW

To add a new RMW implementation to the benchmark suite:

1.  **Update Dockerfile**: Add the installation command for the new RMW package in the `Dockerfile`.
2.  **Update test matrices**: Modify the `.conf` files in `benchmark/test-matrix` to include the new RMW in the `RMW_LIST` variable.
3.  **(Optional) Define RMW-specific variables**: For a new RMW named `my_middleware`, you may need to define:
    -   `COMMS_my_middleware`: Permutations of communication modes to test (e.g., `ipc_on`, `ipc_off`).
    -   `LOANED_ENV_VARS_my_middleware`: Environment variables for loaned messages.
4.  **(Optional) Add XML profiles**: If the new RMW requires specific configuration, add new XML profiles in the `benchmark/profiles` directory.


### Deploying to a remote host
Convience tools are included to deploy benchmark containers built on this host to another host. Checks are automatically run to make sure the target arch matches the docker image arch. A common use case might be benchmarking on more constrained hardware with less build capabilities, like a raspberry pi. 

1.  **Ensure the remote host has this repo**: make sure the `ros2-benchmark-container` repo is available on the remote machine.
2.  **Ensure docker and ssh access**: `docker/deploy` will automatically SSH into the remote host to install the docker image from a file. Please ensure you have SSH access to the target host and that it is capable of running docker without sudo. 
3.  **Build and deploy your image**: For example, to deploy a `kilted` container to a remote host with `arm64` architecture, you would do

    ```bash
    docker/build -d kilted -a arm64 
    docker/deploy -d kilted -a arm64 -u REMOTE_USER -h REMOTE_IP
    ```

## Repository Structure

    .
    ├── benchmark/              # Scripts and configurations for running benchmarks
    ├── docker/                 # Helper scripts for building and running the Docker container
    ├── external/               # Git submodules for external projects (e.g., ros2-performance)
    ├── Dockerfile              # Dockerfile for building the benchmark environment
    ├── docker-bake.hcl         # Docker bake file for multi-platform builds
    ├── CONTRIBUTING.md         # Contribution guidelines
    ├── LICENSE                 # Project license
    └── README.md               # This file

## Contributing

Contributions are welcome! Please read the [CONTRIBUTING.md](CONTRIBUTING.md) file for guidelines on how to contribute to this project.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.