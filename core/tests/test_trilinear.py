import unittest

from lutcore.trilinear import apply_residual_rgb, apply_residual_tensor, sample_residual_rgb


def residual_volume(dimension: int):
    return [[[[0.0 for _red in range(dimension)] for _green in range(dimension)] for _blue in range(dimension)] for _channel in range(3)]


class TrilinearTests(unittest.TestCase):
    def test_constant_residual_is_preserved_between_grid_points(self):
        volume = residual_volume(2)
        for channel, value in enumerate((0.1, -0.2, 0.05)):
            for blue in range(2):
                for green in range(2):
                    for red in range(2):
                        volume[channel][blue][green][red] = value

        self.assertEqual(sample_residual_rgb(volume, (0.37, 0.51, 0.24)), (0.1, -0.2, 0.05))
        self.assertEqual(apply_residual_rgb(volume, (0.37, 0.51, 0.24)), (0.47, 0.31, 0.29))

    def test_channel_axes_follow_nlut_blue_green_red_storage(self):
        volume = residual_volume(2)
        for blue in range(2):
            for green in range(2):
                for red in range(2):
                    volume[0][blue][green][red] = red
                    volume[1][blue][green][red] = green
                    volume[2][blue][green][red] = blue

        self.assertEqual(sample_residual_rgb(volume, (0.25, 0.5, 0.75)), (0.25, 0.5, 0.75))

    def test_out_of_range_input_uses_border_values(self):
        volume = residual_volume(2)
        volume[0][1][0][1] = 0.8

        self.assertEqual(sample_residual_rgb(volume, (2.0, -1.0, 4.0)), (0.8, 0.0, 0.0))

    def test_torch_adapter_matches_reference_sampler(self):
        try:
            import torch
        except ModuleNotFoundError:
            self.skipTest("PyTorch is not installed in this interpreter.")

        volume = residual_volume(2)
        for blue in range(2):
            for green in range(2):
                for red in range(2):
                    volume[0][blue][green][red] = red * 0.1
                    volume[1][blue][green][red] = green * -0.2
                    volume[2][blue][green][red] = blue * 0.05

        image = torch.tensor(
            [[[[0.25, 0.75]], [[0.50, 0.10]], [[0.75, 0.20]]]],
            dtype=torch.float32,
        )
        actual = apply_residual_tensor(image, torch.tensor(volume, dtype=torch.float32))
        expected = [
            apply_residual_rgb(volume, (0.25, 0.50, 0.75)),
            apply_residual_rgb(volume, (0.75, 0.10, 0.20)),
        ]

        self.assertTrue(
            torch.allclose(
                actual[0, :, 0, :],
                torch.tensor(expected, dtype=torch.float32).transpose(0, 1),
                atol=1e-6,
            )
        )


if __name__ == "__main__":
    unittest.main()
