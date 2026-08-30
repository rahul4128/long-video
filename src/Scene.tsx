import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { SceneItem } from './types';

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
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = 12;

  // Smooth Cross-fade between scenes
  let opacity = 1;
  if (frame < fadeDuration) {
    opacity = frame / fadeDuration;
  } else if (frame > safeDuration - fadeDuration) {
    opacity = (safeDuration - frame) / fadeDuration;
  }
  opacity = Math.max(0, Math.min(1, opacity));

  // Ken Burns Motion
  const scale =
    direction === 'zoom-in'
      ? interpolate(frame, Array.of(0, safeDuration), Array.of(1.0, 1.15), {
          extrapolateRight: 'clamp',
        })
      : interpolate(frame, Array.of(0, safeDuration), Array.of(1.12, 1.05), {
          extrapolateRight: 'clamp',
        });

  const translateX =
    direction === 'pan-right'
      ? interpolate(frame, Array.of(0, safeDuration), Array.of(-25, 25), {
          extrapolateRight: 'clamp',
        })
      : 0;

  return (
    <AbsoluteFill style={{ opacity, overflow: 'hidden' }}>
      {/* 1. Scene Audio Track (Guarantees exact voice sync for every scene) */}
      <Audio
        src={staticFile(`audio/chunk_${scene.scene_number}.mp3`)}
        volume={1.0}
      />

      {/* 2. Fullscreen Character Visual with Ken Burns Motion */}
      <Img
        src={staticFile(`images/${scene.imageFileName}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `scale(${scale}) translateX(${translateX}px)`,
        }}
      />

      {/* 3. Subtle Cinematic Vignette */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at center, transparent 60%, rgba(0, 0, 0, 0.45) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};
