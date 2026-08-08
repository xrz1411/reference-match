import {interpolate, useCurrentFrame} from 'remotion';
import {Fade, Frame, palette} from './shared';

export const OutroScene: React.FC = () => {
	const frame = useCurrentFrame();
	return <Frame eyebrow="REFERENCE LUT">
		<div style={{position: 'absolute', left: 0, right: 0, top: 690, textAlign: 'center'}}>
			<Fade from={8} duration={20} style={{fontSize: 210, fontWeight: 850, letterSpacing: -12}}>即将<span style={{color: palette.gold}}>开源</span></Fade>
			<Fade from={30} duration={20} style={{fontSize: 42, color: palette.muted, marginTop: 35}}>Reference LUT for DaVinci Resolve</Fade>
		</div>
		<div style={{position: 'absolute', left: 1320, right: 1320, bottom: 440, height: 6, background: palette.line}}>
			<div style={{height: '100%', background: palette.gold, width: `${interpolate(frame, [52, 105], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}%`}} />
		</div>
		<div style={{position: 'absolute', left: 0, right: 0, bottom: 245, textAlign: 'center', color: palette.gold, fontSize: 25, letterSpacing: 5, fontWeight: 700}}>COMING SOON</div>
	</Frame>;
};
