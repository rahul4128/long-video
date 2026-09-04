export interface SceneItem {
  scene_number: number;
  durationInSeconds: number;
  narration_chunk: string;
  // A single filename for a video clip (.mp4) or a lone static image, OR an
  // array of image filenames for a multi-shot slideshow (see
  // generate_multi_shot_ai_images() in generate_assets.py + Scene.tsx) -
  // used when a scene falls back to AI-generated stills instead of real
  // stock video, so a long scene isn't held on one static frame the whole
  // time.
  imageFileName: string | string[];
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
