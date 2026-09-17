import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Series,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { DevotionalVideoProps } from './types';
import { Scene } from './Scene';
import { Subtitles } from './Subtitles';

export const DevotionalComposition: React.FC<DevotionalVideoProps> = ({
  scenes = [],
  bgmSwellSceneNumbers = [],
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();

  // Per-scene [startFrame, endFrame) so the bgm-swell calculation below can
  // tell whether the CURRENT absolute frame falls inside a climax scene -
  // same cumulative-duration math Root.tsx already does for the overall
  // composition length, just per scene here.
  let cursor = 0;
  const sceneRanges = scenes.map((scene, index) => {
    const durationInFrames = Math.max(30, Math.round((scene.durationInSeconds || 5) * fps));
    const range = { sceneNumber: scene.scene_number || index + 1, start: cursor, end: cursor + durationInFrames };
    cursor += durationInFrames;
    return range;
  });

  // Swells the background music from its normal quiet 0.10 up to 0.28 for a
  // couple of seconds around each climax scene, then back down - instead of
  // bgm sitting at the exact same low volume for the entire video regardless
  // of what's happening in the story. A cheap touch, but it's one of the
  // clearest signals of "someone directed this" vs. "a template rendered
  // this". bgmSwellSceneNumbers is normally just the one revelation scene
  // (see _meta.climax_scene_number in generate_assets.py) but any number of
  // scenes works fine.
  const RAMP_FRAMES = Math.round(fps * 1.2);
  let bgmVolume = 0.1;
  for (const sceneNumber of bgmSwellSceneNumbers) {
    const range = sceneRanges.find((r) => r.sceneNumber === sceneNumber);
    if (!range) continue;
    const swell = interpolate(
      frame,
      [range.start - RAMP_FRAMES, range.start, range.end, range.end + RAMP_FRAMES],
      [0.1, 0.28, 0.28, 0.1],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
    );
    bgmVolume = Math.max(bgmVolume, swell);
  }

  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Background Devotional Flute / Tanpura Music */}
      <Audio
        src={staticFile('audio/bgm.mp3')}
        volume={bgmVolume}
        loop
      />

      {/* Sequential Long-Form Scenes (Widescreen 16:9) */}
      <Series>
        {scenes.map((scene, index) => {
          const sceneDurationInFrames = Math.max(
            30,
            Math.round((scene.durationInSeconds || 5) * fps)
          );
          return (
            <Series.Sequence
              key={scene.scene_number || index}
              durationInFrames={sceneDurationInFrames}
            >
              <Scene
                scene={scene}
                durationInFrames={sceneDurationInFrames}
                direction={index % 2 === 0 ? 'zoom-in' : 'pan-right'}
                format="long"
              />
              <Subtitles text={scene.narration_chunk} words={scene.words} />
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
