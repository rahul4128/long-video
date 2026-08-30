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

export const DevotionalComposition: React.FC<DevotionalVideoProps> = ({
  scenes = [],
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
              <Subtitles text={scene.narration_chunk} />
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
