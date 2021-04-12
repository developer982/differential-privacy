# Copyright 2020 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Common classes and functions for the accounting library."""

import math
import typing

import dataclasses
import numpy
from scipy import fft
from scipy import signal


@dataclasses.dataclass
class DifferentialPrivacyParameters(object):
  """Representation of the differential privacy parameters of a mechanism.

  Attributes:
    epsilon: the epsilon in (epsilon, delta)-differential privacy.
    delta: the delta in (epsilon, delta)-differential privacy.
  """
  epsilon: float
  delta: float = 0

  def __post_init__(self):
    if self.epsilon < 0:
      raise ValueError(f'epsilon should be positive: {self.epsilon}')
    if self.delta < 0 or self.delta > 1:
      raise ValueError(f'delta should be between 0 and 1: {self.delta}')


@dataclasses.dataclass
class BinarySearchParameters(object):
  """Parameters used for binary search.

  Attributes:
    upper_bound: An upper bound on the binary search range.
    lower_bound: A lower bound on the binary search range.
    initial_guess: An initial guess to start the search with. Must be positive.
      When this guess is close to the true value, it can help make the binary
      search faster.
    tolerance: An acceptable error on the returned value.
    discrete: Whether the search is over integers.
  """
  lower_bound: float
  upper_bound: float
  initial_guess: typing.Optional[float] = None
  tolerance: float = 1e-7
  discrete: bool = False


def inverse_monotone_function(
    func: typing.Callable[[float], float],
    value: float,
    search_parameters: BinarySearchParameters,
    increasing: bool = False) -> typing.Optional[float]:
  """Inverse a monotone function.

  Args:
    func: The function to be inversed.
    value: The desired value of the function.
    search_parameters: Parameters used for binary search.
    increasing: Whether the function is monotonically increasing.

  Returns:
    x such that func(x) is no more than value, when such x exists. It is
    guaranteed that the returned x is within search_parameters.tolerance of the
    smallest (for monotonically decreasing func) or the largest (for
    monotonically increasing func) such x. When no such x exists within the
    given range, returns None.
  """
  lower_x = search_parameters.lower_bound
  upper_x = search_parameters.upper_bound
  initial_guess_x = search_parameters.initial_guess

  if increasing:
    check = lambda func_value, target_value: func_value <= target_value
    if lower_x != -math.inf and func(lower_x) > value:
      return None
  else:
    check = lambda func_value, target_value: func_value > target_value
    if upper_x != math.inf and func(upper_x) > value:
      return None

  if initial_guess_x is not None:
    while initial_guess_x < upper_x and check(func(initial_guess_x), value):
      lower_x = initial_guess_x
      initial_guess_x *= 2
    upper_x = min(upper_x, initial_guess_x)

  if search_parameters.discrete:
    tolerance = 1
  else:
    tolerance = search_parameters.tolerance

  while upper_x - lower_x > tolerance:
    if search_parameters.discrete:
      mid_x = (upper_x + lower_x) // 2
    else:
      mid_x = (upper_x + lower_x) / 2

    if check(func(mid_x), value):
      lower_x = mid_x
    else:
      upper_x = mid_x

  if increasing:
    return lower_x
  else:
    return upper_x


def dictionary_to_list(
    input_dictionary: typing.Mapping[int, float]
) -> typing.Tuple[int, typing.List[float]]:
  """Converts an integer-keyed dictionary into an list.

  Args:
    input_dictionary: A dictionary whose keys are integers.

  Returns:
    A tuple of an integer offset and a list result_list. The offset is the
    minimum value of the input dictionary. result_list has length equal to the
    difference between the maximum and minimum values of the input dictionary.
    result_list[i] is equal to dictionary[offset + i] and is zero if offset + i
    is not a key in the input dictionary.
  """
  offset = min(input_dictionary)
  max_val = max(input_dictionary)
  result_list = [input_dictionary.get(i, 0) for i in range(offset, max_val + 1)]
  return (offset, result_list)


