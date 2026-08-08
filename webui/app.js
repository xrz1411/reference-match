const state = {
  reference: null,
  content: null,
  result: null,
  scopeData: null,
  runtimeReady: false,
  size: 33,
  space: 'rec709',
  slog3: { gamut: 'sgamut3-cine', inputRange: 'full' },
  protections: { skin: true, saturation: true, contrast: true },
  comparison: { enabled: true, position: 50 },
};

const referenceImage = document.querySelector('#reference-image');
const contentImage = document.querySelector('#content-image');
const resultImage = document.querySelector('#result-image');
const comparisonLayer = document.querySelector('#comparison-layer');
const comparisonSourceImage = document.querySelector('#comparison-source-image');
const comparisonSourceCanvas = document.querySelector('#comparison-source-canvas');
const comparisonFrame = document.querySelector('#result-frame');
const comparisonDivider = document.querySelector('#comparison-divider');
const comparisonToggle = document.querySelector('#toggle-comparison');
const status = document.querySelector('#match-status');
const runtimeStatus = document.querySelector('#runtime-status');
const matchButton = document.querySelector('#match');
const settingsDialog = document.querySelector('#settings-dialog');
const outputDirectory = document.querySelector('#output-directory');
const resolveLutDirectory = document.querySelector('#resolve-lut-directory');
const outputPathKind = document.querySelector('#output-path-kind');
const resolveOutputCompensationButton = document.querySelector('#resolve-output-compensation');
const cacheOutcome = document.querySelector('#cache-outcome');
const palette = document.querySelector('#palette');
const scopeNote = document.querySelector('#scope-note');
const histogramCanvases = [...document.querySelectorAll('canvas[data-channel]')];
const vectorscopeCanvas = document.querySelector('#vectorscope');
const slog3Options = document.querySelector('#slog3-options');
const contentFileInput = document.querySelector('#content-file');

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(options.headers || {}) } });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || '本地服务请求失败。');
  return payload;
}

function setStatus(message, error = false) {
  status.textContent = message;
  status.style.color = error ? '#dc8080' : '';
}

function setRuntimeStatus(ready) {
  runtimeStatus.replaceChildren(document.createElement('i'), document.createTextNode(ready ? '已就绪' : '未就绪'));
  runtimeStatus.classList.toggle('offline', !ready);
}

function spaceLabel(space = state.space) {
  return space === 'dwg' ? 'DWG + DI' : space === 'slog3' ? 'S-Log3 → LC-709' : 'Rec.709 Gamma 2.4';
}

function updateMatchButton() {
  const invalidSlog3Source = state.space === 'slog3' && state.content && !state.content.name.toLowerCase().endsWith('.dpx');
  matchButton.disabled = !(state.runtimeReady && state.reference && state.content) || invalidSlog3Source;
}

function setRangeAppearance(input) {
  const percent = (Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min)) * 100;
  input.style.background = `linear-gradient(to right,#ebc45f ${percent}%,#545b67 ${percent}%)`;
}

function resetCachedResult() {
  state.result = null;
  resultImage.removeAttribute('src');
  resultImage.hidden = true;
  comparisonSourceImage.removeAttribute('src');
  comparisonSourceCanvas.getContext('2d').clearRect(0, 0, comparisonSourceCanvas.width, comparisonSourceCanvas.height);
  document.querySelector('#result-empty').hidden = false;
  document.querySelector('#result-meta').textContent = '等待匹配';
  document.querySelector('#result-name').textContent = '尚无结果';
  document.querySelector('.result-actions').hidden = true;
  renderComparison();
}

function renderComparison() {
  const enabled = Boolean(state.result && state.content && state.comparison.enabled);
  comparisonLayer.hidden = !enabled;
  comparisonFrame.classList.toggle('comparison-active', enabled);
  comparisonToggle.hidden = !(state.result && state.content);
  comparisonToggle.textContent = enabled ? '关闭对比' : '开启对比';
  comparisonToggle.setAttribute('aria-pressed', String(enabled));
  comparisonLayer.style.setProperty('--comparison-position', `${state.comparison.position}%`);
  if (enabled) drawComparisonSource();
}

