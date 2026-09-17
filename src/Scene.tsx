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

// Normalizes a scene's visual assets into one ordered shot list, whether it
// came from the new `shots` field or the legacy single-asset fields (a
// video filename, one image filename, or an array of image filenames). This
// is what lets Scene.tsx treat "a scene made of 2 stock clips + 1 AI image
// top-up" and "an old scene with a single imageFileName" through the exact
// same rendering path below.
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

export const Scene: React.FC<SceneProps> = ({
  scene,
  durationInFrames,
  direction,
  format = 'long',
}) => {
  const frame = useCurrentFrame();
  const safeDuration = Math.max(30, durationInFrames);
  const fadeDuration = 12;

  // Smooth Cross-fade in/out of the WHOLE scene (unchanged from before).
  let opacity = 1;
  if (frame < fadeDuration) {
    opacity = frame / fadeDuration;
  } else if (frame > safeDuration - fadeDuration) {
    opacity = (safeDuration - frame) / fadeDuration;
  }
  opacity = Math.max(0, Math.min(1, opacity));

  // Long and Shorts renders write narration audio under different filename prefixes
  // (see generate_assets.py: chunk_N.mp3 vs shorts_chunk_N.mp3) - pick the right one.
  const narrationFile =
    format === 'shorts'
      ? `audio/shorts_chunk_${scene.scene_number}.mp3`
      : `audio/chunk_${scene.scene_number}.mp3`;

  // generate_assets.py always guarantees this file exists whenever soundEffect !== 'none'
  // (a fresh Freesound CC0 clip, a checked-in library fallback, or silence as a last
  // resort) - see resolve_sound_effect_audio(). Both long-video AND shorts payloads
  // now carry a soundEffect field (shorts used to have none at all).
  const effectFile = `audio/effects/${format}_effect_${scene.scene_number}.mp3`;

  // --- Multi-shot bookkeeping. THIS IS THE ACTUAL FIX for "stock clip ends,
  // freezes, narration keeps going": generate_assets.py now sizes the number
  // of shots (video and/or image, freely mixed) to cover the scene's full
  // duration - see fetch_video_shots_for_duration() in generate_assets.py -
  // so a scene's total on-screen time is never longer than its combined
  // shots. Fully backward-compatible: a single-shot scene (shots.length ===
  // 1) behaves exactly as the old single-asset code did, just with a
  // slightly punchier Ken Burns range.
  const shots = resolveShots(scene);
  const shotCount = Math.max(1, shots.length);
  const shotDurationFrames = safeDuration / shotCount;
  const transitionFrames = Math.max(4, Math.min(15, shotDurationFrames / 3));

  const currentShot = Math.min(shotCount - 1, Math.floor(frame / shotDurationFrames));
  const nextShot = Math.min(shotCount - 1, currentShot + 1);
  const intoCurrentShot = frame - currentShot * shotDurationFrames;
  const framesToNextShotBoundary = (currentShot + 1) * shotDurationFrames - frame;

  // 0 = fully on currentShot, 1 = fully on nextShot - only ramps up in the
  // last `transitionFrames` of a shot, and only when there IS a distinct
  // next shot to cross into.
  const crossFade =
    nextShot !== currentShot && framesToNextShotBoundary < transitionFrames
      ? 1 - Math.max(0, framesToNextShotBoundary) / transitionFrames
      : 0;

  // Cut-style variety: alternate a plain cross-dissolve with a quick
  // "blur cut" (a short gaussian-blur dip through the transition, like a
  // fast rack-focus) between shot boundaries, driven by the outgoing shot's
  // OWN transition hint when generate_assets.py provided one, falling back
  // to a deterministic alternation by shot index so this never depends on
  // upstream data being present. Doing this at every cut - not just plain
  // cross-fade every time - is what keeps a multi-shot scene from feeling
  // monotonous/workflow-generated.
  const outgoingTransition = shots[currentShot]?.transition;
  const useBlurCut = outgoingTransition ? outgoingTransition === 'blur_cut' : currentShot % 2 === 1;
  const blurPx = useBlurCut ? interpolate(crossFade, [0, 0.5, 1], [0, 6, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) : 0;

  // A short "whoosh" swipe under each cut - cheap, high-impact cinematic
  // sound design that plain cross-fades alone don't sell. Shared single
  // asset (fetched once per run by generate_assets.py's resolve_sound_effect_audio
  // call for "transition_whoosh"), reused at every boundary in both formats.
  // Skipped entirely for single-shot scenes (no cut happens).
  const shotBoundaryFrames: number[] = [];
  if (shotCount > 1) {
    for (let i = 1; i < shotCount; i++) {
      shotBoundaryFrames.push(Math.round(i * shotDurationFrames));
    }
  }

  // Ken Burns motion for a single sub-shot, alternating direction both by
  // the scene's own parity (the `direction` prop, set by the parent
  // composition) AND by shot index within the scene, so a multi-shot scene
  // doesn't repeat the exact same pan on every sub-shot. Now applies to
  // VIDEO shots too (previously video got zero motion treatment at all -
  // a plain static crop) so real footage reads as intentionally framed
  // rather than just dropped in.
  const kenBurnsTransform = (localFrame: number, shotIndex: number): string => {
    const shotDirection: 'zoom-in' | 'pan-right' =
      shotIndex % 2 === 0 ? direction : direction === 'zoom-in' ? 'pan-right' : 'zoom-in';
    const scale =
      shotDirection === 'zoom-in'
        ? interpolate(localFrame, Array.of(0, shotDurationFrames), Array.of(1.0, 1.18), {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
        : interpolate(localFrame, Array.of(0, shotDurationFrames), Array.of(1.15, 1.05), {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
    const translateX =
      shotDirection === 'pan-right'
        ? interpolate(localFrame, Array.of(0, shotDurationFrames), Array.of(-30, 30), {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          })
        : 0;
    return `scale(${scale}) translateX(${translateX}px)`;
  };

  // Renders one shot (video or image) with Ken Burns + the given opacity.
  // `loop` is passed on <Video> as a safety net only: generate_assets.py
  // sizes shots so each clip's own duration should already cover its
  // allotted window, but a slightly-short clip (an odd rounding, or a
  // shorter-than-expected stock hit) now loops seamlessly within its OWN
  // (much smaller, evenly-split) window instead of freezing - a world
  // better fallback than the old "one clip, no loop, freezes for the rest
  // of the whole scene" behavior.
  const renderShot = (shot: Shot, shotIndex: number, localFrame: number, shotOpacity: number) => {
    const transform = kenBurnsTransform(localFrame, shotIndex);
    if (shot.type === 'video') {
      return (
        <Video
          src={staticFile(`images/${shot.file}`)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform,
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
          transform,
          opacity: shotOpacity,
        }}
      />
    );
  };

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
          src={staticFile(effectFile)}
          volume={0.35}
        />
      )}

      {/* 1c. Transition whoosh at every shot cut inside this scene */}
      {shotBoundaryFrames.map((boundaryFrame) => (
        <Sequence
          key={boundaryFrame}
          from={Math.max(0, boundaryFrame - Math.round(transitionFrames / 2))}
          durationInFrames={Math.round(transitionFrames * 1.5)}
          layout="none"
        >
          <Audio src={staticFile('audio/sfx/whoosh.mp3')} volume={0.25} />
        </Sequence>
      ))}

      {/* 2. Visual Layer: cross-fades (plain, or a quick blur-cut for
          variety) between an ordered list of video/image sub-shots sized by
          generate_assets.py to cover this scene's full duration. */}
      <AbsoluteFill style={{ filter: blurPx > 0 ? `blur(${blurPx}px)` : undefined }}>
        <AbsoluteFill>
          {renderShot(shots[currentShot] ?? { type: 'image', file: '' }, currentShot, intoCurrentShot, 1 - crossFade)}
        </AbsoluteFill>
        {crossFade > 0 && nextShot !== currentShot && (
          <AbsoluteFill>
            {renderShot(shots[nextShot], nextShot, 0, crossFade)}
          </AbsoluteFill>
        )}
      </AbsoluteFill>

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
