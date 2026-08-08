import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {Frame, palette} from './shared';

const easeOut = Easing.bezier(.16, 1, .3, 1);

export const IntroducingScene: React.FC = () => {
	const frame = useCurrentFrame();
	const titleIn = interpolate(frame, [6, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const productIn = interpolate(frame, [22, 47], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	return <Frame>
		<div style={{position: 'absolute', inset: 0, background: 'radial-gradient(circle at 50% 49%, rgba(237,197,87,.18), transparent 31%)'}} />
		<div style={{position: 'absolute', left: 0, right: 0, top: 700, textAlign: 'center', opacity: titleIn, translate: `${-95 * (1 - titleIn)}px 0`}}>
			<div style={{fontSize: 45, fontWeight: 700, letterSpacing: 11, color: palette.gold}}>INTRODUCING</div>
			<div style={{fontSize: 160, fontWeight: 850, letterSpacing: -8, marginTop: 35, opacity: productIn, translate: `${105 * (1 - productIn)}px 0`}}>仿色 <span style={{color: palette.gold}}>LUT</span> 生成器</div>
			<div style={{fontSize: 30, fontWeight: 700, letterSpacing: 7, color: palette.muted, marginTop: 42, opacity: productIn}}>REFERENCE LUT FOR DAVINCI RESOLVE</div>
		</div>
		<div style={{position: 'absolute', left: 1390, right: 1390, bottom: 520, height: 4, background: palette.line}}><div style={{height: '100%', width: `${interpolate(frame, [31, 55], [0, 100], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut})}%`, background: palette.gold}} /></div>
	</Frame>;
};
