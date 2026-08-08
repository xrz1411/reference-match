from __future__ import annotations

import unittest


class GenerateLutDomainTests(unittest.TestCase):
    def test_slog3_source_still_uses_the_selected_sony_input_transform(self) -> None:
        import torch
        from generate_lut import source_still_to_match_domain
        from lutcore.colour_management import slog3_to_rec709_gamma24

        source_slog3 = torch.tensor(
            [[[[0.20, 0.34]], [[0.18, 0.28]], [[0.16, 0.24]]]],
            dtype=torch.float32,
        )
        self.assertTrue(torch.allclose(
            source_still_to_match_domain(source_slog3, is_slog3_source=True, slog3_gamut="sgamut3", slog3_input_range="full"),
            slog3_to_rec709_gamma24(source_slog3, gamut="sgamut3", input_range="full"),
            atol=1e-6,
        ))

    def test_dwg_source_still_retains_its_srgb_file_interpretation(self) -> None:
        import torch
        from generate_lut import source_still_to_match_domain
        from lutcore.colour_management import dwg_intermediate_to_srgb, rec709_gamma24_to_dwg_intermediate, reference_srgb_to_rec709_gamma24

        # A selected Resolve JPG carries an sRGB ICC profile.  DWG is the
        # output LUT domain, not a reinterpretation of JPEG code values.
        source_srgb = torch.tensor(
            [[[[0.20, 0.34]], [[0.10, 0.28]], [[0.05, 0.44]]]],
            dtype=torch.float32,
        )
        match_domain = source_still_to_match_domain(source_srgb)
        self.assertTrue(torch.allclose(match_domain, reference_srgb_to_rec709_gamma24(source_srgb), atol=1e-6))
        self.assertTrue(torch.allclose(dwg_intermediate_to_srgb(rec709_gamma24_to_dwg_intermediate(match_domain)), source_srgb, atol=2e-5))

    def test_dpx_decodes_as_raw_dwg_input_code_values(self) -> None:
        import shutil
        import subprocess
        import tempfile
        from pathlib import Path

        import numpy as np
        import torch
        from PIL import Image
        from generate_lut import load_rgb_tensor, source_still_to_match_domain
        from lutcore.colour_management import dwg_intermediate_to_rec709_gamma24

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("ffmpeg is required for DPX decoding")
        expected_rgb = np.array([[[32, 64, 96], [128, 160, 192]]], dtype=np.uint8)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            png_path = directory / "source.png"
            dpx_path = directory / "source.dpx"
            Image.fromarray(expected_rgb).save(png_path)
            subprocess.run([ffmpeg, "-v", "error", "-i", str(png_path), "-frames:v", "1", "-pix_fmt", "rgb48le", str(dpx_path)], check=True)
            decoded = load_rgb_tensor(dpx_path)

        expected_codes = torch.from_numpy(expected_rgb.astype(np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        # DPX is quantised on write (commonly 10-bit), so a one 8-bit code
        # value round-trip difference is acceptable while channel ordering and
        # raw-code preservation remain covered.
        self.assertTrue(torch.allclose(decoded, expected_codes, atol=5e-3))
        self.assertTrue(torch.allclose(source_still_to_match_domain(decoded, is_dpx_source=True), dwg_intermediate_to_rec709_gamma24(decoded), atol=1e-6))

    def test_dwg_cube_rows_reproduce_the_preview_mapping_for_a_di_still(self) -> None:
        import numpy as np
        import torch
        from lutcore.colour_management import bake_dwg_intermediate_residual, dwg_intermediate_to_srgb
        from lutcore.cube_export import residual_to_cube_rows
        from lutcore.trilinear import apply_residual_tensor

        dimension = 17
        baked = bake_dwg_intermediate_residual(torch.full((3, dimension, dimension, dimension), 0.035), dimension=dimension)
        _size, rows = residual_to_cube_rows(baked)
        final_cube = torch.from_numpy(np.asarray(rows, dtype=np.float32).reshape(dimension, dimension, dimension, 3).transpose(3, 0, 1, 2))
        values = torch.linspace(0.0, 1.0, dimension)
        blue, green, red = torch.meshgrid(values, values, values, indexing="ij")
        identity = torch.stack((red, green, blue), dim=0)
        reconstructed_residual = final_cube - identity

        source_dwg = torch.tensor([[[[0.20, 0.34]], [[0.10, 0.28]], [[0.05, 0.44]]]], dtype=torch.float32)
        preview = dwg_intermediate_to_srgb(apply_residual_tensor(source_dwg, baked))
        cube_result = dwg_intermediate_to_srgb(apply_residual_tensor(source_dwg, reconstructed_residual))
        self.assertTrue(torch.allclose(cube_result, preview, atol=2e-5))
