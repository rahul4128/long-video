import React from 'react';
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';
import { VisualBeat, WordTiming } from './types';

const { fontFamily } = loadFont();

interface SubtitlesProps {
  text: string;
  words?: WordTiming[];
  visualBeats?: VisualBeat[];
  format?: 'long' | 'shorts';
  sceneDurationInFrames?: number;
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
      (currentChars + wordLen > MAX_CHUNK_CHARS ||
        current.length >= MAX_CHUNK_WORDS)
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
  visualBeats = [],
  format = 'long',
  sceneDurationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const fallbackDurationInFrames = sceneDurationInFrames || durationInFrames;
  const currentTime = frame / fps;

  if (!text) return null;

  const fallbackWords: WordTiming[] =
    !words || words.length === 0
      ? (text.match(/[^\s]+/g) || []).map((word, i, all) => ({
          word,
          start:
            (i / Math.max(1, all.length)) *
            (fallbackDurationInFrames / fps),
          end:
            ((i + 1) / Math.max(1, all.length)) *
            (fallbackDurationInFrames / fps),
        }))
      : [];

  const effectiveWords = words && words.length > 0 ? words : fallbackWords;
  const chunks =
    effectiveWords.length > 0 ? groupWordsIntoChunks(effectiveWords) : [];

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
  const captionOpacity = isShorts
    ? interpolate(enter, [0, 1], [0.45, 1])
    : 1;

  // Phase 6: one short editorial phrase for selected reveal/climax/action
  // beats. Normal subtitles stay on screen; this is a brief emphasis layer,
  // not a second caption system.
  const emphasisBeat = visualBeats.find((beat) => {
    if (
      !beat.emphasisText ||
      typeof beat.actualStartSeconds !== 'number'
    ) {
      return false;
    }

    const duration = Math.max(
      0.8,
      beat.emphasisDurationSeconds ?? (isShorts ? 1.45 : 1.7),
    );
    const end = Math.min(
      typeof beat.actualEndSeconds === 'number'
        ? beat.actualEndSeconds
        : beat.actualStartSeconds + duration,
      beat.actualStartSeconds + duration,
    );

    return currentTime >= beat.actualStartSeconds && currentTime <= end;
  });

  let emphasisNode: React.ReactNode = null;
  if (emphasisBeat && typeof emphasisBeat.actualStartSeconds === 'number') {
    const startFrame = Math.round(emphasisBeat.actualStartSeconds * fps);
    const ageFrames = Math.max(0, frame - startFrame);
    const durationSeconds = Math.max(
      0.8,
      emphasisBeat.emphasisDurationSeconds ?? (isShorts ? 1.45 : 1.7),
    );
    const totalFrames = Math.max(12, Math.round(durationSeconds * fps));

    const settle = spring({
      frame: ageFrames,
      fps,
      config: {
        damping: 18,
        stiffness: 145,
        mass: 0.8,
      },
      durationInFrames: Math.min(totalFrames, Math.round(fps * 0.6)),
    });

    const emphasisScale = interpolate(settle, [0, 1], [0.94, 1]);
    const emphasisY = interpolate(settle, [0, 1], [18, 0]);
    const fadeIn = interpolate(ageFrames, [0, 5], [0, 1], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });
    const fadeOut = interpolate(
      ageFrames,
      [Math.max(6, totalFrames - 7), totalFrames],
      [1, 0],
      {
        extrapolateLeft: 'clamp',
        extrapolateRight: 'clamp',
      },
    );
    const emphasisOpacity = Math.min(fadeIn, fadeOut);

    const isClimax = emphasisBeat.emphasisStyle === 'climax';
    const isAction = emphasisBeat.emphasisStyle === 'action';

    emphasisNode = (
      <AbsoluteFill
        style={{
          justifyContent: 'flex-start',
          alignItems: 'center',
          paddingTop: isShorts ? 330 : 130,
          paddingLeft: isShorts ? 62 : 150,
          paddingRight: isShorts ? 62 : 150,
          pointerEvents: 'none',
          opacity: emphasisOpacity,
        }}
      >
        <div
          style={{
            transform: `translateY(${emphasisY}px) scale(${emphasisScale})`,
            maxWidth: isShorts ? '88%' : '74%',
            textAlign: 'center',
            willChange: 'transform, opacity',
          }}
        >
          <div
            style={{
              display: 'inline-block',
              padding: isShorts ? '11px 22px 13px' : '10px 24px 12px',
              borderRadius: 18,
              background: 'rgba(8, 7, 5, 0.72)',
              border: isClimax
                ? '1px solid rgba(255, 213, 74, 0.72)'
                : '1px solid rgba(255,255,255,0.24)',
              boxShadow: '0 10px 34px rgba(0,0,0,0.48)',
            }}
          >
            <span
              style={{
                fontFamily,
                fontWeight: isClimax ? 900 : 800,
                fontSize: isShorts ? 58 : 48,
                lineHeight: 1.2,
                letterSpacing: isAction ? '0.01em' : '0',
                color: isClimax ? '#FFD95A' : '#FFF3CF',
                WebkitTextStroke: '1px rgba(0,0,0,0.55)',
                textShadow: '0 4px 16px rgba(0,0,0,0.85)',
              }}
            >
              {emphasisBeat.emphasisText}
            </span>
          </div>

          <div
            style={{
              height: 3,
              width: isShorts ? 90 : 110,
              margin: '8px auto 0',
              borderRadius: 999,
              background: 'rgba(255, 213, 74, 0.78)',
              transform: `scaleX(${settle})`,
              transformOrigin: 'center',
            }}
          />
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <>
      {emphasisNode}

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
            backgroundColor: 'rgba(15, 10, 5, 0.82)',
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
                textShadow:
                  '0 2px 8px rgba(0,0,0,0.9), 0 0 15px rgba(255,180,0,0.3)',
                display: 'inline-block',
              }}
            >
              {captionText}
            </span>
          </p>
        </div>
      </AbsoluteFill>
    </>
  );
};