function drawComparisonSource() {
  if (!comparisonSourceImage.naturalWidth || !resultImage.naturalWidth) return;
  const bounds = comparisonFrame.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(bounds.width * dpr));
  const height = Math.max(1, Math.round(bounds.height * dpr));
  if (comparisonSourceCanvas.width !== width || comparisonSourceCanvas.height !== height) {
    comparisonSourceCanvas.width = width;
    comparisonSourceCanvas.height = height;
  }
  const context = comparisonSourceCanvas.getContext('2d');
  context.clearRect(0, 0, width, height);
  // The output preview is the authority for the visible comparison rectangle.
  // In comparison mode both layers deliberately use the same `cover` mapping.
  // This prevents a DPX browser preview with a slightly different aspect ratio
  // from shrinking or drifting relative to the generated preview.
  const previewRatio = resultImage.naturalWidth / resultImage.naturalHeight;
  const frameRatio = width / height;
  let targetWidth = width;
  let targetHeight = height;
  let targetX = 0;
  let targetY = 0;
  if (previewRatio > frameRatio) {
    targetWidth = height * previewRatio;
    targetX = (width - targetWidth) / 2;
  } else {
    targetHeight = width / previewRatio;
    targetY = (height - targetHeight) / 2;
  }
  context.drawImage(comparisonSourceImage, targetX, targetY, targetWidth, targetHeight);
}

function updateComparisonPosition(clientX) {
  const bounds = comparisonFrame.getBoundingClientRect();
  if (!bounds.width) return;
  state.comparison.position = Math.max(0, Math.min(100, (clientX - bounds.left) / bounds.width * 100));
  renderComparison();
}

function beginComparisonDrag(event) {
  if (!state.comparison.enabled) return;
  event.preventDefault();
  comparisonDivider.setPointerCapture(event.pointerId);
  updateComparisonPosition(event.clientX);
  const move = (moveEvent) => updateComparisonPosition(moveEvent.clientX);
  const finish = () => {
    comparisonDivider.removeEventListener('pointermove', move);
    comparisonDivider.removeEventListener('pointerup', finish);
    comparisonDivider.removeEventListener('pointercancel', finish);
  };
  comparisonDivider.addEventListener('pointermove', move);
  comparisonDivider.addEventListener('pointerup', finish);
  comparisonDivider.addEventListener('pointercancel', finish);
}

async function displayImage(kind, data) {
  const image = kind === 'reference' ? referenceImage : contentImage;
  image.src = data.url;
  image.hidden = false;
  document.querySelector(`#${kind}-empty`).hidden = true;
  document.querySelector(`#${kind}-name`).textContent = data.name;
  await image.decode();
  document.querySelector(`#${kind}-meta`).textContent = `${image.naturalWidth} × ${image.naturalHeight}`;
}

async function uploadImage(kind, file) {
  if (!file) return;
  if (kind === 'content' && state.space === 'slog3' && !file.name.toLowerCase().endsWith('.dpx')) {
    throw new Error('S-Log3 LUT 仅支持导入原生 S-Log3 DPX 视频静帧。');
  }
  const form = new FormData();
  form.append('file', file, file.name);
  setStatus(`正在导入${kind === 'reference' ? '参考图' : '视频静帧'}…`);
  const response = await api(`/api/upload/${kind}`, { method: 'POST', body: form });
  state[kind] = response;
  await displayImage(kind, response);
  if (kind === 'reference') await analyseReference();
  if (state.reference && state.content) setStatus('素材已就绪，可以开始匹配。');
  else setStatus('继续选择另一张图片。');
  updateMatchButton();
}

