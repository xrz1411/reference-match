from __future__ import annotations

import unittest


class LookControlsTests(unittest.TestCase):
    def test_full_strength_preserves_a_constant_residual_without_safeguards(self) -> None:
        import torch
        from lutcore.look_controls import LookControls, apply_look_controls

        residual = torch.ones((3, 3, 3, 3)) * 0.1
        controls = LookControls(match_strength=100.0, protect_skin=False, protect_saturation=False, protect_contrast=False)
        self.assertTrue(torch.allclose(apply_look_controls(residual, controls), residual))

    def test_zero_match_strength_returns_zero_lut(self) -> None:
        import torch
        from lutcore.look_controls import LookControls, apply_look_controls

        residual = torch.ones((3, 3, 3, 3)) * 0.1
        output = apply_look_controls(residual, LookControls(match_strength=0.0))
        self.assertTrue(torch.equal(output, torch.zeros_like(residual)))

    def test_contrast_protection_restores_neutral_luma_without_a_green_cast(self) -> None:
        import torch
        from lutcore.look_controls import LookControls, apply_look_controls

        residual = torch.full((3, 3, 3, 3), -0.20)
        output = apply_look_controls(
            residual,
            LookControls(protect_skin=False, protect_saturation=False, protect_contrast=True),
        )
        mapped = output[:, 1, 1, 1] + 0.5
        self.assertLess(float(mapped.max() - mapped.min()), 1e-6)

    def test_resize_preserves_lut_corners(self) -> None:
        import torch
        from lutcore.look_controls import resize_residual_lut

        residual = torch.zeros((3, 2, 2, 2))
        residual[:, 0, 0, 0] = 0.1
        residual[:, 1, 1, 1] = 0.9
        enlarged = resize_residual_lut(residual, 5)
        self.assertTrue(torch.equal(enlarged[:, 0, 0, 0], residual[:, 0, 0, 0]))
        self.assertTrue(torch.equal(enlarged[:, -1, -1, -1], residual[:, -1, -1, -1]))
