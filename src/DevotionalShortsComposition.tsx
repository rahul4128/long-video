import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Series,
  Sequence,
  staticFile,
  useVideoConfig,
} from 'remotion';
import { loadFont } from '@remotion/google-fonts/NotoSansDevanagari';

const { fontFamily } = loadFont();
import { DevotionalVideoProps } from './types';
import { Scene } from './Scene';
import { Subtitles } from './Subtitles';
import { HookOverlay } from './HookOverlay';

export const DevotionalShortsComposition: React.FC<DevotionalVideoProps & { platform?: 'youtube' | 'instagram' }> = ({
  scenes = [],
  hookText = '',
  platform = 'youtube',
  showSubtitles = false,
}) => {
  const { fps, durationInFrames } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: '#000000' }}>
      {/* Background Devotional Flute / Tanpura Music */}
      {/* Legacy soundtrack only for older props; new music is per scene. */}
      {!scenes.some((scene) => Boolean(scene.musicFile)) && (
        <Audio
          src={staticFile('audio/bgm.mp3')}
          volume={0.10}
          loop
        />
      )}

      {/* Sequential Shorts Scenes (Vertical 9:16) */}
      <Series>
        {scenes.map((scene, index) => {
          const sceneDurationInFrames = Math.max(
            30,
            Math.round((scene.durationInSeconds || 5) * fps)
          );
          return (
            <Series.Sequence
              key={scene.scene_number || index}
              durationInFrames={sceneDurationInFrames}
            >
              <Scene
                scene={scene}
                durationInFrames={sceneDurationInFrames}
                direction={index % 2 === 0 ? 'zoom-in' : 'pan-right'}
                format="shorts"
                // First-frame footage is visible immediately; no black intro.
                fadeIn={false}
                fadeOut={index === scenes.length - 1}
                smoothEntry={index > 0}
              />
              {showSubtitles && (
              <Subtitles
                text={scene.narration_chunk}
                words={scene.words}
                visualBeats={scene.visualBeats}
                captionStyle={scene.captionStyle || 'focus'}
                format="shorts"
                platform={platform}
                sceneDurationInFrames={sceneDurationInFrames}
              /> 
              )}
            </Series.Sequence>
          );
        })}
      </Series>

      {/* First-1.8s on-screen Hindi hook */}
      <HookOverlay text={hookText} format="shorts" platform={platform} />

      {/* A platform-specific ending, not a YouTube "Subscribe" overlay. */}
      {platform === 'instagram' && (
        <Sequence
          from={Math.max(0, durationInFrames - Math.round(fps * 1.7))}
          durationInFrames={Math.min(durationInFrames, Math.round(fps * 1.7))}
        >
          <AbsoluteFill
            style={{
              justifyContent: 'flex-start',
              alignItems: 'center',
              paddingTop: 270,
              pointerEvents: 'none',
            }}
          >
            <div
              style={{
                fontFamily,
                fontWeight: 900,
                fontSize: 52,
                color: '#FFE8A1',
                padding: '18px 30px',
                borderRadius: 22,
                background: 'rgba(18, 10, 6, 0.84)',
                textShadow: '0 4px 14px #000',
              }}
            >
              फॉलो • सेव • शेयर
            </div>
          </AbsoluteFill>
        </Sequence>
      )}
    </AbsoluteFill>
  );
};
