"""Perceptual tone and colour-distribution matching baked into a 3D LUT.

The source still and reference are transformed to Oklab.  A constrained,
monotonic curve first matches their perceptual lightness distribution: this is
the exposure, contrast, black/white point and highlight-rolloff component of
the look.  The two chromatic Oklab axes are then histogram matched separately
in shadows, midtones and highlights.  Sampling that continuous transform on an
RGB lattice produces a portable 33- or 65-point Resolve LUT.
"""

from __future__ import annotations

from typing import Any

import numpy as np


_SAMPLE_LIMIT = 80_000
_QUANTILE_STEPS = 2_049
_TONE_QUANTILES = np.array(
    (0.0, 0.003, 0.01, 0.03, 0.07, 0.15, 0.25, 0.50, 0.75, 0.85, 0.93, 0.97, 0.99, 0.997, 1.0),
    dtype=np.float32,
)
_ZONE_CENTERS = np.array((0.18, 0.50, 0.82), dtype=np.float32)
_ZONE_WIDTH = 0.30
# These are intrinsic stability limits, not the three optional user-facing
# protection switches.  A global LUT must stay usable even when every optional
# safeguard is disabled.
_TONE_MATCH_AMOUNT = 0.86
_CHROMA_MATCH_AMOUNT = 0.90
_NEUTRAL_CHROMA_AMOUNT = 0.80
_LINEAR_TO_LMS = np.array(
    (
        (0.4122214708, 0.5363325363, 0.0514459929),
        (0.2119034982, 0.6806995451, 0.1073969566),
        (0.0883024619, 0.2817188376, 0.6299787005),
    ),
    dtype=np.float32,
)
_LMS_TO_OKLAB = np.array(
    (
        (0.2104542553, 0.7936177850, -0.0040720468),
        (1.9779984951, -2.4285922050, 0.4505937099),
        (0.0259040371, 0.7827717662, -0.8086757660),
    ),
    dtype=np.float32,
)
_OKLAB_TO_LMS = np.array(
    (
        (1.0, 0.3963377774, 0.2158037573),
        (1.0, -0.1055613458, -0.0638541728),
        (1.0, -0.0894841775, -1.2914855480),
    ),
    dtype=np.float32,
)
_LMS_TO_LINEAR = np.array(
    (
        (4.0767416621, -3.3077115913, 0.2309699292),
        (-1.2684380046, 2.6097574011, -0.3413193965),
        (-0.0041960863, -0.7034186147, 1.7076147010),
    ),
    dtype=np.float32,
)
_DWG_TO_XYZ = np.array(
    (
        (0.70062239, 0.14877482, 0.10105872),
        (0.27411851, 0.87363190, -0.14775041),
        (-0.09896291, -0.13789533, 1.32591599),
    ),
    dtype=np.float32,
)
_XYZ_TO_DWG = np.array(
    (
        (1.51667204, -0.28147805, -0.14696363),
        (-0.46491710, 1.25142378, 0.17488461),
        (0.06484905, 0.10913934, 0.76141462),
    ),
    dtype=np.float32,
)
_REC709_TO_XYZ = np.array(
    (
        (0.41239080, 0.35758434, 0.18048079),
        (0.21263901, 0.71516868, 0.07219232),
        (0.01933082, 0.11919478, 0.95053215),
    ),
    dtype=np.float32,
)
_XYZ_TO_REC709 = np.array(
    (
        (3.24096994, -1.53738318, -0.49861076),
        (-0.96924364, 1.87596750, 0.04155506),
        (0.05563008, -0.20397696, 1.05697151),
    ),
    dtype=np.float32,
)
_DI_A = 0.0075
_DI_B = 7.0
_DI_C = 0.07329248
_DI_M = 10.44426855
_DI_LINEAR_CUT = 0.00262409
_DI_LOG_CUT = 0.02740668


def _signed_power(values: np.ndarray, exponent: float) -> np.ndarray:
    return np.sign(values) * np.abs(values) ** exponent


def _display_to_oklab(rgb: np.ndarray) -> np.ndarray:
    linear = _signed_power(rgb, 2.4)
    return np.cbrt(linear @ _LINEAR_TO_LMS.T) @ _LMS_TO_OKLAB.T


