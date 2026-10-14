"""Independent analytic and adverse T01 software oracles; no solver or physical validation."""
from dataclasses import replace
from fractions import Fraction
import hashlib
import math
import sys
import unittest
from fem_solid.gci import compute_gci, FitStatus, Level, MeshRef, Observable, gci


def levels():
    observable = Observable('vm_nodal_max', 'MPa', 'tip-4-15mm', 'nodal', 'max')
    return tuple(Level(MeshRef('mesh-'+str(i), 'fixture-v1', hashlib.sha256(str(i).encode()).hexdigest()), h, observable)
                 for i, h in enumerate((.25, .5, 1.0)))


def analytic():
    return compute_gci(100.5, 102, 108, 2, levels=levels())


class GCI(unittest.TestCase):
    def test_second_order(self):
        f = lambda h: 100.0 + 8.0 * h ** 2
        g = gci(f(0.25), f(0.5), f(1.0), 2.0)
        self.assertAlmostEqual(g['p'], 2.0, places=9); self.assertAlmostEqual(g['f_ext'], 100.0, places=9)
        self.assertAlmostEqual(g['gci_fine'], 1.25 * abs((f(0.25) - f(0.5)) / f(0.25)) / 3.0, places=12)
        self.assertFalse(g['admitted'])  # historical scalar call lacks mesh/observable binding

    def test_oscillatory_flagged(self):
        g = gci(100.0, 101.0, 99.5, 2.0); self.assertFalse(g['monotone']); self.assertIsNone(g['p'])

    def positive(self):
        result = analytic(); self.assertTrue(result.admitted); self.assertEqual(result.asymptotic_validation, 'not_established')
        return result

    def test_T01_01_analytic_order(self):
        result = self.positive()
        for actual, target in [(result.p, 2.0), (result.f_ext, 100.0), (result.gci_fine, float(Fraction(5, 804)))]:
            self.assertLessEqual(abs(actual-target), math.ulp(target))
        self.assertFalse(compute_gci(10, 12, 13, 2, levels=levels()).admitted)

    def test_T01_02_divergent_order(self):
        self.positive(); result = compute_gci(10, 12, 13, 2, levels=levels())
        self.assertEqual(result.fit_status, FitStatus.NONPOSITIVE); self.assertEqual(result.p, -1)
        self.assertFalse(result.admitted); self.assertIsNone(result.gci_fine)

    def test_T01_03_zero_order(self):
        self.positive(); result = compute_gci(10, 11, 12, 2, levels=levels())
        self.assertEqual(result.p, 0); self.assertFalse(result.admitted); self.assertIsNone(result.gci_fine)

    def test_T01_04_plateau(self):
        self.positive(); result = compute_gci(10, 10, 100, 2, levels=levels())
        self.assertEqual(result.reason, 'fine_pair_plateau'); self.assertFalse(result.admitted)

    def test_T01_05_oscillatory(self):
        self.positive(); result = compute_gci(100, 100.5, 100.25, 2, levels=levels())
        self.assertEqual(result.fit_status, FitStatus.OSCILLATORY); self.assertIsNone(result.p); self.assertFalse(result.admitted)
        self.assertLessEqual(float(Fraction(3, 160)), .03)  # unsafe legacy heuristic would pass

    def test_T01_06_exact_equal(self):
        self.positive()
        for value in (10, 0):
            result = compute_gci(value, value, value, 2, levels=levels())
            self.assertEqual(result.reason, 'all_levels_equal'); self.assertIsNone(result.gci_fine); self.assertFalse(result.admitted)

    def test_T01_07_invalid_ratio(self):
        self.positive()
        for invalid in (0, 1, -2, math.nan, math.inf, -math.inf, True, False):
            self.assertEqual(compute_gci(100.5, 102, 108, invalid).fit_status, FitStatus.INVALID)
        for index in range(5):
            for invalid in (math.nan, math.inf, -math.inf, True, False, '1', 1<<10000):
                args = [100.5, 102, 108, 2, 1.25]; args[index] = invalid
                self.assertEqual(compute_gci(*args).fit_status, FitStatus.INVALID)
        self.assertFalse(compute_gci(100.5, 102, 108, 2, -1.25).admitted)
        self.assertFalse(compute_gci(-sys.float_info.max, sys.float_info.max, 1, 2).admitted)

    def test_T01_08_zero_reference(self):
        self.positive(); result = compute_gci(0, 1, 2, 2, levels=levels())
        self.assertEqual(result.reason, 'zero_reference_quantity'); self.assertIsNone(result.gci_fine); self.assertFalse(result.admitted)

    def test_T01_09_precision_floor(self):
        for exponent in (-60, 0, 60, -1070):
            triple = [math.ldexp(x, exponent) for x in (100.5, 102, 108)]
            result = compute_gci(*triple, 2, levels=levels())
            self.assertTrue(result.admitted, result)
            self.assertLessEqual(abs(result.p-2), math.ulp(2.0))
            self.assertLessEqual(abs(result.gci_fine-float(Fraction(5, 804))), math.ulp(float(Fraction(5, 804))))
            self.assertLessEqual(abs(result.f_ext-math.ldexp(100, exponent)), math.ulp(math.ldexp(100, exponent)))
        for start in (1.0, math.ldexp(100.5, -60), math.ldexp(100.5, 60), math.ulp(0.0)):
            middle = math.nextafter(start, math.inf); coarse = math.nextafter(middle, math.inf)
            self.assertEqual(compute_gci(start, middle, coarse, 2).fit_status, FitStatus.PRECISION)
        self.assertEqual(compute_gci(*(math.ldexp(x, -1071) for x in (100.5, 102, 108)), 2).fit_status, FitStatus.PRECISION)

    def test_T01_10_mesh_sequence(self):
        self.positive(); original = levels()
        bad = [original[::-1], (original[0], original[0], original[2]),
               (original[0], replace(original[1], h=.75), original[2]),
               tuple(replace(x, refinement='anisotropic') for x in original),
               tuple(replace(x, mesh=replace(x.mesh, sha256=original[0].mesh.sha256)) for x in original)]
        for sequence in bad: self.assertFalse(compute_gci(100.5, 102, 108, 2, levels=sequence).admitted)

    def test_T01_11_observable_identity(self):
        self.positive(); original = levels()
        for key in ('id', 'units', 'region', 'projection', 'metric'):
            changed = replace(original[1], observable=replace(original[1].observable, **{key:'different'}))
            result = compute_gci(100.5, 102, 108, 2, levels=(original[0], changed, original[2]))
            self.assertEqual(result.reason, 'observable_mismatch'); self.assertFalse(result.admitted)

    def test_T01_18_peak_singularity(self):
        global_result = self.positive(); local = compute_gci(10, 12, 13, 2, levels=levels())
        self.assertTrue(global_result.admitted); self.assertFalse(local.admitted)
        self.assertFalse(global_result.admitted and local.admitted)


if __name__ == '__main__':
    unittest.main()
