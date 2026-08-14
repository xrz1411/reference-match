# Reference LUT

[中文 README](README.md)

A local-first WebUI that accepts a reference image and a video still, extracts the reference image's palette, luminance distribution, and contrast relationship, then generates a downloadable `.cube` LUT and matched PNG preview.

All image reading, analysis, matching, and export happen locally. No media is uploaded.

## Standalone desktop app

The project also ships as a standalone desktop window. It opens on its own and does not require a DaVinci Resolve plugin. The same local import, matching, preview, download, cache cleanup, and Resolve LUT-library import features remain available.

- macOS (Apple Silicon): download `Reference-Match-*-mac-arm64.dmg` from Releases and drag the app into Applications.
- Windows (x64): download and install `Reference-Match-*-win-x64.exe` from Releases.
- The macOS package is not notarized yet. On first launch, use **System Settings → Privacy & Security → Open Anyway** if macOS blocks it.

If macOS reports that the app is damaged, move it to Applications and run the following in Terminal:

```bash
xattr -cr "/Applications/Reference Match.app"
```

Then open the app again. Change the path if you installed it elsewhere.

For maintainers, run `npm install` and `REFERENCE_MATCH_PYTHON=../.venv/bin/python npm run build:mac` inside `desktop/` to create the macOS DMG. Windows installers are built in the repository's GitHub Actions workflow (`Build Windows desktop app`) on Windows; a `v*` tag attaches the installer to its corresponding Release.

## Features

- Dominant-colour palette, RGB histograms, and a Cb/Cr vectorscope;
- Global OKLab colour transfer with luminance and contrast fitting;
- Skin, saturation, and contrast safeguards with tonal-zone weights;
- Rec.709 Gamma 2.4, DWG + DI, and S-Log3 input workflows;
- 33-point and 65-point Resolve `.cube` LUTs plus PNG previews;
- Drag-and-drop import, draggable before/after comparison, browser downloads, and local cache cleanup.

## Quick start

Requires Python 3.10+ and local `ffmpeg` / `ffprobe` for DPX input.

### macOS / Linux

```bash
git clone <your-repository-url> reference-lut
cd reference-lut
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./run-webui.sh
```

### Windows

Run the following in PowerShell or Command Prompt:

```bat
git clone <your-repository-url> reference-lut
cd reference-lut
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
run-webui.bat
```

For DPX input, add the folder containing `ffmpeg.exe` and `ffprobe.exe` to the Windows `PATH`, then open a new terminal.

The terminal prints the local address, normally [http://127.0.0.1:8765](http://127.0.0.1:8765). Exports default to `webui/data/exports/` and can be redirected to any local directory from Settings.

## Usage guide

### 1. Choose the right source files

| Purpose | Accepted formats | Rule |
| --- | --- | --- |
| Reference image | JPG, PNG, WebP, TIFF | Use an sRGB image that already displays the intended look. DPX is not accepted. |
| Rec.709 video still | JPG, PNG, WebP, TIFF | The still should already be in Rec.709 Gamma 2.4. |
| DWG + DI video still | DPX, or a regular sRGB still | DPX is interpreted directly as DWG + DI data. A regular image can be used for look fitting, but it is not treated as original DWG data. |
| S-Log3 video still | **DPX only** | Use an unconverted native S-Log3 / S-Gamut3 or S-Gamut3.Cine DPX. Converted JPG, PNG, WebP, and TIFF files are rejected. |

DPX decoding requires local `ffmpeg` and `ffprobe`. After importing a reference image, its palette, RGB histograms, and vectorscope are generated automatically.

### 2. Select the LUT working space

- **Rec.709 Gamma 2.4**: for footage that has already been converted to Rec.709 Gamma 2.4. The generated LUT uses that input domain.
- **DWG + DI**: for a node workflow already in DaVinci Wide Gamut + DaVinci Intermediate. Apply this LUT in the DWG + DI domain, then use your output transform node to convert to Rec.709.
- **S-Log3**: choose the gamut and range matching the source DPX. The exported LUT contains both the S-Log3 restoration and look match, and produces an LC-709 / Rec.709 display result directly. **Do not add another S-Log3-to-Rec.709 transform after it.**

### 3. Match and export

1. Import the reference image on the left and the video still in the middle.
2. Choose the working space and LUT size (33-point for everyday use; 65-point for finer transitions).
3. Adjust match strength and shadow / midtone / highlight weights. All three safeguards are enabled by default for a more stable result.
4. Click **Start matching**, then drag the divider in the preview to compare the original and match.
5. Download the PNG for review and the `.cube` file for grading software.

Settings can change the default export folder. Resolve 709 output compensation is enabled by default for DWG + DI workflows so the final Resolve Rec.709 display more closely matches the WebUI preview.

### 4. Import into DaVinci Resolve and apply on a node

1. Click **Download LUT** in the WebUI to save the `.cube` file, or click **Import LUT Library** to copy it directly into the `Reference LUT` subfolder of the configured Resolve LUT path (you can name it before importing).
2. Open Resolve's **Color** page. In the LUT browser, right-click and choose **Open LUT Folder**. Depending on the Resolve version, the same action is also available from **Project Settings → Color Management → Lookup Tables**.
3. Copy the `.cube` file into a subfolder such as `Reference LUT`. Return to the LUT browser and choose **Refresh**, or use **Update Lists** in Project Settings.
4. Create a **serial node** in the node graph, right-click it, then choose `3D LUT` → `Reference LUT` → the imported LUT.

Blackmagic Design documents that **Open LUT Folder** opens the LUT directory Resolve is actually using, and that new LUTs must be followed by a LUT-list refresh before they appear. [Blackmagic Design Resolve Reference Manual](https://documents.blackmagicdesign.com/UserManuals/DaVinci_Resolve_12_Reference_Manual.pdf)

**Match the node position to the exported working space:**

```text
Rec.709 LUT: input transform → Rec.709 Gamma 2.4 → [Reference LUT] → later nodes
DWG + DI LUT: input transform → [Reference LUT] → DWG + DI to Rec.709 output transform
S-Log3 LUT: native S-Log3 DPX → [Reference LUT] → output
```

- **Rec.709 LUT**: use it only after the image is Rec.709 Gamma 2.4. Do not apply it directly to Log or DWG footage.
- **DWG + DI LUT**: place it inside the DWG + DI working space, before the final DWG + DI-to-Rec.709 output transform.
- **S-Log3 LUT**: place it on the native S-Log3 DPX. It already includes S-Log3 restoration and the reference match, so do not add an S-Log3-to-Rec.709 transform after it.

Do not put these creative LUTs in the project's global Input LUT, Output LUT, or Display LUT settings: those affect the entire timeline or monitoring pipeline. Apply the LUT on a serial node for the target clip so it remains easy to enable, blend, and adjust per shot.

## Layout

```text
core/             Matching, colour management, LUT export, and tests
webui/            Local web server and browser interface
```

## Development and testing

```bash
cd core
../.venv/bin/python -m unittest discover -s tests -v
```

On Windows, use:

```bat
cd core
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`webui/server.py` uses only the Python standard library for HTTP serving. Core runtime dependencies are listed in `requirements.txt`.
