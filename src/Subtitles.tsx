import React from 'react';
import { AbsoluteFill } from 'remotion';

interface SubtitlesProps {
  text: string;
}

export const Subtitles: React.FC<SubtitlesProps> = ({ text }) => {
  if (!text) return null;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: 70,
        paddingLeft: 80,
        paddingRight: 80,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(15, 10, 5, 0.75)',
          backdropFilter: 'blur(8px)',
          border: '1.5px solid rgba(255, 215, 0, 0.4)',
          borderRadius: 16,
          padding: '16px 36px',
          maxWidth: '88%',
          textAlign: 'center',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.85)',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 36,
            fontFamily: `'Noto Sans Devanagari', 'Poppins', sans-serif`,
            fontWeight: 700,
            color: '#FFEAA7',
            lineHeight: 1.45,
            textShadow: '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)',
          }}
        >
          {text}
        </p>
      </div>
    </AbsoluteFill>
  );
};
