"""CUDA-free trilinear sampling for NLUT residual volumes.

NLUT stores a residual 3D LUT as ``[channel][blue][green][red]``.  The pure
Python sampler exists both as a lightweight reference implementation and as a
test oracle.  The Torch adapter uses ``grid_sample`` and therefore runs on CPU
or Apple Silicon MPS without NLUT's custom CUDA extension.
"""

from __future__ import annotations

from math import floor
from typing import Any, Sequence


RGB = tuple[float, float, float]


def _as_nested_list(residual_lut: Any) -> list[list[list[list[float]]]]:
    if hasattr(residual_lut, "detach"):
        residual_lut = residual_lut.detach().to("cpu").tolist()
    if not isinstance(residual_lut, Sequence) or len(residual_lut) != 3:
        raise ValueError("residual_lut must have shape [3][blue][green][red].")

    channels = [list(channel) for channel in residual_lut]
    dimension = len(channels[0])
    if dimension < 2:
        raise ValueError("A 3D LUT must have a dimension of at least 2.")
    for channel in channels:
        if len(channel) != dimension:
            raise ValueError("All residual LUT axes must have the same dimension.")
        for blue_plane in channel:
            if len(blue_plane) != dimension:
                raise ValueError("All residual LUT axes must have the same dimension.")
            if any(len(green_row) != dimension for green_row in blue_plane):
                raise ValueError("All residual LUT axes must have the same dimension.")
    return channels


def _bounded_coordinate(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _interpolation_bounds(value: float, dimension: int) -> tuple[int, int, float]:
    coordinate = _bounded_coordinate(value) * (dimension - 1)
    lower = floor(coordinate)
    upper = min(lower + 1, dimension - 1)
    return lower, upper, coordinate - lower


def sample_residual_rgb(residual_lut: Any, rgb: RGB) -> RGB:
    """Sample an NLUT residual LUT at a normalized RGB colour.

    Inputs outside ``[0, 1]`` use border sampling, matching the Torch adapter's
    ``padding_mode='border'`` behaviour.
    """
    channels = _as_nested_list(residual_lut)
    dimension = len(channels[0])
    red0, red1, red_weight = _interpolation_bounds(rgb[0], dimension)
    green0, green1, green_weight = _interpolation_bounds(rgb[1], dimension)
    blue0, blue1, blue_weight = _interpolation_bounds(rgb[2], dimension)

    def sample_channel(channel: int) -> float:
        result = 0.0
        for blue_index, blue_factor in ((blue0, 1.0 - blue_weight), (blue1, blue_weight)):
            for green_index, green_factor in ((green0, 1.0 - green_weight), (green1, green_weight)):
                for red_index, red_factor in ((red0, 1.0 - red_weight), (red1, red_weight)):
                    result += (
                        float(channels[channel][blue_index][green_index][red_index])
                        * blue_factor
                        * green_factor
                        * red_factor
                    )
        return result

    return sample_channel(0), sample_channel(1), sample_channel(2)


def apply_residual_rgb(residual_lut: Any, rgb: RGB) -> RGB:
    """Apply the sampled NLUT residual to a normalized RGB colour."""
    residual = sample_residual_rgb(residual_lut, rgb)
    return rgb[0] + residual[0], rgb[1] + residual[1], rgb[2] + residual[2]


def apply_residual_tensor(image: Any, residual_lut: Any) -> Any:
    """Apply an NLUT residual volume to an ``N×3×H×W`` Torch image tensor.

    Torch is deliberately imported only when this function runs.  This keeps
    the LUT exporter and reference tests usable before the model runtime is
    installed.  The returned tensor preserves input headroom; it is not clipped.
    """
    try:
        import torch
        from torch.nn import functional as functional
    except ModuleNotFoundError as error:  # pragma: no cover - depends on runtime setup.
        raise RuntimeError("apply_residual_tensor requires a PyTorch runtime.") from error

    if image.ndim != 4 or image.shape[1] != 3:
        raise ValueError("image must have shape [batch, 3, height, width].")

    lut = residual_lut
    if lut.ndim == 4:
        lut = lut.unsqueeze(0)
    if lut.ndim != 5 or lut.shape[1] != 3:
        raise ValueError("residual_lut must have shape [3, blue, green, red] or [batch, 3, blue, green, red].")
    if any(size < 2 for size in lut.shape[-3:]):
        raise ValueError("Each residual LUT dimension must be at least 2.")
    if lut.shape[0] not in (1, image.shape[0]):
        raise ValueError("LUT batch dimension must be 1 or match the image batch dimension.")

    lut = lut.to(device=image.device, dtype=image.dtype)
    if lut.shape[0] == 1 and image.shape[0] > 1:
        lut = lut.expand(image.shape[0], -1, -1, -1, -1)

    # grid_sample's coordinates are (x, y, z) = (red, green, blue), while the
    # LUT volume is [batch, channel, blue, green, red].
    grid = torch.stack((image[:, 0], image[:, 1], image[:, 2]), dim=-1)
    grid = grid.mul(2.0).sub(1.0).unsqueeze(1)
    sampled_residual = functional.grid_sample(
        lut,
        grid,
        mode="bilinear",
        padding_mode="border",
        align_corners=True,
    ).squeeze(2)
    return image + sampled_residual
