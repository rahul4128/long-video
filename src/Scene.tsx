import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { Shot, SceneItem } from './types';
import { DocumentaryGraphic } from './DocumentaryGraphic';
import { EditorialAccent } from './EditorialAccent';
import { EditFx } from './EditFx';
import { VerifiedComparison, VerifiedPrivacyBlur } from './ConditionalEditSkills';

interface SceneProps {
  scene: SceneItem;
  durationInFrames: number;
  direction: 'zoom-in' | 'pan-right';
  format?: 'long' | 'shorts';
  fadeIn?: boolean;
  fadeOut?: boolean;
  smoothEntry?: boolean;
}

type TransitionStyle = 'cut' | 'crossfade' | 'blur_cut' | 'whip_pan' | 'flash_cut';

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
  // The narrator's question, action or reveal determines the camera speed.
  const rhythm = shot.editRhythm || 'measured';
  const motionCurve = rhythm === 'quick'
    ? Easing.out(Easing.cubic)
    : rhythm === 'linger'
      ? Easing.inOut(Easing.quad)
      : smooth;

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
  const isShorts = format === 'shorts';
  const treatment = shot.editTreatment || 'clean';
  // A restrained grade creates visual consistency across licensed real footage,
  // illustrations and AI visuals; never claim an era or event via an effect.
  const colorGrade =
    shot.editAccent === 'festival_energy'
      ? 'contrast(1.07) saturate(1.13)'
      : shot.editAccent === 'emotional_story'
        ? 'contrast(1.025) saturate(0.94)'
        : shot.editAccent === 'presenter_explainer'
          ? 'contrast(1.06) saturate(1.01)'
          : treatment === 'impact'
            ? 'contrast(1.07) saturate(1.07)'
            : treatment === 'breathing'
              ? 'contrast(1.025) saturate(0.97)'
              : 'contrast(1.045) saturate(1.025)';
  // One restrained whip move on a storytelling pivot; not applied to every cut.
  const whipIn = incomingTransition === 'whip_pan'
    ? interpolate(frame, [0, Math.max(1, incomingTransitionFrames)], [68, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      })
    : 0;
  const whipOut = outgoingTransition === 'whip_pan'
    ? interpolate(
        frame,
        [Math.max(0, safeShotDuration - outgoingTransitionFrames), safeShotDuration],
        [0, -68],
        { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
      )
    : 0;
  const whipOffset = whipIn + whipOut;
  const whipBlur = (Math.abs(whipOffset) / 68) * 1.25;
  const mildMatch = shot.colorCorrection;
  const matchFilter = mildMatch
    ? ' brightness(' + Math.max(0.92, Math.min(1.08, mildMatch.brightness)) + ')' +
      ' saturate(' + Math.max(0.95, Math.min(1.05, mildMatch.saturation)) + ')'
    : '';
  const visualFilter = (blurPx + whipBlur > 0
    ? 'blur(' + (blurPx + whipBlur) + 'px) ' : '') + colorGrade + matchFilter;

  // Phase 5: beat-specific camera direction is authoritative for AI images.
  // Videos keep the existing scene/director behavior so this phase cannot
  // accidentally change real-stock motion or crop decisions.
  const beatCamera = shot.cameraMotion;
  const sceneCamera = scene.director?.camera;
  const plannedCamera =
    shot.type === 'image' && beatCamera
      ? beatCamera
      : sceneCamera === 'slow_push'
        ? 'slow_push_in'
        : sceneCamera;

  const shotDirection: 'zoom-in' | 'pan-right' =
    plannedCamera === 'pan_left'
      ? 'pan-right'
      : plannedCamera === 'pan_right'
        ? 'pan-right'
        : plannedCamera === 'slow_push_in'
          ? 'zoom-in'
          : shotIndex % 2 === 0
            ? direction
            : direction === 'zoom-in'
              ? 'pan-right'
              : 'zoom-in';

  const zoomEnd =
    plannedCamera === 'slow_push_in'
      ? isShorts
        ? 1.07
        : 1.1
      : isShorts
        ? 1.09
        : 1.16;
  const editedZoomEnd =
    treatment === 'impact' ? Math.min(1.10, zoomEnd) :
    treatment === 'breathing' ? Math.min(1.045, zoomEnd) :
    treatment === 'question' ? Math.min(1.06, zoomEnd) :
    treatment === 'detail' ? Math.min(1.09, zoomEnd) : zoomEnd;
  const panStartScale = isShorts ? 1.1 : 1.15;
  const panEndScale = isShorts ? 1.04 : 1.05;
  const panDistance = isShorts ? 18 : 30;

  const scale =
    shotDirection === 'zoom-in'
      ? interpolate(frame, [0, safeShotDuration], [1.0, editedZoomEnd], {
          easing: motionCurve,
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : interpolate(
          frame,
          [0, safeShotDuration],
          [panStartScale, panEndScale],
          {
            easing: motionCurve,
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
            plannedCamera === 'pan_left' ? panDistance : -panDistance,
            plannedCamera === 'pan_left' ? -panDistance : panDistance,
          ],
          {
            easing: motionCurve,
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          },
        )
      : 0;

  const transform = `translateX(${whipOffset}px) scale(${scale}) translateX(${translateX}px)`;

  if (shot.type === 'video') {
    return (
      <OffthreadVideo
        key={`video-${shotIndex}-${shot.file}`}
        src={staticFile(`images/${shot.file}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform,
          opacity,
          filter: visualFilter,
        }}
        muted
        // Source clips are trimmed/extended in Python shot planning; OffthreadVideo does not support the HTML loop prop.
      />
    );
  }

  // AI-image motion is deliberately subtle. We create depth without a
  // segmentation model by using the same artwork as a soft, oversized
  // background layer moving slightly opposite to the sharper foreground.
  // It reads as cinematic depth but avoids the warped "AI animation" look.
  const isAiVisual =
    shot.source === 'ai_image' ||
    shot.cameraMotion === 'slow_push_in' ||
    shot.cameraMotion === 'pan_left' ||
    shot.cameraMotion === 'pan_right';

  if (!isAiVisual) {
    return (
      <Img
        key={`image-${shotIndex}-${shot.file}`}
        src={staticFile(`images/${shot.file}`)}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform,
          opacity,
          filter: visualFilter,
        }}
      />
    );
  }

  const progress = interpolate(frame, [0, safeShotDuration], [0, 1], {
    easing: motionCurve,
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  const imageMotion =
    shot.cameraMotion === 'pan_left' ||
    shot.cameraMotion === 'pan_right' ||
    shot.cameraMotion === 'slow_push_in'
      ? shot.cameraMotion
      : 'slow_push_in';

  // Keep movement especially restrained in vertical Shorts. Large travel on
  // a narrow crop feels like a phone slideshow rather than a camera move.
  const foregroundPush = rhythm === 'linger' ? (isShorts ? 1.035 : 1.045) :
    rhythm === 'quick' && treatment !== 'impact' ? (isShorts ? 1.08 : 1.105) :
    treatment === 'impact' ? 1.085 :
    treatment === 'breathing' ? 1.035 : treatment === 'detail' ? 1.07 :
    isShorts ? 1.055 : 1.075;
  const foregroundPan = isShorts ? 14 : 24;
  const backgroundPan = isShorts ? 6 : 10;
  const verticalDrift = isShorts ? 4 : 7;

  const fgScale =
    imageMotion === 'slow_push_in'
      ? interpolate(progress, [0, 1], [1.025, foregroundPush])
      : interpolate(progress, [0, 1], [1.075, 1.045]);

  const fgX =
    imageMotion === 'pan_left'
      ? interpolate(progress, [0, 1], [foregroundPan, -foregroundPan])
      : imageMotion === 'pan_right'
        ? interpolate(progress, [0, 1], [-foregroundPan, foregroundPan])
        : interpolate(progress, [0, 1], [-3, 3]);

  const fgY =
    shot.shotType === 'detail' || shot.shotType === 'close_up'
      ? interpolate(progress, [0, 1], [verticalDrift, -verticalDrift])
      : interpolate(progress, [0, 1], [2, -2]);

  // Keep the cinematic motion on one sharp layer. The previous duplicated
  // full-frame blurred background was visually hidden by the scaled foreground
  // in most frames but forced Chromium to rasterize a costly blur every frame.
  // One slow moving glow is enough to keep a still alive. Opacity remains
  // tiny so faces/deities are never washed out and devotional art stays calm.
  const glowX = interpolate(progress, [0, 1], [-35, 135]);
  const glowOpacity =
    shot.shotType === 'atmosphere' ? 0.11 : shot.shotType === 'wide' ? 0.075 : 0.055;

  return (
    <AbsoluteFill
      style={{
        opacity,
        overflow: 'hidden',
        filter: visualFilter,
        transform: 'translateX(' + whipOffset + 'px)',
        backgroundColor: '#000000',
      }}
    >
      <Img
        src={staticFile(`images/${shot.file}`)}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: `translate3d(${fgX}px, ${fgY}px, 0) scale(${fgScale})`,
          willChange: 'transform',
        }}
      />

      <AbsoluteFill
        style={{
          background:
            `linear-gradient(105deg, transparent ${glowX - 28}%, rgba(255,244,214,${glowOpacity}) ${glowX}%, transparent ${glowX + 28}%)`,
          pointerEvents: 'none',
        }}
      />

      <AbsoluteFill
        style={{
          background:
            'radial-gradient(circle at 50% 44%, transparent 48%, rgba(0,0,0,0.18) 82%, rgba(0,0,0,0.3) 100%)',
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
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

  // Narration takes priority: duck score under spoken words, fade in/out at
  // scene boundaries and lift slightly only during pauses or reveals.
  const localSeconds = frame / fps;
  const words = scene.words || [];
  const speaking = !words.length || words.some(
    (word) => localSeconds >= word.start - 0.14 && localSeconds <= word.end + 0.14
  );
  const peak = scene.musicMood === 'revelation' || scene.musicMood === 'uplifting';
  const unduckedVolume = peak ? 0.105 : 0.075;
  const musicVolume = (speaking ? 0.34 : 1) * unduckedVolume *
    Math.min(1, frame / Math.max(1, fps * 0.45),
      (safeDuration - frame) / Math.max(1, fps * 0.65));

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
      shot?.transition === 'blur_cut' ||
      shot?.transition === 'whip_pan' ||
      shot?.transition === 'flash_cut'
    ) {
      return shot.transition;
    }
    return index % 2 === 0 ? 'crossfade' : 'blur_cut';
  };

  const transitionFramesFor = (style: TransitionStyle): number =>
    style === 'cut' ? 0 : style === 'flash_cut' ? Math.min(6, defaultTransitionFrames) : defaultTransitionFrames;

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

  // Phase 6: meaningful SFX are attached to individual visual beats after
  // TTS timing is known, so a bell/conch lands on the reveal itself rather
  // than blindly at the beginning of the scene.
  const beatAudioCues = (scene.visualBeats || [])
    .filter(
      (beat) =>
        beat.soundEffectFile &&
        typeof beat.actualStartSeconds === 'number' &&
        Number.isFinite(beat.actualStartSeconds),
    )
    .map((beat) => ({
      frame: Math.max(
        0,
        Math.min(
          safeDuration - 1,
          Math.round((beat.actualStartSeconds || 0) * fps),
        ),
      ),
      file: beat.soundEffectFile as string,
      volume: Math.max(0.04, Math.min(0.24, beat.soundEffectVolume ?? 0.16)),
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
      {scene.musicFile && (
        <Audio
          src={staticFile(`audio/${scene.musicFile}`)}
          volume={Math.max(0, musicVolume)}
          loop
        />
      )}

      {scene.soundEffect && scene.soundEffect !== 'none' && (
        <Audio src={staticFile(effectFile)} volume={0.35} />
      )}

      {beatAudioCues.map((cue, index) => (
        <Sequence
          key={`beat-sfx-${cue.frame}-${index}`}
          from={cue.frame}
          durationInFrames={Math.max(1, safeDuration - cue.frame)}
          layout="none"
        >
          <Audio src={staticFile(cue.file)} volume={cue.volume} />
        </Sequence>
      ))}

      {shotBoundaries.map((boundary, index) => {
        const transitionFrames = transitionFramesFor(boundary.transition);
        const meaningfulCueNearby = beatAudioCues.some(
          (cue) => Math.abs(cue.frame - boundary.frame) <= Math.max(4, transitionFrames),
        );
        // Crossfades are intentionally silent. Blur cuts get a subtle whoosh
        // only when a stronger story SFX is not already landing there.
        if (
          transitionFrames <= 0 ||
          boundary.transition !== 'blur_cut' ||
          meaningfulCueNearby
        ) {
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
                <VerifiedComparison shot={window.shot} format={format} />
                <VerifiedPrivacyBlur shot={window.shot} />
                <EditFx
                  format={format}
                  spotlight={window.shot.editSpotlight}
                  snap={window.shot.editBeatSnap}
                  flash={window.incomingTransition === 'flash_cut'}
                />
                {window.shot.documentaryGraphic && (
                  <DocumentaryGraphic
                    graphic={window.shot.documentaryGraphic}
                    format={format}
                    maxFrames={window.duration}
                  />
                )}
                {window.shot.editorialLabel && (
                  <EditorialAccent
                    label={window.shot.editorialLabel}
                    format={format}
                    maxFrames={window.duration}
                  />
                )}
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
