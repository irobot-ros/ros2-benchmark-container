#!/usr/bin/env python3

# Copyright (c) 2026, iRobot ROS
# All rights reserved.
#
# This source code is licensed under the BSD 3-Clause License found in the
# LICENSE file in the root directory of this source tree.

"""
This module provides common utility functions for the benchmark analysis scripts.
It contains helper functions for performing statistical tests.
"""

import numpy as np
from scipy import stats
from typing import List, Tuple, Optional


def perform_z_test(
    sample_a: List[float], sample_b: List[float], test_case: str = ""
) -> Tuple[Optional[float], float, float, float, float]:
    """
    Performs a one-tailed z-test to compare the means of two independent samples.

    This test is used to determine if there is a statistically significant difference
    between the means of two datasets (e.g., latency or CPU usage measurements).

    The null hypothesis (H0) is that the mean of sample_a is greater than or equal to
    the mean of sample_b. The alternative hypothesis (H1) is that the mean of sample_a
    is less than the mean of sample_b.

    A small p-value (typically <= 0.05) suggests that we can reject the null hypothesis,
    indicating that the mean of sample_a is significantly lower than the mean of sample_b.

    Args:
        sample_a: A list of numerical data representing the first sample.
        sample_b: A list of numerical data representing the second sample.
        test_case: An optional name for the test case, used for logging if data is
                   insufficient.

    Returns:
        A tuple containing:
        - The left-tailed p-value of the z-test. Returns None if there is not enough
          data to perform the test (i.e., if either sample has 1 or fewer data points).
        - The mean of sample_a.
        - The mean of sample_b.
        - The standard deviation of sample_a.
        - The standard deviation of sample_b.
    """
    mean_x1 = np.mean(sample_a)
    mean_x2 = np.mean(sample_b)
    std_dev_x1 = np.std(sample_a)
    std_dev_x2 = np.std(sample_b)
    n1 = len(sample_a)
    n2 = len(sample_b)
    p_left: Optional[float] = None

    if n1 <= 1 or n2 <= 1:
        print(f"Not sufficient data to perform statistical test: {test_case}.")
    else:
        # Calculate the z-score
        z = (mean_x1 - mean_x2) / np.sqrt((std_dev_x1**2 / n1) + (std_dev_x2**2 / n2))
        # Calculate the left-tailed p-value from the z-score
        p_left = stats.norm.cdf(z)

    return p_left, mean_x1, mean_x2, std_dev_x1, std_dev_x2
