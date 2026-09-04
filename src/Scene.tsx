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

  // imageFileName is either a single string (a video .mp4, or one static
  // image) or an array of image filenames (a multi-shot slideshow generated
  // for long static-image scenes - see generate_multi_shot_ai_images() in
  // generate_assets.py). Normalize to an array either way so the rendering
  // logic below has one code path.
  const rawImageField = scene.imageFileName;
  const images: string[] = Array.isArray(rawImageField)
    ? rawImageField
    : [rawImageField || ''];
  const isVideo = !Array.isArray(rawImageField) && !!rawImageField?.endsWith('.mp4');

  // Long and Shorts renders write narration audio under different filename prefixes
  // (see generate_assets.py: chunk_N.mp3 vs shorts_chunk_N.mp3) - pick the right one.
  const narrationFile =
    format === 'shorts'
      ? `audio/shorts_chunk_${scene.scene_number}.mp3`
      : `audio/chunk_${scene.scene_number}.mp3`;

  // generate_assets.py always guarantees this file exists whenever soundEffect !== 'none'
  // (a fresh Freesound CC0 clip, a checked-in library fallback, or silence as a last
  // resort) - see resolve_sound_effect_audio(). Currently only the long-video payload
  // carries a soundEffect field.
  const effectFile = `audio/effects/${format}_effect_${scene.scene_number}.mp3`;

  // --- Multi-shot slideshow bookkeeping (no-op / fully backward-compatible
  // when images.length === 1: shotDurationFrames === safeDuration, so a
  // single-image scene behaves exactly as before, just with a slightly
  // punchier Ken Burns range). When there's more than one shot, the scene's
  // duration is split evenly between them, each gets its own short
  // zoom/pan, and a brief cross-fade smooths the cut between consecutive
  // shots - this is what turns "one static image held for 45 seconds" into
  // a handful of distinct, moving compositions.
  const shotCount = images.length;
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

  // Ken Burns motion for a single sub-shot, alternating direction both by
  // the scene's own parity (the `direction` prop, set by the parent
  // composition) AND by shot index within the scene, so a multi-shot scene
  // doesn't repeat the exact same pan on every sub-shot. Slightly wider
  // ranges than before (1.15 -> 1.18 zoom, +/-25 -> +/-30px pan) since each
  // sub-shot now runs for a shorter window and needs a bit more amplitude
  // to still read as visible motion.
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

      {/* 2. Visual Layer: Renders Real 4K Video, or a Ken Burns image
          slideshow (1+ AI-generated stills cross-fading between sub-shots) */}
      {isVideo ? (
        <Video
          src={staticFile(`images/${images[0]}`)}
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          muted
        />
      ) : (
        <>
          <AbsoluteFill>
            <Img
              src={staticFile(`images/${images[currentShot]}`)}
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                transform: kenBurnsTransform(intoCurrentShot, currentShot),
                opacity: 1 - crossFade,
              }}
            />
          </AbsoluteFill>
          {crossFade > 0 && nextShot !== currentShot && (
            <AbsoluteFill>
              <Img
                src={staticFile(`images/${images[nextShot]}`)}
                style={{
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover',
                  transform: kenBurnsTransform(0, nextShot),
                  opacity: crossFade,
                }}
              />
            </AbsoluteFill>
          )}
        </>
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
