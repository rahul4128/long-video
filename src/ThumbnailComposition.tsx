import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const { fontFamily } = loadFont();

export interface ThumbnailProps {
  backgroundImage: string;
  hookText: string;
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

      {/* Darkening gradient behind the text band so bold hook text stays
          readable over any background image, without hiding the whole
          frame - the subject still needs to read clearly at thumbnail
          scale. */}
      <AbsoluteFill
        style={{
          background:
            'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 30%, rgba(0,0,0,0) 58%)',
        }}
      />

      {hookText && (
        <AbsoluteFill
          style={{
            justifyContent: 'flex-end',
            alignItems: 'center',
            paddingBottom: 64,
            paddingLeft: 60,
            paddingRight: 60,
          }}
        >
          <div style={{ maxWidth: '94%', textAlign: 'center' }}>
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
