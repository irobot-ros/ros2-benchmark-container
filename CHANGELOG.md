# Changelog for ROS 2 Benchmark Container

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