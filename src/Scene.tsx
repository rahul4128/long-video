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
  useVideoConfig,
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

type TransitionStyle = 'cut' | 'crossfade' | 'blur_cut';

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
  incomingTransitionFrames: number;
  outgoingTransitionFrames: number;
  direction: 'zoom-in' | 'pan-right';
  format: 'long' | 'shorts';
  scene: SceneItem;
  isFirst: boolean;
  isLast: boolean;
  incomingTransition: TransitionStyle;
  outgoingTransition: TransitionStyle;
}

const ShotLayer: React.FC<ShotLayerProps> = ({
  shot,
  shotIndex,
  shotDurationInFrames,
  incomingTransitionFrames,
  outgoingTransitionFrames,
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

  const entry =
    isFirst || incomingTransition === 'cut' || incomingTransitionFrames <= 0
      ? 1
      : interpolate(frame, [0, incomingTransitionFrames], [0, 1], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });

  const exit =
    isLast || outgoingTransition === 'cut' || outgoingTransitionFrames <= 0
      ? 1
      : interpolate(
          frame,
          [
            Math.max(0, safeShotDuration - outgoingTransitionFrames),
            safeShotDuration,
          ],
          [1, 0],
          {
            easing: smooth,
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          },
        );

  const opacity = Math.min(entry, exit);

  const entryBlur =
    !isFirst &&
    incomingTransition === 'blur_cut' &&
    incomingTransitionFrames > 0
      ? interpolate(frame, [0, incomingTransitionFrames], [3.5, 0], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 0;

  const exitBlur =
    !isLast &&
    outgoingTransition === 'blur_cut' &&
    outgoingTransitionFrames > 0
      ? interpolate(
          frame,
          [
            Math.max(0, safeShotDuration - outgoingTransitionFrames),
            safeShotDuration,
          ],
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

  const isShorts = format === 'shorts';
  const zoomEnd =
    scene.director?.camera === 'slow_push'
      ? isShorts
        ? 1.07
        : 1.1
      : isShorts
        ? 1.09
        : 1.16;
  const panStartScale = isShorts ? 1.1 : 1.15;
  const panEndScale = isShorts ? 1.04 : 1.05;
  const panDistance = isShorts ? 18 : 30;

  const scale =
    shotDirection === 'zoom-in'
      ? interpolate(frame, [0, safeShotDuration], [1.0, zoomEnd], {
          easing: smooth,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : interpolate(
          frame,
          [0, safeShotDuration],
          [panStartScale, panEndScale],
          {
            easing: smooth,
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          },
        );

  const translateX =
    shotDirection === 'pan-right'
      ? interpolate(
          frame,
          [0, safeShotDuration],
          [
            scene.director?.camera === 'pan_left' ? panDistance : -panDistance,
            scene.director?.camera === 'pan_left' ? -panDistance : panDistance,
          ],
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
  const { fps } = useVideoConfig();
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = format === 'shorts' ? 7 : 12;
  const smooth = Easing.inOut(Easing.cubic);

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
  const defaultTransitionFrames =
    shotCount <= 1
      ? 0
      : format === 'shorts'
        ? Math.max(5, Math.min(9, Math.round(nominalFrames / 6)))
        : Math.max(6, Math.min(12, Math.round(nominalFrames / 5)));

  const transitionFor = (shot: Shot | undefined, index: number): TransitionStyle => {
    if (
      shot?.transition === 'cut' ||
      shot?.transition === 'crossfade' ||
      shot?.transition === 'blur_cut'
    ) {
      return shot.transition;
    }
    return index % 2 === 0 ? 'crossfade' : 'blur_cut';
  };

  const transitionFramesFor = (style: TransitionStyle): number =>
    style === 'cut' ? 0 : defaultTransitionFrames;

  // Phase 4: if the Python asset stage attached real TTS-synchronised start/end
  // times, those become authoritative. Older props still use equal windows.
  const hasNarrationSync =
    shots.length > 0 &&
    shots.every(
      (shot) =>
        typeof shot.startSeconds === 'number' &&
        Number.isFinite(shot.startSeconds) &&
        typeof shot.endSeconds === 'number' &&
        Number.isFinite(shot.endSeconds) &&
        shot.endSeconds > shot.startSeconds,
    );

  const equalSpan = safeDuration / shotCount;
  const baseWindows = shots.map((shot, index) => {
    if (hasNarrationSync) {
      const start = Math.max(
        0,
        Math.min(safeDuration - 1, Math.round((shot.startSeconds || 0) * fps)),
      );
      const end = Math.max(
        start + 1,
        Math.min(safeDuration, Math.round((shot.endSeconds || 0) * fps)),
      );
      return { shot, index, baseStart: start, baseEnd: end };
    }

    const start = Math.max(0, Math.round(index * equalSpan));
    const end =
      index === shots.length - 1
        ? safeDuration
        : Math.min(safeDuration, Math.round((index + 1) * equalSpan));
    return { shot, index, baseStart: start, baseEnd: Math.max(start + 1, end) };
  });

  // Crossfade/blur transitions straddle the narration boundary, so the CENTER
  // of the visual transition lands on the first spoken word of the next beat.
  // A 'cut' gets zero overlap and happens exactly on that word boundary.
  const shotWindows = baseWindows.map((base, i) => {
    const incomingTransition = transitionFor(base.shot, i);
    const outgoingTransition =
      i < baseWindows.length - 1
        ? transitionFor(baseWindows[i + 1].shot, i + 1)
        : 'cut';

    const incomingTransitionFrames =
      i === 0 ? 0 : transitionFramesFor(incomingTransition);
    const outgoingTransitionFrames =
      i === baseWindows.length - 1
        ? 0
        : transitionFramesFor(outgoingTransition);

    const start =
      i === 0
        ? 0
        : Math.max(
            0,
            base.baseStart - Math.floor(incomingTransitionFrames / 2),
          );
    const end =
      i === baseWindows.length - 1
        ? safeDuration
        : Math.min(
            safeDuration,
            base.baseEnd + Math.ceil(outgoingTransitionFrames / 2),
          );

    return {
      ...base,
      start,
      end,
      duration: Math.max(1, end - start),
      incomingTransition,
      outgoingTransition,
      incomingTransitionFrames,
      outgoingTransitionFrames,
    };
  });

  // Whoosh is anchored to the true narration boundary, not to the beginning
  // of the overlap window.
  const shotBoundaries = shotWindows.slice(1).map((window) => ({
    frame: window.baseStart,
    transition: window.incomingTransition,
  }));

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

      {shotBoundaries.map((boundary, index) => {
        const transitionFrames = transitionFramesFor(boundary.transition);
        if (transitionFrames <= 0) {
          return null;
        }
        return (
          <Sequence
            key={`${boundary.frame}-${index}`}
            from={Math.max(0, boundary.frame - Math.round(transitionFrames / 2))}
            durationInFrames={Math.max(4, Math.round(transitionFrames * 1.5))}
            layout="none"
          >
            <Audio
              src={staticFile('audio/sfx/whoosh.mp3')}
              volume={format === 'shorts' ? 0.14 : 0.22}
            />
          </Sequence>
        );
      })}

      <AbsoluteFill
        style={{
          filter: entryBlur > 0 ? `blur(${entryBlur}px)` : undefined,
          transform: `scale(${entryScale})`,
        }}
      >
        {shotWindows.length > 0 ? (
          shotWindows.map((window, i) => (
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
                  incomingTransitionFrames={window.incomingTransitionFrames}
                  outgoingTransitionFrames={window.outgoingTransitionFrames}
                  direction={direction}
                  format={format}
                  scene={scene}
                  isFirst={i === 0}
                  isLast={i === shotWindows.length - 1}
                  incomingTransition={window.incomingTransition}
                  outgoingTransition={window.outgoingTransition}
                />
              </AbsoluteFill>
            </Sequence>
          ))
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
