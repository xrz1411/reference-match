import {Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {Frame, palette} from './shared';

const easeOut = Easing.bezier(.16, 1, .3, 1);

const TypeLine: React.FC<{children: string; from: number; color?: string; size: number}> = ({children, from, color = palette.text, size}) => {
	const frame = useCurrentFrame();
	return <div style={{fontSize: size, fontWeight: 850, letterSpacing: -3, whiteSpace: 'pre'}}>{Array.from(children).map((char, index) => {
		const reveal = interpolate(frame, [from + index * 2.4, from + index * 2.4 + 9], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
		return <span key={`${char}-${index}`} style={{display: 'inline-block', color, opacity: reveal, translate: `0 ${16 * (1 - reveal)}px`}}>{char === ' ' ? '\u00a0' : char}</span>;
	})}</div>;
};

export const ProductScene: React.FC = () => {
	const frame = useCurrentFrame();
	const enter = interpolate(frame, [0, 28], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const title = interpolate(frame, [20, 48], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
	const scanX = interpolate(frame, [35, 130], [-200, 3900], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	return <Frame eyebrow="LOCAL REFERENCE MATCH">
		<div style={{position: 'absolute', left: 250, top: 370, opacity: title}}>
			<TypeLine from={18} size={72}>真实插件界面。</TypeLine>
			<div style={{fontSize: 30, marginTop: 16, color: palette.muted, whiteSpace: 'pre'}}>{Array.from('参考图、视频静帧与匹配预览，在同一处完成。').map((char, index) => {
				const reveal = interpolate(frame, [48 + index * 1.35, 55 + index * 1.35], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: easeOut});
				return <span key={`${char}-${index}`} style={{display: 'inline-block', opacity: reveal}}>{char}</span>;
			})}</div>
		</div>
		<div style={{position: 'absolute', left: 245, right: 245, top: 600, bottom: 185, opacity: enter, scale: .94 + enter * .06, translate: `0 ${80 * (1 - enter)}px`, background: '#05070a', padding: 18, border: `2px solid ${palette.line}`, borderRadius: 29, boxShadow: '0 36px 110px rgba(0,0,0,.52)'}}>
			<Img src={staticFile('demo-plugin-ui.png')} style={{width: '100%', height: '100%', objectFit: 'contain', display: 'block'}} />
			<div style={{position: 'absolute', top: 0, bottom: 0, left: scanX, width: 4, opacity: .66, background: palette.gold, boxShadow: `0 0 28px ${palette.gold}`}} />
		</div>
	</Frame>;
};
