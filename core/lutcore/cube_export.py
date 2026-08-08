"""Export NLUT's residual 3D LUT representation as a standard Resolve .cube LUT.

NLUT stores values in ``[channel][blue][green][red]`` order and applies them as
``output = input + residual``. Resolve .cube rows instead encode final output
RGB values, with red changing fastest. This module performs that conversion
without requiring PyTorch so the output contract is independently testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence


RGB = tuple[float, float, float]


def _as_nested_list(residual_lut: Any) -> list[list[list[list[float]]]]:
    """Accept a nested sequence or a Torch-like tensor and normalise it to lists."""
    if hasattr(residual_lut, "detach"):
        residual_lut = residual_lut.detach().to("cpu").tolist()

    if not isinstance(residual_lut, Sequence) or len(residual_lut) != 3:
        raise ValueError("residual_lut must have shape [3][blue][green][red].")

    channels = [list(channel) for channel in residual_lut]
    dim = len(channels[0])
    if dim < 2:
        raise ValueError("A 3D LUT must have a dimension of at least 2.")

    for channel in channels:
        if len(channel) != dim:
            raise ValueError("All residual LUT axes must have the same dimension.")
        for blue_plane in channel:
            if len(blue_plane) != dim:
                raise ValueError("All residual LUT axes must have the same dimension.")
            for green_row in blue_plane:
                if len(green_row) != dim:
                    raise ValueError("All residual LUT axes must have the same dimension.")

    return channels


def _apply_output_limits(rgb: RGB, output_limits: tuple[float, float] | None) -> RGB:
    if output_limits is None:
        return rgb

    lower, upper = output_limits
    if lower > upper:
        raise ValueError("output_limits must be ordered as (lower, upper).")
    return tuple(max(lower, min(upper, value)) for value in rgb)  # type: ignore[return-value]


def residual_to_cube_rows(
    residual_lut: Any,
    *,
    output_limits: tuple[float, float] | None = None,
) -> tuple[int, list[RGB]]:
    """Bake an NLUT residual volume into final .cube RGB rows.

    ``output_limits`` is opt-in. Keeping it as ``None`` preserves working-space
    headroom; a display-referred export may explicitly use ``(0.0, 1.0)``.
    """
    channels = _as_nested_list(residual_lut)
    dimension = len(channels[0])
    denominator = dimension - 1
    rows: list[RGB] = []

    # Resolve/Iridas .cube convention: red index changes fastest, then green,
    # then blue. NLUT's native storage uses [channel][blue][green][red].
    for blue_index in range(dimension):
        blue = blue_index / denominator
        for green_index in range(dimension):
            green = green_index / denominator
            for red_index in range(dimension):
                red = red_index / denominator
                residual = (
                    float(channels[0][blue_index][green_index][red_index]),
                    float(channels[1][blue_index][green_index][red_index]),
                    float(channels[2][blue_index][green_index][red_index]),
                )
                rows.append(
                    _apply_output_limits(
                        (red + residual[0], green + residual[1], blue + residual[2]),
                        output_limits,
                    )
                )

    return dimension, rows


def write_resolve_cube(
    path: str | Path,
    residual_lut: Any,
    *,
    title: str = "NLUT look",
    output_limits: tuple[float, float] | None = None,
    comments: Iterable[str] = (),
) -> Path:
    """Write a Resolve-compatible 3D .cube file from an NLUT residual volume."""
    dimension, rows = residual_to_cube_rows(residual_lut, output_limits=output_limits)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_title = title.replace('"', "'")

    lines = ["# Generated from an NLUT residual 3D LUT"]
    lines.extend(f"# {comment}" for comment in comments)
    lines.extend([f'TITLE "{safe_title}"', "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", f"LUT_3D_SIZE {dimension}", ""])
    lines.extend(f"{red:.7f} {green:.7f} {blue:.7f}" for red, green, blue in rows)
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return destination
