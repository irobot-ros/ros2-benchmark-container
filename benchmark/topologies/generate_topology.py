#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
ROS 2 Benchmark Topology Generator.

This script generates JSON topology files for ROS 2 benchmarking scenarios.
These topologies define the nodes, publishers, and subscribers that will be used
in the performance tests.

The script supports two main process modes:
- `single-process`: Creates a single publisher node with multiple publishers, and a single
                  subscriber node with multiple subscribers. This is used to test
                  intra-process communication.
- `multi-process`: Creates one publisher node for each topic, and a single subscriber node
                 with multiple subscribers. This simulates a distributed system where
                 nodes run in separate processes.

For each mode, the script generates three types of topology files:
1.  `<output_prefix>.json`: A standard topology using `unique_ptr` for message passing.
2.  `<output_prefix>_loaned.json`: A topology that uses `loaned_msg` for message passing,
                                which can improve performance by avoiding message copies.
3.  `debug_<output_prefix>.json`: A debug topology containing only subscriber nodes. This can
                               be useful for testing and debugging network configurations.

Usage:
    python3 generate_topology.py --num-topics <N> --freq <FREQ> --process-mode <single|multi> --output <OUTPUT_PREFIX>

Arguments:
    --num-topics: Number of topics to generate in the topology (default: 1).
    --freq: Maximum publishing frequency in Hz for each topic (default: 20). A random frequency
            between 1 and this value will be assigned to each publisher.
    --process-mode: Process mode for the topology. Choose between 'single' (one publisher node for all topics)
                    or 'multi' (one publisher node per topic) (default: single).
    --output: Prefix for the output file names. If not provided, a name will be auto-generated based
              on the other arguments.

Examples:
    # Generate topologies for a single-process scenario with 10 topics at 50 Hz.
    # This will create:
    # - single_10_topics_50hz.json
    # - single_10_topics_50hz_loaned.json
    # - debug_single_10_topics_50hz.json
    python3 generate_topology.py --num-topics 10 --freq 50 --process-mode single --output single_10_topics_50hz

    # Generate topologies for a multi-process scenario with 5 topics at 20 Hz.
    # This will create:
    # - multi_5_topics_20hz.json
    # - multi_5_topics_20hz_loaned.json
    # - debug_multi_5_topics_20hz.json
    python3 generate_topology.py --num-topics 5 --freq 20 --process-mode multi --output multi_5_topics_20hz
