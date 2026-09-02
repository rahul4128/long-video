import { Composition } from "remotion";
import { DevotionalComposition, DevotionalProps } from "./DevotionalComposition";
import { DevotionalShortsComposition, DevotionalShortsProps } from "./DevotionalShortsComposition";

const defaultProps: DevotionalProps = {
  audioUrl: "audio/narration.mp3",
  captions: [],
  scenes: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Long Video (16:9 - 1920x1080) */}
      <Composition
        id="DevotionalComposition"
        component={DevotionalComposition}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
        calculateMetadata={({ props }) => {
          const totalDuration = props.scenes?.reduce(
            (acc, s) => acc + (s.durationInFrames || 120),
            0
          ) || 300;
          return {
            durationInFrames: totalDuration,
          };
        }}
      />

      {/* Shorts Video (9:16 - 1080x1920) */}
      <Composition
        id="DevotionalShortsComposition"
        component={DevotionalShortsComposition}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={defaultProps as DevotionalShortsProps}
        calculateMetadata={({ props }) => {
          const totalDuration = props.scenes?.reduce(
            (acc, s) => acc + (s.durationInFrames || 120),
            0
          ) || 300;
          return {
            durationInFrames: totalDuration,
          };
        }}
      />
    </>
  );
};
