import unittest

import matplotlib

matplotlib.use("Agg")

from planche_sim.app import PlancheApp
from planche_sim.model import Pose, solve


class AppTests(unittest.TestCase):
    def setUp(self):
        self.app = PlancheApp(Pose(), lang="en")

    def test_slider_updates_pose_and_textbox(self):
        self.app.sliders["hip_deg"].set_val(45)
        self.assertEqual(self.app.pose.hip_deg, 45)
        self.assertEqual(self.app.boxes["hip_deg"].text, "45")

    def test_textbox_updates_slider_and_clamps(self):
        self.app._on_submit("weight_kg", "500")
        self.assertEqual(self.app.pose.weight_kg, 120)  # clamped to the slider range
        self.assertEqual(self.app.sliders["weight_kg"].val, 120)

    def test_textbox_accepts_decimal_comma(self):
        self.app._on_submit("height_m", "1,95")
        self.assertAlmostEqual(self.app.pose.height_m, 1.95)

    def test_invalid_text_keeps_previous_value(self):
        self.app._on_submit("height_m", "abc")
        self.assertAlmostEqual(self.app.pose.height_m, 1.80)

    def test_preset_button_sets_all_joint_angles(self):
        self.app.apply_preset("tuck")
        p = self.app.pose
        self.assertEqual((p.hip_deg, p.knee_deg, p.tilt_deg), (115, 125, 15))

    def test_warning_text_for_infeasible_pose(self):
        self.app.set_pose(hip_deg=70, knee_deg=0)
        self.assertIn("floor", self.app.warn.get_text())
        self.app.apply_preset("full")
        self.assertEqual(self.app.warn.get_text(), "")

    def test_overlay_toggle(self):
        self.app._on_toggle(None)
        self.assertFalse(self.app.w_arrow.get_visible())
        self.assertFalse(self.app.info.get_visible())
        self.app._on_toggle(None)
        self.assertTrue(self.app.w_arrow.get_visible())

    def test_displayed_torque_matches_model(self):
        self.app.apply_preset("straddle")
        self.assertEqual(self.app.big.get_text(), f"{solve(self.app.pose).torque_per_shoulder:.0f} Nm")


if __name__ == "__main__":
    unittest.main()