"""

import json
import argparse
import random
from typing import List, Dict, Any


def create_publisher_node(
    node_name: str,
    topic_indices: List[int],
    freqs_hz: List[int],
    msg_type: str,
    msg_pass_by: str,
) -> Dict[str, Any]:
    """
    Create a publisher node configuration.

    Args:
        node_name: Name of the publisher node.
        topic_indices: Indices of topics this node will publish.
        freqs_hz: List of frequencies corresponding to each topic.
        msg_type: Message type for the publishers.
        msg_pass_by: Message passing method ('unique_ptr', 'loaned_msg', etc.).

    Returns:
        A dictionary representing the publisher node in the topology.
    """
    return {
        "node_name": node_name,
        "publishers": [
            {
                "topic_name": f"test_topic_{i}",
                "msg_type": msg_type,
                "freq_hz": freqs_hz[i],
                "msg_pass_by": msg_pass_by,
            }
            for i in topic_indices
        ],
    }


def create_subscriber_node(
    node_name: str, topic_indices: List[int], msg_type: str
) -> Dict[str, Any]:
    """
    Create a subscriber node configuration.

    Args:
        node_name: Name of the subscriber node.
        topic_indices: Indices of topics this node will subscribe to.
        msg_type: Message type for the subscribers.

    Returns:
        A dictionary representing the subscriber node in the topology.
    """
    return {
        "node_name": node_name,
        "subscribers": [
            {"topic_name": f"test_topic_{i}", "msg_type": msg_type}
            for i in topic_indices
        ],
    }


def generate_single_process_topology(
    num_topics: int,
    freq_hz: int,
    msg_type: str = "stamped1mb",
    msg_pass_by: str = "unique_ptr",
) -> Dict[str, Any]:
    """
    Generate a single-process ROS 2 topology.

    This topology contains one publisher node with multiple topics and one subscriber node
    subscribing to all those topics. Both nodes are intended to run in the same process.

    Args:
        num_topics: Number of topics to generate.
        freq_hz: Maximum publishing frequency in Hz. A random frequency between 1 and freq_hz
                 will be assigned to each publisher.
        msg_type: Message type for publishers and subscribers.
        msg_pass_by: Message passing method ('unique_ptr' or 'loaned_msg').

    Returns:
        A dictionary representing the single-process ROS 2 topology.
    """
    freqs_hz = [random.randint(1, freq_hz) for _ in range(num_topics)]
    nodes = [
        create_publisher_node(
            "pub_node_sp", list(range(num_topics)), freqs_hz, msg_type, msg_pass_by
        ),
        create_subscriber_node("sub_node_sp", list(range(num_topics)), msg_type),
    ]
    return {"nodes": nodes}


def generate_multi_process_topology(
    num_topics: int,
    freq_hz: int,
    msg_type: str = "stamped1mb",
    msg_pass_by: str = "unique_ptr",
) -> Dict[str, Any]:
    """
    Generate a multi-process ROS 2 topology.

    This topology creates one publisher node per topic (simulating multiple processes)
    and a single subscriber node subscribing to all topics.

    Args:
        num_topics: Number of topics (and publisher nodes) to generate.
        freq_hz: Maximum publishing frequency in Hz. A random frequency between 1 and freq_hz
                 will be assigned to each publisher.
        msg_type: Message type for publishers and subscribers.
        msg_pass_by: Message passing method ('unique_ptr' or 'loaned_msg').

    Returns:
        A dictionary representing the multi-process ROS 2 topology.
    """
    freqs_hz = [random.randint(1, freq_hz) for _ in range(num_topics)]
    nodes = []

    # Create one publisher node for each topic to simulate multiple processes.
    for i in range(num_topics):
        nodes.append(
            create_publisher_node(f"pub_node_{i}", [i], freqs_hz, msg_type, msg_pass_by)
        )

    # Create a single subscriber node that subscribes to all topics.
    nodes.append(
        create_subscriber_node("sub_node_mp", list(range(num_topics)), msg_type)
    )

    return {"nodes": nodes}


def generate_debug_topology(
    num_topics: int, msg_type: str = "stamped1mb"
) -> Dict[str, Any]:
    """
    Generate a debug topology with subscribers only.

    This is useful for debugging network issues or measuring baseline subscriber performance.

    Args:
        num_topics: Number of topics to generate.
        msg_type: Message type used by all subscribers.

    Returns:
        A dictionary representing the debug topology.
    """
    subscribers = [
        {
            "topic_name": f"test_topic_{i}",
            "msg_type": msg_type,
            "qos_reliability": "best_effort",
        }
        for i in range(num_topics)
    ]

    return {"nodes": [{"node_name": "debug_sub_node", "subscribers": subscribers}]}


def main():
    """
    Main function to parse arguments and generate the topology files.
    """
    parser = argparse.ArgumentParser(
        description="Generate ROS 2 benchmark topology JSON files for various scenarios.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--num-topics",
        type=int,
        default=1,
        help="The number of topics to include in the topology (default: 1).",
    )
    parser.add_argument(
        "--freq",
        type=int,
        default=20,
        help="The maximum publishing frequency in Hz for each topic (default: 20).\n"
        "A random frequency between 1 and this value will be used for each publisher.",
    )
    parser.add_argument(
        "--process-mode",
        choices=["single", "multi"],
        default="single",
        help="The process mode for the topology:\n"
        " - 'single': One publisher node for all topics (for intra-process tests).\n"
        " - 'multi': One publisher node per topic (for inter-process tests).\n"
        "(default: single)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="The prefix for the output file names.\n"
        "If not provided, a name will be auto-generated based on the other arguments.",
    )
    args = parser.parse_args()

    base_name = (
        args.output
        or f"topology_{args.process_mode}_{args.num_topics}_topics_{args.freq}hz"
    )

    if args.process_mode == "single":
        topology_generator = generate_single_process_topology
    else:
        topology_generator = generate_multi_process_topology

    # Generate topologies for both unique_ptr and loaned_msg message passing styles.
    for mode in ["unique_ptr", "loaned_msg"]:
        topology = topology_generator(
            num_topics=args.num_topics,
            freq_hz=args.freq,
            msg_pass_by=mode,
        )

        suffix = "_loaned.json" if mode == "loaned_msg" else ".json"
        output_file = f"{base_name}{suffix}"

        with open(output_file, "w") as f:
            json.dump(topology, f, indent=2)

        print(f"✅ Topology JSON written to: {output_file}")

    # Generate a debug topology with only subscribers.
    debug_topology = generate_debug_topology(args.num_topics)
    debug_file = f"debug_{base_name}.json"
    with open(debug_file, "w") as f:
        json.dump(debug_topology, f, indent=2)
    print(f"✅ Debug subscriber-only JSON written to: {debug_file}")


if __name__ == "__main__":
    main()
