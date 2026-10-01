"""Silent 16s animation demo, independent of text-generation/TTS API calls."""
import math
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import motion

OUT=Path(__file__).parent/'motion-preview'
OUT.mkdir(exist_ok=True)
scenes=[{'phase':'setup','movement':'approach','prop':'none'},
        {'phase':'conflict','movement':'idle','prop':'none'},
        {'phase':'care','movement':'approach','prop':'food'},
        {'phase':'reconcile','movement':'approach','prop':'flower'}]
labels=['Walking and blinking','Talking and sulking','Offering warm food','A sweet apology']
for w,h,name in [(960,540,'Puchu_Pihu_motion_preview.mp4'),(540,960,'Puchu_Pihu_vertical_preview.mp4')]:
    bases=[motion.background(w,h,s) for s in scenes]
    proc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24',
                           '-s',f'{w}x{h}','-r','24','-i','pipe:0','-an','-c:v','libx264',
                           '-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/name)],stdin=subprocess.PIPE)
    samples=[]
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',round(w*.025))
    for n in range(16*24):
        t=n/24; index=min(3,int(t//4)); local=t-index*4
        line={'speaker':'pihu' if index==1 else 'puchu','mouth':(math.sin(t*22)+1)/2,'scene_t':local}
        im=motion.animate(bases[index],scenes[index],line,t)
        d=ImageDraw.Draw(im);d.rounded_rectangle((w*.03,h*.80,w*.97,h*.94),radius=14,fill='#fff8ed')
        d.text((w/2,h*.82),labels[index],font=font,anchor='mt',fill='#3f514c')
        d.text((w/2,h*.87),'Motion demo - no narration',font=font,anchor='mt',fill='#3f514c')
        proc.stdin.write(im.tobytes())
        if w==960 and n in [12,36,108,132,204,228,300,324]: samples.append(im.resize((480,270)))
    proc.stdin.close()
    if proc.wait(): raise RuntimeError('Preview encode failed')
    if samples:
        contact=Image.new('RGB',(1920,540))
        for i,im in enumerate(samples):contact.paste(im,((i%4)*480,(i//4)*270))
        contact.save(OUT/'motion_contact.jpg',quality=90)
print('Created landscape and vertical motion previews')
