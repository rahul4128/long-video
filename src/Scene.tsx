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
  format?: 'long' | 'shorts';
}

export const Scene: React.FC<SceneProps> = ({
  scene,
  durationInFrames,
  direction,
  format = 'long',
}) => {
  const frame = useCurrentFrame();
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = 12;

  // Smooth Cross-fade
  let opacity = 1;
  if (frame < fadeDuration) {
    opacity = frame / fadeDuration;
  } else if (frame > safeDuration - fadeDuration) {
    opacity = (safeDuration - frame) / fadeDuration;
  }
  opacity = Math.max(0, Math.min(1, opacity));

  const isVideo = scene.imageFileName?.endsWith('.mp4');

  // Long and Shorts renders write narration audio under different filename prefixes
  // (see generate_assets.py: chunk_N.mp3 vs shorts_chunk_N.mp3) - pick the right one.
  const narrationFile =
    format === 'shorts'
      ? `audio/shorts_chunk_${scene.scene_number}.mp3`
      : `audio/chunk_${scene.scene_number}.mp3`;

  // Ken Burns Motion for images
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
    <AbsoluteFill style={{ opacity, overflow: 'hidden', backgroundColor: '#000000' }}>
      {/* 1. Scene Audio Track (100% synchronized voiceover per scene) */}
      <Audio
        src={staticFile(narrationFile)}
        volume={1.0}
      />

      {/* 1b. Optional Sound-Effect Layer (temple bell / shankh / om drone / flute swell) */}
      {scene.soundEffect && scene.soundEffect !== 'none' && (
        <Audio
          src={staticFile(`audio/effects/${scene.soundEffect}.mp3`)}
          volume={0.35}
        />
      )}

      {/* 2. Visual Layer: Renders Real 4K Video or High-Res Deity Art */}
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
            transform: `scale(${scale}) translateX(${translateX}px)`,
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
