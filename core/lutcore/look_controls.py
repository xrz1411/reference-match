"""Global LUT-domain controls used by the first local reference-match tool.

These controls intentionally operate on the 3D LUT, not on image regions: a
standard ``.cube`` cannot contain a face/subject mask.  "Skin protection" is
therefore a conservative colour-domain guardrail, rather than semantic face
segmentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LookControls:
    """Values mirror the visible controls in the proposed Resolve-tool panel."""

    match_strength: float = 90.0
    shadows: float = 100.0
    midtones: float = 100.0
    highlights: float = 100.0
    protect_skin: bool = True
    protect_saturation: bool = True
    protect_contrast: bool = True

    def validated(self) -> "LookControls":
        for name in ("match_strength", "shadows", "midtones", "highlights"):
            value = getattr(self, name)
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100.")
        return self


def resize_residual_lut(residual_lut: Any, dimension: int) -> Any:
    """Resample a residual LUT to a 33- or 65-point lattice without clipping."""
    if dimension < 2:
        raise ValueError("LUT dimension must be at least 2.")
    if residual_lut.shape[-1] == dimension and residual_lut.shape[-2] == dimension and residual_lut.shape[-3] == dimension:
        return residual_lut

    import torch.nn.functional as functional

    if residual_lut.ndim == 4:
        residual_lut = residual_lut.unsqueeze(0)
        squeezed = True
    elif residual_lut.ndim == 5:
        squeezed = False
    else:
        raise ValueError("residual_lut must have shape [3, B, G, R] or [batch, 3, B, G, R].")
    output = functional.interpolate(
        residual_lut,
        size=(dimension, dimension, dimension),
        mode="trilinear",
        align_corners=True,
    )
    return output.squeeze(0) if squeezed else output


def _smoothstep(edge0: float, edge1: float, value: Any) -> Any:
    t = ((value - edge0) / (edge1 - edge0)).clamp(0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _identity_lattice(residual_lut: Any) -> Any:
    import torch

    dimension = residual_lut.shape[-1]
    if residual_lut.shape[-3:] != (dimension, dimension, dimension):
        raise ValueError("Residual LUT axes must be cubic.")
    values = torch.linspace(0.0, 1.0, dimension, device=residual_lut.device, dtype=residual_lut.dtype)
    blue = values[:, None, None].expand(dimension, dimension, dimension)
    green = values[None, :, None].expand(dimension, dimension, dimension)
    red = values[None, None, :].expand(dimension, dimension, dimension)
    return torch.stack((red, green, blue), dim=0)


def apply_look_controls(residual_lut: Any, controls: LookControls) -> Any:
    """Apply global strength, luminance-zone weights, and conservative safeguards."""
    controls.validated()
    if residual_lut.ndim == 5:
        if residual_lut.shape[0] != 1:
            raise ValueError("Controls currently expect one generated LUT at a time.")
        residual_lut = residual_lut[0]
    if residual_lut.ndim != 4 or residual_lut.shape[0] != 3:
        raise ValueError("residual_lut must have shape [3, blue, green, red].")

    identity = _identity_lattice(residual_lut)
    red, green, blue = identity[0], identity[1], identity[2]
    luma = red * 0.2126 + green * 0.7152 + blue * 0.0722

    # Smooth, partitioned tone zones. With every value at 100, this factor is
    # exactly 1 across the lattice.
    shadow_mask = 1.0 - _smoothstep(0.18, 0.48, luma)
    highlight_mask = _smoothstep(0.52, 0.82, luma)
    midtone_mask = 1.0 - shadow_mask - highlight_mask
    zone_strength = (
        shadow_mask * (controls.shadows / 100.0)
        + midtone_mask * (controls.midtones / 100.0)
        + highlight_mask * (controls.highlights / 100.0)
    )
    adjusted = residual_lut * (controls.match_strength / 100.0) * zone_strength.unsqueeze(0)

    if controls.protect_skin:
        # Conservative RGB-domain skin envelope. It avoids a semantic promise:
        # a .cube can recognise only a colour region, not a person or a face.
        maximum = identity.max(dim=0).values
        minimum = identity.min(dim=0).values
        chroma = maximum - minimum
        skin = (
            (red > 0.35)
            & (green > 0.18)
            & (blue > 0.08)
            & (red > green)
            & (green > blue)
            & (chroma > 0.08)
            & (chroma < 0.62)
            & (luma > 0.10)
            & (luma < 0.92)
        )
        adjusted = adjusted * (1.0 - skin.to(adjusted.dtype).unsqueeze(0) * 0.70)

    if controls.protect_saturation:
        saturation_guard = 1.0 - 0.55 * _smoothstep(0.42, 0.90, (identity.max(dim=0).values - identity.min(dim=0).values))
        adjusted = adjusted * saturation_guard.unsqueeze(0)

    if controls.protect_contrast:
        # Restore part of the source brightness along the neutral RGB axis.
        # Applying the correction in luma-coefficient proportions would add
        # 71.5% of it to green but only 7.2% to blue, creating a green cast
        # whenever this safety control was enabled.
        output = identity + adjusted
        output_luma = output[0] * 0.2126 + output[1] * 0.7152 + output[2] * 0.0722
        luma_delta = output_luma - luma
        adjusted = output - luma_delta.unsqueeze(0) * 0.65 - identity

    return adjusted
