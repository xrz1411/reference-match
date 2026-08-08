#!/usr/bin/env python3
"""Local-only WebUI server for Reference LUT."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

WEB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = WEB_ROOT.parent
CORE_ROOT = PROJECT_ROOT / "core"
DATA_ROOT = WEB_ROOT / "data"
UPLOAD_ROOT = DATA_ROOT / "uploads"
DEFAULT_EXPORT_ROOT = DATA_ROOT / "exports"
SETTINGS_PATH = DATA_ROOT / "settings.json"
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".dpx"}
REFERENCE_EXTENSIONS = ALLOWED_EXTENSIONS - {".dpx"}
CACHE_EXTENSIONS = {".cube", ".png", ".json"}

sys.path.insert(0, str(CORE_ROOT))
from generate_lut import load_rgb_tensor, save_preview  # noqa: E402
from lutcore.reference_analysis import analyse_reference  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Reference LUT WebUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Default: 127.0.0.1 (local only).")
    parser.add_argument("--port", type=int, default=8765, help="Bind port. Default: 8765.")
    return parser.parse_args()


def safe_name(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(value).stem).strip("-") or "image"
    return stem[:80]


def default_resolve_lut_directory() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\\ProgramData")) / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "LUT"
    if sys.platform == "darwin":
        return Path("/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT")
    return Path("/home/resolve/LUT")


def read_settings() -> dict[str, Any]:
    try:
        raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("settings must be an object")
    except (OSError, ValueError, json.JSONDecodeError):
        raw = {}
    return {
        "outputDirectory": str(raw.get("outputDirectory") or DEFAULT_EXPORT_ROOT),
        "resolveLutDirectory": str(raw.get("resolveLutDirectory") or default_resolve_lut_directory()),
        "resolveOutputCompensation": raw.get("resolveOutputCompensation") is not False,
    }


def write_settings(changes: dict[str, Any]) -> dict[str, Any]:
    settings = {**read_settings(), **changes}
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return settings


def output_directory() -> Path:
    destination = Path(read_settings()["outputDirectory"]).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def settings_payload() -> dict[str, Any]:
    settings = read_settings()
    destination = output_directory()
    return {
        "outputDirectory": str(destination),
        "isDefault": destination == DEFAULT_EXPORT_ROOT.resolve(),
        "resolveLutDirectory": str(Path(settings["resolveLutDirectory"]).expanduser()),
        "resolveOutputCompensation": settings["resolveOutputCompensation"],
    }


def local_executable(name: str) -> str | None:
    configured = os.environ.get(f"REFERENCE_LUT_{name.upper()}_PATH")
    candidates = (configured, f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}", f"/usr/bin/{name}", shutil.which(name))
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def dpx_preview(source: Path, destination: Path) -> None:
    """Write an unscaled browser preview from the exact DPX decoder used for matching."""
    save_preview(load_rgb_tensor(source), destination)


def parse_multipart_file(content_type: str, payload: bytes) -> tuple[str, bytes]:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type, flags=re.IGNORECASE)
    if not match:
        raise ValueError("缺少 multipart boundary。")
    delimiter = b"--" + (match.group(1) or match.group(2)).encode("utf-8")
    for part in payload.split(delimiter):
        if b"Content-Disposition:" not in part or b"\r\n\r\n" not in part:
            continue
        headers, body = part.split(b"\r\n\r\n", 1)
        disposition = headers.decode("utf-8", errors="replace")
        filename = re.search(r'filename="([^"]*)"', disposition, flags=re.IGNORECASE)
        if not filename:
            continue
        if body.endswith(b"\r\n"):
            body = body[:-2]
        return filename.group(1), body
    raise ValueError("未收到图片文件。")


class ReferenceLutServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int]):
        super().__init__(address, ReferenceLutHandler)
        self.uploads: dict[str, dict[str, Any]] = {}
        self.artifacts: dict[str, Path] = {}


class ReferenceLutHandler(BaseHTTPRequestHandler):
    server: ReferenceLutServer
    max_request_bytes = 512 * 1024 * 1024

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.send_json({"error": message}, status)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > self.max_request_bytes:
            raise ValueError("请求大小无效。")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("请求格式无效。")
        return value

    def artifact_url(self, path: Path, *, download: bool = False) -> str:
        token = uuid.uuid4().hex
        self.server.artifacts[token] = path
        suffix = "/download" if download else ""
        return f"/media/{token}{suffix}"

    def upload_payload(self, kind: str, original_name: str, body: bytes) -> dict[str, Any]:
        suffix = Path(original_name).suffix.lower()
        accepted = REFERENCE_EXTENSIONS if kind == "reference" else ALLOWED_EXTENSIONS
        if suffix not in accepted:
            raise ValueError("参考图支持常见 sRGB 图片；视频静帧另支持 DPX。")
        if not body:
            raise ValueError("图片文件为空。")
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        source = UPLOAD_ROOT / f"{token}-{safe_name(original_name)}{suffix}"
        source.write_bytes(body)
        preview = source
        if suffix == ".dpx":
            preview = UPLOAD_ROOT / f"{token}-preview.png"
            try:
                dpx_preview(source, preview)
            except (RuntimeError, subprocess.CalledProcessError) as error:
                source.unlink(missing_ok=True)
                detail = getattr(error, "stderr", b"")
                if isinstance(detail, bytes):
                    detail = detail.decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"无法生成 DPX 预览。{detail or error}") from error
        try:
            from PIL import Image
            with Image.open(preview) as image:
                width, height = image.size
        except Exception as error:
            source.unlink(missing_ok=True)
            if preview != source:
                preview.unlink(missing_ok=True)
            raise RuntimeError("无法读取图片，请确认文件格式。") from error
        self.server.uploads[token] = {"path": source, "preview": preview, "name": Path(original_name).name, "kind": kind}
        return {"id": token, "name": Path(original_name).name, "width": width, "height": height, "url": self.artifact_url(preview)}

    def uploaded(self, token: Any, kind: str) -> dict[str, Any]:
        item = self.server.uploads.get(str(token))
        if not item or item["kind"] != kind or not item["path"].is_file():
            raise ValueError("上传素材已失效，请重新导入。")
        return item

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            self.send_json({"ready": True, "message": "已就绪：全部分析与匹配均在此设备完成。"})
            return
        if path == "/api/settings":
            self.send_json(settings_payload())
            return
        if path.startswith("/media/"):
            self.serve_artifact(path)
            return
        requested = "index.html" if path in {"/", ""} else path.lstrip("/")
        candidate = (WEB_ROOT / requested).resolve()
        if WEB_ROOT not in candidate.parents and candidate != WEB_ROOT:
            self.send_error_json("找不到文件。", HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error_json("找不到文件。", HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(candidate))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def serve_artifact(self, path: str) -> None:
        parts = path.split("/")
        token = parts[2] if len(parts) > 2 else ""
        artifact = self.server.artifacts.get(token)
        if not artifact or not artifact.is_file():
            self.send_error_json("文件已失效。", HTTPStatus.NOT_FOUND)
            return
        content = artifact.read_bytes()
        download = len(parts) > 3 and parts[3] == "download"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(artifact))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{artifact.name}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        try:
            if path in {"/api/upload/reference", "/api/upload/content"}:
                self.handle_upload(path.rsplit("/", 1)[-1])
            elif path == "/api/analyse":
                self.handle_analyse()
            elif path == "/api/match":
                self.handle_match()
            elif path == "/api/settings":
                self.handle_settings()
            elif path == "/api/import-lut-library":
                self.handle_import_lut_library()
            elif path == "/api/clear-cache":
                self.handle_clear_cache()
            else:
                self.send_error_json("找不到接口。", HTTPStatus.NOT_FOUND)
        except (ValueError, RuntimeError, subprocess.CalledProcessError) as error:
            self.send_error_json(str(error))
        except Exception as error:  # avoid leaking internal paths or tracebacks to the browser
            print(f"Unexpected error: {error}", file=sys.stderr)
            self.send_error_json("本地处理失败，请查看启动终端的错误信息。", HTTPStatus.INTERNAL_SERVER_ERROR)

    def handle_upload(self, kind: str) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > self.max_request_bytes:
            raise ValueError("图片大小无效或超过 512 MB。")
        filename, body = parse_multipart_file(self.headers.get("Content-Type", ""), self.rfile.read(length))
        self.send_json(self.upload_payload(kind, filename, body))

    def handle_analyse(self) -> None:
        payload = self.read_json()
        reference = self.uploaded(payload.get("referenceId"), "reference")
        report = analyse_reference(load_rgb_tensor(reference["path"]))
        self.send_json(report)

    def handle_match(self) -> None:
        payload = self.read_json()
        reference = self.uploaded(payload.get("referenceId"), "reference")
        content = self.uploaded(payload.get("contentId"), "content")
        space = payload.get("space")
        if space not in {"rec709", "dwg", "slog3"}:
            raise ValueError("请选择有效的 LUT 工作空间。")
        if content["path"].suffix.lower() == ".dpx" and space == "rec709":
            raise ValueError("DPX 视频静帧仅可用于 DWG + DI 或 S-Log3 LUT。")
        if space == "slog3" and content["path"].suffix.lower() != ".dpx":
            raise ValueError("S-Log3 LUT 仅接受原生 S-Log3 DPX 视频静帧；请勿导入已转换的 JPG、PNG、WebP 或 TIFF。")
        size = 65 if payload.get("size") == 65 else 33
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination = output_directory()
        prefix = destination / f"reference-match-{timestamp}-{uuid.uuid4().hex[:8]}-{size}"
        cube_path = prefix.with_suffix(".cube")
        preview_path = prefix.with_name(prefix.name + "-preview.png")
        analysis_path = prefix.with_name(prefix.name + "-analysis.json")
        def percent(key: str, fallback: int) -> str:
            try:
                return str(max(0, min(100, round(float(payload.get(key, fallback))))))
            except (TypeError, ValueError):
                return str(fallback)
        def is_enabled(key: str) -> bool:
            return payload.get(key) is not False
        gamut = "sgamut3" if payload.get("slog3Gamut") == "sgamut3" else "sgamut3-cine"
        input_range = "video" if payload.get("slog3InputRange") == "video" else "full"
        sony_lc709 = space == "slog3" and gamut == "sgamut3-cine" and input_range == "full"
        args = [
            str(CORE_ROOT / "generate_lut.py"), "--content", str(content["path"]), "--reference", str(reference["path"]),
            "--output", str(cube_path), "--preview", str(preview_path), "--analysis", str(analysis_path),
            "--engine", "global", "--size", str(size),
            "--working-space", "dwg-intermediate" if space == "dwg" else space,
            "--output-space", "intermediate" if space == "dwg" else "sony-lc709" if sony_lc709 else "rec709-gamma24" if space == "slog3" else "sRGB",
            "--slog3-gamut", gamut, "--slog3-input-range", input_range,
            "--match-strength", percent("strength", 90), "--shadows", percent("shadows", 100),
            "--midtones", percent("midtones", 100), "--highlights", percent("highlights", 100),
        ]
        if not read_settings()["resolveOutputCompensation"]:
            args.append("--no-resolve-output-compensation")
        for request_key, argument in (("protectSkin", "--no-protect-skin"), ("protectSaturation", "--no-protect-saturation"), ("protectContrast", "--no-protect-contrast")):
            if not is_enabled(request_key):
                args.append(argument)
        try:
            subprocess.run([sys.executable, *args], cwd=CORE_ROOT, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "").strip()
            raise RuntimeError(f"匹配失败。{detail}") from error
        self.send_json({
            "started": True,
            "workingSpace": space,
            "previewUrl": self.artifact_url(preview_path),
            "pngDownloadUrl": self.artifact_url(preview_path, download=True),
            "lutId": self.artifact_url(cube_path).split("/")[2],
            "lutDownloadUrl": self.artifact_url(cube_path, download=True),
        })

    def handle_settings(self) -> None:
        payload = self.read_json()
        changes: dict[str, Any] = {}
        if payload.get("useDefault") is True:
            changes["outputDirectory"] = str(DEFAULT_EXPORT_ROOT.resolve())
        elif "outputDirectory" in payload:
            candidate = str(payload["outputDirectory"]).strip()
            if not candidate:
                raise ValueError("产出路径不能为空。")
            destination = Path(candidate).expanduser().resolve()
            destination.mkdir(parents=True, exist_ok=True)
            changes["outputDirectory"] = str(destination)
        if "resolveLutDirectory" in payload:
            candidate = str(payload["resolveLutDirectory"]).strip()
            if not candidate:
                raise ValueError("Resolve LUT 库路径不能为空。")
            changes["resolveLutDirectory"] = str(Path(candidate).expanduser().resolve())
        if "resolveOutputCompensation" in payload:
            changes["resolveOutputCompensation"] = payload["resolveOutputCompensation"] is not False
        write_settings(changes)
        self.send_json(settings_payload())

    def handle_import_lut_library(self) -> None:
        payload = self.read_json()
        cube_path = self.server.artifacts.get(str(payload.get("lutId")))
        if not cube_path or not cube_path.is_file() or cube_path.suffix.lower() != ".cube" or not cube_path.name.startswith("reference-match-"):
            raise ValueError("当前 LUT 已失效，请重新匹配后再导入。")
        name = safe_name(str(payload.get("name") or cube_path.stem))
        destination = Path(read_settings()["resolveLutDirectory"]).expanduser().resolve() / "Reference LUT" / f"{name}.cube"
        if destination.exists():
            raise ValueError("Resolve LUT 库中已有同名文件，请更换名称后重试。")
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cube_path, destination)
        except OSError as error:
            raise RuntimeError(f"无法写入 Resolve LUT 库：{error}") from error
        self.send_json({"imported": True, "path": str(destination), "message": "已导入 Resolve LUT 库。请在 Resolve LUT 浏览器中右键选择“刷新”。"})

    def handle_clear_cache(self) -> None:
        destination = output_directory()
        removed = 0
        for entry in destination.iterdir():
            if entry.is_file() and entry.name.startswith("reference-match-") and entry.suffix.lower() in CACHE_EXTENSIONS:
                entry.unlink()
                removed += 1
        self.send_json({"cleared": True, "removed": removed, "message": f"已清理 {removed} 个缓存文件。"})


def main() -> None:
    args = parse_args()
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    DEFAULT_EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    server = ReferenceLutServer((args.host, args.port))
    print(f"Reference LUT WebUI 已启动：http://{args.host}:{args.port}")
    print("按 Ctrl+C 停止服务。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
