import {Easing, interpolate, useCurrentFrame} from 'remotion';
import {Frame, palette} from './shared';

const easeOut = Easing.bezier(.16, 1, .3, 1);

export const IntroScene: React.FC = () => {
	const frame = useCurrentFrame();
	const firstIn = interpolate(frame, [3, 20], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const firstOut = interpolate(frame, [36, 47], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const secondIn = interpolate(frame, [39, 57], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const secondOut = interpolate(frame, [76, 89], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});

	return <Frame>
		<div style={{position: 'absolute', inset: 0, opacity: .82, background: 'radial-gradient(circle at 50% 50%, rgba(237,197,87,.12), transparent 36%)'}} />
		<div style={{position: 'absolute', left: 300, right: 300, top: 1050, borderTop: `2px solid ${palette.line}`, opacity: firstIn * firstOut}} />
		<div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', opacity: firstIn * firstOut, translate: `${-100 * (1 - firstIn)}px 0`}}>
			<div>
				<div style={{color: palette.gold, fontSize: 27, letterSpacing: 7, fontWeight: 800, marginBottom: 44}}>REFERENCE LUT</div>
				<div style={{fontSize: 160, lineHeight: 1, fontWeight: 850, letterSpacing: -8}}>把你看见的风格</div>
			</div>
		</div>
		<div style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', opacity: secondIn * secondOut, translate: `${110 * (1 - secondIn)}px 0`}}>
			<div>
				<div style={{fontSize: 160, lineHeight: 1, fontWeight: 850, letterSpacing: -9}}>带进你的<span style={{color: palette.gold}}>镜头</span></div>
				<div style={{margin: '52px auto 0', height: 5, width: `${interpolate(frame, [50, 70], [0, 640], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut})}px`, background: palette.gold, boxShadow: `0 0 34px ${palette.gold}`}} />
			</div>
		</div>
	</Frame>;
};
