import {Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Fade, Frame, palette} from './shared';

const Still: React.FC<{kind: 'reference' | 'source'}> = ({kind}) => {
	const frame = useCurrentFrame();
	const source = kind === 'reference' ? staticFile('demo-reference.jpg') : staticFile('demo-source-preview.png');
	const progress = interpolate(frame, [0, 150], [0, 1], {extrapolateRight: 'clamp'});
	return <div style={{height: 570, borderRadius: 18, overflow: 'hidden', position: 'relative', background: '#080a0d', border: `2px solid ${palette.line}`}}>
		<Img
			src={source}
			style={{width: '100%', height: '100%', objectFit: 'cover', scale: 1.03 + progress * .035, filter: kind === 'source' ? 'brightness(.72) saturate(.62)' : 'saturate(.94) contrast(1.04)'}}
		/>
		<div style={{position: 'absolute', inset: 0, background: kind === 'reference' ? 'linear-gradient(110deg, rgba(7,15,18,.26), transparent 55%)' : 'linear-gradient(110deg, rgba(6,11,15,.48), transparent 60%)'}} />
		<div style={{position: 'absolute', top: 0, bottom: 0, left: `${interpolate(frame, [22, 108], [-5, 105], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.16, 1, .3, 1)})}%`, width: 4, background: palette.gold, boxShadow: `0 0 26px ${palette.gold}`, opacity: interpolate(frame, [22, 30, 103, 113], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}} />
		<div style={{position: 'absolute', left: 28, bottom: 26, padding: '10px 15px', background: 'rgba(10,13,17,.78)', border: `1px solid ${palette.line}`, borderRadius: 9, fontSize: 20, letterSpacing: 1.3, color: kind === 'reference' ? '#e9d58b' : palette.muted}}>{kind === 'reference' ? 'REFERENCE / sRGB' : 'SOURCE / DWG + DI'}</div>
	</div>;
};

export const ReferenceScene: React.FC = () => {
	const frame = useCurrentFrame();
	return <Frame eyebrow="STYLE INPUT">
		<div style={{position: 'absolute', left: 280, top: 425, fontWeight: 800, fontSize: 80, letterSpacing: -2}}>不需要描述风格。</div>
		<Fade from={16} duration={20} style={{position: 'absolute', left: 285, top: 535, color: palette.muted, fontSize: 38}}>给出参考图与视频静帧，开始分析。</Fade>
		<div style={{position: 'absolute', top: 720, left: 280, right: 280, display: 'flex', gap: 56, alignItems: 'center'}}>
			<div style={{width: 1375, opacity: interpolate(frame, [12, 32], [0, 1], {extrapolateRight: 'clamp', easing: Easing.bezier(.16, 1, .3, 1)}), translate: `${interpolate(frame, [12, 40], [-90, 0], {extrapolateRight: 'clamp'})}px 0`}}>
				<div style={{fontSize: 30, color: palette.gold, marginBottom: 24, fontWeight: 700, letterSpacing: 2}}>参考图</div>
				<Still kind="reference" />
			</div>
			<div style={{width: 150, color: palette.gold, fontSize: 70, textAlign: 'center', opacity: interpolate(frame, [42, 57], [0, 1], {extrapolateRight: 'clamp'})}}>＋</div>
			<div style={{width: 1375, opacity: interpolate(frame, [48, 68], [0, 1], {extrapolateRight: 'clamp', easing: Easing.bezier(.16, 1, .3, 1)}), translate: `${interpolate(frame, [48, 75], [90, 0], {extrapolateRight: 'clamp'})}px 0`}}>
				<div style={{fontSize: 30, color: palette.gold, marginBottom: 24, fontWeight: 700, letterSpacing: 2}}>视频静帧</div>
				<Still kind="source" />
			</div>
		</div>
		<Fade from={115} duration={18} style={{position: 'absolute', right: 280, bottom: 205, fontSize: 42, fontWeight: 700}}>一个镜头，<span style={{color: palette.gold}}>一个方向。</span></Fade>
	</Frame>;
};