function renderPalette(colours) {
  palette.replaceChildren(...colours.map((entry) => {
    const chip = document.createElement('div');
    chip.className = 'colour-chip';
    const swatch = document.createElement('i');
    swatch.style.setProperty('--c', entry.hex);
    const label = document.createElement('b');
    label.textContent = entry.hex;
    chip.append(swatch, label);
    return chip;
  }));
}

function prepareCanvas(target) {
  const dpr = window.devicePixelRatio || 1;
  const bounds = target.getBoundingClientRect();
  const width = Math.max(1, Math.round(bounds.width * dpr));
  const height = Math.max(1, Math.round(bounds.height * dpr));
  if (target.width !== width || target.height !== height) { target.width = width; target.height = height; }
  return [target.getContext('2d'), width, height];
}

function smoothAndReduce(channel) {
  const weights = [1, 6, 15, 20, 15, 6, 1];
  const radius = 3;
  const smooth = channel.map((_, index) => {
    let sum = 0; let weight = 0;
    weights.forEach((value, weightIndex) => {
      const source = index + weightIndex - radius;
      if (source >= 0 && source < channel.length) { sum += channel[source] * value; weight += value; }
    });
    return sum / weight;
  });
  return Array.from({ length: 64 }, (_, index) => smooth.slice(index * 4, index * 4 + 4).reduce((sum, value) => sum + value, 0) / 4);
}

function drawChannel(target, channel, stroke, fill) {
  const [context, width, height] = prepareCanvas(target);
  context.clearRect(0, 0, width, height);
  context.strokeStyle = '#343a44'; context.lineWidth = 1;
  for (let y = height / 3; y < height; y += height / 3) { context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke(); }
  const values = smoothAndReduce(channel); const maximum = Math.max(...values) || 1;
  const point = (count, index) => [index / (values.length - 1) * width, height - 2 - Math.log1p(count) / Math.log1p(maximum) * (height - 5)];
  context.beginPath(); context.moveTo(0, height); values.forEach((count, index) => context.lineTo(...point(count, index))); context.lineTo(width, height); context.closePath(); context.fillStyle = fill; context.fill();
  context.beginPath(); values.forEach((count, index) => index ? context.lineTo(...point(count, index)) : context.moveTo(...point(count, index))); context.strokeStyle = stroke; context.lineWidth = 1.4; context.stroke();
}

function drawVectorscope() {
  const [context, width, height] = prepareCanvas(vectorscopeCanvas);
  context.clearRect(0, 0, width, height);
  const cx = width / 2; const cy = height / 2; const radius = Math.min(width, height) * .43;
  context.strokeStyle = '#414958'; context.lineWidth = 1;
  [1 / 3, 2 / 3, 1].forEach((fraction) => { context.beginPath(); context.arc(cx, cy, radius * fraction, 0, Math.PI * 2); context.stroke(); });
  context.beginPath(); context.moveTo(cx - radius, cy); context.lineTo(cx + radius, cy); context.moveTo(cx, cy - radius); context.lineTo(cx, cy + radius); context.stroke();
  const { density, densitySize } = state.scopeData; const maximum = Math.max(...density) || 1;
  for (let y = 0; y < densitySize; y += 1) for (let x = 0; x < densitySize; x += 1) {
    const count = density[y * densitySize + x]; if (!count) continue;
    context.fillStyle = `rgba(158,210,137,${.08 + .82 * Math.sqrt(count / maximum)})`;
    context.fillRect(cx + (x / (densitySize - 1) - .5) * radius * 2.1, cy + (y / (densitySize - 1) - .5) * radius * 2.1, Math.max(1, radius * 2.1 / densitySize), Math.max(1, radius * 2.1 / densitySize));
  }
}

function drawScopes() {
  if (!state.scopeData) return;
  const colours = [['#e07575', 'rgba(144,48,48,.38)'], ['#84b97f', 'rgba(42,113,53,.42)'], ['#7da8d0', 'rgba(35,84,139,.45)']];
  histogramCanvases.forEach((canvas, index) => drawChannel(canvas, state.scopeData.histogram[index], ...colours[index]));
  drawVectorscope();
}

