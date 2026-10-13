import React from 'react';
import {
  Easing,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const { fontFamily } = loadFont();

/** Brief story-derived documentary annotation; never overlaps lower captions. */
export const EditorialAccent: React.FC<{
  label: string;
  format: 'long' | 'shorts';
  maxFrames: number;
}> = ({ label, format, maxFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isShorts = format === 'shorts';
  const duration = Math.max(14, Math.min(maxFrames, Math.round(fps * 1.75)));
  const appear = interpolate(frame, [0, Math.min(8, duration / 3)], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const disappear = interpolate(
    frame, [Math.max(9, duration - 8), duration], [1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const opacity = Math.max(0, Math.min(appear, disappear));
  const x = interpolate(appear, [0, 1], [isShorts ? -24 : -16, 0]);
  const rule = interpolate(frame, [0, Math.round(fps * 0.65)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  if (!label.trim()) return null;
  return (
    <div
      style={{
        position: 'absolute',
        top: isShorts ? 310 : 118,
        left: isShorts ? 72 : 136,
        maxWidth: isShorts ? 790 : 850,
        zIndex: 3,
        opacity,
        transform: 'translate3d(' + x + 'px,0,0)',
        pointerEvents: 'none',
        display: 'flex',
        alignItems: 'stretch',
        gap: isShorts ? 18 : 15,
        filter: 'drop-shadow(0 5px 12px rgba(0,0,0,0.85))',
      }}
    >
      <div
        style={{
          width: 5,
          minHeight: isShorts ? 56 : 40,
          borderRadius: 8,
          background: 'linear-gradient(180deg, #fff3c6, #d9a849)',
          transform: 'scaleY(' + rule + ')',
          transformOrigin: 'top',
        }}
      />
      <div
        style={{
          fontFamily,
          fontSize: isShorts ? 46 : 37,
          lineHeight: 1.25,
          fontWeight: 800,
          maxWidth: isShorts ? 720 : 770,
          color: '#FFF7E7',
          padding: '5px 14px 7px 8px',
          background: 'linear-gradient(90deg, rgba(8,9,14,0.7), rgba(8,9,14,0.05))',
          WebkitTextStroke: '0.35px rgba(0,0,0,0.3)',
        }}
      >
        {label}
      </div>
    </div>
  );
};
