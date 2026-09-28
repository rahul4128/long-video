import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
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
  fadeIn?: boolean;
  fadeOut?: boolean;
  smoothEntry?: boolean;
}

function resolveShots(scene: SceneItem): Shot[] {
  if (scene.shots && scene.shots.length > 0) {
    return scene.shots;
  }
  const legacy = scene.imageFileName;
  if (Array.isArray(legacy)) {
    return legacy.map((file) => ({ type: 'image', file }));
  }
  if (legacy) {
    return [{ type: legacy.endsWith('.mp4') ? 'video' : 'image', file: legacy }];
  }
  return [];
}

interface ShotLayerProps {
  shot: Shot;
  shotIndex: number;
  shotDurationInFrames: number;
  transitionFrames: number;
  direction: 'zoom-in' | 'pan-right';
  format: 'long' | 'shorts';
  scene: SceneItem;
  isFirst: boolean;
  isLast: boolean;
  incomingTransition: 'crossfade' | 'blur_cut';
  outgoingTransition: 'crossfade' | 'blur_cut';
}

const ShotLayer: React.FC<ShotLayerProps> = ({
  shot,
  shotIndex,
  shotDurationInFrames,
  transitionFrames,
  direction,
  format,
  scene,
  isFirst,
  isLast,
  incomingTransition,
  outgoingTransition,
}) => {
  const frame = useCurrentFrame();
  const safeShotDuration = Math.max(1, shotDurationInFrames);
  const smooth = Easing.inOut(Easing.cubic);

  const entry = isFirst
    ? 1
    : interpolate(frame, [0, transitionFrames], [0, 1], {
        easing: smooth,
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      });
  const exit = isLast
    ? 1
    : interpolate(
        frame,
        [Math.max(0, safeShotDuration - transitionFrames), safeShotDuration],
        [1, 0],
        {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        },
      );
  const opacity = Math.min(entry, exit);

  const entryBlur =
    !isFirst && incomingTransition === 'blur_cut'
      ? interpolate(frame, [0, transitionFrames], [3.5, 0], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 0;
  const exitBlur =
    !isLast && outgoingTransition === 'blur_cut'
      ? interpolate(
          frame,
          [Math.max(0, safeShotDuration - transitionFrames), safeShotDuration],
          [0, 3.5],
          {
            easing: smooth,
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          },
        )
      : 0;
  const blurPx = Math.max(entryBlur, exitBlur);

  const planned = scene.director?.camera;
  const shotDirection: 'zoom-in' | 'pan-right' =
    planned === 'pan_left'
      ? 'pan-right'
      : planned === 'pan_right'
        ? 'pan-right'
        : planned === 'slow_push'
          ? 'zoom-in'
          : shotIndex % 2 === 0
            ? direction
            : direction === 'zoom-in'
              ? 'pan-right'
              : 'zoom-in';

  // Shorts use deliberately gentler travel than long-form. Large 18% zooms
  // on a 9:16 crop read as jerky; an eased 7-9% push feels much more like a
  // controlled camera move while still keeping static AI images alive.
  const isShorts = format === 'shorts';
  const zoomEnd = scene.director?.camera === 'slow_push'
    ? (isShorts ? 1.07 : 1.10)
    : (isShorts ? 1.09 : 1.16);
  const panStartScale = isShorts ? 1.10 : 1.15;
  const panEndScale = isShorts ? 1.04 : 1.05;
  const panDistance = isShorts ? 18 : 30;

  const scale =
    shotDirection === 'zoom-in'
      ? interpolate(frame, [0, safeShotDuration], [1.0, zoomEnd], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : interpolate(frame, [0, safeShotDuration], [panStartScale, panEndScale], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

  const translateX =
    shotDirection === 'pan-right'
      ? interpolate(
          frame,
          [0, safeShotDuration],
          [scene.director?.camera === 'pan_left' ? panDistance : -panDistance,
           scene.director?.camera === 'pan_left' ? -panDistance : panDistance],
          {
            easing: smooth,
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          },
        )
      : 0;

  const transform = `scale(${scale}) translateX(${translateX}px)`;
  const commonStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    transform,
    opacity,
    filter: blurPx > 0 ? `blur(${blurPx}px)` : undefined,
  };

  if (shot.type === 'video') {
    return (
      <Video
        key={`video-${shotIndex}-${shot.file}`}
        src={staticFile(`images/${shot.file}`)}
        style={commonStyle}
        muted
        loop
      />
    );
  }

  return (
    <Img
      key={`image-${shotIndex}-${shot.file}`}
      src={staticFile(`images/${shot.file}`)}
      style={commonStyle}
    />
  );
};

export const Scene: React.FC<SceneProps> = ({
  scene,
  durationInFrames,
  direction,
  format = 'long',
  fadeIn = true,
  fadeOut = true,
  smoothEntry = false,
}) => {
  const frame = useCurrentFrame();
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = format === 'shorts' ? 7 : 12;
  const smooth = Easing.inOut(Easing.cubic);

  // Only fade the edges explicitly requested by the parent. Shorts now fade
  // only at the beginning/end of the whole video, not at every scene boundary.
  // This removes the repeated black dip that made the Short feel stitched.
  let opacity = 1;
  if (fadeIn && frame < fadeDuration) {
    opacity = interpolate(frame, [0, fadeDuration], [0, 1], {
      easing: smooth,
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
  }
  if (fadeOut && frame > safeDuration - fadeDuration) {
    const out = interpolate(
      frame,
      [safeDuration - fadeDuration, safeDuration],
      [1, 0],
      {
        easing: smooth,
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      },
    );
    opacity = Math.min(opacity, out);
  }

  const narrationFile =
    format === 'shorts'
      ? `audio/shorts_chunk_${scene.scene_number}.mp3`
      : `audio/chunk_${scene.scene_number}.mp3`;
  const effectFile = `audio/effects/${format}_effect_${scene.scene_number}.mp3`;

  const shots = resolveShots(scene);
  const shotCount = Math.max(1, shots.length);
  const nominalFrames = safeDuration / shotCount;
  const transitionFrames =
    shotCount <= 1
      ? 0
      : format === 'shorts'
        ? Math.max(5, Math.min(9, Math.round(nominalFrames / 6)))
        : Math.max(6, Math.min(12, Math.round(nominalFrames / 5)));

  // Give each visual its own Remotion Sequence. Adjacent sequences overlap by
  // transitionFrames, so videos have a real local timeline and do not restart
  // or jump when the crossfade boundary is crossed.
  const shotSpan =
    shotCount > 1
      ? (safeDuration + transitionFrames * (shotCount - 1)) / shotCount
      : safeDuration;

  const shotWindows = shots.map((shot, index) => {
    const start = Math.max(0, Math.round(index * (shotSpan - transitionFrames)));
    const end =
      index === shots.length - 1
        ? safeDuration
        : Math.min(safeDuration, Math.round(start + shotSpan));
    return {
      shot,
      index,
      start,
      duration: Math.max(1, end - start),
    };
  });

  const shotBoundaryFrames = shotWindows.slice(1).map((w) => w.start);

  // A tiny focus settle on each incoming Shorts scene softens the hard scene
  // cut without fading through black or overlapping narration tracks.
  const entryFrames = format === 'shorts' && smoothEntry ? 6 : 0;
  const entryBlur =
    entryFrames > 0
      ? interpolate(frame, [0, entryFrames], [2.4, 0], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 0;
  const entryScale =
    entryFrames > 0
      ? interpolate(frame, [0, entryFrames], [1.012, 1], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 1;

  return (
    <AbsoluteFill style={{ opacity, overflow: 'hidden', backgroundColor: '#000000' }}>
      <Audio src={staticFile(narrationFile)} volume={1.0} />

      {scene.soundEffect && scene.soundEffect !== 'none' && (
        <Audio src={staticFile(effectFile)} volume={0.35} />
      )}

      {shotBoundaryFrames.map((boundaryFrame) => (
        <Sequence
          key={boundaryFrame}
          from={Math.max(0, boundaryFrame - Math.round(Math.max(1, transitionFrames) / 2))}
          durationInFrames={Math.max(4, Math.round(Math.max(1, transitionFrames) * 1.5))}
          layout="none"
        >
          <Audio
            src={staticFile('audio/sfx/whoosh.mp3')}
            volume={format === 'shorts' ? 0.14 : 0.22}
          />
        </Sequence>
      ))}

      <AbsoluteFill
        style={{
          filter: entryBlur > 0 ? `blur(${entryBlur}px)` : undefined,
          transform: `scale(${entryScale})`,
        }}
      >
        {shotWindows.length > 0 ? (
          shotWindows.map((window, i) => {
            const incoming =
              window.shot.transition ||
              (i % 2 === 0 ? 'crossfade' : 'blur_cut');
            const nextTransition =
              shotWindows[i + 1]?.shot.transition ||
              ((i + 1) % 2 === 0 ? 'crossfade' : 'blur_cut');
            return (
              <Sequence
                key={`${window.index}-${window.shot.file}`}
                from={window.start}
                durationInFrames={window.duration}
                layout="none"
              >
                <AbsoluteFill>
                  <ShotLayer
                    shot={window.shot}
                    shotIndex={window.index}
                    shotDurationInFrames={window.duration}
                    transitionFrames={transitionFrames}
                    direction={direction}
                    format={format}
                    scene={scene}
                    isFirst={i === 0}
                    isLast={i === shotWindows.length - 1}
                    incomingTransition={incoming}
                    outgoingTransition={nextTransition}
                  />
                </AbsoluteFill>
              </Sequence>
            );
          })
        ) : (
          <AbsoluteFill style={{ backgroundColor: '#000000' }} />
        )}
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at center, transparent 60%, rgba(0, 0, 0, 0.42) 100%)',
        }}
      />
    </AbsoluteFill>
  );
};
