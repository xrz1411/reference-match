# Reference LUT / 参考图仿色 LUT 生成器

[English README](README.en.md)

一个本地运行的 WebUI：导入一张参考图和一张视频静帧，提取参考图的主色调、亮度分布与对比关系，生成可直接下载的 `.cube` LUT 和匹配预览图。

所有图像读取、分析、匹配与导出均在本机完成，不上传素材。

## 独立桌面版

除 WebUI 外，项目提供可独立打开的桌面窗口版：不需要启动浏览器，也不依赖 DaVinci Resolve 插件。窗口内保留相同的本地导入、匹配、预览、下载、缓存清理与 LUT 库导入能力。

- macOS（Apple Silicon）：从 Releases 下载 `Reference-Match-*-mac-arm64.dmg`，将应用拖入“应用程序”后打开。
- Windows（x64）：从 Releases 下载 `Reference-Match-*-win-x64.exe` 后安装。
- macOS 发布包暂未公证，首次打开如出现保护提示，请在“系统设置 → 隐私与安全性”中选择“仍要打开”。

如果 macOS 提示“软件已损坏”，请先确认应用已拖入“应用程序”，再在终端执行：

```bash
xattr -cr "/Applications/Reference Match.app"
```

执行后重新打开应用即可。若放在其他位置，请将命令中的路径改为实际应用路径。

维护者在 macOS 构建 DMG：

```bash
cd desktop
npm install
REFERENCE_MATCH_PYTHON=../.venv/bin/python npm run build:mac
```

Windows EXE 由仓库的 GitHub Actions（`Build Windows desktop app`）在 Windows 环境生成；推送 `v*` 标签后会自动附加到对应 Release，也可在 Actions 页面手动运行。

## 功能

- 参考图主色板、RGB 直方图、Cb/Cr 矢量示波器；
- 全局 OKLab 色彩匹配，以及亮度和对比关系拟合；
- 肤色、饱和度、对比保护和分区权重；
- Rec.709 Gamma 2.4、DWG + DI、S-Log3 三种输入流程；
- 输出 33 点或 65 点 Resolve `.cube` LUT 与 PNG 预览；
- 拖放上传、原图/预览拖动对比、浏览器下载及本地缓存清理。

## 快速开始

需要 Python 3.10+，以及本机 `ffmpeg` / `ffprobe`（仅 DPX 读取需要）。

### macOS / Linux

```bash
git clone <your-repository-url> reference-lut
cd reference-lut
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run-webui.sh
```

### Windows

在 PowerShell 或命令提示符中执行：

```bat
git clone <your-repository-url> reference-lut
cd reference-lut
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
run-webui.bat
```

如果使用 DPX，请把 `ffmpeg` 和 `ffprobe` 所在目录加入 Windows 的 `PATH`，然后重新打开终端。