def _oklab_to_display(lab: np.ndarray) -> np.ndarray:
    lms = lab @ _OKLAB_TO_LMS.T
    linear = (lms * lms * lms) @ _LMS_TO_LINEAR.T
    return _signed_power(linear, 1.0 / 2.4)


def _di_to_linear(values: np.ndarray) -> np.ndarray:
    return np.where(values <= _DI_LOG_CUT, values / _DI_M, np.exp2(values / _DI_C - _DI_B) - _DI_A)


def _linear_to_di(values: np.ndarray) -> np.ndarray:
    return np.where(
        values <= _DI_LINEAR_CUT,
        values * _DI_M,
        (np.log2(np.maximum(values + _DI_A, 1e-12)) + _DI_B) * _DI_C,
    )


def _dwg_di_to_oklab(values: np.ndarray) -> np.ndarray:
    """Decode DWG/DI code values into the common, perceptual Oklab space."""
    xyz = _di_to_linear(values) @ _DWG_TO_XYZ.T
    rec709_linear = xyz @ _XYZ_TO_REC709.T
    lms = rec709_linear @ _LINEAR_TO_LMS.T
    return np.cbrt(lms) @ _LMS_TO_OKLAB.T


def _oklab_to_dwg_di(lab: np.ndarray) -> np.ndarray:
    lms = lab @ _OKLAB_TO_LMS.T
    rec709_linear = (lms * lms * lms) @ _LMS_TO_LINEAR.T
    xyz = rec709_linear @ _REC709_TO_XYZ.T
    return _linear_to_di(xyz @ _XYZ_TO_DWG.T)


def _display_to_dwg_di(values: np.ndarray) -> np.ndarray:
    rec709_linear = _signed_power(values, 2.4)
    xyz = rec709_linear @ _REC709_TO_XYZ.T
    return _linear_to_di(xyz @ _XYZ_TO_DWG.T)


def _sample_pixels(image: np.ndarray) -> np.ndarray:
    pixels = image.reshape(-1, 3)
    if pixels.shape[0] <= _SAMPLE_LIMIT:
        return pixels
    indexes = np.linspace(0, pixels.shape[0] - 1, _SAMPLE_LIMIT, dtype=np.int64)
    return pixels[indexes]


