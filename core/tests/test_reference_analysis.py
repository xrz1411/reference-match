from __future__ import annotations

import unittest


class ReferenceAnalysisTests(unittest.TestCase):
    def test_main_colours_are_ordered_by_perceived_brightness(self) -> None:
        import torch
        from lutcore.reference_analysis import analyse_reference

        image = torch.zeros((1, 3, 10, 10))
        image[:, 0, :, :] = 0.8
        image[:, :, :2, :] = torch.tensor([0.02, 0.05, 0.1]).view(1, 3, 1, 1)
        report = analyse_reference(image, colours=2)
        self.assertEqual(len(report["main_colours"]), 2)
        brightness = [sum(component * weight for component, weight in zip(entry["rgb"], (0.2126, 0.7152, 0.0722))) for entry in report["main_colours"]]
        self.assertLessEqual(brightness[0], brightness[1])
        self.assertIn("contrast_span", report["brightness"])

    def test_hue_label_changes_with_reference_colour(self) -> None:
        import torch
        from lutcore.reference_analysis import analyse_reference

        warm = torch.zeros((1, 3, 8, 8)); warm[:, 0] = 0.9; warm[:, 1] = 0.38; warm[:, 2] = 0.05
        cool = torch.zeros((1, 3, 8, 8)); cool[:, 0] = 0.05; cool[:, 1] = 0.35; cool[:, 2] = 0.9
        self.assertEqual(analyse_reference(warm)["hue"]["label"], "暖橙")
        self.assertEqual(analyse_reference(cool)["hue"]["label"], "冷蓝")

    def test_low_saturation_reference_reports_neutral_label(self) -> None:
        import torch
        from lutcore.reference_analysis import analyse_reference

        neutral = torch.full((1, 3, 8, 8), 0.42)
        report = analyse_reference(neutral)
        self.assertIsNone(report["hue"]["mean_degrees"])
        self.assertEqual(report["hue"]["label"], "中性低饱和")
