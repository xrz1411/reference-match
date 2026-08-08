"""Explain the reference image as a small, deterministic colour-style summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _rgb_to_hsv(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    maximum = rgb.max(axis=1)
    minimum = rgb.min(axis=1)
    delta = maximum - minimum
    hue = np.zeros_like(maximum)
    nonzero = delta > 1e-7
    red = (maximum == rgb[:, 0]) & nonzero
    green = (maximum == rgb[:, 1]) & nonzero
    blue = (maximum == rgb[:, 2]) & nonzero
    hue[red] = ((rgb[red, 1] - rgb[red, 2]) / delta[red]) % 6.0
    hue[green] = (rgb[green, 2] - rgb[green, 0]) / delta[green] + 2.0
    hue[blue] = (rgb[blue, 0] - rgb[blue, 1]) / delta[blue] + 4.0
    return hue * 60.0, np.divide(delta, maximum, out=np.zeros_like(delta), where=maximum > 1e-7), maximum


def _hex(rgb: np.ndarray) -> str:
    values = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    return "#" + "".join(f"{value:02X}" for value in values)


def _main_colours(pixels: np.ndarray, *, count: int = 10) -> list[dict[str, Any]]:
    """Return weighted RGB k-means clusters with deterministic initialization."""
    if pixels.shape[0] > 80_000:
        indexes = np.linspace(0, pixels.shape[0] - 1, 80_000, dtype=np.int64)
        pixels = pixels[indexes]
    seed_indexes = np.linspace(0, pixels.shape[0] - 1, count, dtype=np.int64)
    centroids = pixels[seed_indexes].copy()
    for _ in range(24):
        distances = ((pixels[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        labels = distances.argmin(axis=1)
        updated = np.array(
            [pixels[labels == index].mean(axis=0) if np.any(labels == index) else centroids[index] for index in range(count)]
        )
        if np.allclose(updated, centroids, atol=1e-5):
            break
        centroids = updated
    proportions = np.bincount(labels, minlength=count) / labels.size
    result = [
        {"hex": _hex(centroid), "rgb": [round(float(value), 4) for value in centroid], "coverage": round(float(share), 4)}
        for centroid, share in zip(centroids, proportions)
    ]
    # The palette is presented as a visual ramp, so keep nearby perceived
    # brightness values adjacent instead of ordering it by coverage.
    return sorted(
        result,
        key=lambda entry: (
            sum(component * weight for component, weight in zip(entry["rgb"], (0.2126, 0.7152, 0.0722))),
            entry["hex"],
        ),
    )


def _hue_label(degrees: float | None) -> str:
    """Return a concise Chinese colour-family label for the displayed hue."""
    if degrees is None:
        return "中性低饱和"
    hue = degrees % 360.0
    if hue < 15.0 or hue >= 345.0:
        return "暖红"
    if hue < 45.0:
        return "暖橙"
    if hue < 70.0:
        return "暖黄"
    if hue < 105.0:
        return "黄绿"
    if hue < 150.0:
        return "自然绿"
    if hue < 185.0:
        return "冷青"
    if hue < 230.0:
        return "冷蓝"
    if hue < 275.0:
        return "冷紫"
    if hue < 325.0:
        return "洋红"
    return "玫红"


def analyse_reference(image: Any, *, colours: int = 10) -> dict[str, Any]:
    """Summarise major colours plus brightness, contrast, and saturation tendencies."""
    if image.ndim != 4 or image.shape[1] != 3:
        raise ValueError("image must have shape [batch, 3, height, width].")
    pixels = image[0].detach().to("cpu").permute(1, 2, 0).numpy().reshape(-1, 3).clip(0.0, 1.0)
    luma = pixels @ np.array([0.2126, 0.7152, 0.0722])
    hue, saturation, _ = _rgb_to_hsv(pixels)
    colourful = saturation > 0.12
    if np.any(colourful):
        weights = saturation[colourful]
        angles = np.deg2rad(hue[colourful])
        # Hue is circular: an ordinary mean incorrectly calls a mixture around
        # 359° and 1° cyan.  The vector mean keeps it near red as expected.
        average_hue = float(np.rad2deg(np.arctan2(np.average(np.sin(angles), weights=weights), np.average(np.cos(angles), weights=weights))) % 360.0)
    else:
        average_hue = None
    return {
        "main_colours": _main_colours(pixels, count=colours),
        "brightness": {
            "p10": round(float(np.percentile(luma, 10)), 4),
            "median": round(float(np.percentile(luma, 50)), 4),
            "p90": round(float(np.percentile(luma, 90)), 4),
            "contrast_span": round(float(np.percentile(luma, 90) - np.percentile(luma, 10)), 4),
        },
        "saturation": {"mean": round(float(saturation.mean()), 4), "p90": round(float(np.percentile(saturation, 90)), 4)},
        "hue": {
            "mean_degrees": round(average_hue, 1) if average_hue is not None else None,
            "label": _hue_label(average_hue),
        },
    }


def write_reference_analysis(path: str | Path, analysis: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination
