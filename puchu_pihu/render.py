"""CPU-only lovebird animation. No social publishing. Fail closed on weak scripts/audio."""
import argparse
import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).parent
OUT = Path(os.getenv('PUCHU_OUTPUT', 'puchu-output'))
FPS = 15
SR = 24000
VOICE = {'puchu': 'hm_omega', 'pihu': 'hf_alpha', 'narrator': 'hf_beta'}

def run(args, **kw):
    return subprocess.run(args, check=True, **kw)

def spoken(scene):
    lines = []
    if scene.get('narration', '').strip():
        lines.append({'speaker': 'narrator', 'text': scene['narration'], 'emotion': scene.get('emotion', 'warm')})
    lines.extend(scene.get('dialogue', []))
    return lines

def validate(p):
    errors = []
    if {c.get('id') for c in p.get('characters', [])} != {'puchu', 'pihu'}:
        errors.append('Exactly puchu and pihu character IDs are required')
    for key, limits in [('long_video', (400, 680)), ('shorts', (70, 120))]:
        scenes = p.get(key, {}).get('scenes', [])
        texts = []
        if not scenes:
            errors.append(f'{key}: no scenes')
        for scene in scenes:
            if not scene.get('setting') or not scene.get('action'):
                errors.append(f'{key}: missing setting/action')
            for line in spoken(scene):
                t = line.get('text', '').strip()
                if line.get('speaker') not in VOICE:
                    errors.append(f'{key}: unknown speaker')
                letters = re.findall(r'[A-Za-z\u0900-\u097f]', t)
                hindi = re.findall(r'[\u0900-\u097f]', t)
                if not letters or len(hindi) / len(letters) < .9:
                    errors.append(f'{key}: spoken text must be Devanagari Hindi')
                texts.append(t)
        count = len(' '.join(texts).split())
        if not limits[0] <= count <= limits[1]:
            errors.append(f'{key}: {count} spoken words, expected {limits}')
        if len(texts) != len(set(texts)):
            errors.append(f'{key}: duplicate spoken lines')
    meta = p.get('seo_metadata', {})
    for k in ['long_video_title', 'long_video_description', 'shorts_title', 'shorts_description', 'instagram_caption']:
        if not meta.get(k):
            errors.append(f'Missing {k}')
    if not p.get('thumbnail', {}).get('thumbnailText'):
        errors.append('Missing thumbnail text')
    return errors

def write_wav(path, samples):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())

