export interface SceneItem {
  scene_number: number;
  durationInSeconds: number;
  narration_chunk: string;
  imageFileName: string;
}

export interface DevotionalVideoProps {
  title: string;
  scenes: SceneItem[];
  fps: number;
}
