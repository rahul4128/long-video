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

export interface DevotionalProps {
  audioUrl: string;
  captions: CaptionWord[];
  scenes: SceneItem[];
}

export const DevotionalComposition: React.FC<DevotionalProps> = ({
  audioUrl = "audio/narration.mp3",
  captions = [],
  scenes = [],
}) => {
  const frame = useCurrentFrame();
  const currentMs = (frame / 30) * 1000;

  const activeWord = captions.find(
    (c) => currentMs >= c.startMs && currentMs <= c.endMs
  );

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      <Series>
        {scenes.map((scene) => (
          <Series.Sequence
            key={scene.id}
            durationInFrames={scene.durationInFrames || 120}
          >
            <SceneRenderer scene={scene} />
          </Series.Sequence>
        ))}
      </Series>

      {audioUrl && <Audio src={staticFile(audioUrl)} />}

      {activeWord && (
        <AbsoluteFill
          style={{
            justifyContent: "flex-end",
            alignItems: "center",
            paddingBottom: 90,
          }}
        >
          <div
            style={{
              fontFamily: "Noto Sans Devanagari, sans-serif",
              fontSize: 54,
              fontWeight: 800,
              color: "#FFF4D2",
              textShadow: "0 0 16px rgba(0,0,0,0.9), 0 0 30px #D4AF37",
              textAlign: "center",
              padding: "8px 24px",
            }}
          >
            {activeWord.text}
          </div>
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};

const SceneRenderer: React.FC<{ scene: SceneItem }> = ({ scene }) => {
  const frame = useCurrentFrame();

  const scale = interpolate(frame, [0, 120], [1.0, 1.12], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        filter: "contrast(1.08) saturate(1.15) sepia(0.06)",
      }}
    >
      {scene.type === "video" ? (
        <OffthreadVideo
          src={staticFile(scene.src)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
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

      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle, transparent 55%, rgba(10, 5, 0, 0.45) 100%)",
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
