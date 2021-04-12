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
"""Implementing Privacy Loss Distribution.

This file implements the privacy loss distribution (PLD) and its basic
functionalities. The main feature of PLD is that it allows for accurate
computation of privacy parameters under composition. Please refer to the
supplementary material below for more details:
../../common_docs/Privacy_Loss_Distributions.pdf
"""

import collections
import math
import typing

from dp_accounting import common
from dp_accounting import privacy_loss_mechanism


class PrivacyLossDistribution(object):
  """Class for privacy loss distributions and computation involving them.

  The privacy loss distribution (PLD) of two discrete distributions, the upper
  distribution mu_upper and the lower distribution mu_lower, is defined as a
  distribution on real numbers generated by first sampling an outcome o
  according to mu_upper and then outputting the privacy loss
  ln(mu_upper(o) / mu_lower(o)) where mu_lower(o) and mu_upper(o) are the
  probability masses of o in mu_lower and mu_upper respectively. This class
  allows one to create and manipulate privacy loss distributions.

  PLD allows one to (approximately) compute the epsilon-hockey stick divergence
  between mu_upper and mu_lower, which is defined as
  sum_{o} [mu_upper(o) - e^{epsilon} * mu_lower(o)]_+. This quantity in turn
  governs the parameter delta of (eps, delta)-differential privacy of the
  corresponding protocol. (See Observation 1 in the supplementary material.)

  The above definitions extend to continuous distributions. The PLD of two
  continuous distributions mu_upper and mu_lower is defined as a distribution on
  real numbers generated by first sampling an outcome o according to mu_upper
  and then outputting the privacy loss ln(f_{mu_upper}(o) / f_{mu_lower}(o))
  where f_{mu_lower}(o) and f_{mu_upper}(o) are the probability density
  functions at o in mu_lower and mu_upper respectively. Moreover, for continuous
  distributions the epsilon-hockey stick divergence is defined as
  integral [f_{mu_upper}(o) - e^{epsilon} * f_{mu_lower}(o)]_+ do.

  Attributes:
    value_discretization_interval: the interval length for which the values of
      the privacy loss distribution are discretized. In particular, the values
      are always integer multiples of value_discretization_interval.
    rounded_probability_mass_function: the probability mass function for the
      privacy loss distribution where each value is rounded to be an integer
      multiple of value_discretization_interval. To avoid floating point errors
      in the values, the keys here are the integer multipliers. For example,
      suppose that the probability mass function assigns mass of 0.1 to the
      value 2 * value_discretization_interval, then the dictionary will have
      (key: value) pair (2: 0.1).
    infinity_mass: The probability mass of mu_upper over all the outcomes that
      can occur only in mu_upper but not in mu_lower.(These outcomes result in
      privacy loss ln(mu_upper(o) / mu_lower(o)) of infinity.)
    pessimistic_estimate: whether the rounding is done in such a way that the
      resulting epsilon-hockey stick divergence computation gives an upper
      estimate to the real value.
  """

  def __init__(self,
               rounded_probability_mass_function: typing.Mapping[int, float],
               value_discretization_interval: float,
               infinity_mass: float,
               pessimistic_estimate: bool = True):
    self.rounded_probability_mass_function = rounded_probability_mass_function
    self.value_discretization_interval = value_discretization_interval
    self.infinity_mass = infinity_mass
    self.pessimistic_estimate = pessimistic_estimate

  @classmethod
  def identity(
      cls,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Constructs an identity privacy loss distribution.

    Args:
      value_discretization_interval: the dicretization interval for the privacy
        loss distribution. The values will be rounded up/down to be integer
        multiples of this number.

    Returns:
      The privacy loss distribution corresponding to an algorithm with no
      privacy leak (i.e. output is independent of input).
    """
    return cls({0: 1}, value_discretization_interval, 0)

  @classmethod
  def from_two_probability_mass_functions(
      cls,
      log_probability_mass_function_lower: typing.Mapping[typing.Any, float],
      log_probability_mass_function_upper: typing.Mapping[typing.Any, float],
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4,
      log_mass_truncation_bound: float = -math.inf
  ) -> 'PrivacyLossDistribution':
    """Constructs a privacy loss distribution from mu_lower and mu_upper.

    Args:
      log_probability_mass_function_lower: the probability mass function of
        mu_lower represented as a dictionary where each key is an outcome o of
        mu_lower and the corresponding value is the natural log of the
        probability mass of mu_lower at o.
      log_probability_mass_function_upper: the probability mass function of
        mu_upper represented as a dictionary where each key is an outcome o of
        mu_upper and the corresponding value is the natural log of the
        probability mass of mu_upper at o.
      pessimistic_estimate: whether the rounding is done in such a way that the
        resulting epsilon-hockey stick divergence computation gives an upper
        estimate to the real value.
      value_discretization_interval: the dicretization interval for the privacy
        loss distribution. The values will be rounded up/down to be integer
        multiples of this number.
      log_mass_truncation_bound: when the log of the probability mass of the
        upper distribution is below this bound, it is either (i) included in
        infinity_mass in the case of pessimistic estimate or (ii) discarded
        completely in the case of optimistic estimate. The larger
        log_mass_truncation_bound is, the more error it may introduce in
        divergence calculations.

    Returns:
      The privacy loss distribution constructed as specified.
    """

    infinity_mass = 0
    for outcome in log_probability_mass_function_upper:
      if (log_probability_mass_function_lower.get(outcome,
                                                  -math.inf) == -math.inf):
        # When an outcome only appears in the upper distribution but not in the
        # lower distribution, then it must be counted in infinity_mass as such
        # an outcome contributes to the hockey stick divergence.
        infinity_mass += math.exp(log_probability_mass_function_upper[outcome])

    # Compute the (non-discretized) probability mass function for the privacy
    # loss distribution.
    probability_mass_function = {}
    for outcome in log_probability_mass_function_lower:
      if log_probability_mass_function_lower[outcome] == -math.inf:
        # This outcome never occurs in mu_lower. This case was already included
        # as infinity_mass above.
        continue
      elif (log_probability_mass_function_upper.get(outcome, -math.inf) >
            log_mass_truncation_bound):
        # When the probability mass of mu_upper at the outcome is greater than
        # the threshold, add it to the distribution.
        privacy_loss_value = (
            log_probability_mass_function_upper[outcome] -
            log_probability_mass_function_lower[outcome])
        probability_mass_function[privacy_loss_value] = (
            probability_mass_function.get(privacy_loss_value, 0) +
            math.exp(log_probability_mass_function_upper[outcome]))
      else:
        if pessimistic_estimate:
          # When the probability mass of mu_upper at the outcome is no more than
          # the threshold and we would like to get a pessimistic estimate,
          # account for this in infinity_mass.
          infinity_mass += math.exp(
              log_probability_mass_function_upper.get(outcome, -math.inf))

    # Discretize the probability mass so that the values are integer multiples
    # of value_discretization_interval
    rounded_probability_mass_function = collections.defaultdict(lambda: 0)
    round_fn = math.ceil if pessimistic_estimate else math.floor
    for val in probability_mass_function:
      rounded_probability_mass_function[round_fn(
          val /
          value_discretization_interval)] += probability_mass_function[val]

    return cls(
        rounded_probability_mass_function,
        value_discretization_interval,
        infinity_mass,
        pessimistic_estimate=pessimistic_estimate)

  @classmethod
  def create_from_additive_noise(
      cls,
      additive_noise_privacy_loss:
      'privacy_loss_mechanism.AdditiveNoisePrivacyLoss',
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Constructs the privacy loss distribution of an additive noise mechanism.

    An additive noise mechanism for computing a scalar-valued function f is a
    mechanism that outputs the sum of the true value of the function and a noise
    drawn from a certain distribution mu. This function calculates the privacy
    loss distribution for such an additive noise mechanism.

    Args:
      additive_noise_privacy_loss: the privacy loss representation of the
        mechanism.
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution constructed as specified.
    """
    round_fn = math.ceil if pessimistic_estimate else math.floor

    tail_pld = additive_noise_privacy_loss.privacy_loss_tail()

    rounded_probability_mass_function = collections.defaultdict(lambda: 0)
    infinity_mass = tail_pld.tail_probability_mass_function.get(math.inf, 0)
    for privacy_loss in tail_pld.tail_probability_mass_function:
      if privacy_loss != math.inf:
        rounded_probability_mass_function[round_fn(
            privacy_loss / value_discretization_interval
        )] += tail_pld.tail_probability_mass_function[privacy_loss]

    if additive_noise_privacy_loss.discrete_noise:
      xs = list(
          range(
              math.ceil(tail_pld.lower_x_truncation) - 1,
              math.floor(tail_pld.upper_x_truncation) + 1))

      # Compute PMF for the x's. Note that a vectorized call to noise_cdf can be
      # much faster than many scalar calls.
      cdf_values = additive_noise_privacy_loss.noise_cdf(xs)
      probability_mass = cdf_values[1:] - cdf_values[:-1]

      for x, prob in zip(xs[1:], probability_mass):
        rounded_probability_mass_function[round_fn(
            additive_noise_privacy_loss.privacy_loss(x) /
            value_discretization_interval)] += prob
    else:
      lower_x = tail_pld.lower_x_truncation
      rounded_down_value = math.floor(
          additive_noise_privacy_loss.privacy_loss(lower_x) /
          value_discretization_interval)

      # Compute discretization intervals for PLD approximation.
      xs, rounded_values = [lower_x], []
      x = lower_x
      while x < tail_pld.upper_x_truncation:
        x = min(
            tail_pld.upper_x_truncation,
            additive_noise_privacy_loss.inverse_privacy_loss(
                value_discretization_interval * rounded_down_value))

        xs.append(x)
        rounded_values.append(round_fn(rounded_down_value + 0.5))
        rounded_down_value -= 1

      # Compute PLD for discretization intervals. Note that a vectorized call to
      # noise_cdf is much faster than many scalar calls.
      cdf_values = additive_noise_privacy_loss.noise_cdf(xs)
      probability_mass = cdf_values[1:] - cdf_values[:-1]

      # Each x in [lower_x, upper_x] results in privacy loss that lies in
      # [value_discretization_interval * rounded_down_value,
      #  value_discretization_interval * (rounded_down_value + 1)]
      for rounded_value, prob in zip(rounded_values, probability_mass):
        rounded_probability_mass_function[rounded_value] += prob

    return cls(
        dict(rounded_probability_mass_function),
        value_discretization_interval,
        infinity_mass,
        pessimistic_estimate=pessimistic_estimate)

  @classmethod
  def from_randomized_response(
      cls,
      noise_parameter: float,
      num_buckets: int,
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Constructs the privacy loss distribution of Randomized Response.

    The Randomized Response over k buckets with noise parameter p takes in an
    input which is one of the k buckets. With probability 1 - p, it simply
    outputs the input bucket. Otherwise, with probability p, it outputs a bucket
    drawn uniformly at random from the k buckets.

    This function calculates the privacy loss distribution for the
    aforementioned Randomized Response with a given number of buckets, and a
    given noise parameter.

    Specifically, suppose that the original input is x and it is changed to x'.
    Recall that the privacy loss distribution of the Randomized Response
    mechanism is generated as follows: first pick o according to R(x), where
    R(x) denote the output distribution of the Randomized Response mechanism
    on input x. Then, the privacy loss is ln(Pr[R(x) = o] / Pr[R(x') = o]).
    There are three cases here:
      - When o = x, ln(Pr[R(x) = o] / Pr[R(x') = o]) =
        ln(Pr[R(x) = x] / Pr[R(x') = x]). Here Pr[R(x) = x] = 1 - p + p / k
        and Pr[R(x') = x] = p / k.
      - When o = x', ln(Pr[R(x) = o] / Pr[R(x') = o]) =
        ln(Pr[R(x') = x'] / Pr[R(x) = x']), which is just the negation of the
        previous privacy loss.
      - When o != x, x', the privacy loss is zero.

    Args:
      noise_parameter: the probability that the Randomized Response outputs a
        completely random bucket.
      num_buckets: the total number of possible input values (which is equal to
        the total number of possible output values).
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution constructed as specified.
    """

    if noise_parameter <= 0 or noise_parameter >= 1:
      raise ValueError(f'Noise parameter must be strictly between 0 and 1: '
                       f'{noise_parameter}')

    if num_buckets <= 1:
      raise ValueError(
          f'Number of buckets must be strictly greater than 1: {num_buckets}')

    round_fn = math.ceil if pessimistic_estimate else math.floor

    rounded_probability_mass_function = collections.defaultdict(lambda: 0)

    # Probability that the output is equal to the input, i.e., Pr[R(x) = x]
    probability_output_equal_input = ((1 - noise_parameter) +
                                      noise_parameter / num_buckets)
    # Probability that the output is equal to a specific bucket that is not the
    # input, i.e., Pr[R(x') = x] for x' != x.
    probability_output_not_input = noise_parameter / num_buckets

    # Add privacy loss for the case o = x
    rounded_value = round_fn(
        math.log(probability_output_equal_input / probability_output_not_input)
        / value_discretization_interval)
    rounded_probability_mass_function[
        rounded_value] += probability_output_equal_input

    # Add privacy loss for the case o = x'
    rounded_value = round_fn(
        math.log(probability_output_not_input / probability_output_equal_input)
        / value_discretization_interval)
    rounded_probability_mass_function[
        rounded_value] += probability_output_not_input

    # Add privacy loss for the case o != x, x'
    rounded_probability_mass_function[0] += (
        probability_output_not_input * (num_buckets - 2))

    return cls(
        rounded_probability_mass_function,
        value_discretization_interval,
        0,
        pessimistic_estimate=pessimistic_estimate)

  @classmethod
  def from_laplace_mechanism(
      cls,
      parameter: float,
      sensitivity: float = 1,
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Computes the privacy loss distribution of the Laplace mechanism.

    Args:
      parameter: the parameter of the Laplace distribution.
      sensitivity: the sensitivity of function f. (i.e. the maximum absolute
        change in f when an input to a single user changes.)
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution corresponding to the Laplace mechanism with
      given parameters.
    """
    return PrivacyLossDistribution.create_from_additive_noise(
        privacy_loss_mechanism.LaplacePrivacyLoss(
            parameter, sensitivity=sensitivity),
        pessimistic_estimate=pessimistic_estimate,
        value_discretization_interval=value_discretization_interval)

  @classmethod
  def from_gaussian_mechanism(
      cls,
      standard_deviation: float,
      sensitivity: float = 1,
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4,
      log_mass_truncation_bound: float = -50) -> 'PrivacyLossDistribution':
    """Creates the privacy loss distribution of the Gaussian mechanism.

    Args:
      standard_deviation: the standard_deviation of the Gaussian distribution.
      sensitivity: the sensitivity of function f. (i.e. the maximum absolute
        change in f when an input to a single user changes.)
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.
      log_mass_truncation_bound: the ln of the probability mass that might be
        discarded from the noise distribution. The larger this number, the more
        error it may introduce in divergence calculations.

    Returns:
      The privacy loss distribution corresponding to the Gaussian mechanism with
      given parameters.
    """
    return PrivacyLossDistribution.create_from_additive_noise(
        privacy_loss_mechanism.GaussianPrivacyLoss(
            standard_deviation,
            sensitivity=sensitivity,
            pessimistic_estimate=pessimistic_estimate,
            log_mass_truncation_bound=log_mass_truncation_bound),
        pessimistic_estimate=pessimistic_estimate,
        value_discretization_interval=value_discretization_interval)

  @classmethod
  def from_discrete_laplace_mechanism(
      cls,
      parameter: float,
      sensitivity: int = 1,
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Computes the privacy loss distribution of the Discrete Laplace mechanism.

    Args:
      parameter: the parameter of the discrete Laplace distribution.
      sensitivity: the sensitivity of function f. (i.e. the maximum absolute
        change in f when an input to a single user changes.)
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution corresponding to the Discrete Laplace
      mechanism with given parameters.
    """
    return PrivacyLossDistribution.create_from_additive_noise(
        privacy_loss_mechanism.DiscreteLaplacePrivacyLoss(
            parameter, sensitivity=sensitivity),
        pessimistic_estimate=pessimistic_estimate,
        value_discretization_interval=value_discretization_interval)

  @classmethod
  def from_discrete_gaussian_mechanism(
      cls,
      sigma: float,
      sensitivity: int = 1,
      truncation_bound: int = None,
      pessimistic_estimate: bool = True,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Creates the privacy loss distribution of the discrete Gaussian mechanism.

    Args:
      sigma: the parameter of the discrete Gaussian distribution. Note that
        unlike the (continuous) Gaussian distribution this is not equal to the
        standard deviation of the noise.
      sensitivity: the sensitivity of function f. (i.e. the maximum absolute
        change in f when an input to a single user changes.)
      truncation_bound: bound for truncating the noise, i.e. the noise will only
        have a support in [-truncation_bound, truncation_bound]. When not
        specified, truncation_bound will be chosen in such a way that the mass
        of the noise outside of this range is at most 1e-30.
      pessimistic_estimate: a value indicating whether the rounding is done in
        such a way that the resulting epsilon-hockey stick divergence
        computation gives an upper estimate to the real value.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution corresponding to the discrete Gaussian
      mechanism with given parameters.
    """
    return PrivacyLossDistribution.create_from_additive_noise(
        privacy_loss_mechanism.DiscreteGaussianPrivacyLoss(
            sigma, sensitivity=sensitivity, truncation_bound=truncation_bound),
        pessimistic_estimate=pessimistic_estimate,
        value_discretization_interval=value_discretization_interval)

  @classmethod
  def from_privacy_parameters(
      cls,
      privacy_parameters: common.DifferentialPrivacyParameters,
      value_discretization_interval: float = 1e-4) -> 'PrivacyLossDistribution':
    """Constructs pessimistic PLD from epsilon and delta parameters.

    When the mechanism is (epsilon, delta)-differentially private, the following
    is a pessimistic estimate of its privacy loss distribution (see Section 3.5
    of the supplementary material for more explanation):
      - infinity with probability delta.
      - epsilon with probability (1 - delta) / (1 + exp(-eps))
      - -epsilon with probability (1 - delta) / (1 + exp(eps))

    Args:
      privacy_parameters: the privacy guarantee of the mechanism.
      value_discretization_interval: the length of the dicretization interval
        for the privacy loss distribution. The values will be rounded up/down to
        be integer multiples of this number.

    Returns:
      The privacy loss distribution constructed as specified.
    """
    delta = privacy_parameters.delta
    epsilon = privacy_parameters.epsilon

    rounded_probability_mass_function = {
        math.ceil(epsilon / value_discretization_interval):
            (1 - delta) / (1 + math.exp(-epsilon)),
        math.ceil(-epsilon / value_discretization_interval):
            (1 - delta) / (1 + math.exp(epsilon))
    }

    return cls(rounded_probability_mass_function, value_discretization_interval,
               privacy_parameters.delta)

  def get_delta_for_epsilon(self, epsilon: float) -> float:
    """Computes the epsilon-hockey stick divergence between mu_upper, mu_lower.

    When this privacy loss distribution corresponds to a mechanism, the
    epsilon-hockey stick divergence gives the value of delta for which the
    mechanism is (epsilon, delta)-differentially private. (See Observation 1 in
    the supplementary material.)

    Args:
      epsilon: the epsilon in epsilon-hockey stick divergence.

    Returns:
      A non-negative real number which is the epsilon-hockey stick divergence
      between the upper (mu_upper) and the lower (mu_lower) distributions
      corresponding to this privacy loss distribution.
    """

    # The epsilon-hockey stick divergence of mu_upper with respect to mu_lower
    # is  equal to (the sum over all the values in the privacy loss distribution
    # of the probability mass at value times max(0, 1 - e^{epsilon - value}) )
    # plus the infinity_mass.
    divergence = self.infinity_mass
    for i in self.rounded_probability_mass_function:
      val = i * self.value_discretization_interval
      if val > epsilon and self.rounded_probability_mass_function[i] > 0:
        divergence += ((1 - math.exp(epsilon - val)) *
                       self.rounded_probability_mass_function[i])

    return divergence

  def get_epsilon_for_delta(self, delta: float) -> float:
    """Computes epsilon for which hockey stick divergence is at most delta.

    This function computes the smallest non-negative epsilon for which the
    epsilon-hockey stick divergence between mu_upper, mu_lower is at most delta.

    When this privacy loss distribution corresponds to a mechanism and the
    rounding is pessimistic, the returned value corresponds to an epsilon for
    which the mechanism is (epsilon, delta)-differentially private. (See
    Observation 1 in the supplementary material.)

    Args:
      delta: the target epsilon-hockey stick divergence.

    Returns:
      A non-negative real number which is the smallest epsilon such that the
      epsilon-hockey stick divergence between the upper (mu_upper) and the
      lower (mu_lower) distributions is at most delta. When no such finite
      epsilon exists, return math.inf.
    """

    if self.infinity_mass > delta:
      return math.inf

    mass_upper = self.infinity_mass
    mass_lower = 0
    for i in sorted(
        self.rounded_probability_mass_function.keys(), reverse=True):
      val = i * self.value_discretization_interval

      if (mass_upper > delta and mass_lower > 0 and math.log(
          (mass_upper - delta) / mass_lower) >= val):
        # Epsilon is greater than or equal to val.
        break

      mass_upper += self.rounded_probability_mass_function[i]
      mass_lower += (math.exp(-val) * self.rounded_probability_mass_function[i])

      if mass_upper >= delta and mass_lower == 0:
        # This only occurs when val is very large, which results in exp(-val)
        # being treated as zero.
        return max(0, val)

    if mass_upper <= mass_lower + delta:
      return 0
    else:
      return math.log((mass_upper - delta) / mass_lower)

  def compose(
      self,
      privacy_loss_distribution: 'PrivacyLossDistribution',
      tail_mass_truncation: float = 1e-15,
  ) -> 'PrivacyLossDistribution':
    """Computes a privacy loss distribution resulting from composing two PLDs.

    Args:
      privacy_loss_distribution: the privacy loss distribution to be composed
        with the current privacy loss distribution. The two must have the same
        value_discretization_interval.
      tail_mass_truncation: an upper bound on the tails of the probability mass
        of the PLD that might be truncated.

    Returns:
      A privacy loss distribution which is the result of composing the two.
    """

    # The two privacy loss distributions must have the same discretization
    # interval for the composition to go through.
    if (self.value_discretization_interval !=
        privacy_loss_distribution.value_discretization_interval):
      raise ValueError(
          f'Discretization intervals are different: '
          f'{self.value_discretization_interval}'
          f'{privacy_loss_distribution.value_discretization_interval}')

    if (self.pessimistic_estimate !=
        privacy_loss_distribution.pessimistic_estimate):
      raise ValueError(f'Estimation types are different: '
                       f'{self.pessimistic_estimate}'
                       f'{privacy_loss_distribution.pessimistic_estimate}')

    # The probability mass function of the resulting distribution is simply the
    # convolutaion of the two input probability mass functions.
    new_rounded_probability_mass_function = common.convolve_dictionary(
        self.rounded_probability_mass_function,
        privacy_loss_distribution.rounded_probability_mass_function,
        tail_mass_truncation=tail_mass_truncation)

    new_infinity_mass = (
        self.infinity_mass + privacy_loss_distribution.infinity_mass -
        (self.infinity_mass * privacy_loss_distribution.infinity_mass))

    if self.pessimistic_estimate:
      # In the pessimistic case, the truncated probability mass needs to be
      # treated as if it were infinity.
      new_infinity_mass += tail_mass_truncation

    return PrivacyLossDistribution(
        new_rounded_probability_mass_function,
        self.value_discretization_interval,
        new_infinity_mass,
        pessimistic_estimate=self.pessimistic_estimate)

  def self_compose(self, num_times: int) -> 'PrivacyLossDistribution':
    """Computes PLD resulting from repeated composing the PLD with itself.

    Args:
      num_times: the number of times to compose this PLD with itself.

    Returns:
      A privacy loss distribution which is the result of the composition.
    """

    new_rounded_probability_mass_function = common.self_convolve_dictionary(
        self.rounded_probability_mass_function, num_times)

    new_infinity_mass = (1 - ((1 - self.infinity_mass)**num_times))

    return PrivacyLossDistribution(
        new_rounded_probability_mass_function,
        self.value_discretization_interval,
        new_infinity_mass,
        pessimistic_estimate=self.pessimistic_estimate)