function calculateScopes(image) {
  const width = Math.min(320, image.naturalWidth); const height = Math.max(1, Math.round(image.naturalHeight * width / image.naturalWidth));
  const sample = document.createElement('canvas'); sample.width = width; sample.height = height;
  const context = sample.getContext('2d', { willReadFrequently: true }); context.drawImage(image, 0, 0, width, height);
  const rgba = context.getImageData(0, 0, width, height).data;
  const histogram = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)]; const densitySize = 128; const density = new Uint32Array(densitySize * densitySize);
  for (let index = 0; index < rgba.length; index += 4) {
    const red = rgba[index]; const green = rgba[index + 1]; const blue = rgba[index + 2]; histogram[0][red] += 1; histogram[1][green] += 1; histogram[2][blue] += 1;
    const cb = (-.168736 * red - .331264 * green + .5 * blue) / 255 + .5; const cr = (.5 * red - .418688 * green - .081312 * blue) / 255 + .5;
    density[Math.min(densitySize - 1, Math.max(0, Math.round(cb * (densitySize - 1)))) * densitySize + Math.min(densitySize - 1, Math.max(0, Math.round(cr * (densitySize - 1))))] += 1;
  }
  return { histogram, density, densitySize };
}

async function analyseReference() {
  const report = await api('/api/analyse', { method: 'POST', body: JSON.stringify({ referenceId: state.reference.id }) });
  renderPalette(report.main_colours);
  document.querySelector('#hue-value').textContent = report.hue.mean_degrees == null ? report.hue.label : `${report.hue.label} · ${Math.round(report.hue.mean_degrees)}°`;
  document.querySelector('#brightness-value').textContent = report.brightness.median.toFixed(3);
  document.querySelector('#saturation-value').textContent = report.saturation.mean.toFixed(3);
  state.scopeData = calculateScopes(referenceImage); drawScopes();
  scopeNote.textContent = '直方图采用 7 点平滑与 64 段显示 · 矢量示波器为 Cb / Cr 密度';
}

function renderSpaceSelection() {
  for (const space of ['rec709', 'dwg', 'slog3']) document.querySelector(`#${space}`).classList.toggle('active', state.space === space);
  slog3Options.hidden = state.space !== 'slog3';
  contentFileInput.accept = state.space === 'slog3' ? '.dpx' : '.jpg,.jpeg,.png,.webp,.tif,.tiff,.dpx';
}

function selectWorkingSpace(space) {
  const changed = state.space !== space;
  state.space = space;
  renderSpaceSelection();
  if (changed) resetCachedResult();
  if (space === 'slog3' && state.content && !state.content.name.toLowerCase().endsWith('.dpx')) {
    setStatus('S-Log3 LUT 仅支持 DPX 视频静帧，请重新导入原生 S-Log3 DPX。', true);
  } else {
    setStatus(changed ? `已切换到 ${spaceLabel()}，请重新匹配。` : `当前适用于 ${spaceLabel()}。`);
  }
  updateMatchButton();
}

