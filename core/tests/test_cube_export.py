import tempfile
import unittest
from pathlib import Path

from lutcore.cube_export import residual_to_cube_rows, write_resolve_cube


def zero_residual(dimension: int):
    return [[[[0.0 for _red in range(dimension)] for _green in range(dimension)] for _blue in range(dimension)] for _channel in range(3)]


class CubeExportTests(unittest.TestCase):
    def test_zero_residual_bakes_an_identity_cube_in_resolve_order(self):
        dimension, rows = residual_to_cube_rows(zero_residual(2))

        self.assertEqual(dimension, 2)
        self.assertEqual(
            rows,
            [
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                (1.0, 1.0, 0.0),
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 1.0),
                (0.0, 1.0, 1.0),
                (1.0, 1.0, 1.0),
            ],
        )

    def test_residual_is_added_to_identity_values_not_written_directly(self):
        residual = zero_residual(2)
        for blue in range(2):
            for green in range(2):
                for red in range(2):
                    residual[0][blue][green][red] = -0.03
                    residual[1][blue][green][red] = 0.01
                    residual[2][blue][green][red] = 0.05

        _dimension, rows = residual_to_cube_rows(residual)
        self.assertEqual(rows[0], (-0.03, 0.01, 0.05))
        self.assertEqual(rows[-1], (0.97, 1.01, 1.05))

    def test_output_limits_are_opt_in(self):
        residual = zero_residual(2)
        residual[0][1][1][1] = 0.2

        _dimension, rows = residual_to_cube_rows(residual, output_limits=(0.0, 1.0))
        self.assertEqual(rows[-1], (1.0, 1.0, 1.0))

    def test_writer_emits_resolve_cube_headers_and_rows(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            cube_path = write_resolve_cube(
                Path(temporary_directory) / "look.cube",
                zero_residual(2),
                title='Test "look"',
            )
            text = cube_path.read_text(encoding="utf-8")

        self.assertIn("TITLE \"Test 'look'\"", text)
        self.assertIn("LUT_3D_SIZE 2", text)
        self.assertTrue(text.endswith("1.0000000 1.0000000 1.0000000\n"))


if __name__ == "__main__":
    unittest.main()
