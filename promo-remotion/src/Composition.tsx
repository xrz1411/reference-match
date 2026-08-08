import {Composition, interpolate, Sequence, staticFile} from 'remotion';
import {Audio} from '@remotion/media';
import {IntroScene} from './scenes/IntroScene';
import {IntroducingScene} from './scenes/IntroducingScene';
import {ProductScene} from './scenes/ProductScene';
import {ReferenceScene} from './scenes/ReferenceScene';
import {MatchScene} from './scenes/MatchScene';
import {FormatsScene} from './scenes/FormatsScene';
import {OutroScene} from './scenes/OutroScene';
import {PageFade} from './scenes/PageFade';

export const FPS = 30;
export const WIDTH = 3840;
export const HEIGHT = 2160;

export const PromoAssembly: React.FC = () => {
	return (
		<>
			<Audio
				src={staticFile('reference-lut-release-bed.mp3')}
				volume={(frame) => interpolate(frame, [0, 14, 880, 899], [0, 0.22, 0.22, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}
			/>
			<Sequence durationInFrames={102} name="01 文字开场">
				<PageFade duration={102}><IntroScene /></PageFade>
			</Sequence>
			<Sequence from={90} durationInFrames={72} name="02 Introducing">
				<PageFade duration={72}><IntroducingScene /></PageFade>
			</Sequence>
			<Sequence from={150} durationInFrames={162} name="03 真实插件界面">
				<PageFade duration={162}><ProductScene /></PageFade>
			</Sequence>
			<Sequence from={300} durationInFrames={192} name="04 参考图与静帧">
				<PageFade duration={192}><ReferenceScene /></PageFade>
			</Sequence>
			<Sequence from={480} durationInFrames={222} name="05 匹配与分析">
				<PageFade duration={222}><MatchScene /></PageFade>
			</Sequence>
			<Sequence from={690} durationInFrames={132} name="06 工作色彩空间">
				<PageFade duration={132}><FormatsScene /></PageFade>
			</Sequence>
			<Sequence from={810} durationInFrames={90} name="07 即将开源">
				<PageFade duration={90}><OutroScene /></PageFade>
			</Sequence>
		</>
	);
};

export const MyComposition = () => {
	return (
		<>
			<Composition id="ReferenceLUT-Promo" component={PromoAssembly} durationInFrames={900} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="01-Hook" component={IntroScene} durationInFrames={90} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="02-Introducing" component={IntroducingScene} durationInFrames={60} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="03-Product" component={ProductScene} durationInFrames={150} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="04-Reference" component={ReferenceScene} durationInFrames={180} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="05-Match" component={MatchScene} durationInFrames={210} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="06-Formats" component={FormatsScene} durationInFrames={120} fps={FPS} width={WIDTH} height={HEIGHT} />
			<Composition id="07-ComingSoon" component={OutroScene} durationInFrames={90} fps={FPS} width={WIDTH} height={HEIGHT} />
		</>
	);
};
