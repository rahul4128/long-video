import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';
import { WordTiming } from './types';

const { fontFamily } = loadFont();

interface SubtitlesProps {
  text: string;
  words?: WordTiming[];
}

// Keeps each on-screen caption chunk short enough to read at a glance -
// roughly matches the phrase-by-phrase style used by high-retention
// Shorts/Reels captions, rather than one long sentence sitting on screen.
const MAX_CHUNK_CHARS = 38;
const MAX_CHUNK_WORDS = 7;

function groupWordsIntoChunks(words: WordTiming[]): WordTiming[][] {
  const chunks: WordTiming[][] = [];
  let current: WordTiming[] = [];
  let currentChars = 0;

  for (const w of words) {
    const wordLen = (w.word || '').length + 1;
    if (
      current.length > 0 &&
      (currentChars + wordLen > MAX_CHUNK_CHARS || current.length >= MAX_CHUNK_WORDS)
    ) {
      chunks.push(current);
      current = [];
      currentChars = 0;
    }
    current.push(w);
    currentChars += wordLen;
  }
  if (current.length > 0) {
    chunks.push(current);
  }
  return chunks;
}

export const Subtitles: React.FC<SubtitlesProps> = ({ text, words }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const currentTime = frame / fps;

  if (!text) return null;

  // Show one short narration phrase at a time. The active phrase is fully
  // readable instead of revealing individual words, which keeps the long-form
  // video cinematic and avoids a karaoke/full-paragraph look.
  const fallbackWords: WordTiming[] = !words || words.length === 0
    ? (text.match(/[^\\s]+/g) || []).map((word, i, all) => ({
        word,
        start: (i / Math.max(1, all.length)) * (durationInFrames / fps),
        end: ((i + 1) / Math.max(1, all.length)) * (durationInFrames / fps),
      }))
    : [];

  const effectiveWords = words && words.length > 0 ? words : fallbackWords;
  const chunks = effectiveWords.length > 0 ? groupWordsIntoChunks(effectiveWords) : [];

  let activeChunk: WordTiming[] | null = null;
  if (chunks.length > 0) {
    for (const chunk of chunks) {
      if (chunk[0].start <= currentTime) {
        activeChunk = chunk;
      } else {
        break;
      }
    }
  }

  const captionText = activeChunk
    ? activeChunk.map((w) => w.word).join(' ')
    : text;


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
            fontFamily,
            fontWeight: 700,
            lineHeight: 1.45,
          }}
        >
          <span
            style={{
              color: '#FFEAA7',
              textShadow: '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)',
              display: 'inline-block',
              opacity: activeChunk ? 1 : 0.9,
            }}
          >
            {captionText}
          </span>
        </p>
      </div>
    </AbsoluteFill>
  );
};
