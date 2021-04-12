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
"""Tests for common."""

import math
import unittest
from absl.testing import parameterized

from dp_accounting import common
from dp_accounting import test_util


class DifferentialPrivacyParametersTest(parameterized.TestCase):

  @parameterized.parameters((-0.1, 0.1), (1, -0.1), (1, 1.1))
  def test_epsilon_delta_value_errors(self, epsilon, delta):
    with self.assertRaises(ValueError):
      common.DifferentialPrivacyParameters(epsilon, delta)


class CommonTest(parameterized.TestCase):

  @parameterized.named_parameters(
      {
          'testcase_name': 'no_initial_guess',
          'func': (lambda x: -x),
          'value': -4.5,
          'lower_x': 0,
          'upper_x': 10,
          'initial_guess_x': None,
          'expected_x': 4.5,
          'increasing': False,
      }, {
          'testcase_name': 'with_initial_guess',
          'func': (lambda x: -x),
          'value': -5,
          'lower_x': 0,
          'upper_x': 10,
          'initial_guess_x': 2,
          'expected_x': 5,
          'increasing': False,
      }, {
          'testcase_name': 'out_of_range',
          'func': (lambda x: -x),
          'value': -5,
          'lower_x': 0,
          'upper_x': 4,
          'initial_guess_x': None,
          'expected_x': None,
          'increasing': False,
      }, {
          'testcase_name': 'infinite_upper_bound',
          'func': (lambda x: -1 / (1 / x)),
          'value': -5,
          'lower_x': 0,
          'upper_x': math.inf,
          'initial_guess_x': 2,
          'expected_x': 5,
          'increasing': False,
      }, {
          'testcase_name': 'increasing_no_initial_guess',
          'func': (lambda x: x**2),
          'value': 25,
          'lower_x': 0,
          'upper_x': 10,
          'initial_guess_x': None,
          'expected_x': 5,
          'increasing': True,
      }, {
          'testcase_name': 'increasing_with_initial_guess',
          'func': (lambda x: x**2),
          'value': 25,
          'lower_x': 0,
          'upper_x': 10,
          'initial_guess_x': 2,
          'expected_x': 5,
          'increasing': True,
      }, {
          'testcase_name': 'increasing_out_of_range',
          'func': (lambda x: x**2),
          'value': 5,
          'lower_x': 6,
          'upper_x': 10,
          'initial_guess_x': None,
          'expected_x': None,
          'increasing': True,
      }, {
          'testcase_name': 'discrete',
          'func': (lambda x: -x),
          'value': -4.5,
          'lower_x': 0,
          'upper_x': 10,
          'initial_guess_x': None,
          'expected_x': 5,
          'increasing': False,
          'discrete': True,
      })
  def test_inverse_monotone_function(self,
                                     func,
                                     value,
                                     lower_x,
                                     upper_x,
                                     initial_guess_x,
                                     expected_x,
                                     increasing,
                                     discrete=False):
    search_parameters = common.BinarySearchParameters(
        lower_x, upper_x, initial_guess=initial_guess_x, discrete=discrete)
    x = common.inverse_monotone_function(
        func, value, search_parameters, increasing=increasing)
    if expected_x is None:
      self.assertIsNone(x)
    else:
      self.assertAlmostEqual(expected_x, x)


class DictListConversionTest(parameterized.TestCase):

  @parameterized.named_parameters(
      {
          'testcase_name': 'truncate_both_sides',
          'input_list': [0.2, 0.5, 0.3],
          'offset': 1,
          'tail_mass_truncation': 0.6,
          'expected_result': {
              2: 0.5
          },
      }, {
          'testcase_name': 'truncate_lower_only',
          'input_list': [0.2, 0.5, 0.3],
          'offset': 1,
          'tail_mass_truncation': 0.4,
          'expected_result': {
              2: 0.5,
              3: 0.3
          },
      }, {
          'testcase_name': 'truncate_upper_only',
          'input_list': [0.4, 0.5, 0.1],
          'offset': 1,
          'tail_mass_truncation': 0.3,
          'expected_result': {
              1: 0.4,
              2: 0.5
          },
      }, {
          'testcase_name': 'truncate_all',
          'input_list': [0.4, 0.5, 0.1],
          'offset': 1,
          'tail_mass_truncation': 3,
          'expected_result': {},
      })
  def test_list_to_dict_truncation(self, input_list, offset,
                                   tail_mass_truncation, expected_result):
    result = common.list_to_dictionary(
        input_list, offset, tail_mass_truncation=tail_mass_truncation)
    test_util.dictionary_almost_equal(self, expected_result, result)


class ConvolveTest(unittest.TestCase):

  def test_convolve_dictionary(self):
    dictionary1 = {1: 2, 3: 4}
    dictionary2 = {2: 3, 4: 6}
    expected_result = {3: 6, 5: 24, 7: 24}
    result = common.convolve_dictionary(dictionary1, dictionary2)
    test_util.dictionary_almost_equal(self, expected_result, result)

  def test_convolve_dictionary_with_truncation(self):
    dictionary1 = {1: 0.4, 2: 0.6}
    dictionary2 = {1: 0.7, 3: 0.3}
    expected_result = {3: 0.42, 4: 0.12}
    result = common.convolve_dictionary(dictionary1, dictionary2, 0.57)
    test_util.dictionary_almost_equal(self, expected_result, result)

  def test_self_convolve_dictionary(self):
    inp_dictionary = {1: 2, 3: 5, 4: 6}
    expected_result = {
        3: 8,
        5: 60,
        6: 72,
        7: 150,
        8: 360,
        9: 341,
        10: 450,
        11: 540,
        12: 216
    }
    result = common.self_convolve_dictionary(inp_dictionary, 3)
    test_util.dictionary_almost_equal(self, expected_result, result)

  def test_self_convolve(self):
    input_list = [3, 5, 7]
    expected_result = [9, 30, 67, 70, 49]
    result = common.self_convolve(input_list, 2)
    self.assertEqual(len(expected_result), len(result))
    for expected_value, value in zip(expected_result, result):
      self.assertAlmostEqual(expected_value, value)


if __name__ == '__main__':
  unittest.main()
