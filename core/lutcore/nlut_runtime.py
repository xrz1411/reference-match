"""Load the official NLUT model without its Linux/CUDA trilinear extension.

The upstream repository is intentionally left untouched in ``../NLUT``.  This
adapter imports its model and replaces only the custom CUDA sampler with the
portable Torch sampler in :mod:`lutcore.trilinear`.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
import types
from pathlib import Path
from typing import Any, Iterator

from .trilinear import apply_residual_tensor


DEFAULT_MODEL_CONFIG = "2048+32+32"
DEFAULT_LUT_DIMENSION = 33


@contextlib.contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def select_device(preferred: str | None = None) -> str:
    """Return an available local inference device; CUDA is deliberately unused."""
    import torch

    if preferred is not None:
        if preferred not in {"cpu", "mps"}:
            raise ValueError("preferred device must be 'mps' or 'cpu'.")
        if preferred == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("MPS was requested but is not available in this PyTorch runtime.")
        return preferred
    return "mps" if torch.backends.mps.is_available() else "cpu"


class _PortableResidualSampler:  # wrapped as a Torch module after Torch is imported.
    pass


def _portable_sampler_module() -> Any:
    import torch

    class PortableResidualSampler(torch.nn.Module):
        """Keep NLUT's expected sampler contract: return residual, not final RGB."""

        def forward(self, lut: Any, image: Any) -> Any:
            return apply_residual_tensor(image, lut) - image

    return PortableResidualSampler()


def _import_upstream_model(nlut_root: Path) -> Any:
    """Import NLUT while supplying a harmless placeholder for its CUDA extension."""
    if not nlut_root.is_dir():
        raise FileNotFoundError(f"NLUT source directory does not exist: {nlut_root}")
    if not (nlut_root / "models" / "vgg_normalised.pth").is_file():
        raise FileNotFoundError("NLUT's bundled VGG weights are missing.")

    path_text = str(nlut_root)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

    # ``nlut_models`` imports this compiled Linux/CUDA module at import time.
    # It is not called because load_nlut replaces the sampler before inference.
    sys.modules.setdefault("trilinear", types.ModuleType("trilinear"))
    # ``utils.LUT`` unconditionally imports pyplot although inference never
    # touches plotting.  Avoid making a display/plotting stack a runtime
    # dependency for a local LUT export tool.
    try:
        importlib.import_module("matplotlib.pyplot")
    except ModuleNotFoundError:
        matplotlib = types.ModuleType("matplotlib")
        pyplot = types.ModuleType("matplotlib.pyplot")
        matplotlib.pyplot = pyplot  # type: ignore[attr-defined]
        sys.modules.setdefault("matplotlib", matplotlib)
        sys.modules.setdefault("matplotlib.pyplot", pyplot)
    return importlib.import_module("nlut_models")


def load_nlut(
    *,
    nlut_root: str | Path,
    checkpoint_path: str | Path,
    model_config: str = DEFAULT_MODEL_CONFIG,
    lut_dimension: int = DEFAULT_LUT_DIMENSION,
    device: str | None = None,
) -> Any:
    """Load the official checkpoint and return an eval-mode portable NLUT model.

    The model still produces a *residual* LUT in NLUT's ``[3, B, G, R]`` order.
    Use ``lutcore.cube_export.write_resolve_cube`` to bake it for Resolve.
    """
    import torch

    source_root = Path(nlut_root).resolve()
    checkpoint = Path(checkpoint_path).resolve()
    if not checkpoint.is_file():
        raise FileNotFoundError(f"NLUT checkpoint does not exist: {checkpoint}")

    upstream = _import_upstream_model(source_root)
    with _working_directory(source_root):
        model = upstream.NLUTNet(model_config, lut_dimension)
    model.TrilinearInterpolation = _portable_sampler_module()

    loaded = torch.load(checkpoint, map_location="cpu", weights_only=False)
    state_dict = loaded.get("state_dict", loaded) if isinstance(loaded, dict) else loaded
    incompatible = model.load_state_dict(state_dict, strict=False)
    if incompatible.missing_keys:
        raise RuntimeError(
            "The NLUT checkpoint is missing active model parameters: "
            + ", ".join(incompatible.missing_keys)
        )
    allowed_legacy_keys = ("SB1.", "blurer.")
    unexpected = [
        key
        for key in incompatible.unexpected_keys
        if not key.startswith(allowed_legacy_keys)
    ]
    if unexpected:
        raise RuntimeError(
            "The NLUT checkpoint has unexpected parameters that are not known "
            "legacy training-only layers: " + ", ".join(unexpected)
        )
    model.to(select_device(device))
    model.eval()
    return model


def infer_residual_lut(model: Any, content: Any, reference: Any) -> Any:
    """Predict one NLUT residual LUT from normalized ``N×3×H×W`` image tensors."""
    import torch

    if content.ndim != 4 or reference.ndim != 4:
        raise ValueError("content and reference must have shape [batch, 3, height, width].")
    if content.shape[0] != reference.shape[0] or content.shape[1] != 3 or reference.shape[1] != 3:
        raise ValueError("content and reference must have matching batch sizes and three RGB channels.")

    device = next(model.parameters()).device
    with torch.inference_mode():
        _, _, metadata = model(content.to(device), content.to(device), reference.to(device))
    return metadata["LUT"]
