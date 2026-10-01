"""Upload completed files to Canva for optional manual finishing."""
import json
import os
from pathlib import Path
from canva_bridge import upload, create_design

out = Path('puchu-output')
report = {'assets': [], 'designs': [], 'warnings': []}
token = os.getenv('CANVA_ACCESS_TOKEN', '')
if token:
    for name in ['thumbnail.jpg', 'long_story.mp4', 'short_reel.mp4']:
        try:
            asset = upload(out / name, token, f'Puchu Pihu {os.getenv("GITHUB_RUN_ID", "")} {name}', 600)
            report['assets'].append({'file': name, 'id': asset.get('id')})
            if name == 'thumbnail.jpg':
                report['designs'].append(create_design(token, asset['id'], 'Puchu & Pihu — shared thumbnail', 1280, 720))
        except Exception as exc:
            report['warnings'].append(f'{name}: {type(exc).__name__}')
else:
    report['warnings'].append('Canva access unavailable; download the package and import videos into Canva manually.')
(out / 'canva_assets.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
notes = ['# Canva finishing', '', 'The MP4 files are finished animations. You can import them into Canva to polish, then export for manual upload.', '']
notes += [f'- Shared thumbnail: {d.get("edit_url")}' for d in report['designs']]
notes += [f'- {w}' for w in report['warnings']]
(out / 'canva_notes.md').write_text('\n'.join(notes), encoding='utf-8')