终端会显示本地地址；通常为 [http://127.0.0.1:8765](http://127.0.0.1:8765)。在浏览器打开即可使用。默认导出路径为 `webui/data/exports/`，可在界面“设置”中改为任意本机目录。

## 使用教程

### 1. 选择正确的素材

| 用途 | 可导入格式 | 规则 |
| --- | --- | --- |
| 参考图 | JPG、PNG、WebP、TIFF | 必须是已经显示为目标风格的 sRGB 图片，不能使用 DPX。 |
| Rec.709 视频静帧 | JPG、PNG、WebP、TIFF | 静帧应已处于 Rec.709 Gamma 2.4。 |
| DWG + DI 视频静帧 | DPX；或普通 sRGB 静帧 | DPX 会被直接视为 DWG + DI 数据。普通图片可用于风格拟合，但不代表它本身是 DWG 原始数据。 |
| S-Log3 视频静帧 | **仅 DPX** | 必须是未转色域的原生 S-Log3 / S-Gamut3 或 S-Gamut3.Cine DPX；不能导入已转换的 JPG、PNG、WebP 或 TIFF。 |

DPX 读取需要本机 `ffmpeg` 与 `ffprobe`。导入后，参考图会自动生成主色板、RGB 直方图和矢量示波器。

### 2. 选择 LUT 工作空间

- **Rec.709 Gamma 2.4**：用于已完成 Rec.709 Gamma 2.4 输入转换的素材。生成的 LUT 也以此为输入域。
- **DWG + DI**：用于已进入 DaVinci Wide Gamut + DaVinci Intermediate 的节点流程。将 LUT 放在 DWG + DI 域中，之后再由你的输出转换节点转为 Rec.709。
- **S-Log3**：选择与 DPX 源素材一致的输入色域和数据范围。生成的 LUT 已包含 S-Log3 还原及仿色结果，套用后直接输出 LC-709 / Rec.709 显示效果，**不要再在它后面叠加 S-Log3 → Rec.709 的色彩空间转换**。

### 3. 匹配与导出

1. 左侧导入参考图，中间导入视频静帧；
2. 选择工作空间、LUT 尺寸（33 点适合日常使用；65 点适合需要更细腻过渡的情况）；
3. 调整匹配强度与暗部 / 中间调 / 高光权重；默认三个保护均开启，结果会更稳定；
4. 点击“开始匹配”，用预览图上的分界线拖动对比原图与结果；
5. 下载 PNG 用于审阅，下载 `.cube` 用于调色软件。

“设置”可以调整默认导出文件夹；DWG + DI 流程的 Resolve 709 输出补偿默认开启，用于让 Resolve 内的最终 709 显示更接近 WebUI 预览。

### 4. 导入到 DaVinci Resolve 并套用到节点

1. 在 WebUI 点击“下载 LUT”保存 `.cube` 文件，或点击“导入 LUT 库”直接复制到设置中 Resolve LUT 路径的 `Reference LUT` 子文件夹（可在导入前命名）；
2. 打开 Resolve 的**调色**页面，在 LUT 浏览器中右键并选择“打开 LUT 文件夹”（不同版本也可在“项目设置 → 色彩管理 → 查找表”中找到“打开 LUT 文件夹”）；
3. 将 `.cube` 放入一个自建子文件夹，例如 `Reference LUT`；回到 LUT 浏览器右键选择“刷新”，或在项目设置中点击“更新列表”；
4. 在调色节点区域新建一个**串行节点**，右键该节点 → `3D LUT` → `Reference LUT` → 选择刚导入的 LUT。

Resolve 官方说明中，“打开 LUT 文件夹”用于打开当前安装实际使用的 LUT 目录；新增 LUT 后需要刷新 LUT 列表才会显示。[Blackmagic Design Resolve Reference Manual](https://documents.blackmagicdesign.com/UserManuals/DaVinci_Resolve_12_Reference_Manual.pdf)

**节点位置必须与导出工作空间一致：**

```text
Rec.709 LUT：输入转换 → Rec.709 Gamma 2.4 → [Reference LUT] → 后续节点
DWG + DI LUT：输入转换 → [Reference LUT] → DWG + DI 到 Rec.709 输出转换
S-Log3 LUT：原生 S-Log3 DPX → [Reference LUT] → 输出
```

- **Rec.709 LUT**：仅在图像已经到达 Rec.709 Gamma 2.4 后使用；不要把它直接套在 Log 或 DWG 节点上。
- **DWG + DI LUT**：放在 DWG + DI 工作空间内，且在最终 DWG + DI → Rec.709 输出转换之前。
- **S-Log3 LUT**：放在原生 S-Log3 DPX 上。该 LUT 已包含 S-Log3 还原和仿色结果，之后不要再添加 S-Log3 → Rec.709 转换节点。

不要把生成的创意 LUT 放进项目的 Input LUT、Output LUT 或 Display LUT 全局设置；它们会影响整个时间线或监看链路。应把它加在目标片段的串行节点中，便于逐镜头开关、混合和调整。

## 目录

```text
core/             匹配、色彩管理、LUT 导出与测试
webui/            本地 Web 服务与浏览器界面
promo-remotion/   宣传片 Remotion 源码（不含素材与渲染成品）
preview/          早期视觉预览稿
```

## 开发与测试

```bash
cd core
../.venv/bin/python -m unittest discover -s tests -v
```

Windows 下对应命令为：

```bat
cd core
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`webui/server.py` 只使用 Python 标准库作为 Web 服务；核心运行时依赖见 `requirements.txt`。
