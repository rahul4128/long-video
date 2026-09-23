import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
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
  if (current.length > 0) chunks.push(current);
  return chunks;
}

export const Subtitles: React.FC<SubtitlesProps> = ({ text, words, format = 'long' }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const currentTime = frame / fps;
  const isShort = format === 'shorts';

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
      if (chunk[0].start <= currentTime) activeChunk = chunk;
      else break;
    }
  }

  const captionWords = activeChunk || effectiveWords;
  const activeWordIndex = captionWords.findIndex(
    (word) => currentTime >= word.start && currentTime <= word.end,
  );

  const captionText = activeChunk
    ? activeChunk.map((w) => w.word).join(' ')
    : text;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        // Deliberately high enough to clear YouTube/mobile controls and the
        // bottom edge of vertical players. The old 70px placement was too low.
        paddingBottom: isShort ? 250 : 135,
        paddingLeft: isShort ? 48 : 100,
        paddingRight: isShort ? 48 : 100,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          maxWidth: isShort ? '86%' : '82%',
          textAlign: 'center',
          padding: isShort ? '14px 22px 16px' : '12px 28px 14px',
          borderRadius: isShort ? 24 : 20,
          background:
            'linear-gradient(180deg, rgba(8,8,12,0.58) 0%, rgba(8,8,12,0.82) 100%)',
          border: '2px solid rgba(255,215,0,0.42)',
          boxShadow:
            '0 8px 30px rgba(0,0,0,0.58), 0 0 22px rgba(255,190,50,0.10)',
          backdropFilter: 'blur(10px)',
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: isShort ? 42 : 38,
            fontFamily,
            fontWeight: 800,
            lineHeight: 1.34,
            letterSpacing: '0.01em',
          }}
        >
          {activeChunk ? (
            activeChunk.map((word, index) => (
              <React.Fragment key={index}>
                {index > 0 ? ' ' : ''}
                <span
                  style={{
                    color: index === activeWordIndex ? '#FFFFFF' : '#FFEAA7',
                    backgroundColor:
                      index === activeWordIndex
                        ? 'rgba(255,190,40,0.28)'
                        : 'transparent',
                    borderRadius: 8,
                    padding: index === activeWordIndex ? '0 5px' : 0,
                    textShadow: '0 2px 8px rgba(0,0,0,0.92)',
                  }}
                >
                  {word.word}
                </span>
              </React.Fragment>
            ))
          ) : (
            <span style={{ color: '#FFEAA7', textShadow: '0 2px 8px rgba(0,0,0,0.92)' }}>
              {captionText}
            </span>
          )}
        </p>
      </div>
    </AbsoluteFill>
  );
};