def _quantile_mapping(source: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return a continuous equal-CDF mapping for one Oklab axis."""
    quantiles = np.linspace(0.0, 1.0, _QUANTILE_STEPS, dtype=np.float32)
    source_knots = np.quantile(source, quantiles).astype(np.float32)
    reference_knots = np.quantile(reference, quantiles).astype(np.float32)
    unique_source, indexes = np.unique(source_knots, return_index=True)
    return unique_source, reference_knots[indexes]


def _monotonic_tone_mapping(source_lightness: np.ndarray, reference_lightness: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return a sparse, monotonic L mapping for exposure and contrast.

    Unlike an unconstrained per-bin histogram equalisation, these percentile
    anchors form a continuous tone curve.  Their spacing deliberately puts more
    control around black, white and highlight rolloff than in the middle.
    """
    source_knots = np.quantile(source_lightness, _TONE_QUANTILES).astype(np.float32)
    reference_knots = np.quantile(reference_lightness, _TONE_QUANTILES).astype(np.float32)
    unique_source, indexes = np.unique(source_knots, return_index=True)
    return unique_source, reference_knots[indexes]


def _apply_mapping(values: np.ndarray, source_knots: np.ndarray, reference_knots: np.ndarray) -> np.ndarray:
    if source_knots.size == 1:
        return np.full_like(values, reference_knots[0])
    return np.interp(values, source_knots, reference_knots).astype(np.float32)


def _zone_weights(lightness: np.ndarray) -> np.ndarray:
    """Soft shadow/midtone/highlight memberships summing to one."""
    weights = np.exp(-0.5 * ((lightness[..., None] - _ZONE_CENTERS) / _ZONE_WIDTH) ** 2)
    return weights / np.maximum(weights.sum(axis=-1, keepdims=True), 1e-8)


def _smoothstep(edge0: float, edge1: float, values: np.ndarray) -> np.ndarray:
    fraction = np.clip((values - edge0) / (edge1 - edge0), 0.0, 1.0)
    return fraction * fraction * (3.0 - 2.0 * fraction)


def _zone_mapping(
    source_axis: np.ndarray,
    source_lightness: np.ndarray,
    reference_axis: np.ndarray,
    reference_lightness: np.ndarray,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Fit one chromatic-axis CDF mapping for each tonal zone.

    The masks intentionally overlap.  It prevents hue discontinuities at a
    particular code value while letting warm highlights and cool shadows remain
    independent trends when they exist in a reference image.
    """
    source_weights = _zone_weights(source_lightness)
    reference_weights = _zone_weights(reference_lightness)
    mappings: list[tuple[np.ndarray, np.ndarray]] = []
    for zone in range(3):
        source_mask = source_weights[:, zone] >= 0.22
        reference_mask = reference_weights[:, zone] >= 0.22
        # Very small zones are not statistically meaningful; fall back to the
        # full-image distribution rather than creating a volatile colour shift.
        if source_mask.sum() < 128 or reference_mask.sum() < 128:
            mappings.append(_quantile_mapping(source_axis, reference_axis))
        else:
            mappings.append(_quantile_mapping(source_axis[source_mask], reference_axis[reference_mask]))
    return mappings


def _apply_zone_mapping(
    values: np.ndarray,
    lightness: np.ndarray,
    mappings: list[tuple[np.ndarray, np.ndarray]],
) -> np.ndarray:
    mapped = np.stack([_apply_mapping(values, *mapping) for mapping in mappings], axis=-1)
    return (mapped * _zone_weights(lightness)).sum(axis=-1).astype(np.float32)


def _identity_lattice(dimension: int) -> np.ndarray:
    values = np.linspace(0.0, 1.0, dimension, dtype=np.float32)
    blue, green, red = np.meshgrid(values, values, values, indexing="ij")
    return np.stack((red, green, blue), axis=-1)


def fit_global_residual_lut(content: Any, reference: Any, *, dimension: int = 33) -> Any:
    """Fit a smooth Oklab tone-and-colour residual 3D LUT."""
    import torch

    if dimension < 2:
        raise ValueError("dimension must be at least 2")
    if content.ndim != 4 or reference.ndim != 4 or content.shape[1] != 3 or reference.shape[1] != 3:
        raise ValueError("content and reference must have shape [batch, 3, height, width].")

    source_rgb = content[0].detach().to("cpu").permute(1, 2, 0).numpy().clip(0.0, 1.0).astype(np.float32)
    reference_rgb = reference[0].detach().to("cpu").permute(1, 2, 0).numpy().clip(0.0, 1.0).astype(np.float32)
    if np.array_equal(source_rgb, reference_rgb):
        return torch.zeros((3, dimension, dimension, dimension), dtype=torch.float32)

    source_oklab = _display_to_oklab(_sample_pixels(source_rgb))
    reference_oklab = _display_to_oklab(_sample_pixels(reference_rgb))
    tone_mapping = _monotonic_tone_mapping(source_oklab[:, 0], reference_oklab[:, 0])
    chroma_mappings = [
        _zone_mapping(source_oklab[:, axis], source_oklab[:, 0], reference_oklab[:, axis], reference_oklab[:, 0])
        for axis in (1, 2)
    ]

    lattice = _identity_lattice(dimension)
    lattice_oklab = _display_to_oklab(lattice)
    source_lightness = lattice_oklab[..., 0]
    raw_lightness = _apply_mapping(source_lightness, *tone_mapping)
    # Retaining a small amount of the original curve prevents an unrelated
    # composition in the reference from forcing a brittle exposure/contrast
    # change when the optional contrast guard is disabled.
    mapped_lightness = source_lightness + (raw_lightness - source_lightness) * _TONE_MATCH_AMOUNT
    source_chroma = np.hypot(lattice_oklab[..., 1], lattice_oklab[..., 2])
    # Near-neutral RGB values include walls, paper and practical highlights.
    # Anchor them modestly to their source colour; strongly chromatic inputs
    # retain the full reference-style response.
    chroma_amount = _CHROMA_MATCH_AMOUNT * (
        _NEUTRAL_CHROMA_AMOUNT + (1.0 - _NEUTRAL_CHROMA_AMOUNT) * _smoothstep(0.018, 0.16, source_chroma)
    )
    raw_a = _apply_zone_mapping(lattice_oklab[..., 1], source_lightness, chroma_mappings[0])
    raw_b = _apply_zone_mapping(lattice_oklab[..., 2], source_lightness, chroma_mappings[1])
    mapped_oklab = np.stack(
        (
            mapped_lightness,
            lattice_oklab[..., 1] + (raw_a - lattice_oklab[..., 1]) * chroma_amount,
            lattice_oklab[..., 2] + (raw_b - lattice_oklab[..., 2]) * chroma_amount,
        ),
        axis=-1,
    )
    mapped_rgb = _oklab_to_display(mapped_oklab).clip(0.0, 1.0)
    identity = lattice.transpose(3, 0, 1, 2)
    return torch.from_numpy((mapped_rgb.transpose(3, 0, 1, 2) - identity).astype(np.float32))


def fit_dwg_residual_lut(content_dwg_di: Any, reference_display: Any, *, dimension: int = 33) -> Any:
    """Fit final DWG/DI LUT values directly from a DPX still and an sRGB reference.

    Unlike ``fit_global_residual_lut`` followed by a display-domain bake, this
    builds the lattice in DaVinci Intermediate from the start.  The reference
    is transformed into that same working space for the distribution fit, and
    every LUT row is written as a final DWG/DI result.
    """
    import torch

    if dimension < 2:
        raise ValueError("dimension must be at least 2")
    if content_dwg_di.ndim != 4 or reference_display.ndim != 4 or content_dwg_di.shape[1] != 3 or reference_display.shape[1] != 3:
        raise ValueError("content_dwg_di and reference_display must have shape [batch, 3, height, width].")

    source_dwg = content_dwg_di[0].detach().to("cpu").permute(1, 2, 0).numpy().clip(0.0, 1.0).astype(np.float32)
    reference_rgb = reference_display[0].detach().to("cpu").permute(1, 2, 0).numpy().clip(0.0, 1.0).astype(np.float32)
    reference_dwg = _display_to_dwg_di(reference_rgb)
    source_oklab = _dwg_di_to_oklab(_sample_pixels(source_dwg))
    reference_oklab = _dwg_di_to_oklab(_sample_pixels(reference_dwg))
    # A source DPX and a reference may represent exactly the same image after
    # their respective space conversions.  Treat that numerical round trip as
    # identity rather than letting sub-micro precision alter a far LUT corner.
    if source_oklab.shape == reference_oklab.shape and np.allclose(source_oklab, reference_oklab, atol=2e-6, rtol=2e-6):
        return torch.zeros((3, dimension, dimension, dimension), dtype=torch.float32)
    tone_mapping = _monotonic_tone_mapping(source_oklab[:, 0], reference_oklab[:, 0])
    chroma_mappings = [
        _zone_mapping(source_oklab[:, axis], source_oklab[:, 0], reference_oklab[:, axis], reference_oklab[:, 0])
        for axis in (1, 2)
    ]

    lattice_dwg = _identity_lattice(dimension)
    lattice_oklab = _dwg_di_to_oklab(lattice_dwg)
    source_lightness = lattice_oklab[..., 0]
    raw_lightness = _apply_mapping(source_lightness, *tone_mapping)
    mapped_lightness = source_lightness + (raw_lightness - source_lightness) * _TONE_MATCH_AMOUNT
    source_chroma = np.hypot(lattice_oklab[..., 1], lattice_oklab[..., 2])
    chroma_amount = _CHROMA_MATCH_AMOUNT * (
        _NEUTRAL_CHROMA_AMOUNT + (1.0 - _NEUTRAL_CHROMA_AMOUNT) * _smoothstep(0.018, 0.16, source_chroma)
    )
    raw_a = _apply_zone_mapping(lattice_oklab[..., 1], source_lightness, chroma_mappings[0])
    raw_b = _apply_zone_mapping(lattice_oklab[..., 2], source_lightness, chroma_mappings[1])
    mapped_oklab = np.stack(
        (
            mapped_lightness,
            lattice_oklab[..., 1] + (raw_a - lattice_oklab[..., 1]) * chroma_amount,
            lattice_oklab[..., 2] + (raw_b - lattice_oklab[..., 2]) * chroma_amount,
        ),
        axis=-1,
    )
    final_dwg = _oklab_to_dwg_di(mapped_oklab).clip(0.0, 1.0)
    identity = lattice_dwg.transpose(3, 0, 1, 2)
    return torch.from_numpy((final_dwg.transpose(3, 0, 1, 2) - identity).astype(np.float32))
