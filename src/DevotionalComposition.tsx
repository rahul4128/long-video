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

export const DevotionalComposition: React.FC<DevotionalVideoProps> = ({
  scenes = [],
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: '#0b090a' }}>
      {/* Background Devotional Flute / Tanpura Music */}
      <Audio
        src={staticFile('audio/bgm.mp3')}
        volume={0.12}
        loop
      />

      {/* Main Hindi Voiceover */}
      <Audio src={staticFile('audio/voiceover.mp3')} volume={1.0} />

      {/* Visual Scene Transitions with Ken Burns Effect */}
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
              />
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
