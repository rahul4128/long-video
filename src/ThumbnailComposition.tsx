import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const { fontFamily } = loadFont();

export interface ThumbnailProps {
  backgroundImage: string;
  hookText: string;
  textPosition?: string;
}

// Renders the final YouTube thumbnail: the AI-generated background image
// (already produced by generate_ai_image() in generate_assets.py) plus a
// bold Hindi hook-text overlay - the single biggest CTR lever most
// successful channels use that this pipeline was missing entirely.
//
// This is deliberately rendered through Remotion/Chromium (via `npx remotion
// still`, see .github/workflows/render.yml) rather than stamped on with a
// plain image-editing library. Devanagari text needs real script shaping
// (conjuncts, matra reordering) to display correctly, and a naive
// draw-text-on-image approach is likely to render it garbled - Chromium's
// text layout already handles this correctly (it's the same reason
// Subtitles.tsx's captions render properly), so reusing it here is the safe
// choice instead of a second, untested text-rendering path.
export const ThumbnailComposition: React.FC<ThumbnailProps> = ({
  backgroundImage,
  hookText,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      <Img
        src={staticFile(`images/${backgroundImage}`)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      {/* Subtle adaptive vignette; text is not forced to the bottom. */}
      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse at center, rgba(0,0,0,0) 38%, rgba(0,0,0,0.34) 100%)',
        }}
      />

      {hookText && (
        <AbsoluteFill
          style={{
            ...placement,
            padding: 48,
          }}
        >
          <div style={{ maxWidth: '58%', textAlign: placement.textAlign as React.CSSProperties['textAlign'] }}>
            <span
              style={{
                fontFamily,
                fontWeight: 900,
                fontSize: 92,
                lineHeight: 1.15,
                color: '#FFFFFF',
                WebkitTextStroke: '3px rgba(0,0,0,0.9)',
                textShadow:
                  '0 6px 18px rgba(0,0,0,0.95), 0 0 40px rgba(255,180,0,0.35)',
              }}
            >
              {hookText}
            </span>
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
