"""One hand-staged 2D character-rig scene. No photo backgrounds or sprite swaps."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import wave
import numpy as np
from PIL import Image, ImageDraw

OUT=Path(__file__).parent/'output'
OUT.mkdir(exist_ok=True)
FPS=24
SR=24000
SCALE=2
INK='#38273d'
SKIN='#ffc9a0'

def ease(t):
    t=max(0,min(1,t));return t*t*(3-2*t)

def lerp(a,b,t):return a+(b-a)*t

class Canvas:
    def __init__(self,image):self.d=ImageDraw.Draw(image)
    def pts(self,points):return [(round(x*SCALE),round(y*SCALE)) for x,y in points]
    def box(self,b):return tuple(round(x*SCALE) for x in b)
    def ellipse(self,b,fill,outline=INK,width=2):self.d.ellipse(self.box(b),fill,outline,width=round(width*SCALE))
    def rect(self,b,fill,outline=INK,width=2,radius=0):
        self.d.rounded_rectangle(self.box(b),round(radius*SCALE),fill,outline,round(width*SCALE))
    def poly(self,p,fill,outline=INK,width=2):
        pts=self.pts(p);self.d.polygon(pts,fill)
        if outline:self.d.line(pts+[pts[0]],fill=outline,width=round(width*SCALE),joint='curve')
    def line(self,p,color=INK,width=2):self.d.line(self.pts(p),fill=color,width=round(width*SCALE),joint='curve')
    def arc(self,b,start,end,color=INK,width=2):self.d.arc(self.box(b),start,end,color,round(width*SCALE))

def bone(c,a,b,color,width):
    c.line([a,b],INK,width+4);c.ellipse((a[0]-width/2-2,a[1]-width/2-2,a[0]+width/2+2,a[1]+width/2+2),INK,None)
    c.line([a,b],color,width);c.ellipse((b[0]-width/2,b[1]-width/2,b[0]+width/2,b[1]+width/2),color,None)

def elbow(shoulder,hand,L1=46,L2=48,bend=1):
    dx,dy=hand[0]-shoulder[0],hand[1]-shoulder[1]
    distance=max(.01,math.hypot(dx,dy))
    if distance>L1+L2-1:
        factor=(L1+L2-1)/distance;hand=(shoulder[0]+dx*factor,shoulder[1]+dy*factor);dx*=factor;dy*=factor;distance=L1+L2-1
    theta=math.atan2(dy,dx)
    offset=math.acos(max(-1,min(1,(L1*L1+distance*distance-L2*L2)/(2*L1*distance))))
    angle=theta+bend*offset
    return (shoulder[0]+math.cos(angle)*L1,shoulder[1]+math.sin(angle)*L1),hand

def arm(c,shoulder,hand,clothes,bend):
    joint,hand=elbow(shoulder,hand,bend=bend)
    bone(c,shoulder,joint,clothes,22)
    bone(c,joint,hand,SKIN,15)
    c.ellipse((hand[0]-10,hand[1]-8,hand[0]+10,hand[1]+8),SKIN)
    return hand

def room(c):
    c.rect((0,0,1000,600),'#ffe6bc',outline=None)
    c.rect((0,430,1000,600),'#dfb28a',outline=None)
    c.line([(0,431),(1000,431)],width=3)
    for y in [470,525,580]:c.line([(0,y),(1000,y)],'#c99876',1)
    c.rect((65,65,310,240),'#f8ce93',radius=12)
    c.rect((80,80,295,225),'#bce4f4',radius=7)
    c.ellipse((110,95,155,140),'#ffed9a',outline=None)
    c.poly([(80,180),(140,145),(200,190),(240,165),(295,191),(295,225),(80,225)],'#aedba4',outline=None)
    c.line([(187,80),(187,225)],'#faf1d6',7);c.line([(80,153),(295,153)],'#faf1d6',7)
    c.rect((745,335,965,428),'#bda5d9',radius=22)
    c.rect((738,382,972,455),'#c8afe6',radius=18)
    c.rect((748,386,780,452),'#a68cc8',radius=12)
    c.rect((931,386,963,452),'#a68cc8',radius=12)
    c.rect((795,342,845,382),'#ffcebb',radius=8)
    c.rect((650,80,830,225),'#f6c889',radius=4)
    c.rect((663,93,817,212),'#fff5e0',radius=3)
    c.ellipse((717,110,755,149),'#f6b09b',outline=None)
    c.line([(735,151),(735,189)],'#7d9a62',4)
    for dx in [-20,20]:c.ellipse((735+dx-13,155,735+dx+13,171),'#9eb978',outline=None)
    c.rect((35,330,95,432),'#b48762',radius=4)
    c.ellipse((30,319,100,339),'#c7976c')
    for i in range(5):
        x=65+math.sin(i*2)*30;y=300-i*13
        c.line([(65,328),(x,y)],'#73935d',3)
        c.ellipse((x-15,y-11,x+15,y+11),'#a0bb77')
    c.rect((350,52,550,93),'#c19269',radius=5)
    for x,color in [(376,'#f3afa8'),(418,'#91c1cd'),(473,'#cfb9e8')]:c.rect((x,19,x+25,54),color,radius=5)

def face(c,x,y,girl,t,mouth,emotion,yaw):
    hair='#4e3343' if girl else '#4a3545'
    if girl:
        for sign in [-1,1]:
            px=x+sign*67;py=y-25+math.sin(t*3+sign)*2
            c.ellipse((px-28,py-34,px+28,py+42),hair,width=3)
            c.ellipse((px-8,py-24,px+8,py-10),'#f293b4',width=2)
    c.ellipse((x-71,y-73,x+71,y+65),hair,width=3)
    c.ellipse((x-64,y-52,x+66,y+68),SKIN,width=3)
    for sign in [-1,1]:c.ellipse((x+sign*65-10,y+4,x+sign*65+10,y+24),SKIN,width=2)
    if girl:
        c.poly([(x-65,y-37),(x-54,y-60),(x-20,y-70),(x+25,y-64),(x+58,y-45),(x+65,y-17),(x+35,y-31),(x+12,y-52),(x-11,y-21),(x-28,y-39),(x-54,y-8)],hair,width=2)
        c.ellipse((x-53,y-50,x-36,y-33),'#ffde85',width=2)
    else:
        c.poly([(x-67,y-26),(x-79,y-54),(x-60,y-50),(x-62,y-78),(x-36,y-65),(x-22,y-89),(x-4,y-71),(x+26,y-84),(x+25,y-66),(x+52,y-67),(x+73,y-42),(x+64,y-19),(x+28,y-42),(x+6,y-34),(x-19,y-53),(x-35,y-34),(x-46,y-45)],hair,width=3)
    blink=(t+(1.1 if girl else 0))%3.5<.12
    look=yaw*7
    for sign in [-1,1]:
        ex=x+sign*26+look;ey=y+9
        if blink:c.arc((ex-14,ey-6,ex+14,ey+7),0,180,width=3)
        else:
            c.ellipse((ex-15,ey-20,ex+15,ey+19),'#fffaf4',width=2)
            c.ellipse((ex-5+yaw*3,ey-10,ex+10+yaw*3,ey+12),'#61452c',width=1)
            c.ellipse((ex-2+yaw*3,ey-7,ex+7+yaw*3,ey+9),'#302637',outline=None)
            c.ellipse((ex+yaw*3,ey-8,ex+5+yaw*3,ey-3),'white',outline=None)
        if emotion=='angry':
            c.line([(ex-14,ey-29-sign*4),(ex+13,ey-29+sign*4)],width=3)
        else:c.arc((ex-14,ey-34,ex+14,ey-21),190,340,width=3)
    c.arc((x+look-3,y+15,x+look+12,y+29),30,120,'#c48368',2)
    for sign in [-1,1]:c.ellipse((x+sign*46-12,y+29,x+sign*46+12,y+39),'#efaa94',outline=None)
    mx=x+look;my=y+46
    if mouth<.13:
        if emotion=='angry':c.arc((mx-14,my-3,mx+14,my+7),195,345,width=3)
        else:c.arc((mx-19,my-12,mx+19,my+8),0,180,width=3)
    else:
        width=12+mouth*10;height=5+mouth*13
        c.ellipse((mx-width,my-height,mx+width,my+height),'#703e4d',width=2)
        c.arc((mx-width+2,my,mx+width-2,my+height+7),190,350,'#e896a6',5)
        if mouth>.55:c.rect((mx-width+5,my-height+2,mx+width-5,my-height+6),'#fff5e7',outline=None,radius=2)

def actor(c,x,girl,t,walk,mouth,emotion,hands=None,nod=0):
    floor=480
    bounce=abs(math.sin(t*math.pi*4))*4*walk
    pelvis=400-bounce;shouldery=328-bounce
    clothes='#f39ebd' if girl else '#87b8e3'
    # Continuously articulated legs with knee and ankle positions.
    for sign in [-1,1]:
        hip=(x+sign*20,pelvis)
        phase=t*math.pi*4+(math.pi if sign==1 else 0)
        swing=math.sin(phase)*24*walk
        lift=max(0,math.cos(phase))*20*walk
        foot=(x+sign*22+swing,floor-lift)
        knee=(x+sign*22+swing*.45,pelvis+38-lift*.35)
        color=SKIN if girl else '#596b96'
        bone(c,hip,knee,color,20);bone(c,knee,(foot[0],foot[1]-9),color,17)
        c.ellipse((foot[0]-17,foot[1]-15,foot[0]+24,foot[1]+2),'#e486af' if girl else '#faf0dd',width=3)
        c.line([(foot[0]-13,foot[1]-1),(foot[0]+20,foot[1]-1)],width=2)
    if girl:
        c.poly([(x-29,shouldery-10),(x+29,shouldery-10),(x+49,pelvis+12),(x-49,pelvis+12)],clothes,width=3)
        c.line([(x-40,pelvis),(x+40,pelvis)],'#e180a6',2)
    else:
        c.rect((x-39,shouldery-12,x+39,pelvis+8),clothes,width=3,radius=13)
        c.line([(x-10,shouldery+7),(x-10,shouldery+38)],'#edf4fb',3)
        c.line([(x+10,shouldery+7),(x+10,shouldery+38)],'#edf4fb',3)
        c.rect((x-25,pelvis-21,x+25,pelvis-3),'#75a7d4',radius=5)
    if hands is None:
        if emotion=='angry':hands=[(x+20,shouldery+40),(x-20,shouldery+46)]
        else:
            swing=math.sin(t*math.pi*4)*20*walk
            hands=[(x-42+swing,shouldery+65),(x+42-swing,shouldery+65)]
    actual=[]
    for i,sign in enumerate([-1,1]):actual.append(arm(c,(x+sign*35,shouldery+4),hands[i],clothes,-sign))
    c.rect((x-12,shouldery-20,x+12,shouldery+4),SKIN,outline=None,radius=4)
    heady=264-bounce+nod
    face(c,x,heady,girl,t,mouth,emotion,-.7 if girl else .7)
    return actual

def bowl(c,x,y,t):
    c.ellipse((x-36,y-7,x+36,y+31),'#fff1d2',width=3)
    c.ellipse((x-37,y-16,x+37,y+3),'#ffe1ac',width=3)
    c.ellipse((x-31,y-12,x+31,y),'#eaa352',width=1)
    for dx in [-14,2,17]:c.ellipse((x+dx-3,y-9,x+dx+3,y-4),'#82a36b',outline=None)
    c.ellipse((x-6,y+10,x+6,y+21),'#c88e6d',outline=None)
    for i in [-1,0,1]:
        c.line([(x+i*16,y-21),(x+i*16+math.sin(t*3+i)*5,y-32),(x+i*16,y-42)],'#e7bf9b',2)

def make_audio(silent=False):
    lines=[('pihu','मुझे तुमसे बात नहीं करनी!'),('puchu','गुस्सा बाद में करना। पहले गरम सूप पी लो।'),('pihu','अच्छा, पर अगली बार मेरा इंतज़ार करना।'),('puchu','पक्का!')]
    pieces=[np.zeros(int(2.4*SR),dtype=np.float32)];now=2.4;timeline=[]
    pipe=None
    if not silent:
        from kokoro import KPipeline
        pipe=KPipeline(lang_code='h',repo_id='hexgrad/Kokoro-82M')
    for i,(speaker,text) in enumerate(lines):
        if i==2:
            pieces.append(np.zeros(int(3.4*SR),dtype=np.float32));now+=3.4
        if silent:audio=np.zeros(int([2.2,3.8,3.2,.9][i]*SR),dtype=np.float32)
        else:
            chunks=[]
            for r in pipe(text,voice='hf_alpha' if speaker=='pihu' else 'hm_omega',speed=.95):
                a=r.audio if hasattr(r,'audio') else r[2]
                if a is not None:chunks.append(a.detach().cpu().numpy() if hasattr(a,'detach') else np.asarray(a))
            audio=np.concatenate(chunks).astype(np.float32)
        timeline.append({'speaker':speaker,'text':text,'start':now,'end':now+len(audio)/SR})
        pieces.extend([audio,np.zeros(int(.35*SR),dtype=np.float32)]);now+=len(audio)/SR+.35
    pieces.append(np.zeros(int(1.2*SR),dtype=np.float32))
    speech=np.concatenate(pieces)
    with wave.open(str(OUT/'dialogue.wav'),'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(SR);wav.writeframes((np.clip(speech,-1,1)*32767).astype('<i2').tobytes())
    return speech,timeline,len(speech)/SR

def staging(t,timeline,speech):
    first,second,third,fourth=timeline
    handoff_start=second['end']+.35
    handoff_end=third['start']
    boy=lerp(135,490,ease(t/2.4));girl=690
    walking=float(t<2.4)
    transfer=ease((t-handoff_start)/max(.01,handoff_end-handoff_start))
    bx=lerp(boy+62,girl,transfer);by=365
    rest=[(boy-42,393),(boy+42,393)]
    release=[ease((transfer-.08)/.16),ease((transfer-.22)/.16)]
    boyhands=[(lerp(bx+sign*23,rest[i][0],release[i]),lerp(by+1,rest[i][1],release[i])) for i,sign in enumerate([-1,1])]
    girlhands=None
    if t>=handoff_start:
        reach=ease((t-handoff_start)/.65)
        leftx=lerp(bx+23,bx-23,ease((transfer-.45)/.25))
        rightreach=ease((transfer-.5)/.25)
        girlhands=[(lerp(girl-25,leftx,reach),lerp(375,by+1,reach)),(lerp(girl+25,bx+23,rightreach),lerp(385,by+1,rightreach))]
    speaker=None;mouth=0
    for line in timeline:
        if line['start']<=t<=line['end']:
            speaker=line['speaker'];chunk=speech[int(t*SR):int((t+.04)*SR)]
            mouth=min(1,float(np.sqrt(np.mean(chunk*chunk)))*12) if len(chunk) else 0
            break
    emotion='angry' if t<third['start'] else 'happy'
    camera='girl' if first['start']<=t<=first['end'] else 'boy' if second['start']<=t<=second['end'] else 'wide'
    return boy,girl,walking,bx,by,boyhands,girlhands,speaker,mouth,emotion,camera

def frame(t,timeline,speech):
    image=Image.new('RGB',(1000*SCALE,600*SCALE));c=Canvas(image);room(c)
    boy,girl,walk,bx,by,bh,gh,speaker,mouth,emotion,camera=staging(t,timeline,speech)
    boy_actual=actor(c,boy,False,t,walk,mouth if speaker=='puchu' else 0,'happy',bh,math.sin(t*4)*2)
    girl_actual=actor(c,girl,True,t,0,mouth if speaker=='pihu' else 0,emotion,gh,math.sin(t*3)*1.5)
    bowl(c,bx,by,t)
    # Fingers sit over the bowl rim, linking it visibly to the characters' hands.
    for x,y in boy_actual+girl_actual:
        if abs(x-bx)<37 and abs(y-by)<9:c.ellipse((x-7,y-3,x+7,y+6),SKIN,width=1)
    if camera=='girl':image=image.crop((int(480*SCALE),int(160*SCALE),int(920*SCALE),int(410*SCALE)))
    elif camera=='boy':image=image.crop((int((boy-165)*SCALE),int(155*SCALE),int((boy+270)*SCALE),int(400*SCALE)))
    return image.resize((1280,720),Image.Resampling.LANCZOS)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--silent',action='store_true');args=parser.parse_args()
    speech,timeline,duration=make_audio(args.silent)
    output=OUT/('tv_animation_silent_preview.mp4' if args.silent else 'Puchu_Pihu_2D_scene.mp4')
    command=['ffmpeg','-y','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r',str(FPS),'-i','pipe:0']
    if not args.silent:command+=['-i',str(OUT/'dialogue.wav'),'-c:a','aac','-b:a','160k']
    command+=['-c:v','libx264','-threads','2','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    contact=[]
    for n in range(math.ceil(duration*FPS)):
        t=n/FPS;image=frame(t,timeline,speech);process.stdin.write(image.tobytes())
        if n%48==0:contact.append(image.resize((384,216)))
    process.stdin.close()
    if process.wait():raise RuntimeError('Encode failed')
    report=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    video=next(s for s in report['streams'] if s['codec_type']=='video')
    assert video['width']==1280 and video['height']==720
    assert args.silent or any(s['codec_type']=='audio' for s in report['streams'])
    (OUT/'scene_timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
    (OUT/'scene_qc.json').write_text(json.dumps({'passed':True,'duration':float(report['format']['duration']),'fps':FPS,'audio':not args.silent,'method':'continuous 2D articulated limbs and hand-staged object interaction, four character dialogue lines; no narrator'},indent=2))
    sheet=Image.new('RGB',(384*4,216*math.ceil(len(contact)/4)))
    for i,image in enumerate(contact):sheet.paste(image,((i%4)*384,(i//4)*216))
    sheet.save(OUT/'contact_sheet.jpg',quality=90)
    print(json.dumps({'output':str(output),'duration':duration,'audio':not args.silent}))

if __name__=='__main__':main()
