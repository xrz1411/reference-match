import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from 'remotion';

const easeOut = Easing.bezier(.16, 1, .3, 1);

export const PageFade: React.FC<{children: React.ReactNode; duration: number}> = ({children, duration}) => {
	const frame = useCurrentFrame();
	const opacity = interpolate(frame, [0, 12, duration - 12, duration], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};
