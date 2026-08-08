"""Small, explicit colour-management transforms for supported LUT domains.

Reference images are treated as sRGB.  The matching model works in a
Rec.709 Gamma 2.4 display domain, then is optionally baked into a DaVinci Wide
Gamut / DaVinci Intermediate LUT domain.  DWG primary matrices and the DI
transfer function are taken from Blackmagic Design's *DaVinci Wide Gamut
Intermediate* specification (revision 1.1, 2021).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np


_REC709_TO_XYZ = (
    (0.41239080, 0.35758434, 0.18048079),
    (0.21263901, 0.71516868, 0.07219232),
    (0.01933082, 0.11919478, 0.95053215),
)
_XYZ_TO_REC709 = (
    (3.24096994, -1.53738318, -0.49861076),
    (-0.96924364, 1.87596750, 0.04155506),
    (0.05563008, -0.20397696, 1.05697151),
)
_DWG_TO_XYZ = (
    (0.70062239, 0.14877482, 0.10105872),
    (0.27411851, 0.87363190, -0.14775041),
    (-0.09896291, -0.13789533, 1.32591599),
)
_XYZ_TO_DWG = (
    (1.51667204, -0.28147805, -0.14696363),
    (-0.46491710, 1.25142378, 0.17488461),
    (0.06484905, 0.10913934, 0.76141462),
)
# Sony's S-Log3 transfer curve and the S-Gamut3 / S-Gamut3.Cine primaries
# come from Sony's "Technical Summary for S-Gamut3.Cine/S-Log3 and
# S-Gamut3/S-Log3".  The matrices below are RGB-to-XYZ (D65), so they share
# the same XYZ/Rec.709 bridge used by the existing working spaces.
_S_GAMUT3_TO_XYZ = (
    (0.7064827132, 0.1288010498, 0.1151721641),
    (0.2709796708, 0.7866064112, -0.0575860820),
    (-0.0096778454, 0.0046000375, 1.0941355587),
)
_S_GAMUT3_CINE_TO_XYZ = (
    (0.5990839208, 0.2489255161, 0.1024464902),
    (0.2150758201, 0.8850685017, -0.1001443219),
    (-0.0320658495, -0.0276583907, 1.1487819910),
)
_SLOG3_LINEAR_CUT = 0.01125
_SLOG3_LOG_CUT = 171.2102946929 / 1023.0
_SLOG3_BLACK_CODE = 95.0
_SLOG3_MID_GREY_CODE = 420.0
_SLOG3_LOG_SLOPE = 261.5
_SLOG3_TOE_CODE = 171.2102946929
_VIDEO_RANGE_MIN = 64.0 / 1023.0
_VIDEO_RANGE_MAX = 940.0 / 1023.0
_SONY_LC709_CUBE_PATH = Path(__file__).with_name("assets") / "Sony_SLog3_SGamut3_CineToLC709.cube"
_DI_A = 0.0075
_DI_B = 7.0
_DI_C = 0.07329248
_DI_M = 10.44426855
_DI_LINEAR_CUT = 0.00262409
_DI_LOG_CUT = 0.02740668

# Measured from the user's Resolve export pair on 2026-08-06:
#   DWG/DI after the Reference LUT -> final Rec.709 Gamma 2.4 DPX.
#
# ``dwg_intermediate_to_rec709_gamma24`` is the mathematically direct colour
# conversion.  The active Resolve output chain applies an additional, smooth
# display roll-off.  These paired luminance knots model that final response in
# Rec.709 code values.  We use its inverse while writing a DWG LUT, then use
# its forward form for the in-app preview.  That makes the preview represent
# the *post-output-transform* image the editor will see, rather than the
# intermediate DI image.
_RESOLVE_709_CALIBRATION_INPUT = (
    0.013008, 0.082726, 0.095465, 0.110166, 0.130877,
    0.165866, 0.206379, 0.311328, 0.428005, 0.534343,
    0.697033, 0.805503, 1.161946, 1.340291, 1.689948,
)
_RESOLVE_709_CALIBRATION_OUTPUT = (
    0.009959, 0.018216, 0.025439, 0.035250, 0.051845,
    0.085751, 0.129193, 0.244167, 0.362749, 0.459052,
    0.583667, 0.651135, 0.800904, 0.849449, 0.903124,
)


def _torch() -> Any:
    import torch

    return torch


def _matrix(image: Any, values: tuple[tuple[float, float, float], ...]) -> Any:
    if image.ndim != 4 or image.shape[1] != 3:
        raise ValueError("image must have shape [batch, 3, height, width].")
    torch = _torch()
    matrix = torch.tensor(values, dtype=image.dtype, device=image.device)
    return torch.einsum("ij,bjhw->bihw", matrix, image)


def _signed_power(values: Any, exponent: float) -> Any:
    torch = _torch()
    return values.sign() * values.abs().pow(exponent)


def srgb_to_linear(image: Any) -> Any:
    torch = _torch()
    return torch.where(image <= 0.04045, image / 12.92, ((image + 0.055) / 1.055).clamp_min(0.0).pow(2.4))


def linear_to_srgb(image: Any) -> Any:
    torch = _torch()
    return torch.where(image <= 0.0031308, image * 12.92, 1.055 * image.clamp_min(0.0).pow(1.0 / 2.4) - 0.055)


def rec709_gamma24_to_linear(image: Any) -> Any:
    return _signed_power(image, 2.4)


def linear_to_rec709_gamma24(image: Any) -> Any:
    return _signed_power(image, 1.0 / 2.4)


def davinci_intermediate_to_linear(image: Any) -> Any:
    torch = _torch()
    return torch.where(image <= _DI_LOG_CUT, image / _DI_M, torch.pow(2.0, image / _DI_C - _DI_B) - _DI_A)


def linear_to_davinci_intermediate(image: Any) -> Any:
    torch = _torch()
    return torch.where(image <= _DI_LINEAR_CUT, image * _DI_M, (torch.log2(image.clamp_min(-_DI_A + 1e-12) + _DI_A) + _DI_B) * _DI_C)


def reference_srgb_to_rec709_gamma24(image: Any) -> Any:
    """Convert the browser/reference-image encoding into the match domain."""
    # sRGB and Rec.709 use the same D65 primaries; only their transfer
    # functions differ for this display-referred input path.
    return linear_to_rec709_gamma24(srgb_to_linear(image))


def rec709_gamma24_to_srgb(image: Any) -> Any:
    return linear_to_srgb(rec709_gamma24_to_linear(image))


def video_range_to_full(image: Any) -> Any:
    """Expand normalized 10-bit legal-range code values to full-range code values."""
    return (image - _VIDEO_RANGE_MIN) / (_VIDEO_RANGE_MAX - _VIDEO_RANGE_MIN)


def slog3_to_linear(image: Any) -> Any:
    """Decode normalized full-range S-Log3 code values to scene-linear reflection."""
    torch = _torch()
    return torch.where(
        image >= _SLOG3_LOG_CUT,
        torch.pow(10.0, (image * 1023.0 - _SLOG3_MID_GREY_CODE) / _SLOG3_LOG_SLOPE) * 0.19 - 0.01,
        (image * 1023.0 - _SLOG3_BLACK_CODE) * _SLOG3_LINEAR_CUT / (_SLOG3_TOE_CODE - _SLOG3_BLACK_CODE),
    )


def _slog3_gamut_matrix(gamut: str) -> tuple[tuple[float, float, float], ...]:
    if gamut == "sgamut3-cine":
        return _S_GAMUT3_CINE_TO_XYZ
    if gamut == "sgamut3":
        return _S_GAMUT3_TO_XYZ
    raise ValueError("S-Log3 gamut must be 'sgamut3-cine' or 'sgamut3'.")


def _slog3_sdr_highlight_rolloff(linear_rec709: Any) -> Any:
    """Map scene-linear S-Log3 highlights into an SDR Rec.709 display range.

    The neutral conversion keeps all scene values through 90% reflection, then
    applies one smooth, luminance-preserving knee.  This is the restoration
    component of the direct S-Log3-to-Rec.709 LUT; reference matching happens
    *after* this transform in the display domain.
    """
    torch = _torch()
    luminance = (
        linear_rec709[:, 0:1] * 0.2126
        + linear_rec709[:, 1:2] * 0.7152
        + linear_rec709[:, 2:3] * 0.0722
    )
    safe_luminance = luminance.clamp_min(1e-6)
    shoulder = 0.90 + 0.10 * (1.0 - torch.exp(-((safe_luminance - 0.90).clamp_min(0.0)) / 0.90))
    mapped_luminance = torch.where(luminance > 0.90, shoulder, luminance)
    return linear_rec709 * (mapped_luminance / safe_luminance)


def slog3_to_rec709_gamma24(
    image: Any,
    *,
    gamut: str = "sgamut3-cine",
    input_range: str = "full",
) -> Any:
    """Restore S-Log3 / S-Gamut3(-Cine) code values into SDR Rec.709 Gamma 2.4."""
    if input_range not in {"full", "video"}:
        raise ValueError("S-Log3 input range must be 'full' or 'video'.")
    code_values = image if input_range == "full" else video_range_to_full(image)
    linear_sgamut = slog3_to_linear(code_values)
    linear_rec709 = _matrix(_matrix(linear_sgamut, _slog3_gamut_matrix(gamut)), _XYZ_TO_REC709)
    return linear_to_rec709_gamma24(_slog3_sdr_highlight_rolloff(linear_rec709)).clamp(0.0, 1.0)


def uses_sony_lc709_baseline(*, gamut: str, input_range: str) -> bool:
    """Whether an input exactly matches the bundled Sony Cine/Full Look Profile."""
    return gamut == "sgamut3-cine" and input_range == "full"


@lru_cache(maxsize=1)
def _sony_lc709_residual_values() -> np.ndarray:
    """Load Sony's final 33-point cube as a residual volume in NLUT axis order."""
    if not _SONY_LC709_CUBE_PATH.is_file():
        raise RuntimeError(f"缺少内置 Sony LC-709 还原 LUT：{_SONY_LC709_CUBE_PATH}")
    rows: list[tuple[float, float, float]] = []
    dimension: int | None = None
    for line in _SONY_LC709_CUBE_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[0] == "LUT_3D_SIZE":
            dimension = int(fields[1])
            continue
        if len(fields) != 3:
            continue
        try:
            rows.append((float(fields[0]), float(fields[1]), float(fields[2])))
        except ValueError:
            continue
    if dimension != 33 or len(rows) != dimension ** 3:
        raise RuntimeError("内置 Sony LC-709 LUT 格式无效。")
    final_values = np.asarray(rows, dtype=np.float32).reshape(dimension, dimension, dimension, 3).transpose(3, 0, 1, 2)
    values = np.linspace(0.0, 1.0, dimension, dtype=np.float32)
    blue, green, red = np.meshgrid(values, values, values, indexing="ij")
    identity = np.stack((red, green, blue), axis=0)
    return final_values - identity


