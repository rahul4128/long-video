import React from 'react';
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate } from 'remotion';
import { Shot } from './types';

/** Explicitly verified side-by-side evidence; never synthesize before/after facts. */
export const VerifiedComparison: React.FC<{ shot: Shot; format: 'long' | 'shorts' }> =
  ({ shot, format }) => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();
    if (!shot.comparisonApproved || !shot.comparisonBeforeFile || !shot.comparisonAfterFile) return null;
    const isShort = format === 'shorts';
    const fill = interpolate(frame, [0, Math.max(8, Math.round(fps * 0.48))], [0.35, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    return (
      <AbsoluteFill style={{ zIndex: 1, display: 'flex', flexDirection: 'row',
        border: isShort ? '10px solid rgba(25,18,8,0.8)' : '9px solid rgba(25,18,8,0.8)',
        backgroundColor: '#111', opacity: fill }}>
        {[shot.comparisonBeforeFile, shot.comparisonAfterFile].map((name, i) => (
          <div key={name + i} style={{ width: '50%', height: '100%', position: 'relative',
            overflow: 'hidden', borderRight: i === 0 ? '3px solid #FFDC81' : 'none' }}>
            <Img src={staticFile('images/' + name)}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            <div style={{
              position: 'absolute', top: isShort ? 205 : 90,
              left: isShort ? 16 : 34, padding: isShort ? '11px 17px' : '9px 20px',
              borderRadius: 6, fontSize: isShort ? 38 : 32, fontWeight: 900,
              background: i === 0 ? '#342418' : '#155846',
              color: '#fff6e0',
            }}>
              {i === 0 ? 'पहले' : 'बाद में'}
            </div>
          </div>
        ))}
      </AbsoluteFill>
    );
  };

/** Blur only explicitly human-approved fixed regions; not auto face detection/tracking. */
export const VerifiedPrivacyBlur: React.FC<{ shot: Shot }> = ({ shot }) => {
  if (!shot.privacyApproved || !shot.privacyBlurBoxes?.length) return null;
  return (
    <AbsoluteFill style={{ zIndex: 3, pointerEvents: 'none' }}>
      {shot.privacyBlurBoxes.map((box, i) => (
        <div key={i} style={{
          position: 'absolute',
          left: (box.x * 100) + '%',
          top: (box.y * 100) + '%',
          width: (box.width * 100) + '%',
          height: (box.height * 100) + '%',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          background: 'rgba(20,20,20,0.12)',
          borderRadius: 14,
        }} />
      ))}
    </AbsoluteFill>
  );
};
