import {interpolate, useCurrentFrame} from 'remotion';
import {Fade, Frame, palette} from './shared';

const Tag: React.FC<{title: string; sub: string; index: number}> = ({title, sub, index}) => {
	const frame = useCurrentFrame();
	return <div style={{width: 760, height: 360, border: `3px solid ${index === 2 ? palette.gold : palette.line}`, borderRadius: 26, background: index === 2 ? '#2c2719' : palette.panel, padding: 48, opacity: interpolate(frame, [18 + index * 20, 42 + index * 20], [0, 1], {extrapolateRight: 'clamp'}), translate: `${interpolate(frame, [18 + index * 20, 42 + index * 20], [0, 0], {extrapolateRight: 'clamp'})}px ${interpolate(frame, [18 + index * 20, 42 + index * 20], [70, 0], {extrapolateRight: 'clamp'})}px`}}>
		<div style={{fontSize: 58, fontWeight: 800, color: index === 2 ? '#fff0b1' : palette.text}}>{title}</div>
		<div style={{fontSize: 30, color: palette.muted, marginTop: 22}}>{sub}</div>
	</div>;
};

export const FormatsScene: React.FC = () => {
	return <Frame eyebrow="WORKING SPACES">
		<div style={{position: 'absolute', left: 280, top: 535, fontSize: 78, fontWeight: 800}}>从不同工作空间，进入同一套流程。</div>
		<Fade from={18} duration={20} style={{position: 'absolute', left: 285, top: 645, color: palette.muted, fontSize: 36}}>输出适合你实际使用的 LUT。</Fade>
		<div style={{position: 'absolute', top: 870, left: 280, right: 280, display: 'flex', gap: 70, justifyContent: 'space-between'}}>
			<Tag title="Rec.709" sub="Gamma 2.4" index={0} />
			<Tag title="DWG" sub="DI" index={1} />
			<Tag title="S-Log3" sub="直出 LC-709" index={2} />
		</div>
		<Fade from={95} duration={20} style={{position: 'absolute', left: 280, right: 280, bottom: 285, textAlign: 'center', fontSize: 48, color: palette.text, fontWeight: 700}}>
			导出 <span style={{color: palette.gold}}>.cube</span>，导入 LUT 库，准备进入 Resolve。
		</Fade>
	</Frame>;
};