def sony_slog3_cine_to_lc709(image: Any) -> Any:
    """Apply Sony's supplied full-range S-Log3/S-Gamut3.Cine → LC-709 LUT."""
    from .trilinear import apply_residual_tensor

    torch = _torch()
    residual = torch.from_numpy(_sony_lc709_residual_values())
    return apply_residual_tensor(image, residual)


def slog3_to_display_match_domain(
    image: Any,
    *,
    gamut: str = "sgamut3-cine",
    input_range: str = "full",
) -> Any:
    """Restore S-Log3 into the exact display baseline used by matching.

    Cine/Full uses the bundled Sony LC-709 Look Profile, which is the same
    restoration LUT the user supplied.  Other supported Sony combinations
    retain the explicit analytical Rec.709 Gamma 2.4 fallback rather than
    incorrectly reusing a Cine/Full LUT.
    """
    if uses_sony_lc709_baseline(gamut=gamut, input_range=input_range):
        return sony_slog3_cine_to_lc709(image)
    return slog3_to_rec709_gamma24(image, gamut=gamut, input_range=input_range)


def dwg_intermediate_to_rec709_gamma24(image: Any) -> Any:
    linear_dwg = davinci_intermediate_to_linear(image)
    xyz = _matrix(linear_dwg, _DWG_TO_XYZ)
    return linear_to_rec709_gamma24(_matrix(xyz, _XYZ_TO_REC709))


