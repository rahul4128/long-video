export interface WordTiming {
  word: string;
  start: number;
  end: number;
}

export interface Shot {
  type: 'video' | 'image';
  file: string;
  transition?: 'crossfade' | 'blur_cut' | 'cut';
}

export interface AnimationPlan {
  type:
    | 'slow_push'
    | 'slow_pull'
    | 'pan_left'
    | 'pan_right'
    | 'parallax'
    | 'reveal'
    | 'map_reveal'
    | 'fact_callout'
    | 'climax_push'
    | 'none';
  intensity?: number;
  direction?: 'left' | 'right' | 'up' | 'down' | 'forward' | 'backward';
  particles?: boolean;
  lightRays?: boolean;
  vignette?: number;
  cameraShake?: number;
  overlay?: 'none' | 'fact' | 'location' | 'timeline';
  transition?: 'crossfade' | 'blur_cut' | 'cut';
}

export interface VoiceDirection {
  emotion?: string;
  energy?: number;
  pace?: number;
  pauseBefore?: number;
  pauseAfter?: number;
  emphasis?: string[];
}

export interface DirectorPlan {
  camera?: 'slow_push' | 'pan_left' | 'pan_right' | 'zoom_in';
  mood?: string;
  transition?: 'crossfade' | 'blur_cut' | 'cut';
  emphasis?: 'climax' | 'normal';
  visual_priority?: string[];
  director_version?: number;
  entertainmentBeat?: 'hook' | 'climax' | 'reveal' | 'action' | 'curiosity' | 'establish' | 'divine';
  patternBreak?: boolean;
  animation?: AnimationPlan;
  voiceDirection?: VoiceDirection;
  audioBeat?: string;
  effectReason?: string;
  transitionReason?: string;
  emotion?: string;
  prosody?: Record<string, unknown>;
}

export interface SceneItem {
  scene_number: number;
  durationInSeconds: number;
  narration_chunk: string;
  shots?: Shot[];
  imageFileName?: string | string[];
  soundEffect?: 'temple_bell' | 'shankh' | 'om_drone' | 'flute_swell' | 'none';
  visualEntities?: string[];
  visualAttributes?: string[];
  visualStrict?: boolean;
  words?: WordTiming[];
  director?: DirectorPlan;
  entertainmentBeat?: string;
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
  bgmSwellSceneNumbers?: number[];
}
