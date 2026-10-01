# Puchu & Pihu animated character stories

Primary Make scenario 7709916 creates one Hindi long story and one Short daily at 07:00 Asia/Kolkata. Social publishing remains manual. Main and office branches are separate.

Characters have a softly shaded 3D cartoon appearance, animated as 2D sprites at 24 fps. The renderer switches walking steps, blinks, mouth and speaking gestures, sulking and caring poses, and moves props between characters. Mouth movement follows the actual active speaker's audio energy. It is approximate speech animation, not phoneme-perfect lip synchronization or full 3D skeletal animation. This replaces the previous static illustration zooms.

Reusable AI-generated transparent character/prop atlases and empty scene backgrounds are stored as WebP base64 text in motion_characters.b64, motion_props.b64 and motion_backgrounds.b64. The built-in image-generation tool made the assets; no paid daily image/video generation API is required. Kokoro supplies Hindi voices on CPU. Text generation remains Gemini and is subject to the existing account limits.

Motion integration test uses a fixed story fixture and generates both full formats without Gemini calls. motion_qc.json checks transparency and distinct blink, speech, walking and sulking states before narration. media_qc.json checks measured duration, audio and dimensions. Canva finishing follows the regular daily workflow; final upload is manual.