def rec709_gamma24_to_dwg_intermediate(image: Any) -> Any:
    linear_rec709 = rec709_gamma24_to_linear(image)
    xyz = _matrix(linear_rec709, _REC709_TO_XYZ)
    return linear_to_davinci_intermediate(_matrix(xyz, _XYZ_TO_DWG))


def _piecewise_curve(image: Any, inputs: tuple[float, ...], outputs: tuple[float, ...]) -> Any:
    """Evaluate a monotonic curve, linearly extrapolating only at its ends."""
    torch = _torch()
    input_knots = torch.tensor(inputs, dtype=image.dtype, device=image.device)
    output_knots = torch.tensor(outputs, dtype=image.dtype, device=image.device)
    indexes = torch.bucketize(image.contiguous(), input_knots).clamp(1, input_knots.numel() - 1)
    left = indexes - 1
    right = indexes
    x0, x1 = input_knots[left], input_knots[right]
    y0, y1 = output_knots[left], output_knots[right]
    return y0 + (image - x0) * (y1 - y0) / (x1 - x0)


def _rec709_code_luminance(image: Any) -> Any:
    return image[:, 0:1] * 0.2126 + image[:, 1:2] * 0.7152 + image[:, 2:3] * 0.0722


def _resolve_calibration_gate(luminance: Any) -> Any:
    """Fade calibration in only after usable SDR shadow detail begins."""
    fraction = ((luminance - 0.015) / (0.080 - 0.015)).clamp(0.0, 1.0)
    return fraction * fraction * (3.0 - 2.0 * fraction)


