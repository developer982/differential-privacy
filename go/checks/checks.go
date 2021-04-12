//
// Copyright 2020 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

// Package checks contains checks for differentially private functions.
package checks

import (
	"fmt"
	"math"

	log "github.com/golang/glog"
)

// CheckEpsilonVeryStrict returns an error if ε is +∞ or less than 2⁻⁵⁰.
func CheckEpsilonVeryStrict(label string, epsilon float64) error {
	if epsilon < math.Exp2(-50.0) || math.IsInf(epsilon, 0) || math.IsNaN(epsilon) {
		return fmt.Errorf("%s: Epsilon is %f, should be at least 2^-50 (and cannot be infinity or NaN)", label, epsilon)
	}
	return nil
}

// CheckEpsilonStrict returns an error if ε is nonpositive or +∞.
func CheckEpsilonStrict(label string, epsilon float64) error {
	if epsilon <= 0 || math.IsInf(epsilon, 0) || math.IsNaN(epsilon) {
		return fmt.Errorf("%s: Epsilon is %f, should be strictly positive (and cannot be infinity or NaN)", label, epsilon)
	}
	return nil
}

// CheckEpsilon returns an error if ε is strictly negative or +∞.
func CheckEpsilon(label string, epsilon float64) error {
	if epsilon < 0 || math.IsInf(epsilon, 0) || math.IsNaN(epsilon) {
		return fmt.Errorf("%s: Epsilon is %f, should be nonnegative (and cannot be infinity or NaN)", label, epsilon)
	}
	return nil
}

// CheckDelta returns an error if δ is negative or greater than or equal to 1.
func CheckDelta(label string, delta float64) error {
	if math.IsNaN(delta) {
		return fmt.Errorf("%s: Delta is %e, cannot be NaN", label, delta)
	}
	if delta < 0 {
		return fmt.Errorf("%s: Delta is %e, cannot be negative", label, delta)
	}
	if delta >= 1 {
		return fmt.Errorf("%s: Delta is %e, should be strictly less than 1", label, delta)
	}
	return nil
}

// CheckDeltaStrict returns an error if δ is nonpositive or greater than or equal to 1.
func CheckDeltaStrict(label string, delta float64) error {
	if math.IsNaN(delta) {
		return fmt.Errorf("%s: Delta is %e, cannot be NaN", label, delta)
	}
	if delta <= 0 {
		return fmt.Errorf("%s: Delta is %e, should be strictly positive", label, delta)
	}
	if delta >= 1 {
		return fmt.Errorf("%s: Delta is %e, should be strictly less than 1", label, delta)
	}
	return nil
}

// CheckNoDelta returns an error if δ is non-zero.
func CheckNoDelta(label string, delta float64) error {
	if delta != 0 {
		return fmt.Errorf("%s: Delta is %e, should be 0", label, delta)
	}
	return nil
}

// CheckL0Sensitivity returns an error if l0Sensitivity is nonpositive.
func CheckL0Sensitivity(label string, l0Sensitivity int64) error {
	if l0Sensitivity <= 0 {
		return fmt.Errorf("%s: L0Sensitivity is %d, should be strictly positive", label, l0Sensitivity)
	}
	return nil
}

// CheckLInfSensitivity returns an error if lInfSensitivity is nonpositive or +∞.
func CheckLInfSensitivity(label string, lInfSensitivity float64) error {
	if lInfSensitivity <= 0 || math.IsInf(lInfSensitivity, 0) || math.IsNaN(lInfSensitivity) {
		return fmt.Errorf("%s: LInfSensitivity is %f, should be strictly positive (and cannot be infinity or NaN)", label, lInfSensitivity)
	}
	return nil
}

// CheckBoundsInt64 returns an error if lower is larger than upper, and ensures it won't lead to sensitivity overflow.
func CheckBoundsInt64(label string, lower, upper int64) error {
	if lower == math.MinInt64 || upper == math.MinInt64 {
		return fmt.Errorf("%s: lower (%d) and upper (%d) must be strictly larger than math.MinInt64 to avoid sensitivity overflow", label, lower, upper)
	}
	if lower > upper {
		return fmt.Errorf("%s: Upper (%d) should be larger than Lower (%d)", label, upper, lower)
	}
	if lower == upper {
		log.Warningf("Lower bound is equal to upper bound: all added elements will be clamped to %d", upper)
	}
	return nil
}

// CheckBoundsInt64IgnoreOverflows returns an error if lower is larger than upper but ignores sensitivity overflows.
// This is used when noise is unrecognised.
func CheckBoundsInt64IgnoreOverflows(label string, lower, upper int64) error {
	if lower > upper {
		return fmt.Errorf("%s: Upper (%d) should be larger than Lower (%d)", label, upper, lower)
	}
	if lower == upper {
		log.Warningf("Lower bound is equal to upper bound: all added elements will be clamped to %d", upper)
	}
	return nil
}

