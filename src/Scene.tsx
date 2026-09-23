import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  Video,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { Shot, SceneItem } from './types';

interface SceneProps {
  scene: SceneItem;
  durationInFrames: number;
  direction: 'zoom-in' | 'pan-right';
  format?: 'long' | 'shorts';
}

function resolveShots(scene: SceneItem): Shot[] {
  if (scene.shots && scene.shots.length > 0) return scene.shots;
  const legacy = scene.imageFileName;
  if (Array.isArray(legacy)) return legacy.map((file) => ({ type: 'image', file }));
  if (legacy) return [{ type: legacy.endsWith('.mp4') ? 'video' : 'image', file: legacy }];
  return [];
}

const PARTICLES = Array.from({ length: 22 }, (_, i) => ({
  left: ((i * 47) % 97) + 1,
  top: ((i * 71) % 91) + 4,
  size: 2 + ((i * 13) % 5),
  drift: ((i % 5) - 2) * 18,
  speed: 0.45 + (i % 4) * 0.08,
}));

export const Scene: React.FC<SceneProps> = ({
  scene,
  durationInFrames,
  direction,
  format = 'long',
}) => {
  const frame = useCurrentFrame();
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = 12;
  const animation = scene.director?.animation;
  const intensity = Math.max(0, Math.min(1, animation?.intensity ?? 0.22));
  const type = animation?.type ?? (scene.director?.camera === 'slow_push' ? 'slow_push' : direction);
  const vignette = animation?.vignette ?? 0.38;

  let opacity = 1;
  if (frame < fadeDuration) opacity = frame / fadeDuration;
  else if (frame > safeDuration - fadeDuration) opacity = (safeDuration - frame) / fadeDuration;
  opacity = Math.max(0, Math.min(1, opacity));

  const narrationFile =
    format === 'shorts'
      ? `audio/shorts_chunk_${scene.scene_number}.mp3`
      : `audio/chunk_${scene.scene_number}.mp3`;
  const effectFile = `audio/effects/${format}_effect_${scene.scene_number}.mp3`;

  const shots = resolveShots(scene);
  const shotCount = Math.max(1, shots.length);
  const shotDurationFrames = safeDuration / shotCount;
  const transitionFrames = Math.max(4, Math.min(15, shotDurationFrames / 3));
  const currentShot = Math.min(shotCount - 1, Math.floor(frame / shotDurationFrames));
  const nextShot = Math.min(shotCount - 1, currentShot + 1);
  const intoCurrentShot = frame - currentShot * shotDurationFrames;
  const framesToNextShotBoundary = (currentShot + 1) * shotDurationFrames - frame;
  const crossFade =
    nextShot !== currentShot && framesToNextShotBoundary < transitionFrames
      ? 1 - Math.max(0, framesToNextShotBoundary) / transitionFrames
      : 0;

  const outgoingTransition = shots[currentShot]?.transition;
  const useBlurCut =
    outgoingTransition === 'blur_cut' ||
    (!outgoingTransition && (animation?.transition === 'blur_cut' || currentShot % 3 === 1));
  const blurPx = useBlurCut
    ? interpolate(crossFade, [0, 0.5, 1], [0, 4 + intensity * 4, 0], {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 0;

  const localProgress = Math.max(0, Math.min(1, intoCurrentShot / Math.max(1, shotDurationFrames)));
  const baseScale =
    type === 'climax_push'
      ? 1.0 + intensity * 0.14 * localProgress
      : type === 'slow_pull'
        ? 1.10 - intensity * 0.08 * localProgress
        : type === 'parallax'
          ? 1.06 + intensity * 0.06 * localProgress
          : 1.02 + intensity * 0.08 * localProgress;

  const motion = type === 'pan_left' ? -1 : type === 'pan_right' ? 1 : 0;
  const pan = motion * interpolate(localProgress, [0, 1], [-34, 34], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  }) * intensity / 0.34;
  const parallaxX = type === 'parallax'
    ? Math.sin(localProgress * Math.PI) * 22 * intensity
    : 0;
  const parallaxY = type === 'parallax'
    ? Math.cos(localProgress * Math.PI) * -10 * intensity
    : 0;
  const shakeAmount = (animation?.cameraShake ?? 0) * 100;
  const shakeX = shakeAmount ? Math.sin(frame * 1.7) * shakeAmount : 0;
  const shakeY = shakeAmount ? Math.cos(frame * 1.45) * shakeAmount * 0.65 : 0;

  const transform = (layer: number) => {
    const layerDepth = layer === 0 ? 1 : 1 + layer * 0.012;
    return `translate3d(${pan + parallaxX + shakeX}px,${parallaxY + shakeY}px,0) scale(${baseScale * layerDepth})`;
  };

  const shotBoundaryFrames: number[] = [];
  for (let i = 1; i < shotCount; i++) shotBoundaryFrames.push(Math.round(i * shotDurationFrames));

  const renderShot = (
    shot: Shot,
    shotIndex: number,
    shotLocalFrame: number,
    shotOpacity: number,
    layer = 0,
  ) => {
    const layerProgress = Math.max(0, Math.min(1, shotLocalFrame / Math.max(1, shotDurationFrames)));
    const layerTransform =
      layer === 0
        ? transform(0)
        : `translate3d(${(layerProgress * 26 - 13) * intensity * (layer % 2 ? 1 : -1)}px,0,0) scale(${baseScale * (1 + layer * 0.015)})`;

    if (shot.type === 'video') {
      return (
        <Video
          src={staticFile(`images/${shot.file}`)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: layerTransform,
            opacity: shotOpacity,
          }}
          muted
          loop
        />
      );
    }
    return (
      <Img
        src={staticFile(`images/${shot.file}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: layerTransform,
          opacity: shotOpacity,
        }}
      />
    );
  };

  const activeShot = shots[currentShot];
  const shouldParallax = type === 'parallax' && activeShot?.type === 'image';
  const particlesOn = Boolean(animation?.particles);
  const lightRaysOn = Boolean(animation?.lightRays);

  return (
    <AbsoluteFill style={{ opacity, overflow: 'hidden', backgroundColor: '#000' }}>
      <Audio src={staticFile(narrationFile)} volume={1.0} />

      {scene.soundEffect && scene.soundEffect !== 'none' && (
        <Audio src={staticFile(effectFile)} volume={0.30} />
      )}

      {shotBoundaryFrames.map((boundaryFrame) => (
        <Sequence
          key={boundaryFrame}
          from={Math.max(0, boundaryFrame - Math.round(transitionFrames / 2))}
          durationInFrames={Math.round(transitionFrames * 1.5)}
          layout="none"
        >
          <Audio src={staticFile('audio/sfx/whoosh.mp3')} volume={0.20} />
        </Sequence>
      ))}

      <AbsoluteFill style={{ filter: blurPx > 0 ? `blur(${blurPx}px)` : undefined }}>
        {shouldParallax && (
          <AbsoluteFill style={{ transform: 'scale(1.10)', opacity: 0.32 }}>
            {renderShot(activeShot, currentShot, intoCurrentShot, 1, 1)}
          </AbsoluteFill>
        )}
        <AbsoluteFill>
          {activeShot
            ? renderShot(activeShot, currentShot, intoCurrentShot, 1 - crossFade)
            : null}
        </AbsoluteFill>
        {crossFade > 0 && nextShot !== currentShot && shots[nextShot] && (
          <AbsoluteFill>
            {renderShot(shots[nextShot], nextShot, 0, crossFade)}
          </AbsoluteFill>
        )}
      </AbsoluteFill>

      {lightRaysOn && (
        <AbsoluteFill
          style={{
            opacity: 0.08 + intensity * 0.10,
            background:
              'conic-gradient(from 210deg at 50% 0%, transparent 0deg, rgba(255,220,140,0.28) 22deg, transparent 48deg, rgba(255,220,140,0.18) 72deg, transparent 105deg)',
            mixBlendMode: 'screen',
          }}
        />
      )}

      {particlesOn && (
        <AbsoluteFill>
          {PARTICLES.map((particle, i) => {
            const y = (particle.top + ((frame * particle.speed) / 18)) % 104 - 2;
            const x = particle.left + Math.sin(frame / 28 + i) * particle.drift / 10;
            const pulse = 0.35 + 0.30 * Math.sin(frame / 12 + i);
            return (
              <div
                key={i}
                style={{
                  position: 'absolute',
                  left: `${x}%`,
                  top: `${y}%`,
                  width: particle.size,
                  height: particle.size,
                  borderRadius: '50%',
                  background: 'rgba(255,224,160,0.75)',
                  opacity: pulse,
                  boxShadow: '0 0 8px rgba(255,210,120,0.55)',
                }}
              />
            );
          })}
        </AbsoluteFill>
      )}

      {animation?.overlay === 'fact' && scene.narration_chunk && (
        <AbsoluteFill style={{ justifyContent: 'flex-start', alignItems: 'flex-start', padding: format === 'shorts' ? 36 : 64 }}>
          <div
            style={{
              maxWidth: format === 'shorts' ? '82%' : '58%',
              padding: '10px 16px',
              borderRadius: 14,
              background: 'rgba(8,8,12,0.55)',
              border: '1px solid rgba(255,215,120,0.35)',
              color: '#FFEAA7',
              fontSize: format === 'shorts' ? 22 : 25,
              fontWeight: 700,
              opacity: interpolate(localProgress, [0, 0.12, 0.82, 1], [0, 1, 1, 0], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
              }),
            }}
          >
            {scene.entertainmentBeat === 'reveal' || scene.director?.animation?.overlay === 'fact'
              ? 'रहस्य का संकेत'
              : 'महत्वपूर्ण तथ्य'}
          </div>
        </AbsoluteFill>
      )}

      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at center, transparent 54%, rgba(0,0,0,${Math.max(0.18, Math.min(0.65, vignette))}) 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};
