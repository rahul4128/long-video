import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  Series,
} from "remotion";

export interface SceneItem {
  id: number;
  type: "video" | "image";
  src: string;
  durationInFrames: number;
}

export interface CaptionWord {
  text: string;
  startMs: number;
  endMs: number;
}

export interface DevotionalShortsProps {
  audioUrl: string;
  captions: CaptionWord[];
  scenes: SceneItem[];
}

export const DevotionalShortsComposition: React.FC<DevotionalShortsProps> = ({
  audioUrl = "audio/narration.mp3",
  captions = [],
  scenes = [],
}) => {
  const frame = useCurrentFrame();
  const currentMs = (frame / 30) * 1000;

  // Active subtitle word
  const activeWord = captions.find(
    (c) => currentMs >= c.startMs && currentMs <= c.endMs
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* 1. Scenes Sequence (9:16 Vertical Cropping) */}
      <Series>
        {scenes.map((scene) => (
          <Series.Sequence
            key={scene.id}
            durationInFrames={scene.durationInFrames || 120}
          >
            <ShortsSceneRenderer scene={scene} />
          </Series.Sequence>
        ))}
      </Series>

      {/* 2. Audio Track */}
      {audioUrl && <Audio src={staticFile(audioUrl)} />}

      {/* 3. YouTube Shorts Center-High Subtitles (Keeps clear of UI icons) */}
      {activeWord && (
        <AbsoluteFill
          style={{
            justifyContent: "center",
            alignItems: "center",
            paddingTop: 180, // Sits above YouTube Shorts like/comment buttons
          }}
        >
          <div
            style={{
              fontFamily: "Noto Sans Devanagari, sans-serif",
              fontSize: 64,
              fontWeight: 900,
              color: "#FFF4D2",
              textShadow: "0 0 20px rgba(0,0,0,0.95), 0 0 35px #D4AF37",
              textAlign: "center",
              padding: "12px 30px",
              maxWidth: "85%",
              lineHeight: 1.3,
            }}
          >
            {activeWord.text}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

const ShortsSceneRenderer: React.FC<{ scene: SceneItem }> = ({ scene }) => {
  const frame = useCurrentFrame();

  // Subtle zoom to keep static images dynamic in vertical format
  const scale = interpolate(frame, [0, 120], [1.02, 1.15], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        filter: "contrast(1.1) saturate(1.2) sepia(0.06)",
      }}
    >
      {scene.type === "video" ? (
        <OffthreadVideo
          src={staticFile(scene.src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      ) : (
        <Img
          src={staticFile(scene.src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${scale})`,
          }}
        />
      )}

      {/* Vertical vignette to highlight center content */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle, transparent 40%, rgba(0, 0, 0, 0.6) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