async function runMatch() {
  matchButton.disabled = true;
  setStatus('正在提取主色调并拟合整体色彩与光影…');
  try {
    const response = await api('/api/match', { method: 'POST', body: JSON.stringify({
      referenceId: state.reference.id, contentId: state.content.id, size: state.size, space: state.space,
      slog3Gamut: state.slog3.gamut, slog3InputRange: state.slog3.inputRange,
      strength: Number(document.querySelector('#strength').value), shadows: Number(document.querySelector('#shadows').value), midtones: Number(document.querySelector('#midtones').value), highlights: Number(document.querySelector('#highlights').value),
      protectSkin: state.protections.skin, protectSaturation: state.protections.saturation, protectContrast: state.protections.contrast,
    }) });
    state.result = response;
    resultImage.src = response.previewUrl;
    comparisonSourceImage.src = state.content.url;
    resultImage.hidden = false;
    document.querySelector('#result-empty').hidden = true;
    await Promise.all([resultImage.decode(), comparisonSourceImage.decode()]);
    state.comparison.enabled = true; state.comparison.position = 50; renderComparison();
    document.querySelector('#result-meta').textContent = `${state.size} 点 LUT · ${spaceLabel(response.workingSpace)}`;
    document.querySelector('#result-name').textContent = '匹配预览已生成';
    document.querySelector('.result-actions').hidden = false;
    setStatus('匹配完成。可下载 PNG、LUT 或导入 Resolve LUT 库。');
  } catch (error) { setStatus(error.message || '匹配失败。', true); }
  updateMatchButton();
}

function renderOutputSettings(settings) {
  outputDirectory.value = settings.outputDirectory;
  resolveLutDirectory.value = settings.resolveLutDirectory;
  outputPathKind.textContent = settings.isDefault ? '当前使用 WebUI 默认路径' : '当前使用自定义本机路径';
  const enabled = settings.resolveOutputCompensation !== false;
  resolveOutputCompensationButton.classList.toggle('active', enabled);
  resolveOutputCompensationButton.setAttribute('aria-pressed', String(enabled));
}

async function loadSettings() {
  renderOutputSettings(await api('/api/settings'));
}

async function saveSettings(reset = false) {
  const response = await api('/api/settings', { method: 'POST', body: JSON.stringify(reset ? { useDefault: true, resolveLutDirectory: resolveLutDirectory.value } : { outputDirectory: outputDirectory.value, resolveLutDirectory: resolveLutDirectory.value }) });
  renderOutputSettings(response);
  resetCachedResult();
  setStatus(reset ? '已恢复默认产出路径。' : '已更新默认产出路径。');
}

