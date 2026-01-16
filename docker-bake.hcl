// Copyright (c) 2026, iRobot ROS
// All rights reserved.
//
// This source code is licensed under the BSD 3-Clause License found in the
// LICENSE file in the root directory of this source tree.

// =================================================================================================
//
// This file defines the build configuration for the Docker images using Docker Bake.
// Docker Bake is a tool that allows building multiple Docker images in parallel,
// based on a declarative configuration file.
//
// For more information on Docker Bake, see the official documentation:
// https://docs.docker.com/build/bake/reference/
//
// == Usage ==
//
// To build the images, you can use the `docker buildx bake` command.
//
// Build the default target (amd64 for all distros):
// docker buildx bake
//
// Build all targets (amd64 and arm64):
// docker buildx bake all
//
// Build a specific target:
// docker buildx bake amd64
//
// =================================================================================================

// Defines the prefix for the Docker image tags.
variable "TAG_PREFIX" {
  default = "ros2-benchmark-container"
}

variable "DISTRO" {
  default = "jazzy"
}

// Defines a common base target with shared configuration.
target "_common" {
  dockerfile = "Dockerfile"
  labels = {
    "org.opencontainers.image.version" = "1.0.0"
    "org.opencontainers.image.description" = "Container for running ROS2 / rmw benchmark utilities."
    "org.opencontainers.image.title" = "${TAG_PREFIX}"
    "org.opencontainers.image.created" = "${timestamp()}"
  }
}

// Defines the build target for the amd64 architecture.
target "amd64" {
  inherits = ["_common"]
  matrix = {
    distro = [DISTRO]
  }
  target = "ros2-benchmark-container"
  name = "ros2-benchmark-container-${distro}-amd64"
  tags = [
    "${TAG_PREFIX}:${distro}-amd64"
  ]
  args = {
    ROS_DISTRO = distro
    BASE_IMAGE = "ros:${distro}"
  }
  platforms = ["${BAKE_LOCAL_PLATFORM}"]
}

// Defines the build target for the arm64 architecture.
target "arm64" {
  inherits = ["_common"]
  matrix = {
    distro = [DISTRO]
  }
  target = "ros2-benchmark-container"
  name = "ros2-benchmark-container-${distro}-arm64"
  tags = [
    "${TAG_PREFIX}:${distro}-arm64"
  ]
  args = {
    ROS_DISTRO = distro
    BASE_IMAGE = "ros:${distro}"
  }
  platforms = ["linux/arm64/v8"]
}

// Defines a build group that includes both amd64 and arm64 targets.
group "all" {
  targets = ["amd64", "arm64"]
}

// Defines the default build group.
group "default" {
  targets = ["amd64"]
}
