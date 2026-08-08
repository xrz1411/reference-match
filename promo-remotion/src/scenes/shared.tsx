import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';

export const palette = {
	ink: '#0b0d11',
	panel: '#151923',
	panelDeep: '#10131a',
	line: '#394152',
	text: '#f1f3f5',
	muted: '#a7afbe',
	gold: '#edc557',
	green: '#69c99a',
	red: '#e77476',
	blue: '#719bea',
};

export const Frame: React.FC<{children: React.ReactNode; eyebrow?: string}> = ({children, eyebrow}) => {
	return <AbsoluteFill style={{backgroundColor: palette.ink, color: palette.text, overflow: 'hidden'}}>
		<div style={{position: 'absolute', inset: 0, opacity: 0.42, backgroundImage: 'linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)', backgroundSize: '96px 96px'}} />
		<div style={{position: 'absolute', top: 112, left: 148, right: 148, display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 2}}>
			<div style={{display: 'flex', gap: 26, alignItems: 'center'}}>
				<div style={{width: 50, height: 50, border: `2px solid ${palette.gold}`, color: palette.gold, display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 30}}>L</div>
				<div style={{fontSize: 32, letterSpacing: 2, fontWeight: 700}}>仿色 LUT 生成器</div>
			</div>
			{eyebrow ? <div style={{color: palette.gold, fontSize: 24, letterSpacing: 4, fontWeight: 700}}>{eyebrow}</div> : null}
		</div>
		{children}
	</AbsoluteFill>;
};

export const Fade: React.FC<{children: React.ReactNode; from?: number; duration?: number; style?: React.CSSProperties}> = ({children, from = 0, duration = 20, style}) => {
	const frame = useCurrentFrame();
	return <div style={{
		opacity: interpolate(frame, [from, from + duration], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.16, 1, 0.3, 1)}),
		...style,
	}}>{children}</div>;
};

export const GridMark: React.FC<{x: number; y: number}> = ({x, y}) => <div style={{position: 'absolute', left: x, top: y, width: 32, height: 32, borderLeft: `2px solid ${palette.gold}`, borderTop: `2px solid ${palette.gold}`, opacity: .85}} />;
