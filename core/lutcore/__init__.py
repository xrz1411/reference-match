"""Portable utilities for baking NLUT residuals into Resolve .cube files."""

from .cube_export import residual_to_cube_rows, write_resolve_cube
from .trilinear import apply_residual_rgb, apply_residual_tensor, sample_residual_rgb

__all__ = [
    "apply_residual_rgb",
    "apply_residual_tensor",
    "residual_to_cube_rows",
    "sample_residual_rgb",
    "write_resolve_cube",
]
"""Portable building blocks for the local Resolve reference-LUT tool."""

from .cube_export import residual_to_cube_rows, write_resolve_cube
from .nlut_runtime import infer_residual_lut, load_nlut, select_device
from .reference_analysis import analyse_reference, write_reference_analysis

__all__ = [
    "infer_residual_lut",
    "load_nlut",
    "residual_to_cube_rows",
    "select_device",
    "analyse_reference",
    "write_resolve_cube",
    "write_reference_analysis",
]
