#!/usr/bin/env python3
"""Generate a portable Resolve .cube LUT from a source still and reference image."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from lutcore.cube_export import write_resolve_cube
from lutcore.colour_management import (
    bake_dwg_intermediate_residual,
    bake_slog3_to_rec709_residual,
    dwg_intermediate_to_rec709_gamma24,
    dwg_intermediate_to_srgb,
    precompensate_dwg_lut_residual_for_resolve_rec709,
    rec709_gamma24_to_dwg_intermediate,
    rec709_gamma24_to_srgb,
    reference_srgb_to_rec709_gamma24,
    resolve_dwg_to_rec709_gamma24,
    slog3_to_display_match_domain,
    uses_sony_lc709_baseline,
)
from lutcore.global_match import fit_dwg_residual_lut, fit_global_residual_lut
from lutcore.look_controls import LookControls, apply_look_controls, resize_residual_lut
from lutcore.nlut_runtime import infer_residual_lut, load_nlut, select_device
from lutcore.reference_analysis import analyse_reference, write_reference_analysis
from lutcore.trilinear import apply_residual_tensor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NLUT_ROOT = PROJECT_ROOT / "NLUT"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "models" / "336999_style_lut.pth"
DPX_SUFFIXES = {".dpx"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a global 33/65-point Resolve LUT from one source still and one reference image."
    )
    parser.add_argument("--content", type=Path, required=True, help="Source still: sRGB image data, DPX DWG + DI values, or native S-Log3 code values.")
    parser.add_argument("--reference", type=Path, required=True, help="Reference-grade image, expected as sRGB image data.")
    parser.add_argument("--output", type=Path, required=True, help="Destination .cube file.")
    parser.add_argument("--preview", type=Path, help="Optional sRGB PNG preview applied to the source still.")
    parser.add_argument("--analysis", type=Path, help="Optional JSON report of reference main colours and style statistics.")
    parser.add_argument("--engine", choices=("global", "nlut"), default="global", help="Global matching is the stable default; NLUT is experimental until per-pair refinement is added.")
    parser.add_argument("--size", choices=(33, 65), type=int, default=33, help="LUT lattice size (default: 33).")
    parser.add_argument("--match-strength", type=float, default=90.0)
    parser.add_argument("--shadows", type=float, default=100.0)
    parser.add_argument("--midtones", type=float, default=100.0)
    parser.add_argument("--highlights", type=float, default=100.0)
    parser.add_argument("--protect-skin", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--protect-saturation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--protect-contrast", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--working-space",
        choices=("rec709", "dwg-intermediate", "slog3"),
        default="rec709",
        help="LUT input domain: Rec.709 Gamma 2.4, DaVinci Wide Gamut + DaVinci Intermediate, or Sony S-Log3.",
    )
    parser.add_argument("--output-space", choices=("intermediate", "sRGB", "rec709-gamma24", "sony-lc709"), default="intermediate")
    parser.add_argument(
        "--slog3-gamut",
        choices=("sgamut3-cine", "sgamut3"),
        default="sgamut3-cine",
        help="Sony input gamut for S-Log3 mode.",
    )
    parser.add_argument(
        "--slog3-input-range",
        choices=("full", "video"),
        default="full",
        help="How the selected S-Log3 still stores its normalized RGB code values.",
    )
    parser.add_argument(
        "--resolve-output-compensation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="For a DPX-to-DWG LUT, precompensate the measured Resolve DWG-to-Rec.709 output response.",
    )
    parser.add_argument("--device", choices=("mps", "cpu"), help="Default: use MPS when the local Torch runtime supports it.")
    parser.add_argument("--nlut-root", type=Path, default=DEFAULT_NLUT_ROOT, help=argparse.SUPPRESS)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT, help=argparse.SUPPRESS)
    return parser.parse_args()


def is_dpx(path: Path) -> bool:
    return path.suffix.lower() in DPX_SUFFIXES


def _load_dpx_array(path: Path) -> np.ndarray:
    """Decode one DPX frame as normalized RGB code values with ffmpeg.

    ``rgb48le`` keeps DPX's precision in a predictable 0..65535 container;
    critically, no display transfer is applied here.  In DWG mode those values
    are the DI input to the LUT, not an sRGB image to reinterpret.
    """
    def executable(name: str) -> str | None:
        configured = os.environ.get(f"REFERENCE_LUT_{name.upper()}_PATH")
        candidates = (configured, f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}", shutil.which(name))
        return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)

    ffprobe = executable("ffprobe")
    ffmpeg = executable("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise RuntimeError("读取 DPX 需要本机安装 ffmpeg 与 ffprobe。")
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        stream = json.loads(probe.stdout)["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        decoded = subprocess.run(
            [ffmpeg, "-v", "error", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb48le", "pipe:1"],
            check=True,
            capture_output=True,
        ).stdout
    except (KeyError, IndexError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        raise RuntimeError(f"无法读取 DPX：{path.name}") from error
    expected_bytes = width * height * 3 * 2
    if len(decoded) != expected_bytes:
        raise RuntimeError(f"DPX 解码数据不完整：期望 {expected_bytes} 字节，实际 {len(decoded)} 字节。")
    return np.frombuffer(decoded, dtype="<u2").reshape(height, width, 3).astype(np.float32) / 65535.0


def load_rgb_tensor(path: Path) -> torch.Tensor:
    if not path.is_file():
        raise FileNotFoundError(path)
    if is_dpx(path):
        array = _load_dpx_array(path)
    else:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            array = np.asarray(image, dtype=np.float32) / 255.0
    return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)


def save_preview(image: torch.Tensor, path: Path) -> None:
    rgb = image.detach().to("cpu").squeeze(0).clamp(0.0, 1.0)
    pixels = (rgb.permute(1, 2, 0).numpy() * 255.0).round().astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels, mode="RGB").save(path)


def source_still_to_match_domain(
    content: torch.Tensor,
    *,
    is_dpx_source: bool = False,
    is_slog3_source: bool = False,
    slog3_gamut: str = "sgamut3-cine",
    slog3_input_range: str = "full",
) -> torch.Tensor:
    """Convert a selected still into the display match domain without losing its encoding."""
    if is_slog3_source:
        return slog3_to_display_match_domain(content, gamut=slog3_gamut, input_range=slog3_input_range)
    return dwg_intermediate_to_rec709_gamma24(content) if is_dpx_source else reference_srgb_to_rec709_gamma24(content)


def main() -> None:
    args = parse_args()
    controls = LookControls(
        match_strength=args.match_strength,
        shadows=args.shadows,
        midtones=args.midtones,
        highlights=args.highlights,
        protect_skin=args.protect_skin,
        protect_saturation=args.protect_saturation,
        protect_contrast=args.protect_contrast,
    ).validated()
    device = select_device(args.device)
    content = load_rgb_tensor(args.content)
    reference = load_rgb_tensor(args.reference)
    content_is_dpx = is_dpx(args.content)
    if is_dpx(args.reference):
        raise ValueError("参考图目前必须是 sRGB 图片；请使用 JPG、PNG、WebP 或 TIFF。")
    if content_is_dpx and args.working_space not in {"dwg-intermediate", "slog3"}:
        raise ValueError("DPX 视频静帧只能用于 DWG + DI 或 S-Log3 LUT。")
    if args.working_space == "slog3" and not content_is_dpx:
        raise ValueError("S-Log3 LUT 仅接受原生 S-Log3 DPX 视频静帧；请勿导入已转换的 JPG、PNG、WebP 或 TIFF。")
    reference_match = reference_srgb_to_rec709_gamma24(reference)
    # The selected still is an sRGB-tagged JPG/PNG display image.  Selecting
    # DWG changes the *LUT's target/input domain*, not the encoding of this
    # file.  Convert it to the match domain first, then bake that same look
    # into a DI cube below.
    slog3_match = args.working_space == "slog3"
    sony_lc709_match = slog3_match and uses_sony_lc709_baseline(gamut=args.slog3_gamut, input_range=args.slog3_input_range)
    content_match = source_still_to_match_domain(
        content,
        is_dpx_source=content_is_dpx and not slog3_match,
        is_slog3_source=slog3_match,
        slog3_gamut=args.slog3_gamut,
        slog3_input_range=args.slog3_input_range,
    )
    direct_dwg_match = args.engine == "global" and args.working_space == "dwg-intermediate" and content_is_dpx
    if args.engine == "global":
        residual = (
            fit_dwg_residual_lut(content, reference_match, dimension=args.size)
            if direct_dwg_match
            else fit_global_residual_lut(content_match, reference_match, dimension=args.size)
        )
    else:
        if args.working_space != "rec709":
            raise ValueError("The experimental NLUT engine is currently supported only for Rec.709 Gamma 2.4.")
        model = load_nlut(nlut_root=args.nlut_root, checkpoint_path=args.checkpoint, device=device)
        residual = infer_residual_lut(model, content_match, reference_match)
    residual = apply_look_controls(residual, controls)
    residual = resize_residual_lut(residual, args.size)
    if residual.ndim == 5:
        residual = residual[0]
    lut_residual = residual
    if args.working_space == "dwg-intermediate" and not direct_dwg_match:
        lut_residual = bake_dwg_intermediate_residual(residual, dimension=args.size)
    if slog3_match:
        lut_residual = bake_slog3_to_rec709_residual(
            residual,
            dimension=args.size,
            gamut=args.slog3_gamut,
            input_range=args.slog3_input_range,
        )
    resolve_output_compensation = direct_dwg_match and args.resolve_output_compensation
    if resolve_output_compensation:
        # The active Resolve output pipeline is calibrated from a real paired
        # DWG/DI -> Rec.709 DPX export.  Bake its inverse into the LUT so the
        # final Resolve image agrees with this tool's preview.
        lut_residual = precompensate_dwg_lut_residual_for_resolve_rec709(lut_residual)

    output_limits = (0.0, 1.0) if args.output_space in {"sRGB", "rec709-gamma24", "sony-lc709"} else None
    write_resolve_cube(
        args.output,
        lut_residual,
        title=f"Reference match {args.working_space} ({args.size}-point)",
        output_limits=output_limits,
        comments=(
            "Input domain: Rec.709 Gamma 2.4." if args.working_space == "rec709" else "Input domain: DaVinci Wide Gamut + DaVinci Intermediate." if args.working_space == "dwg-intermediate" else f"Input domain: Sony S-Log3 / {'S-Gamut3.Cine' if args.slog3_gamut == 'sgamut3-cine' else 'S-Gamut3'} ({args.slog3_input_range} range).",
            f"Export intent: {args.output_space}.",
            "Reference image is transformed into the DWG/DI working space for direct lattice matching." if direct_dwg_match else "Reference image is treated as sRGB and matched in a Rec.709 Gamma 2.4 display domain.",
            "S-Log3 source still is decoded with the selected Sony gamut and range, then restored through the selected display baseline." if slog3_match else "DPX source still is interpreted directly as DaVinci Intermediate." if content_is_dpx else "Source still is interpreted as sRGB image data; DWG selection changes only the exported LUT input domain.",
            "S-Log3 display baseline: bundled Sony S-Log3/S-Gamut3.Cine → LC-709 Look Profile." if sony_lc709_match else "S-Log3 display baseline: analytical S-Log3 → Rec.709 Gamma 2.4 fallback." if slog3_match else "S-Log3 display baseline: not applicable.",
            "Match method: direct DWG/DI lattice." if direct_dwg_match else "Match method: display-domain residual.",
            "Resolve DWG-to-Rec.709 output-response compensation: enabled." if resolve_output_compensation else "Resolve DWG-to-Rec.709 output-response compensation: disabled." if direct_dwg_match else "Resolve DWG-to-Rec.709 output-response compensation: not applicable.",
        ),
    )
    if args.preview:
        if args.working_space == "dwg-intermediate":
            # The static image is display-referred sRGB.  Re-encode its match
            # values into DI, then apply the same baked residual written to
            # the cube.  This is the target-node input that Resolve sees.
            preview_input = content.to(device) if content_is_dpx else rec709_gamma24_to_dwg_intermediate(content_match.to(device))
            preview_domain = apply_residual_tensor(preview_input, lut_residual)
            preview = rec709_gamma24_to_srgb(resolve_dwg_to_rec709_gamma24(preview_domain)) if resolve_output_compensation else dwg_intermediate_to_srgb(preview_domain)
        elif slog3_match:
            # The cube itself contains the S-Log3 restoration and final Rec.709
            # result.  Apply that same cube-domain residual to the unmodified
            # S-Log3 still so preview and exported LUT share one transform.
            preview_domain = apply_residual_tensor(content.to(device), lut_residual)
            preview = rec709_gamma24_to_srgb(preview_domain)
        else:
            preview_domain = apply_residual_tensor(content_match.to(device), lut_residual)
            preview = rec709_gamma24_to_srgb(preview_domain)
        save_preview(preview.to("cpu"), args.preview)
    if args.analysis:
        write_reference_analysis(args.analysis, analyse_reference(reference))
    print(f"Wrote LUT: {args.output}")
    if args.preview:
        print(f"Wrote preview: {args.preview}")
    if args.analysis:
        print(f"Wrote reference analysis: {args.analysis}")
    print(f"Engine: {args.engine}; working space: {args.working_space}; inference device: {device}")


if __name__ == "__main__":
    main()