def list_to_dictionary(
    input_list: typing.List[float],
    offset: int,
    tail_mass_truncation: float = 0) -> typing.Mapping[int, float]:
  """Converts a list into an integer-keyed dictionary, with a specified offset.

  Args:
    input_list: An input list.
    offset: The offset in the key of the output dictionary
    tail_mass_truncation: an upper bound on the tails of the input list that
      might be truncated.

  Returns:
    A dictionary whose value at key is equal to input_list[key - offset]. If
    input_list[key - offset] is less than or equal to zero, it is not included
    in the dictionary.
  """
  lower_truncation_index = 0
  lower_truncation_mass = 0
  while lower_truncation_index < len(input_list):
    lower_truncation_mass += input_list[lower_truncation_index]
    if lower_truncation_mass > tail_mass_truncation / 2:
      break
    lower_truncation_index += 1

  upper_truncation_index = len(input_list) - 1
  upper_truncation_mass = 0
  while upper_truncation_index >= 0:
    upper_truncation_mass += input_list[upper_truncation_index]
    if upper_truncation_mass > tail_mass_truncation / 2:
      break
    upper_truncation_index -= 1

  result_dictionary = {}
  for i in range(lower_truncation_index, upper_truncation_index + 1):
    if input_list[i] > 0:
      result_dictionary[i + offset] = input_list[i]
  return result_dictionary


def convolve_dictionary(
    dictionary1: typing.Mapping[int, float],
    dictionary2: typing.Mapping[int, float],
    tail_mass_truncation: float = 0) -> typing.Mapping[int, float]:
  """Computes a convolution of two dictionaries.

  Args:
    dictionary1: The first dictionary whose keys are integers.
    dictionary2: The second dictionary whose keys are integers.
    tail_mass_truncation: an upper bound on the tails of the output that might
      be truncated.

  Returns:
    The dictionary where for each key its corresponding value is the sum, over
    all key1, key2 such that key1 + key2 = key, of dictionary1[key1] times
    dictionary2[key2]
  """

  # Convert the dictionaries to lists.
  min1, list1 = dictionary_to_list(dictionary1)
  min2, list2 = dictionary_to_list(dictionary2)

  # Compute the convolution of the two lists.
  result_list = signal.fftconvolve(list1, list2)

  # Convert the list back to a dictionary and return
  return list_to_dictionary(
      result_list, min1 + min2, tail_mass_truncation=tail_mass_truncation)


def self_convolve(input_list: typing.List[float],
                  num_times: int) -> typing.List[float]:
  """Computes a convolution of the input list with itself num_times times.

  Args:
    input_list: The input list to be convolved.
    num_times: The number of times the list is to be convolved with itself.

  Returns:
    The list where for each i-th entry its corresponding value is the sum, over
    all i_1, i_2, ..., i_num_times such that i_1 + i_2 + ... + i_num_times = i,
    of input_list[i_1] * input_list[i_2] * ... * input_list[i_num_times].
  """
  # Use FFT to compute the convolution
  output_len = num_times * len(input_list) - 1
  fast_len = fft.next_fast_len(output_len)
  return numpy.real(fft.ifft(fft.fft(input_list,
                                             fast_len)**num_times))[:output_len]


def self_convolve_dictionary(input_dictionary: typing.Mapping[int, float],
                             num_times: int) -> typing.Mapping[int, float]:
  """Computes a convolution of the input dictionary with itself num_times times.

  Args:
    input_dictionary: The input dictionary whose keys are integers.
    num_times: The number of times the dictionary is to be convolved with
      itself.

  Returns:
    The dictionary where for each key its corresponding value is the sum, over
    all key1, key2, ..., key_num_times such that key1 + key2 + ... +
    key_num_times = key, of input_dictionary[key1] * input_dictionary[key2] *
    ... * input_dictionary[key_num_times]
  """
  min_val, input_list = dictionary_to_list(input_dictionary)
  return list_to_dictionary(
      self_convolve(input_list, num_times), min_val * num_times)
