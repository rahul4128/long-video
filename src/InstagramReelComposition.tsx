import React from 'react';
import { DevotionalShortsComposition } from './DevotionalShortsComposition';
import { DevotionalVideoProps } from './types';

// Dedicated portrait Instagram export. Never reuse the 16:9 Long video.
export const InstagramReelComposition: React.FC<DevotionalVideoProps> = (props) => {
  return <DevotionalShortsComposition {...props} platform="instagram" />;
};
