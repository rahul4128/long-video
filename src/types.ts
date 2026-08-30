export interface SceneItem {
  scene_number: number;
  durationInSeconds: number;
  narration_chunk: string;
  imageFileName: string;
  soundEffect?: 'temple_bell' | 'shankh' | 'om_drone' | 'flute_swell' | 'none';
}

export interface SEOMetadata {
  long_video_title: string;
  shorts_title: string;
  description: string;
  tags: string[];
  pinned_comment: string;
}

export interface DevotionalVideoProps {
  title: string;
  scenes: SceneItem[];
  fps: number;
  seo_metadata?: SEOMetadata;
}
