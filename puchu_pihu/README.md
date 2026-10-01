# Puchu & Pihu daily cartoon stories

Primary Make scenario 7709916 runs daily at 07:00 Asia/Kolkata. Gemini writes an original Hindi long story and a complete Short using episode history. GitHub Actions generates Hindi voices, subtitles, 1280x720 and 1080x1920 videos, a thumbnail and upload metadata. Canva finishing and a downloadable manual upload package follow. No social publishing is performed.

The fixed human cartoon characters are Puchu (blue hoodie) and Pihu (pink dress, twin ponytails). Six reusable AI-generated 3D-style illustrations are stored in cartoon_atlas.b64; the renderer composes them with gentle camera zooms. This is illustrated video, not full 3D character motion or lip synchronization. Daily episodes reuse these artwork scenes and must match their actions.

The main and office workflows are separate. This workflow lives on branch puchu-pihu-manual. Previous flat-art production passed content/media checks; the cartoon upgrade must be checked in its own workflow run.
