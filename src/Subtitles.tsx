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
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  if (!text) return null;

  // Progressive, word-timed captions (with a karaoke-style highlight on the
  // word currently being spoken) when word-level timing was captured during
  // TTS synthesis - see generate_clean_audio() in generate_assets.py, which
  // has captured this timing all along but it was never wired up on the
  // frontend. Falls back to the old static full-sentence caption when
  // `words` wasn't provided (an older props.json, or a TTS attempt that
  // couldn't capture WordBoundary events) so nothing ever breaks over it.
  // The reason this matters more now than it used to: scenes commonly run
  // 35-55 seconds after the 10-15 minute duration change, and showing the
  // ENTIRE scene's narration as one static paragraph for that whole time is
  // both a wall of text to read at once and completely out of sync with
  // what's actually being said at any given moment.
  const chunks = words && words.length > 0 ? groupWordsIntoChunks(words) : [];

  let activeChunk: WordTiming[] | null = null;
  if (chunks.length > 0) {
    activeChunk = chunks[0];
    for (const chunk of chunks) {
      if (chunk[0].start <= currentTime) {
        activeChunk = chunk;
      } else {
        break;
      }
    }
  }

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
          {activeChunk
            ? activeChunk.map((w, i) => {
                const spoken = w.start <= currentTime;
                return (
                  <span
                    key={i}
                    style={{
                      color: spoken ? '#FFEAA7' : 'rgba(255, 234, 167, 0.45)',
                      textShadow: spoken
                        ? '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)'
                        : '0 2px 8px rgba(0,0,0,0.9)',
                    }}
                  >
                    {w.word}
                    {i < activeChunk!.length - 1 ? ' ' : ''}
                  </span>
                );
              })
            : (
                <span
                  style={{
                    color: '#FFEAA7',
                    textShadow: '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)',
                  }}
                >
                  {text}
                </span>
              )}
        </p>
      </div>
    </AbsoluteFill>
  );
};
