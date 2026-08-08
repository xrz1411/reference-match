from __future__ import annotations

import unittest


class ColourManagementTests(unittest.TestCase):
    def test_reference_srgb_round_trips_through_rec709_gamma24_match_domain(self) -> None:
        import torch
        from lutcore.colour_management import rec709_gamma24_to_srgb, reference_srgb_to_rec709_gamma24

        image = torch.rand((1, 3, 4, 4))
        self.assertTrue(torch.allclose(rec709_gamma24_to_srgb(reference_srgb_to_rec709_gamma24(image)), image, atol=1e-6))

    def test_slog3_decodes_sony_black_and_middle_grey_code_values(self) -> None:
        import torch
        from lutcore.colour_management import slog3_to_linear

        codes = torch.tensor([95.0 / 1023.0, 420.0 / 1023.0]).view(1, 1, 1, 2).repeat(1, 3, 1, 1)
        decoded = slog3_to_linear(codes)
        expected = torch.tensor([0.0, 0.18]).view(1, 1, 1, 2).repeat(1, 3, 1, 1)
        self.assertTrue(torch.allclose(decoded, expected, atol=2e-6))

    def test_slog3_video_range_matches_equivalent_full_range_code_values(self) -> None:
        import torch
        from lutcore.colour_management import slog3_to_rec709_gamma24

        full_range = torch.tensor([[[[0.20, 0.41055718, 0.62]], [[0.19, 0.41055718, 0.60]], [[0.18, 0.41055718, 0.58]]]])
        video_range = full_range * ((940.0 - 64.0) / 1023.0) + 64.0 / 1023.0
        expected = slog3_to_rec709_gamma24(full_range, gamut="sgamut3-cine", input_range="full")
        actual = slog3_to_rec709_gamma24(video_range, gamut="sgamut3-cine", input_range="video")
        self.assertTrue(torch.allclose(actual, expected, atol=2e-6))

    def test_sony_lc709_baseline_matches_the_bundled_look_profile_midgrey_and_white(self) -> None:
        import torch
        from lutcore.colour_management import sony_slog3_cine_to_lc709

        source_slog3 = torch.tensor([[[[420.0 / 1023.0, 598.0 / 1023.0]]]]).repeat(1, 3, 1, 1)
        result = sony_slog3_cine_to_lc709(source_slog3)
        self.assertTrue(torch.allclose(result[:, :, :, 0], torch.full((1, 3, 1), 0.3983), atol=2e-3))
        self.assertTrue(torch.allclose(result[:, :, :, 1], torch.full((1, 3, 1), 0.7200), atol=2e-3))

    def test_baked_slog3_identity_match_outputs_the_selected_restoration_baseline(self) -> None:
        import torch
        from lutcore.colour_management import bake_slog3_to_rec709_residual, slog3_to_display_match_domain
        from lutcore.trilinear import apply_residual_tensor

        dimension = 33
        baked = bake_slog3_to_rec709_residual(torch.zeros((3, dimension, dimension, dimension)), dimension=dimension)
        source_slog3 = torch.tensor([[[[0.25, 0.50, 0.75]], [[0.30, 0.50, 0.70]], [[0.35, 0.50, 0.65]]]])
        actual = apply_residual_tensor(source_slog3, baked)
        expected = slog3_to_display_match_domain(source_slog3)
        difference = (actual - expected).abs()
        self.assertLess(float(difference.mean()), 2e-6)
        self.assertLess(float(difference.max()), 2e-5)

    def test_davinci_intermediate_matches_official_reference_values(self) -> None:
        import torch
        from lutcore.colour_management import davinci_intermediate_to_linear, linear_to_davinci_intermediate

        scene_linear = torch.tensor([0.0, 0.18, 1.0, 10.0, 100.0]).view(1, 1, 1, 5).repeat(1, 3, 1, 1)
        expected = torch.tensor([0.0, 0.336043, 0.513837, 0.756599, 1.0]).view(1, 1, 1, 5).repeat(1, 3, 1, 1)
        encoded = linear_to_davinci_intermediate(scene_linear)
        self.assertTrue(torch.allclose(encoded, expected, atol=2e-6))
        self.assertTrue(torch.allclose(davinci_intermediate_to_linear(encoded), scene_linear, atol=2e-5))

    def test_zero_display_transform_bakes_to_near_identity_dwg_lut(self) -> None:
        import torch
        from lutcore.colour_management import bake_dwg_intermediate_residual

        baked = bake_dwg_intermediate_residual(torch.zeros((3, 5, 5, 5)), dimension=5)
        self.assertLess(float(baked.abs().max()), 2e-4)

    def test_baked_dwg_lut_matches_the_sdr_display_transform(self) -> None:
        import torch
        from lutcore.colour_management import (
            bake_dwg_intermediate_residual,
            dwg_intermediate_to_rec709_gamma24,
            rec709_gamma24_to_dwg_intermediate,
        )
        from lutcore.trilinear import apply_residual_tensor

        torch.manual_seed(0)
        display_input = torch.rand((1, 3, 7, 7)) * 0.55 + 0.15
        display_residual = torch.full((3, 33, 33, 33), 0.03)
        baked = bake_dwg_intermediate_residual(display_residual, dimension=33)
        dwg_input = rec709_gamma24_to_dwg_intermediate(display_input)
        actual = dwg_intermediate_to_rec709_gamma24(apply_residual_tensor(dwg_input, baked))
        expected = apply_residual_tensor(display_input, display_residual)
        # A 33-point cube is sampled/interpolated in DI's log domain, so it
        # cannot reproduce every SDR floating-point value exactly.  Keep both
        # average and worst-case interpolation error bounded.
        difference = (actual - expected).abs()
        self.assertLess(float(difference.mean()), 4e-3)
        self.assertLess(float(difference.max()), 1.7e-2)

    def test_baked_dwg_lut_preserves_extended_range_coordinates(self) -> None:
        import torch
        from lutcore.colour_management import bake_dwg_intermediate_residual
        from lutcore.trilinear import apply_residual_tensor

        baked = bake_dwg_intermediate_residual(torch.full((3, 33, 33, 33), 0.08), dimension=33)
        hdr_neutral = torch.full((1, 3, 2, 2), 0.95)
        actual = apply_residual_tensor(hdr_neutral, baked)
        self.assertTrue(torch.allclose(actual, hdr_neutral, atol=2e-4))

    def test_baked_dwg_lut_styles_visible_wide_gamut_colours(self) -> None:
        import torch
        from lutcore.colour_management import bake_dwg_intermediate_residual, dwg_intermediate_to_rec709_gamma24
        from lutcore.trilinear import apply_residual_tensor

        baked = bake_dwg_intermediate_residual(torch.full((3, 33, 33, 33), 0.06), dimension=33)
        # This is a normal-brightness DWG colour whose blue Rec.709 component
        # is negative.  It is wide gamut, not HDR, and must not become an
        # identity point merely because one display primary is out of range.
        wide_gamut_colour = torch.tensor([0.20, 0.10, 0.05]).view(1, 3, 1, 1)
        display_input = dwg_intermediate_to_rec709_gamma24(wide_gamut_colour)
        self.assertLess(float(display_input[0, 2, 0, 0]), 0.0)
        self.assertGreater(float(display_input[:, :3].mean()), 0.0)

        actual = apply_residual_tensor(wide_gamut_colour, baked)
        self.assertGreater(float((actual - wide_gamut_colour).abs().max()), 2e-3)

    def test_resolve_output_compensation_round_trips_the_measured_response(self) -> None:
        import torch
        from lutcore.colour_management import (
            dwg_intermediate_to_rec709_gamma24,
            precompensate_dwg_for_resolve_rec709,
            resolve_dwg_to_rec709_gamma24,
        )

        # Stay within the measured SDR range.  The inverse compensation should
        # make the Resolve-response simulation return the direct target look.
        source = torch.tensor(
            [[[[0.18, 0.29, 0.42]], [[0.14, 0.25, 0.37]], [[0.10, 0.21, 0.34]]]],
            dtype=torch.float32,
        )
        expected = dwg_intermediate_to_rec709_gamma24(source)
        actual = resolve_dwg_to_rec709_gamma24(precompensate_dwg_for_resolve_rec709(source))
        self.assertTrue(torch.allclose(actual, expected, atol=2e-5))
