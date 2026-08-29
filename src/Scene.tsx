import React from 'react';
import {
  AbsoluteFill,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { SceneItem } from './types';
import { Subtitles } from './Subtitles';

interface SceneProps {
  scene: SceneItem;
  durationInFrames: number;
  direction: 'zoom-in' | 'pan-right';
}

export const Scene: React.FC<SceneProps> = ({
  scene,
  durationInFrames,
  direction,
}) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(
    frame,
    [0, 15, durationInFrames - 15, durationInFrames],
   ,
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  const scale =
    direction === 'zoom-in'
      ? interpolate(frame, [0, durationInFrames], [1.0, 1.15], {
          extrapolateRight: 'clamp',
        })
      : interpolate(frame, [0, durationInFrames], [1.12, 1.05], {
          extrapolateRight: 'clamp',
        });

  const translateX =
    direction === 'pan-right'
      ? interpolate(frame, [0, durationInFrames], [-25, 25], {
          extrapolateRight: 'clamp',
        })
      : 0;

  return (
    <AbsoluteFill style={{ opacity, overflow: 'hidden' }}>
      <Img
        src={staticFile(`images/${scene.imageFileName}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale}) translateX(${translateX}px)`,
        }}
      />
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at center, transparent 45%, rgba(0, 0, 0, 0.6) 100%), linear-gradient(to top, rgba(0, 0, 0, 0.75) 0%, transparent 35%)',
        }}
      />
      <Subtitles text={scene.narration_chunk} />
    </AbsoluteFill>
  );
};
