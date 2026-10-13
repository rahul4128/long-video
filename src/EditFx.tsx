import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

/**
 * Lightweight selective editorial effects — CPU-friendly CSS only.
 * Applied solely when a narration beat warrants focus or an impact cut.
 * Never continuously flashes or obscures central devotional subjects.
 */
export const EditFx: React.FC<{
  spotlight?: boolean;
  snap?: boolean;
  flash?: boolean;
  format: 'long' | 'shorts';
}> = ({ spotlight = false, snap = false, flash = false, format }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const short = format === 'shorts';

  const intro = interpolate(frame, [0, Math.max(5, Math.round(fps * 0.2))], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  // Emphasize the main subject without face recognition or unrelated blur.
  const blurStrength = spotlight ? 1.5 * intro : 0;
  const glow = flash
    ? interpolate(frame, [0, 2, 6, 9], [0.10, 0.16, 0.055, 0], {
        extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
      })
    : snap
      ? interpolate(frame, [0, 5, 12], [0.11, 0.045, 0], {
          extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
        })
      : 0;

  return (
    <>
      {spotlight && (
        <AbsoluteFill
          style={{
            pointerEvents: 'none',
            zIndex: 2,
            backdropFilter: 'blur(' + blurStrength + 'px)',
            WebkitBackdropFilter: 'blur(' + blurStrength + 'px)',
            maskImage: 'radial-gradient(ellipse 44% 41% at 50% 44%, transparent 0%, transparent 66%, black 99%)',
            WebkitMaskImage: 'radial-gradient(ellipse 44% 41% at 50% 44%, transparent 0%, transparent 66%, black 99%)',
          }}
        />
      )}
      {(flash || snap) && glow > 0 && (
        <AbsoluteFill
          style={{
            pointerEvents: 'none',
            zIndex: 2,
            background: short
              ? 'radial-gradient(ellipse at 50% 42%, rgba(255,239,187,0.85), transparent 70%)'
              : 'linear-gradient(95deg, transparent 5%, rgba(255,240,200,0.64) 48%, transparent 90%)',
            opacity: glow,
          }}
        />
      )}
    </>
  );
};
