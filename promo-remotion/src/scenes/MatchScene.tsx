import {Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Fade, Frame, palette} from './shared';

const Histogram: React.FC<{color: string; offset: number}> = ({color, offset}) => {
	const frame = useCurrentFrame();
	const points = Array.from({length: 18}, (_, index) => {
		const x = index * 54;
		const y = 194 - Math.max(24, 162 * Math.exp(-((index - 5) ** 2) / 28) + Math.sin(index * 1.7 + offset) * 22);
		return `${x},${y}`;
	}).join(' ');
	return <svg width="570" height="220" viewBox="0 0 990 220" style={{overflow: 'visible'}}>
		<line x1="0" x2="990" y1="194" y2="194" stroke={palette.line} strokeWidth="2" />
		<polyline points={`0,194 ${points} 972,194`} fill={`${color}25`} stroke={color} strokeWidth="5" strokeLinejoin="round" style={{strokeDasharray: 1200, strokeDashoffset: interpolate(frame, [70, 130], [1200, 0], {extrapolateRight: 'clamp', easing: Easing.bezier(.16, 1, .3, 1)})}} />
	</svg>;
};

export const MatchScene: React.FC = () => {
	const frame = useCurrentFrame();
	const divider = interpolate(frame, [132, 205], [30, 71], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.16, 1, .3, 1)});
	return <Frame eyebrow="LOCAL ANALYSIS">
		<div style={{position: 'absolute', left: 280, top: 402, fontWeight: 800, fontSize: 78}}>提取主色，匹配色彩与光影。</div>
		<Fade from={12} duration={18} style={{position: 'absolute', left: 285, top: 510, color: palette.muted, fontSize: 36}}>主色调、亮度分布与对比关系，一起参与匹配。</Fade>
		<div style={{position: 'absolute', top: 690, left: 280, width: 1060, bottom: 215, border: `2px solid ${palette.line}`, borderRadius: 24, padding: 54, background: palette.panelDeep}}>
			<div style={{fontSize: 32, fontWeight: 700}}>主色调提取</div>
			<div style={{color: palette.muted, fontSize: 25, marginTop: 16}}>按视觉亮度从暗到亮排序</div>
			<div style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 22, marginTop: 54}}>{['#19210A','#124536','#3C4618','#165D4E','#666927','#3D7863'].map((color, index) => <div key={color} style={{aspectRatio: '1 / 1', background: color, borderRadius: 16, border: '2px solid rgba(255,255,255,.22)', opacity: interpolate(frame, [26 + index * 9, 43 + index * 9], [0, 1], {extrapolateRight: 'clamp'}), scale: interpolate(frame, [26 + index * 9, 43 + index * 9], [0.78, 1], {extrapolateRight: 'clamp'})}} />)}</div>
			<div style={{position: 'absolute', left: 54, right: 54, bottom: 54, paddingTop: 34, borderTop: `2px solid ${palette.line}`, fontSize: 28, color: palette.muted, lineHeight: 1.75}}>主色倾向 <span style={{color: palette.text, fontWeight: 700}}>自然绿 · 130°</span><br />中位明度 <span style={{color: palette.text, fontWeight: 700}}>0.381</span><br />饱和度 <span style={{color: palette.text, fontWeight: 700}}>0.516</span></div>
		</div>
		<div style={{position: 'absolute', top: 690, left: 1400, right: 280, height: 490, border: `2px solid ${palette.line}`, borderRadius: 24, padding: 46, background: palette.panelDeep}}>
			<div style={{fontSize: 32, fontWeight: 700}}>图像示波器</div>
			<div style={{display: 'flex', gap: 26, marginTop: 40}}>
				{[{color: palette.red, offset: 0, label: '红'}, {color: palette.green, offset: 1, label: '绿'}, {color: palette.blue, offset: 2, label: '蓝'}].map(({color, offset, label}) => <div key={color}><div style={{fontSize: 28, color, marginBottom: 18, fontWeight: 700}}>{label}</div><div style={{border: `2px solid ${palette.line}`, borderRadius: 14, padding: '10px 8px'}}><Histogram color={color} offset={offset} /></div></div>)}
			</div>
			<div style={{position: 'absolute', left: 46, right: 46, bottom: 34, color: palette.muted, fontSize: 24}}>分区直方图匹配 · 色彩、亮度与对比关系共同参与</div>
		</div>
		<div style={{position: 'absolute', left: 1400, right: 280, top: 1230, bottom: 215, border: `2px solid ${palette.gold}`, borderRadius: 24, overflow: 'hidden', background: '#101318', boxShadow: '0 18px 55px rgba(0,0,0,.3)'}}>
			<Img src={staticFile('demo-match-preview.png')} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', filter: 'brightness(.74) contrast(.95) saturate(.90)'}} />
			<div style={{position: 'absolute', inset: 0, width: `${divider}%`, overflow: 'hidden'}}><Img src={staticFile('demo-source-preview.png')} style={{width: `${100 / (divider / 100)}%`, height: '100%', maxWidth: 'none', objectFit: 'cover', filter: 'brightness(.68) contrast(1.04) saturate(.88)'}} /></div>
			<div style={{position: 'absolute', left: `${divider}%`, top: 0, bottom: 0, width: 6, background: palette.gold, boxShadow: `0 0 22px ${palette.gold}`}} />
			<div style={{position: 'absolute', left: 28, top: 26, padding: '8px 12px', background: 'rgba(11,13,17,.74)', borderRadius: 8, color: palette.text, fontSize: 25, fontWeight: 700}}>原图</div>
			<div style={{position: 'absolute', right: 28, top: 26, padding: '8px 12px', background: 'rgba(11,13,17,.74)', borderRadius: 8, color: palette.text, fontSize: 25, fontWeight: 700}}>匹配预览</div>
		</div>
	</Frame>;
};