// CheckBoundsFloat64 returns an error if lower is larger than upper, or if either parameter is ±∞.
func CheckBoundsFloat64(label string, lower, upper float64) error {
	if math.IsNaN(lower) {
		return fmt.Errorf("%s: lower can't be NaN", label)
	}
	if math.IsNaN(upper) {
		return fmt.Errorf("%s: upper can't be NaN", label)
	}
	if math.IsInf(lower, 0) {
		return fmt.Errorf("%s: lower can't be infinity", label)
	}
	if math.IsInf(upper, 0) {
		return fmt.Errorf("%s: upper can't be infinity", label)
	}
	if lower > upper {
		return fmt.Errorf("%s: Upper (%f) should be larger than Lower (%f)", label, upper, lower)
	}
	if lower == upper {
		log.Warningf("Lower bound is equal to upper bound: all added elements will be clamped to %f", upper)
	}
	return nil
}

// CheckBoundsFloat64IgnoreOverflows returns an error if lower is larger than upper but accepts either parameter being ±∞.
func CheckBoundsFloat64IgnoreOverflows(label string, lower, upper float64) error {
	if math.IsNaN(lower) {
		return fmt.Errorf("%s: lower can't be NaN", label)
	}
	if math.IsNaN(upper) {
		return fmt.Errorf("%s: upper can't be NaN", label)
	}
	if lower > upper {
		return fmt.Errorf("%s: Upper (%f) should be larger than Lower (%f)", label, upper, lower)
	}
	if lower == upper {
		log.Warningf("Lower bound is equal to upper bound: all added elements will be clamped to %f", upper)
	}
	return nil
}

// CheckBoundsFloat64AsInt64 returns an error if lower is larger are NaN, or if either parameter overflow after conversion to int64.
func CheckBoundsFloat64AsInt64(label string, lower, upper float64) error {
	if math.IsNaN(lower) {
		return fmt.Errorf("%s: Lower must not be NaN", label)
	}
	if math.IsNaN(upper) {
		return fmt.Errorf("%s: Upper must not be NaN", label)
	}
	maxInt := float64(math.MaxInt64)
	minInt := float64(math.MinInt64)
	if lower < minInt || lower > maxInt {
		return fmt.Errorf("%s: Lower should be within MinInt64 and MaxInt64 bounds, got %f", label, lower)
	}
	if upper < minInt || upper > maxInt {
		return fmt.Errorf("%s: Upper should be within MinInt64 and MaxInt64 bounds, got %f", label, upper)
	}
	return CheckBoundsInt64(label, int64(lower), int64(upper))
}

// CheckMaxPartitionsContributed returns an error if maxPartitionsContributed is nonpositive.
func CheckMaxPartitionsContributed(label string, maxPartitionsContributed int64) error {
	if maxPartitionsContributed < 0 {
		return fmt.Errorf("%s: MaxPartitionsContributed is %d, should not be negative", label, maxPartitionsContributed)
	}
	return nil
}

// CheckConfidenceLevel returns an error if the supplied confidence level is not between 0 and 1.
func CheckConfidenceLevel(label string, confidenceLevel float64) error {
	if confidenceLevel < 0 || confidenceLevel > 1 || math.IsNaN(confidenceLevel) || math.IsInf(confidenceLevel, 0) {
		return fmt.Errorf("%s: confidenceLevel is %f, should be between 0 and 1 (and cannot be NaN or Infinity)", label, confidenceLevel)
	}
	return nil
}

// CheckAlpha returns an error if the supplied alpha is not between 0 and 1.
func CheckAlpha(label string, alpha float64) error {
	if alpha <= 0 || alpha >= 1 || math.IsNaN(alpha) || math.IsInf(alpha, 0) {
		return fmt.Errorf("%s: alpha is %f, should be strictly between 0 and 1 (and cannot be NaN or Infinity)", label, alpha)
	}
	return nil
}

// CheckBoundsNotEqual returns an error if lower and upper bounds are equal.
func CheckBoundsNotEqual(label string, lower, upper float64) error {
	if lower == upper {
		return fmt.Errorf("%s: lower and upper are both %f, they should not be equal", label, lower)
	}
	return nil
}

// CheckTreeHeight returns an error if treeHeight is less than 1.
func CheckTreeHeight(label string, treeHeight int) error {
	if treeHeight < 1 {
		return fmt.Errorf("%s: treeHeight is %d, should be at least 1", label, treeHeight)
	}
	return nil
}

// CheckBranchingFactor returns an error if branchingFactor is less than 2.
func CheckBranchingFactor(label string, branchingFactor int) error {
	if branchingFactor < 2 {
		return fmt.Errorf("%s: branchingFactor is %d, should be at least 2", label, branchingFactor)
	}
	return nil
}
