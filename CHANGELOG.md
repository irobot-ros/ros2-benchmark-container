# Changelog for ROS 2 Benchmark Container

## 1.0.2 (2026-01-26)
* Replace currently unused `zenoh_low_latency.json` with `ZENOH_DEFAULT_ROUTER_CONFIG.json5` and `ZENOH_DEFAULT_SESSION_CONFIG.json5`. These configs will be used by default for all test matrices. Currently, the only change from defaults is to massively reduce the cli/srv session timeout. 
* Add `docker/attach`, a script for easily attaching to running benchmark containers.
* add `docker/deploy`, a script to deploy containers built on one host to a remote host, with automatic checks for compatible architecture
* Shrink image size by ~1/3 (a little under 1 GB) by using the `builder` pattern. Now we will only copy over the resulting `install` folder instead of all the `build` artifacts.
* make `docker/build` API consistent with `docker/run`
* update documentation for new tooling

## 1.0.1 (2026-01-16)
* Expose SYSTEM_EXECUTOR as a command line option when starting the container
* Fix handling of paths with spaces
* Add rmw_zenoh_cpp to the test matrix
* Update documentation
* Set default shm size for the container to 1000mb
* Change shm size for remote host tests to 1000mb

## 1.0.0 (2026-01-06)

Initial public release of the ROS 2 Benchmark Container.

This release provides a comprehensive framework for performance testing and analysis of ROS 2 middleware implementations.

### Key Features

*   **Dockerized Environment**: Provides a consistent and reproducible Docker-based environment for running benchmarks for ROS 2 Jazzy and Iron.
*   **Multi-Platform Builds**: Supports building Docker images for both `amd64` and `arm64` architectures using Docker Bake.
*   **Flexible Test Configuration**: Test matrices are defined in simple configuration files, allowing users to easily customize test runs.
*   **Support for Multiple RMWs**: Includes support for benchmarking `rmw_fastrtps_cpp`, and `rmw_cyclonedds_cpp`, and `rmw_zenoh_cpp`.
*   **Variety of Communication Settings**: Tests can be configured to run with different communication mechanisms, including intra-process communication (`ipc_on`) and loaned messages.

### Benchmark Tests

A wide range of benchmark scenarios are included to test various aspects of performance:

*   **Single-Process Communication**: Benchmarks for intra-process pub/sub, client/server, and actions.
*   **Multi-Process Communication**: Benchmarks for inter-process communication between nodes on the same host.
*   **Mixed-Process Communication**: Scenarios that combine intra-process, inter-process, and remote communication.
*   **Long-Duration Stability**: Tests designed to run for extended periods to detect memory leaks and performance degradation over time.
*   **Scalability Analysis**:
    *   **RAM Scalability**: Measures how RAM usage scales with an increasing number of processes.
    *   **Client Scalability**: Tests how server performance is affected by an increasing number of connected clients for services and actions.

### Analysis & Reporting

The framework includes a powerful suite of post-processing scripts for analysis:

*   **Automated Data Parsing**: Scripts to automatically parse raw results from latency and resource usage files.
*   **Statistical Analysis**: Performs statistical tests (t-test, z-test) to compare different configurations and check for significant performance differences.
*   **Trend Analysis**: Uses linear regression to analyze how performance metrics scale with factors like payload size and number of entities.
*   **Plot Generation**: Automatically generates a wide range of plots to visualize metrics like latency vs. payload, CPU usage over time, and RAM scalability.
*   **Comprehensive PDF Report**: Generates a detailed PDF report that summarizes the results of the entire benchmark run, including key plots and analysis, making it easy to share and interpret the findings.