def audio_timeline(p, key, pipeline):
    timeline, parts, now = [], [], 0.
    cache = OUT / 'audio-cache'; cache.mkdir(parents=True, exist_ok=True)
    for index, scene in enumerate(p[key]['scenes']):
        for line in spoken(scene):
            text = line['text'].strip(); speaker = line['speaker']
            digest = hashlib.sha256((speaker + text).encode()).hexdigest()
            path = cache / f'{digest}.npy'
            if path.exists():
                audio = np.load(path)
            else:
                chunks = []
                for result in pipeline(text, voice=VOICE[speaker], speed=1.02):
                    a = result.audio if hasattr(result, 'audio') else result[2]
                    if a is not None:
                        chunks.append(a.detach().cpu().numpy() if hasattr(a, 'detach') else np.asarray(a))
                if not chunks:
                    raise RuntimeError(f'No audio for {speaker}')
                audio = np.concatenate(chunks).astype(np.float32)
                active = np.flatnonzero(np.abs(audio) > .003)
                if not len(active):
                    raise RuntimeError('Silent TTS rejected')
                audio = audio[max(0, active[0] - 800):min(len(audio), active[-1] + 1200)]
                n = min(240, len(audio) // 2)
                audio[:n] *= np.linspace(0, 1, n); audio[-n:] *= np.linspace(1, 0, n)
                np.save(path, audio)
            duration = len(audio) / SR
            timeline.append({'start': now, 'end': now + duration, 'speaker': speaker,
                             'text': text, 'emotion': line.get('emotion', ''), 'scene': index})
            parts.extend([audio, np.zeros(int(.18 * SR), dtype=np.float32)])
            now += duration + .18
    audio = np.concatenate(parts)
    limits = (180, 300) if key == 'long_video' else (30, 60)
    duration = len(audio) / SR
    if not limits[0] <= duration <= limits[1]:
        raise RuntimeError(f'{key}: actual audio {duration:.1f}s outside {limits}. Rewrite the script; do not pad silence.')
    write_wav(OUT / f'{key}.wav', audio)
    return timeline, duration

def font(size):
    paths = ['/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
             '/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf']
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    raise RuntimeError('Install fonts-noto-core for correctly shaped Hindi')

def wrap(draw, text, f, width):
    lines, row = [], ''
    for word in text.split():
        test = (row + ' ' + word).strip()
        if row and draw.textlength(test, font=f) > width:
            lines.append(row); row = word
        else:
            row = test
    if row: lines.append(row)
    return lines

def heart(d, x, y, r, color):
    points = []
    for i in range(40):
        a = i * math.tau / 40
        points.append((x + r * math.sin(a)**3,
                       y - r * (13*math.cos(a)-5*math.cos(2*a)-2*math.cos(3*a)-math.cos(4*a))/16))
    d.polygon(points, fill=color)

def bird(d, x, y, scale, who, emotion, talking, t, facing=1):
    def box(a,b,c,e): return (x+a*scale,y+b*scale,x+c*scale,y+e*scale)
    color = '#9ad9c5' if who == 'puchu' else '#ffc2af'
    edge = '#47736b' if who == 'puchu' else '#ac716a'
    y += math.sin(t*3 + (0 if who == 'puchu' else 1))*3*scale
    d.ellipse(box(-76,111,76,131), fill='#ccb8a5')
    d.line([(x-35*scale,y+102*scale),(x-45*scale,y+121*scale)],fill='#d88b4d',width=max(2,int(7*scale)))
    d.line([(x+35*scale,y+102*scale),(x+45*scale,y+121*scale)],fill='#d88b4d',width=max(2,int(7*scale)))
    d.ellipse(box(-86,-98,86,115),fill=color,outline=edge,width=max(1,int(3*scale)))
    d.ellipse(box(-58,15,58,102),fill='#fff3da')
    wing = math.sin(t*5)*8 if talking else math.sin(t*2)*3
    d.ellipse(box(-89,-3+wing,-48,73+wing),fill=color,outline=edge,width=max(1,int(3*scale)))
    d.ellipse(box(48,-3-wing,89,73-wing),fill=color,outline=edge,width=max(1,int(3*scale)))
    d.ellipse(box(-64,-39,-33,-16),fill='#f39ba1'); d.ellipse(box(33,-39,64,-16),fill='#f39ba1')
    closed = t % 4.1 < .15
    sad = any(z in emotion.lower() for z in ['sad','sulk','hurt','angry','jealous','worried','upset'])
    for ex in [-30,30]:
        if closed:
            d.arc(box(ex-13,-66,ex+13,-40),0,180,fill='#34363d',width=max(2,int(4*scale)))
        else:
            d.ellipse(box(ex-12,-67,ex+12,-37),fill='white')
            d.ellipse(box(ex-5+facing*2,-63,ex+5+facing*2,-42),fill='#34363d')
            d.ellipse(box(ex,-61,ex+4,-55),fill='white')
        if sad:
            d.line([(x+(ex-11)*scale,y-76*scale),(x+(ex+11)*scale,y-69*scale)],fill=edge,width=max(2,int(3*scale)))
    mouth = 13 + (7*abs(math.sin(t*15)) if talking else 0)
    d.polygon([(x-15*scale,y-35*scale),(x+15*scale,y-35*scale),(x,y+(-35+mouth)*scale)],fill='#efa753')
    if who == 'puchu':
        d.polygon([(x-13*scale,y-95*scale),(x-6*scale,y-126*scale),(x+8*scale,y-101*scale),(x+20*scale,y-116*scale),(x+22*scale,y-93*scale)],fill='#69b7a8')
        d.rounded_rectangle(box(-65,0,65,19),radius=8*scale,fill='#f5cd65')
        d.polygon([(x+30*scale,y+9*scale),(x+61*scale,y+13*scale),(x+62*scale,y+63*scale),(x+36*scale,y+56*scale)],fill='#f5cd65')
    else:
        d.polygon([(x-40*scale,y-90*scale),(x-69*scale,y-109*scale),(x-69*scale,y-75*scale)],fill='#b19bdb')
        d.polygon([(x-40*scale,y-90*scale),(x-15*scale,y-109*scale),(x-11*scale,y-77*scale)],fill='#b19bdb')
        d.ellipse(box(-47,-98,-32,-83),fill='#8b79bb')

def background(w,h,scene):
    palette = scene.get('background','garden').lower()
    sky = '#fee8d9' if palette == 'sunset' else '#d4e6ee' if palette == 'rain' else '#dff3ee'
    im = Image.new('RGB',(w,h),sky); d = ImageDraw.Draw(im)
    d.ellipse((w*.72,h*.08,w*.86,h*.08+w*.14),fill='#ffe5a1')
    d.ellipse((-w*.25,h*.48,w*.85,h*1.3),fill='#c1d8b8')
    d.ellipse((w*.2,h*.5,w*1.3,h*1.4),fill='#aec9a7')
    # A consistent cozy treehouse set.
    d.rounded_rectangle((w*.06,h*.22,w*.31,h*.59),radius=18,fill='#d9b597')
    d.polygon([(w*.035,h*.24),(w*.185,h*.12),(w*.335,h*.24)],fill='#bb937e')
    d.rounded_rectangle((w*.15,h*.3,w*.25,h*.43),radius=12,fill='#ffe5bb')
    d.line((w*.20,h*.3,w*.20,h*.43),fill='#bb937e',width=5)
    d.rounded_rectangle((w*.035,h*.69,w*.965,h*.735),radius=15,fill='#ad8b72')
    for i in range(10):
        xx=(i*.113+.035)*w; yy=h*(.76+(i%3)*.03)
        d.line((xx,yy,xx,yy+h*.06),fill='#799978',width=3)
        d.ellipse((xx-7,yy-7,xx+7,yy+7),fill=['#e8b9bd','#fff0c6','#baa8d3'][i%3])
    return im

def frame(base, scene, line, t, title, thumbnail=False):
    im=base.copy(); w,h=im.size; d=ImageDraw.Draw(im)
    vertical=h>w; scale=w/(490 if vertical else 730)
    phase=scene.get('phase','setup')
    closeness= .14 if phase in ['reconcile','care','payoff'] else .20
    movement=scene.get('movement','idle')
    shift=math.sin(t*.6)*w*.025 if movement=='approach' else 0
    yy=h*(.49 if vertical else .49)
    bird(d,w*(.5-closeness)+shift,yy,scale,'puchu',line.get('emotion',''),line.get('speaker')=='puchu',t,1)
    bird(d,w*(.5+closeness)-shift,yy,scale,'pihu',line.get('emotion',''),line.get('speaker')=='pihu',t,-1)
    prop=scene.get('prop','heart')
    x=w*.5; y=yy+scale*60
    if prop=='flower':
        d.line((x,y,x,y+scale*70),fill='#70a27e',width=max(2,int(scale*4)))
        for i in range(5):
            a=i*math.tau/5; xx=x+math.cos(a)*scale*17; yy2=y+math.sin(a)*scale*17
            d.ellipse((xx-scale*15,yy2-scale*15,xx+scale*15,yy2+scale*15),fill='#efb3bd')
        d.ellipse((x-scale*11,y-scale*11,x+scale*11,y+scale*11),fill='#ffe5a1')
    elif prop in ['berry','food','tea']:
        d.ellipse((x-scale*35,y+scale*20,x+scale*35,y+scale*35),fill='#f6e6cc')
        if prop=='tea':
            d.rounded_rectangle((x-scale*20,y-scale*5,x+scale*20,y+scale*25),radius=9,fill='#bea7d6')
        else:
            for dx in [-14,12,0]:
                d.ellipse((x+(dx-10)*scale,y+(5-abs(dx))*scale,x+(dx+10)*scale,y+(25-abs(dx))*scale),fill='#cc8794')
    elif prop=='umbrella':
        d.pieslice((x-scale*120,y-scale*265,x+scale*120,y-scale*100),180,360,fill='#b7a0d6')
        d.line((x,y-scale*183,x,y),fill='#8b798e',width=max(2,int(5*scale)))
    elif prop=='blanket':
        d.rounded_rectangle((w*.25,h*.6,w*.75,h*.7),radius=25,fill='#bca8d6')
    if phase in ['care','reconcile','payoff'] or thumbnail:
        for i in range(3):
            heart(d,w*(.45+i*.05),h*.29+math.sin(t+i)*8,scale*(11+i*3),'#eaa6af')
    if scene.get('background')=='rain':
        for i in range(32):
            rx=(i*117%w); ry=((i*81+t*110)%(h*.72))
            d.line((rx,ry,rx-6,ry+18),fill='#a6bdce',width=2)
    f=font(round(w*(.045 if vertical else .030)))
    small=font(round(w*.024))
    d.text((w*.045,h*.035),'पुचू और पिहू',font=small,fill='#596e68')
    text=title if thumbnail else line.get('text','')
    rows=wrap(d,text,f,w*.83)
    # Caption pages are created before rendering; never truncate dialogue.
    lineh=int(f.size*1.65)
    y0=h*(.80 if vertical else .79)
    d.rounded_rectangle((w*.05,y0-15,w*.95,min(h*.96,y0+len(rows)*lineh+12)),radius=18,fill='#fff8ed')
    for j,row in enumerate(rows):
        d.text((w*.5,y0+j*lineh),row,font=f,fill='#3f514c',anchor='mt')
    return im

def caption_pages(text, width, vertical):
    dummy=ImageDraw.Draw(Image.new('RGB',(1,1)))
    f=font(round(width*(.045 if vertical else .030)))
    rows=wrap(dummy,text,f,width*.83)
    return [' '.join(rows[i:i+2]) for i in range(0,len(rows),2)] or ['']

def timestamp(sec):
    ms=round(sec*1000); hours,ms=divmod(ms,3600000); minutes,ms=divmod(ms,60000); seconds,ms=divmod(ms,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'

def render_video(p,key,timeline,duration,preview=False):
    w,h=(1280,720) if key=='long_video' else (1080,1920)
    if preview: w,h=(640,360) if key=='long_video' else (360,640)
    scenes=p[key]['scenes']; backgrounds=[background(w,h,s) for s in scenes]
    starts=[x['start'] for x in timeline]
    output=OUT/('long_story.mp4' if key=='long_video' else 'short_reel.mp4')
    pages=[caption_pages(x['text'],w,h>w) for x in timeline]
    srt=[]; subnum=1
    for line, chunks in zip(timeline,pages):
        step=(line['end']-line['start'])/len(chunks)
        for k,chunk in enumerate(chunks):
            srt.append(f'{subnum}\n{timestamp(line["start"]+k*step)} --> {timestamp(line["start"]+(k+1)*step)}\n{chunk}\n'); subnum+=1
    (OUT/f'{key}.srt').write_text('\n'.join(srt),encoding='utf-8')
    log=open(OUT/f'{key}-ffmpeg.log','w')
    proc=subprocess.Popen(['ffmpeg','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}',
        '-r',str(FPS),'-i','pipe:0','-i',str(OUT/f'{key}.wav'),'-c:v','libx264',
        '-preset','ultrafast','-crf','22','-threads','2','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(output)],stdin=subprocess.PIPE,stderr=log)
    try:
        for n in range(math.ceil(duration*FPS)):
            t=n/FPS; i=max(0,bisect.bisect_right(starts,t)-1); line=dict(timeline[i])
            chunks=pages[i]; progress=(t-line['start'])/max(.01,line['end']-line['start'])
            line['text']=chunks[min(len(chunks)-1,int(max(0,progress)*len(chunks)))]
            si=line['scene']
            proc.stdin.write(frame(backgrounds[si],scenes[si],line,t,p['title']).tobytes())
        proc.stdin.close()
        if proc.wait()!=0: raise RuntimeError(f'ffmpeg failed: {key}')
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        log.close()
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    streams=info['streams']; video=next(x for x in streams if x['codec_type']=='video')
    if video['width']!=w or video['height']!=h or not any(x['codec_type']=='audio' for x in streams):
        raise RuntimeError('Media QC: dimensions/audio failed')
    measured=float(info['format']['duration'])
    if abs(measured-duration)>.5: raise RuntimeError('Media QC: timing mismatch')
    return {'file':output.name,'duration_sec':measured,'width':w,'height':h}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--validate-only',action='store_true'); args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    raw=os.environ.get('DISPATCH_PAYLOAD','')
    p=json.loads(raw) if raw else json.loads((ROOT/'sample.json').read_text())
    errors=validate(p)
    (OUT/'content_qc.json').write_text(json.dumps({'passed':not errors,'errors':errors},ensure_ascii=False,indent=2))
    if errors: raise RuntimeError('Content QC rejected: '+'; '.join(errors))
    if args.validate_only: print('Content QC passed'); return
    if not features.check('raqm'): raise RuntimeError('Pillow must include RAQM for Hindi captions')
    from kokoro import KPipeline
    import torch
    torch.set_num_threads(2)
    pipeline=KPipeline(lang_code='h',repo_id='hexgrad/Kokoro-82M')
    timings={key:audio_timeline(p,key,pipeline) for key in ['long_video','shorts']}
    outputs=[render_video(p,key,*timings[key]) for key in ['long_video','shorts']]
    scene=dict(p['long_video']['scenes'][-1]); scene.update(phase='reconcile')
    frame(background(1280,720,scene),scene,{'speaker':'narrator','emotion':'affectionate','text':''},1,
          p['thumbnail']['thumbnailText'],True).save(OUT/'thumbnail.jpg',quality=95)
    (OUT/'story.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
    (OUT/'metadata.json').write_text(json.dumps(p['seo_metadata'],ensure_ascii=False,indent=2))
    (OUT/'media_qc.json').write_text(json.dumps({'passed':True,'outputs':outputs},indent=2))
    meta=p['seo_metadata']
    pack=f"# Puchu & Pihu — manual upload package\n\n## YouTube long\n{meta['long_video_title']}\n\n{meta['long_video_description']}\n\n## YouTube Short\n{meta['shorts_title']}\n\n{meta['shorts_description']}\n\n## Instagram Reel\n{meta['instagram_caption']}\n\n## Tags\n{', '.join(meta.get('tags',[]))}\n\n## Hashtags\n{' '.join(meta.get('hashtags',[]))}\n\nFiles: long_story.mp4, short_reel.mp4, thumbnail.jpg, and two SRT files. Review both videos before publishing. Captions use phrase-level estimated timing.\n"
    (OUT/'upload_pack.md').write_text(pack,encoding='utf-8')
    print(json.dumps(outputs))

if __name__=='__main__': main()
