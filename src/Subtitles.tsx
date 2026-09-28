import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';
import { WordTiming } from './types';

const { fontFamily } = loadFont();

interface SubtitlesProps {
  text: string;
  words?: WordTiming[];
  format?: 'long' | 'shorts';
}

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

export const Subtitles: React.FC<SubtitlesProps> = ({
  text,
  words,
  format = 'long',
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const currentTime = frame / fps;

  if (!text) return null;

  const fallbackWords: WordTiming[] = !words || words.length === 0
    ? (text.match(/[^\s]+/g) || []).map((word, i, all) => ({
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

  // Shorts captions used to snap instantly from one phrase to the next.
  // Give each phrase a very short eased settle so the typography feels
  // intentional without creating distracting karaoke-style movement.
  const chunkStart = activeChunk?.[0]?.start ?? 0;
  const chunkAgeFrames = Math.max(0, frame - Math.round(chunkStart * fps));
  const isShorts = format === 'shorts';
  const enter = isShorts
    ? interpolate(chunkAgeFrames, [0, 5], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      })
    : 1;
  const translateY = isShorts ? interpolate(enter, [0, 1], [12, 0]) : 0;
  const scale = isShorts ? interpolate(enter, [0, 1], [0.985, 1]) : 1;
  const captionOpacity = isShorts ? interpolate(enter, [0, 1], [0.45, 1]) : 1;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: isShorts ? 105 : 70,
        paddingLeft: isShorts ? 42 : 80,
        paddingRight: isShorts ? 42 : 80,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(15, 10, 5, 0.75)',
          backdropFilter: 'blur(8px)',
          border: '1.5px solid rgba(255, 215, 0, 0.4)',
          borderRadius: isShorts ? 20 : 16,
          padding: isShorts ? '18px 28px' : '16px 36px',
          maxWidth: isShorts ? '91%' : '88%',
          textAlign: 'center',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.85)',
          transform: `translateY(${translateY}px) scale(${scale})`,
          opacity: captionOpacity,
          willChange: 'transform, opacity',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: isShorts ? 43 : 36,
            fontFamily,
            fontWeight: 700,
            lineHeight: isShorts ? 1.38 : 1.45,
          }}
        >
          <span
            style={{
              color: '#FFEAA7',
              textShadow: '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)',
              display: 'inline-block',
            }}
          >
            {captionText}
          </span>
        </p>
      </div>
    </AbsoluteFill>
  );
};
