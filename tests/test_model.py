import math
import unittest
from dataclasses import replace

from planche_sim import PRESETS, Pose, compare, relative_to_full, solve, torque_from_lean, with_preset
from planche_sim.model import G, MASS_FRAC


class ModelTests(unittest.TestCase):
    def test_mass_fractions_sum_to_one(self):
        f = MASS_FRAC
        total = f["head"] + f["trunk"] + 2 * f["arm"] + 2 * (f["thigh"] + f["shank"] + f["foot"])
        self.assertAlmostEqual(total, 1.0, delta=2e-3)

    def test_total_cg_is_above_the_wrist(self):
        for name in PRESETS:
            with self.subTest(name):
                r = solve(with_preset(Pose(), name))
                self.assertAlmostEqual(r.cg_total[0], 0.0, places=9)

    def test_torque_equals_body_weight_times_lever_arm(self):
        for name in PRESETS:
            with self.subTest(name):
                r = solve(with_preset(Pose(), name))
                self.assertAlmostEqual(r.torque_total, r.mass_body * G * r.d_cg)
                self.assertAlmostEqual(r.torque_per_shoulder, r.torque_total / 2)

    def test_moment_balance_on_the_arm(self):
        """Independent check from the arm's free-body diagram.

        Moments about the shoulder: ground force at the wrist minus the arm's own
        weight must equal the muscle torque obtained from the trunk's diagram.
        """
        for name in PRESETS:
            with self.subTest(name):
                r = solve(with_preset(Pose(), name))
                s = -r.points["shoulder"][0]
                arm_cg = r.cg_arms[0] - r.points["shoulder"][0]
                tau_arm = r.normal_force * s - r.mass_arms * G * arm_cg
                self.assertAlmostEqual(tau_arm / r.torque_total, 1.0, places=9)

    def test_arm_bar_method_needs_only_the_lean(self):
        """Torque from the arms alone (given the lean) equals the full-body result."""
        for name in PRESETS:
            with self.subTest(name):
                r = solve(with_preset(Pose(weight_kg=82, height_m=1.86), name))
                tau = torque_from_lean(r.pose.weight_kg, r.pose.height_m, r.lean_deg)
                self.assertAlmostEqual(tau / r.torque_total, 1.0, places=9)

    def test_torque_scales_linearly_with_body_mass(self):
        a, b = solve(Pose(weight_kg=60)), solve(Pose(weight_kg=90))
        self.assertAlmostEqual(b.torque_total / a.torque_total, 1.5)
        self.assertAlmostEqual(b.lean_deg, a.lean_deg)

    def test_torque_scales_with_height(self):
        a, b = solve(Pose(height_m=1.6)), solve(Pose(height_m=1.9))
        self.assertAlmostEqual(b.torque_total / a.torque_total, 1.9 / 1.6)

    def test_progressions_get_harder_in_the_expected_order(self):
        t = {k: r.torque_per_shoulder for k, r in compare().items()}
        self.assertLess(t["tuck"], t["adv_tuck"])
        self.assertLess(t["adv_tuck"], t["straddle"])
        self.assertLess(t["straddle"], t["full"])
        self.assertAlmostEqual(relative_to_full(solve(with_preset(Pose(), "full"))), 1.0)

    def test_wider_straddle_reduces_torque(self):
        torques = [solve(replace(Pose(), straddle_deg=a)).torque_per_shoulder for a in (0, 60, 120, 180)]
        self.assertEqual(torques, sorted(torques, reverse=True))

    def test_hip_flexion_reduces_torque(self):
        torques = [solve(replace(Pose(), hip_deg=a)).torque_per_shoulder for a in (0, 30, 60, 90)]
        self.assertEqual(torques, sorted(torques, reverse=True))

    def test_presets_are_physically_feasible(self):
        for name, r in compare().items():
            with self.subTest(name):
                self.assertTrue(r.feasible, r.warnings)

    def test_legs_through_the_floor_are_flagged(self):
        r = solve(Pose(hip_deg=70, knee_deg=0))  # straight legs pointing at the floor
        self.assertIn("below_floor", r.warnings)
        self.assertFalse(r.feasible)

    def test_arm_geometry_is_consistent(self):
        r = solve(with_preset(Pose(), "full"))
        l_arm = (0.186 + 0.146) * r.pose.height_m
        sx, sy = r.points["shoulder"]
        self.assertAlmostEqual(math.hypot(sx, sy), l_arm)
        self.assertAlmostEqual(math.sin(math.radians(r.lean_deg)), -sx / l_arm)


if __name__ == "__main__":
    unittest.main()