document.querySelector('#choose-reference').addEventListener('click', () => document.querySelector('#reference-file').click());
document.querySelector('#choose-content').addEventListener('click', () => document.querySelector('#content-file').click());
document.querySelector('#reference-file').addEventListener('change', async (event) => { try { await uploadImage('reference', event.target.files[0]); } catch (error) { setStatus(error.message, true); } finally { event.target.value = ''; } });
document.querySelector('#content-file').addEventListener('change', async (event) => { try { await uploadImage('content', event.target.files[0]); } catch (error) { setStatus(error.message, true); } finally { event.target.value = ''; } });
for (const zone of document.querySelectorAll('[data-drop-target]')) {
  const kind = zone.dataset.dropTarget;
  zone.addEventListener('dragenter', (event) => { event.preventDefault(); zone.classList.add('drop-active'); });
  zone.addEventListener('dragover', (event) => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; zone.classList.add('drop-active'); });
  zone.addEventListener('dragleave', (event) => { if (!zone.contains(event.relatedTarget)) zone.classList.remove('drop-active'); });
  zone.addEventListener('drop', async (event) => { event.preventDefault(); zone.classList.remove('drop-active'); try { await uploadImage(kind, event.dataTransfer.files?.[0]); } catch (error) { setStatus(error.message, true); } });
}
document.querySelector('#match').addEventListener('click', runMatch);
comparisonDivider.addEventListener('pointerdown', beginComparisonDrag);
comparisonToggle.addEventListener('click', () => { state.comparison.enabled = !state.comparison.enabled; renderComparison(); });
document.querySelector('#export-png').addEventListener('click', () => { if (state.result) window.location.assign(state.result.pngDownloadUrl); });
document.querySelector('#export-lut').addEventListener('click', () => { if (state.result) window.location.assign(state.result.lutDownloadUrl); });
document.querySelector('#import-lut-library').addEventListener('click', async () => {
  if (!state.result) return;
  const name = prompt('为导入 Resolve LUT 库的文件命名：', 'Reference-LUT');
  if (name == null) return;
  try {
    const response = await api('/api/import-lut-library', { method: 'POST', body: JSON.stringify({ lutId: state.result.lutId, name }) });
    setStatus(`${response.message} ${response.path}`);
  } catch (error) { setStatus(error.message || '导入 LUT 库失败。', true); }
});
document.querySelector('#strength').addEventListener('input', (event) => { document.querySelector('#strength-output').textContent = event.target.value; setRangeAppearance(event.target); });
for (const input of document.querySelectorAll('input[type=range]')) { setRangeAppearance(input); input.addEventListener('input', () => setRangeAppearance(input)); }
for (const [id, key] of [['protect-skin', 'skin'], ['protect-saturation', 'saturation'], ['protect-contrast', 'contrast']]) {
  document.querySelector(`#${id}`).addEventListener('click', (event) => { state.protections[key] = !state.protections[key]; event.currentTarget.classList.toggle('active', state.protections[key]); event.currentTarget.setAttribute('aria-pressed', String(state.protections[key])); });
}
for (const button of document.querySelectorAll('.size button')) button.addEventListener('click', () => { state.size = Number(button.dataset.size); document.querySelectorAll('.size button').forEach((candidate) => candidate.classList.toggle('active', candidate === button)); resetCachedResult(); });
document.querySelector('#rec709').addEventListener('click', () => selectWorkingSpace('rec709'));
document.querySelector('#dwg').addEventListener('click', () => selectWorkingSpace('dwg'));
document.querySelector('#slog3').addEventListener('click', () => selectWorkingSpace('slog3'));
document.querySelector('#slog3-gamut').addEventListener('change', (event) => { state.slog3.gamut = event.target.value; if (state.space === 'slog3') resetCachedResult(); });
document.querySelector('#slog3-input-range').addEventListener('change', (event) => { state.slog3.inputRange = event.target.value; if (state.space === 'slog3') resetCachedResult(); });
document.querySelector('#settings').addEventListener('click', async () => { try { await loadSettings(); cacheOutcome.hidden = true; settingsDialog.showModal(); } catch (error) { setStatus(error.message, true); } });
document.querySelector('#save-output-directory').addEventListener('click', async () => { try { await saveSettings(); } catch (error) { setStatus(error.message, true); } });
document.querySelector('#reset-output-directory').addEventListener('click', async () => { try { await saveSettings(true); } catch (error) { setStatus(error.message, true); } });
resolveOutputCompensationButton.addEventListener('click', async () => { try { const current = resolveOutputCompensationButton.getAttribute('aria-pressed') === 'true'; renderOutputSettings(await api('/api/settings', { method: 'POST', body: JSON.stringify({ resolveOutputCompensation: !current }) })); resetCachedResult(); setStatus('已更新 Resolve 709 输出补偿，请重新匹配。'); } catch (error) { setStatus(error.message, true); } });
document.querySelector('#clear-cache').addEventListener('click', async () => { if (!confirm('清理此前生成的 LUT、预览 PNG 与分析数据？')) return; try { const response = await api('/api/clear-cache', { method: 'POST', body: '{}' }); cacheOutcome.hidden = false; cacheOutcome.textContent = response.message; resetCachedResult(); setStatus('缓存已清理。'); } catch (error) { setStatus(error.message, true); } });
new ResizeObserver(drawScopes).observe(document.querySelector('.scope-side'));
new ResizeObserver(drawComparisonSource).observe(comparisonFrame);

(async () => {
  try {
    const health = await api('/api/health');
    state.runtimeReady = Boolean(health.ready);
    setRuntimeStatus(state.runtimeReady);
    setStatus(health.message);
    await loadSettings();
  } catch (error) {
    setRuntimeStatus(false);
    setStatus(error.message || '无法连接本地服务。', true);
  }
  updateMatchButton();
})();
