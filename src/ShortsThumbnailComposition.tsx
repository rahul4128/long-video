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
  textPosition = 'centerRight',
}) => {
  const positionStyles: Record<string, React.CSSProperties> = {
    topLeft: { top: 70, left: 36, right: 'auto', bottom: 'auto', alignItems: 'flex-start', justifyContent: 'flex-start', textAlign: 'left' },
    topRight: { top: 70, left: 'auto', right: 36, bottom: 'auto', alignItems: 'flex-end', justifyContent: 'flex-start', textAlign: 'right' },
    centerLeft: { top: 0, left: 36, right: 'auto', bottom: 0, alignItems: 'flex-start', justifyContent: 'center', textAlign: 'left' },
    centerRight: { top: 0, left: 'auto', right: 36, bottom: 0, alignItems: 'flex-end', justifyContent: 'center', textAlign: 'right' },
    bottomLeft: { top: 'auto', left: 36, right: 'auto', bottom: 70, alignItems: 'flex-start', justifyContent: 'flex-end', textAlign: 'left' },
    bottomRight: { top: 'auto', left: 'auto', right: 36, bottom: 70, alignItems: 'flex-end', justifyContent: 'flex-end', textAlign: 'right' },
    center: { top: 0, left: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center', textAlign: 'center' },
  };
  const placement = positionStyles[textPosition] || positionStyles.centerRight;
  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      <Img
        src={staticFile(`images/${backgroundImage}`)}
        style={{ width: '100%', height: '100%', objectFit: 'cover' }}
      />

      <AbsoluteFill
        style={{
          background:
            'radial-gradient(ellipse at center, rgba(0,0,0,0) 34%, rgba(0,0,0,0.38) 100%)',
        }}
      />

      {hookText && (
        <AbsoluteFill
          style={{
            ...placement,
            padding: 34,
          }}
        >
          <div style={{ maxWidth: '72%', textAlign: placement.textAlign as React.CSSProperties['textAlign'] }}>
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
