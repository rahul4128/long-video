import React from 'react';
import { Composition } from 'remotion';
import { DevotionalComposition } from './DevotionalComposition';
import { DevotionalVideoProps } from './types';
import defaultProps from '../public/props.json';

export const RemotionRoot: React.FC = () => {
  const fps = 30;
  const typedProps = defaultProps as DevotionalVideoProps;

  const totalDurationInSeconds = typedProps.scenes?.length
    ? typedProps.scenes.reduce((acc, scene) => acc + (scene.durationInSeconds || 5), 0)
    : 10;

  const durationInFrames = Math.max(30, Math.round(totalDurationInSeconds * fps));

  return (
    <Composition
      id="DevotionalComposition"
      component={DevotionalComposition}
      durationInFrames={durationInFrames}
      fps={fps}
      width={1920}
      height={1080}
      defaultProps={typedProps}
    />
  );
};
