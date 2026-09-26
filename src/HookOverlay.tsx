import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const { fontFamily } = loadFont();

// Big Hindi hook text for the first ~1.8 s of the video. It repeats the
// thumbnail promise on screen so a viewer who just clicked sees the promise
// confirmed immediately - the first 1-2 seconds decide most swipe-aways.
export const HookOverlay: React.FC<{ text?: string; format?: 'long' | 'shorts' }> = ({
  text,
  format = 'long',
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!text) return null;

  const visibleFrames = Math.round(fps * 1.8);
  if (frame > visibleFrames) return null;

  const pop = spring({ frame, fps, config: { damping: 12, stiffness: 180 } });
  const scale = interpolate(pop, [0, 1], [0.82, 1]);
  const opacity = interpolate(
    frame,
    [0, 4, visibleFrames - 8, visibleFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' },
  );
  const isShorts = format === 'shorts';

  return (
    <AbsoluteFill
      style={{
        justifyContent: isShorts ? 'flex-start' : 'center',
        alignItems: 'center',
        paddingTop: isShorts ? 360 : 0,
        paddingLeft: 60,
        paddingRight: 60,
        opacity,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          maxWidth: isShorts ? '92%' : '80%',
          textAlign: 'center',
          background: 'rgba(0,0,0,0.45)',
          borderRadius: 24,
          padding: isShorts ? '28px 36px' : '22px 44px',
        }}
      >
        <span
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize: isShorts ? 92 : 84,
            lineHeight: 1.2,
            color: '#FFD54A',
            WebkitTextStroke: '2px rgba(0,0,0,0.9)',
            textShadow: '0 6px 18px rgba(0,0,0,0.95)',
          }}
        >
          {text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
