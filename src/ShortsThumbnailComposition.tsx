import React from 'react';
import { AbsoluteFill, Img, staticFile } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';
import { ThumbnailProps } from './ThumbnailComposition';

const { fontFamily } = loadFont();

// Vertical (9:16) counterpart to ThumbnailComposition.tsx, for the Shorts
// upload. Previously Shorts either reused the long-video 16:9 thumbnail or
// got no custom thumbnail at all once uploaded - this renders its OWN
// background image (a separate generate_ai_image() call in
// generate_assets.py, from the Make.com prompt's new `shorts_thumbnail`
// field) with its own bold Hindi hook-text overlay, distinct from both the
// long-video thumbnail and the shorts_title itself, so the Shorts feed and
// channel page get a genuinely unique, high-CTR image instead of a
// stretched/cropped 16:9 one.
//
// Reuses the exact same ThumbnailProps shape (backgroundImage + hookText) -
// only the canvas size and text sizing differ, since a 1080-wide vertical
// frame needs smaller/differently-placed text than a 1920-wide one.
export const ShortsThumbnailComposition: React.FC<ThumbnailProps> = ({
  backgroundImage,
  hookText,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      <Img
        src={staticFile(`images/${backgroundImage}`)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      <AbsoluteFill
        style={{
          background:
            'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.55) 34%, rgba(0,0,0,0) 62%)',
        }}
      />

      {hookText && (
        <AbsoluteFill
          style={{
            justifyContent: 'flex-end',
            alignItems: 'center',
            paddingBottom: 90,
            paddingLeft: 48,
            paddingRight: 48,
          }}
        >
          <div style={{ maxWidth: '96%', textAlign: 'center' }}>
            <span
              style={{
                fontFamily,
                fontWeight: 900,
                fontSize: 76,
                lineHeight: 1.18,
                color: '#FFFFFF',
                WebkitTextStroke: '2.5px rgba(0,0,0,0.9)',
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
