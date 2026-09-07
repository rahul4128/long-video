export interface WordTiming {
  word: string;
  start: number;
  end: number;
}

// One sub-shot inside a scene. A scene now carries an ORDERED LIST of shots
// (video clips and/or AI images, freely mixed) that together are sized by
// generate_assets.py to cover the scene's full spoken duration - this is the
// actual fix for "stock clip ends, freezes, narration keeps going": instead
// of handing Scene.tsx one video clip and hoping it happens to be long
// enough, generate_assets.py now fetches as many clips as needed (topping up
// with AI-image sub-shots when real footage runs out) so there is always
// enough real screen time, see fetch_video_shots_for_duration() and
// process_long_scene_visual()/process_shorts_scene_visual().
export interface Shot {
  type: 'video' | 'image';
  file: string;
  // Optional per-shot transition style for the CUT INTO this shot (ignored
  // for the first shot in a scene, which only cross-dissolves in from the
  // previous scene). Scene.tsx alternates crossfade/blur_cut by shot index
  // when this isn't provided, so older props.json files still render fine.
  transition?: 'crossfade' | 'blur_cut';
}

export interface SceneItem {
  scene_number: number;
  durationInSeconds: number;
  narration_chunk: string;
  // Preferred: an ordered list of video/image sub-shots covering the scene's
  // full duration - see the Shot interface above. When absent, Scene.tsx
  // falls back to the legacy single-asset fields below so an older
  // props.json (or a manual test payload) still renders correctly.
  shots?: Shot[];
  // LEGACY (pre-multi-shot-video) fields: a single filename for a video clip
  // (.mp4) or a lone static image, OR an array of image filenames for a
  // multi-shot slideshow. Still written by generate_assets.py for backward
  // compatibility/debugging, but `shots` above is authoritative whenever
  // present.
  imageFileName?: string | string[];
  soundEffect?: 'temple_bell' | 'shankh' | 'om_drone' | 'flute_swell' | 'none';
  // Word-level caption timing captured during TTS synthesis (see
  // generate_clean_audio() in generate_assets.py) - drives the progressive,
  // karaoke-style captions in Subtitles.tsx. Optional so older props.json
  // files (or a TTS attempt that couldn't capture WordBoundary events)
  // still render fine with the static full-sentence fallback. This is
  // ALREADY fully dynamic per day's unique narration - nothing about
  // Subtitles.tsx is hardcoded text; see the comment on `words` usage there.
  words?: WordTiming[];
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
  // 1-based scene_number(s) marking the story's "revelation"/climax beat(s).
  // DevotionalComposition.tsx swells the background-music volume for a
  // couple of seconds around these scenes instead of leaving bgm flat at the
  // same low volume for the entire video - a cheap, high-impact touch that
  // makes the pacing feel directed rather than uniformly generated. Absent
  // or empty is fine (no swell, same as before).
  bgmSwellSceneNumbers?: number[];
}