def resolve_dwg_to_rec709_gamma24(image: Any) -> Any:
    """Model the measured Resolve DWG->Rec.709 output response for preview."""
    direct_rec709 = dwg_intermediate_to_rec709_gamma24(image)
    direct_luma = _rec709_code_luminance(direct_rec709)
    safe_luma = direct_luma.clamp_min(0.015)
    resolved_luma = _piecewise_curve(
        safe_luma,
        _RESOLVE_709_CALIBRATION_INPUT,
        _RESOLVE_709_CALIBRATION_OUTPUT,
    )
    gain = (resolved_luma / safe_luma).clamp(0.0, 1.0)
    gain = 1.0 + (gain - 1.0) * _resolve_calibration_gate(direct_luma)
    return direct_rec709 * gain


def precompensate_dwg_for_resolve_rec709(image: Any) -> Any:
    """Precompensate DI values so the measured Resolve output reaches ``image``'s direct look."""
    direct_rec709 = dwg_intermediate_to_rec709_gamma24(image)
    target_luma = _rec709_code_luminance(direct_rec709)
    safe_luma = target_luma.clamp_min(0.015)
    required_luma = _piecewise_curve(
        safe_luma,
        _RESOLVE_709_CALIBRATION_OUTPUT,
        _RESOLVE_709_CALIBRATION_INPUT,
    )
    # Do not force the response calibration into impossible, negative-luma
    # LUT corners.  A Resolve cube must remain stable for every RGB lattice
    # coordinate, including wide-gamut positions no SDR reference can measure.
    gain = (required_luma / safe_luma).clamp(1.0, 2.0)
    gain = 1.0 + (gain - 1.0) * _resolve_calibration_gate(target_luma)
    precompensated_rec709 = direct_rec709 * gain
    return rec709_gamma24_to_dwg_intermediate(precompensated_rec709)


def precompensate_dwg_lut_residual_for_resolve_rec709(residual_lut: Any) -> Any:
    """Apply the Resolve-output inverse curve to final values in a DI 3D LUT."""
    torch = _torch()
    if residual_lut.ndim != 4 or residual_lut.shape[0] != 3:
        raise ValueError("residual_lut must have shape [3, blue, green, red].")
    dimension = residual_lut.shape[-1]
    if any(size != dimension for size in residual_lut.shape[-3:]) or dimension < 2:
        raise ValueError("residual_lut must have equal LUT axes of length at least 2.")
    values = torch.linspace(0.0, 1.0, dimension, dtype=residual_lut.dtype, device=residual_lut.device)
    blue, green, red = torch.meshgrid(values, values, values, indexing="ij")
    identity = torch.stack((red, green, blue), dim=0)
    final_values = identity + residual_lut
    compensated = precompensate_dwg_for_resolve_rec709(final_values.reshape(1, 3, dimension, dimension * dimension))
    return compensated.squeeze(0).reshape_as(identity) - identity


