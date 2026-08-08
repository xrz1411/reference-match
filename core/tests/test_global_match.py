from __future__ import annotations

import unittest


class GlobalMatchTests(unittest.TestCase):
    def test_direct_dwg_match_is_near_identity_for_equivalent_images(self) -> None:
        import torch
        from lutcore.colour_management import rec709_gamma24_to_dwg_intermediate
        from lutcore.global_match import fit_dwg_residual_lut

        display_image = torch.rand((1, 3, 20, 20)) * 0.70 + 0.10
        residual = fit_dwg_residual_lut(rec709_gamma24_to_dwg_intermediate(display_image), display_image, dimension=17)
        self.assertEqual(tuple(residual.shape), (3, 17, 17, 17))
        self.assertLess(float(residual.abs().max()), 3e-4)

    def test_direct_dwg_match_moves_luminance_toward_reference(self) -> None:
        import torch
        from lutcore.colour_management import dwg_intermediate_to_rec709_gamma24, rec709_gamma24_to_dwg_intermediate
        from lutcore.global_match import fit_dwg_residual_lut
        from lutcore.trilinear import apply_residual_tensor

        source_display = torch.linspace(0.12, 0.48, 192).view(1, 1, 1, 192).repeat(1, 3, 8, 1)
        reference_display = torch.linspace(0.32, 0.78, 192).view(1, 1, 1, 192).repeat(1, 3, 8, 1)
        source_dwg = rec709_gamma24_to_dwg_intermediate(source_display)
        residual = fit_dwg_residual_lut(source_dwg, reference_display, dimension=33)
        output_display = dwg_intermediate_to_rec709_gamma24(apply_residual_tensor(source_dwg, residual))

        self.assertGreater(float(output_display.mean()), float(source_display.mean()) + 0.08)

    def test_same_image_produces_identity_lut(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut

        image = torch.rand((1, 3, 24, 24))
        residual = fit_global_residual_lut(image, image, dimension=9)
        self.assertEqual(tuple(residual.shape), (3, 9, 9, 9))
        self.assertTrue(torch.equal(residual, torch.zeros_like(residual)))

    def test_warm_and_cool_histograms_transfer_opposite_colour_directions(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut
        from lutcore.trilinear import apply_residual_rgb

        ramp = torch.linspace(0.18, 0.82, 48).view(1, 1, 1, 48).repeat(1, 3, 24, 1)
        warm = torch.stack((ramp[:, 0] + 0.075, ramp[:, 1] + 0.010, ramp[:, 2] - 0.055), dim=1).clamp(0.0, 1.0)
        cool = torch.stack((ramp[:, 0] - 0.050, ramp[:, 1] + 0.015, ramp[:, 2] + 0.080), dim=1).clamp(0.0, 1.0)
        warm_output = apply_residual_rgb(fit_global_residual_lut(ramp, warm, dimension=33), (0.50, 0.50, 0.50))
        cool_output = apply_residual_rgb(fit_global_residual_lut(ramp, cool, dimension=33), (0.50, 0.50, 0.50))
        self.assertGreater(warm_output[0] - warm_output[2], 0.035)
        self.assertGreater(cool_output[2] - cool_output[0], 0.035)

    def test_histogram_transfer_is_deterministic(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut

        source = torch.rand((1, 3, 20, 20))
        reference = torch.rand((1, 3, 18, 18))
        first = fit_global_residual_lut(source, reference, dimension=9)
        second = fit_global_residual_lut(source, reference, dimension=9)
        self.assertTrue(torch.equal(first, second))

    def test_tone_curve_moves_brightness_and_contrast_toward_reference(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut
        from lutcore.trilinear import apply_residual_tensor

        # A dark, more contrasty reference should not merely recolour this
        # neutral ramp: its brightness distribution must also move downward
        # and spread out.
        source_values = torch.linspace(0.22, 0.78, 256).view(1, 1, 1, 256)
        reference_values = torch.linspace(0.10, 0.90, 256).pow(1.8).view(1, 1, 1, 256)
        source = source_values.repeat(1, 3, 12, 1)
        reference = reference_values.repeat(1, 3, 12, 1)
        residual = fit_global_residual_lut(source, reference, dimension=33)
        output = apply_residual_tensor(source, residual)

        self.assertLess(float(output.mean()), float(source.mean()) - 0.06)
        self.assertGreater(float(output.std()), float(source.std()) + 0.03)

    def test_tone_mapping_is_monotonic_on_a_neutral_ramp(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut
        from lutcore.trilinear import apply_residual_tensor

        source_values = torch.linspace(0.08, 0.92, 128).view(1, 1, 1, 128)
        reference_values = torch.linspace(0.16, 0.84, 128).pow(0.75).view(1, 1, 1, 128)
        source = source_values.repeat(1, 3, 4, 1)
        reference = reference_values.repeat(1, 3, 4, 1)
        output = apply_residual_tensor(source, fit_global_residual_lut(source, reference, dimension=33))
        luma = output.mean(dim=1)[0, 0]
        self.assertTrue(bool(torch.all(luma[1:] >= luma[:-1] - 1e-5)))

    def test_neutral_colours_have_an_intrinsic_stability_anchor(self) -> None:
        import torch
        from lutcore.global_match import fit_global_residual_lut
        from lutcore.trilinear import apply_residual_rgb

        ramp = torch.linspace(0.20, 0.80, 64).view(1, 1, 1, 64).repeat(1, 3, 12, 1)
        # Deliberately stronger than a normal reference look.  No LookControls
        # are applied here: the core LUT itself must avoid fully tinting a
        # neutral test patch when every optional protection is off.
        warm_reference = torch.stack((ramp[:, 0] + 0.17, ramp[:, 1], ramp[:, 2] - 0.13), dim=1).clamp(0.0, 1.0)
        output = apply_residual_rgb(fit_global_residual_lut(ramp, warm_reference, dimension=33), (0.50, 0.50, 0.50))
        self.assertGreater(output[0] - output[2], 0.05)
        self.assertLess(output[0] - output[2], 0.235)
