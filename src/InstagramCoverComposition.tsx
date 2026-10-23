import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';
import { ThumbnailProps } from './ThumbnailComposition';

const { fontFamily } = loadFont();

// Cover source is the first QC-approved portrait shot, NOT an unrelated AI image.
// Always fit text in the central Reels/grid-safe region.
export const InstagramCoverComposition: React.FC<ThumbnailProps> = ({
  backgroundImage,
  hookText,
}) => (
  <AbsoluteFill style={{ backgroundColor: '#080605' }}>
    <Img
      src={staticFile(`images/${backgroundImage}`)}
      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
    />
    <AbsoluteFill
      style={{
        background: 'linear-gradient(180deg, rgba(0,0,0,.35), transparent 30%, rgba(0,0,0,.68) 100%)',
      }}
    />
    <AbsoluteFill
      style={{
        justifyContent: 'center',
        alignItems: 'center',
        paddingLeft: 96,
        paddingRight: 96,
        paddingTop: 250,
        paddingBottom: 320,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 860,
          textAlign: 'center',
          background: 'rgba(19,10,4,.68)',
          padding: '20px 32px',
          borderRadius: 24,
          border: '2px solid rgba(250,190,65,.5)',
          fontFamily,
          fontSize: 76,
          fontWeight: 900,
          lineHeight: 1.26,
          whiteSpace: 'pre-line',
          wordBreak: 'keep-all',
          overflowWrap: 'normal',
          color: '#FFF6D6',
          textShadow: '0 5px 14px rgba(0,0,0,.9)',
        }}
      >
        {hookText}
      </div>
    </AbsoluteFill>
  </AbsoluteFill>
);
