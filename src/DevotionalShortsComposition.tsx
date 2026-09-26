import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Series,
  staticFile,
  useVideoConfig,
} from 'remotion';
import { DevotionalVideoProps } from './types';
import { Scene } from './Scene';
import { Subtitles } from './Subtitles';
import { HookOverlay } from './HookOverlay';

export const DevotionalShortsComposition: React.FC<DevotionalVideoProps> = ({
  scenes = [],
  hookText = '',
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Background Devotional Flute / Tanpura Music */}
      <Audio
        src={staticFile('audio/bgm.mp3')}
        volume={0.10}
        loop
      />

      {/* Sequential Shorts Scenes (Vertical 9:16) */}
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
                format="shorts"
              />
              <Subtitles text={scene.narration_chunk} words={scene.words} />
            </Series.Sequence>
          );
        })}
      </Series>

      {/* First-1.8s on-screen Hindi hook */}
      <HookOverlay text={hookText} format="shorts" />
    </AbsoluteFill>
  );
};