def dwg_intermediate_to_srgb(image: Any) -> Any:
    return rec709_gamma24_to_srgb(dwg_intermediate_to_rec709_gamma24(image))


def bake_slog3_to_rec709_residual(
    display_residual: Any,
    *,
    dimension: int,
    gamut: str = "sgamut3-cine",
    input_range: str = "full",
) -> Any:
    """Bake an SDR reference-match residual into a direct S-Log3 display LUT.

    Resolve cubes always contain final RGB output.  Here each S-Log3 lattice
    position is first restored through the selected display baseline (Sony
    LC-709 for Cine/Full), receives the same display residual used by preview,
    and is then written back as its final display RGB value.  No additional CST
    node is required after the exported cube.
    """
    from .trilinear import apply_residual_tensor

    torch = _torch()
    if display_residual.ndim != 4 or display_residual.shape[0] != 3:
        raise ValueError("display_residual must have shape [3, blue, green, red].")
    if display_residual.shape[-3:] != (dimension, dimension, dimension):
        raise ValueError("display_residual LUT dimensions must match dimension.")
    values = torch.linspace(0.0, 1.0, dimension, dtype=display_residual.dtype, device=display_residual.device)
    blue, green, red = torch.meshgrid(values, values, values, indexing="ij")
    input_slog3 = torch.stack((red, green, blue), dim=0)
    flattened = input_slog3.reshape(1, 3, dimension, dimension * dimension)
    restored_display = slog3_to_display_match_domain(flattened, gamut=gamut, input_range=input_range)
    matched_display = apply_residual_tensor(restored_display, display_residual).clamp(0.0, 1.0)
    final_display = matched_display.squeeze(0).reshape_as(input_slog3)
    return final_display - input_slog3


def bake_dwg_intermediate_residual(display_residual: Any, *, dimension: int) -> Any:
    """Bake an SDR display-domain residual into a bounded DWG/Intermediate LUT.

    The match is derived from SDR reference images.  A DWG cube also contains
    wide-gamut and HDR coordinates which cannot be meaningfully inferred from
    those images.  Genuine extended-range highlights are therefore left
    unchanged, while normal-luminance wide-gamut colours still receive the
    same display look as the preview.  The latter matters in real DWG footage:
    a saturated green can sit outside a Rec.709 primary even though it is not
    an HDR pixel.
    """
    from .trilinear import apply_residual_tensor

    torch = _torch()
    values = torch.linspace(0.0, 1.0, dimension, dtype=display_residual.dtype, device=display_residual.device)
    blue, green, red = torch.meshgrid(values, values, values, indexing="ij")
    identity = torch.stack((red, green, blue), dim=0)
    flattened = identity.reshape(3, dimension, dimension * dimension).unsqueeze(0)
    display_input = dwg_intermediate_to_rec709_gamma24(flattened)
    # grid_sample uses border lookup outside its 0..1 domain.  Use that clipped
    # display position to retrieve the SDR look, then apply its delta back to
    # the original DWG-derived display value.  We deliberately do *not* gate on
    # every RGB channel being in range: that previously made any normal-bright
    # wide-gamut colour identity, so the exported DWG LUT diverged from the
    # preview.  Only luminance outside the meaningful SDR viewing range fades
    # back to identity, protecting true DI headroom without dropping chroma.
    display_clamped = display_input.clamp(0.0, 1.0)
    display_adjusted = apply_residual_tensor(display_clamped, display_residual)
    luminance = (
        display_input[:, 0:1] * 0.2126
        + display_input[:, 1:2] * 0.7152
        + display_input[:, 2:3] * 0.0722
    )
    shadow_gate = ((luminance + 0.08) / 0.08).clamp(0.0, 1.0)
    highlight_gate = ((1.18 - luminance) / 0.18).clamp(0.0, 1.0)
    visible_gate = shadow_gate * highlight_gate
    display_output = display_input + (display_adjusted - display_clamped) * visible_gate
    encoded_output = rec709_gamma24_to_dwg_intermediate(display_output).clamp(0.0, 1.0)
    return encoded_output.squeeze(0).reshape_as(identity) - identity
