"""Smoke-test the portable NLUT adapter against the downloaded official checkpoint."""

from __future__ import annotations

import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NLUT_ROOT = ROOT / "NLUT"
CHECKPOINT = ROOT / "models" / "336999_style_lut.pth"


@unittest.skipUnless(
    os.environ.get("RUN_NLUT_MODEL_TEST") == "1" and CHECKPOINT.is_file(),
    "Set RUN_NLUT_MODEL_TEST=1 after downloading the official checkpoint.",
)
class NLUTRuntimeTests(unittest.TestCase):
    def test_official_checkpoint_loads_and_predicts_33_cube(self) -> None:
        import torch
        from lutcore.nlut_runtime import infer_residual_lut, load_nlut

        model = load_nlut(nlut_root=NLUT_ROOT, checkpoint_path=CHECKPOINT, device="cpu")
        content = torch.full((1, 3, 8, 8), 0.5)
        reference = torch.full((1, 3, 8, 8), 0.25)
        lut = infer_residual_lut(model, content, reference)
        self.assertEqual(tuple(lut.shape), (1, 3, 33, 33, 33))
        self.assertTrue(torch.isfinite(lut).all())


if __name__ == "__main__":
    unittest.main()
