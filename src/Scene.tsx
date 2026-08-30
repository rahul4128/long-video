import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Video,
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

  // Smooth Cross-fade transition
  let opacity = 1;
  if (frame < fadeDuration) {
    opacity = frame / fadeDuration;
  } else if (frame > safeDuration - fadeDuration) {
    opacity = (safeDuration - frame) / fadeDuration;
  }
  opacity = Math.max(0, Math.min(1, opacity));

  const isVideo = scene.imageFileName?.endsWith('.mp4');

  // Ken Burns Motion for fallback images
  const scale =
    direction === 'zoom-in'
      ? interpolate(frame, Array.of(0, safeDuration), Array.of(1.0, 1.15), {
          extrapolateRight: 'clamp',
        })
      : interpolate(frame, Array.of(0, safeDuration), Array.of(1.12, 1.05), {
          extrapolateRight: 'clamp',
        });

  return (
    <AbsoluteFill style={{ opacity, overflow: 'hidden', backgroundColor: '#000000' }}>
      {/* 1. Scene Audio Track (100% synchronized voiceover) */}
      <Audio
        src={staticFile(`audio/chunk_${scene.scene_number}.mp3`)}
        volume={1.0}
      />

      {/* 2. Visual Layer: Renders true AI Video or High-Res Visual */}
      {isVideo ? (
        <Video
          src={staticFile(`images/${scene.imageFileName}`)}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          muted
        />
      ) : (
        <Img
          src={staticFile(`images/${scene.imageFileName}`)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: `scale(${scale})`,
          }}
        />
      )}

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
