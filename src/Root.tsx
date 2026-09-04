import React from 'react';
import { Composition, Still } from 'remotion';
import { DevotionalComposition } from './DevotionalComposition';
import { DevotionalShortsComposition } from './DevotionalShortsComposition';
import { ThumbnailComposition, ThumbnailProps } from './ThumbnailComposition';
import { DevotionalVideoProps } from './types';
import defaultPropsLong from '../public/props.json';
import defaultPropsShorts from '../public/props_shorts.json';
import defaultPropsThumbnail from '../public/thumbnail_props.json';

export const RemotionRoot: React.FC = () => {
  const fps = 30;
  const typedPropsLong = defaultPropsLong as DevotionalVideoProps;
  const typedPropsShorts = defaultPropsShorts as DevotionalVideoProps;
  const typedPropsThumbnail = defaultPropsThumbnail as ThumbnailProps;

  // Calculate dynamic duration for Long Video
  const totalLongSeconds = typedPropsLong.scenes?.length
    ? typedPropsLong.scenes.reduce((acc, scene) => acc + (scene.durationInSeconds || 5), 0)
    : 10;
  const durationInFramesLong = Math.max(30, Math.round(totalLongSeconds * fps));

  // Calculate dynamic duration for Shorts Video (no longer hardcoded to 45s)
  const totalShortsSeconds = typedPropsShorts.scenes?.length
    ? typedPropsShorts.scenes.reduce((acc, scene) => acc + (scene.durationInSeconds || 5), 0)
    : 45;
  const durationInFramesShorts = Math.max(30, Math.round(totalShortsSeconds * fps));

  return (
    <>
      {/* 1. Long Devotional Video (16:9 Widescreen) */}
      <Composition
        id="DevotionalComposition"
        component={DevotionalComposition}
        durationInFrames={durationInFramesLong}
        fps={fps}
        width={1920}
        height={1080}
        defaultProps={typedPropsLong}
      />

      {/* 2. YouTube Shorts Video (9:16 Vertical) */}
      <Composition
        id="DevotionalShortsComposition"
        component={DevotionalShortsComposition}
        durationInFrames={durationInFramesShorts}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={typedPropsShorts}
      />

      {/* 3. High-CTR Thumbnail (16:9 still, background image + bold Hindi
          hook-text overlay) - rendered as a single frame via `npx remotion
          still`, see .github/workflows/render.yml */}
      <Still
        id="ThumbnailComposition"
        component={ThumbnailComposition}
        width={1920}
        height={1080}
        defaultProps={typedPropsThumbnail}
      />
    </>
  );
};
