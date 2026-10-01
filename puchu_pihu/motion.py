"""Reusable AI sprite animation; body poses and voice-reactive mouth movement."""
import base64
import io
import math
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

ROOT = Path(__file__).parent

@lru_cache(maxsize=4)
def atlas(name):
    return Image.open(io.BytesIO(base64.b64decode((ROOT/name).read_text()))).convert('RGBA')

@lru_cache(maxsize=80)
def sprite(character, pose, size):
    sheet = atlas('motion_characters.b64')
    index = pose + (8 if character == 'pihu' else 0)
    x, y = index % 4, index // 4
    tile = sheet.crop((round(x*sheet.width/4), round(y*sheet.height/4),
                       round((x+1)*sheet.width/4), round((y+1)*sheet.height/4)))
    return tile.resize((size,size), Image.Resampling.LANCZOS)

@lru_cache(maxsize=24)
def prop_image(kind, size):
    sheet = atlas('motion_props.b64')
    index = {'food':0,'tea':0,'berry':0,'flower':1,'blanket':2,'umbrella':2}.get(kind,0)
    tile = sheet.crop((round(index*sheet.width/3),0,round((index+1)*sheet.width/3),sheet.height))
    return ImageOps.contain(tile,(size,size),Image.Resampling.LANCZOS)

def background(w,h,scene):
    sheet = atlas('motion_backgrounds.b64')
    phase = scene.get('phase','setup')
    index = {'setup':0,'conflict':1,'care':2,'reconcile':4,'payoff':5}.get(phase,0)
    if scene.get('background')=='rain' or scene.get('prop')=='blanket': index=3
    x,y=index%3,index//3
    tile=sheet.crop((round(x*sheet.width/3),round(y*sheet.height/2),
                     round((x+1)*sheet.width/3),round((y+1)*sheet.height/2)))
    return ImageOps.fit(tile.convert('RGB'),(w,h),Image.Resampling.LANCZOS)

def actor_pose(character, scene, line, t, walking):
    if walking: return 4+int(t*5)%2
    active = line.get('speaker')==character
    if active and line.get('mouth',1)>.16:
        return 2+int(line.get('mouth',1)>.56)
    if (t+(1.4 if character=='pihu' else 0))%3.7<.14: return 1
    if character=='pihu' and scene.get('phase')=='conflict': return 6
    if scene.get('phase') in ['care','reconcile','payoff'] and character=='puchu': return 7
    return 0

def animate(base,scene,line,t,thumbnail=False):
    im=base.convert('RGBA'); w,h=im.size
    vertical=h>w
    size=round(min(w*(.57 if vertical else .37),h*(.46 if vertical else .68)))
    local=max(0,line.get('scene_t',t))
    approach=scene.get('movement')=='approach' and not thumbnail
    walking=approach and local<2.4
    progress=min(1,local/2.4)
    ease=progress*progress*(3-2*progress)
    gap=w*(.21-(.065*ease if approach else 0))
    floor=h*(.765 if vertical else .765)
    positions={}
    d=ImageDraw.Draw(im)
    for character,sign in [('puchu',-1),('pihu',1)]:
        x=w/2+sign*gap
        bob=(abs(math.sin(local*math.pi*5))*size*.018 if walking else math.sin(t*2.5+sign)*size*.003)
        d.ellipse((x-size*.24,floor-size*.018,x+size*.24,floor+size*.018),fill=(70,45,30,65))
        pose=0 if thumbnail else actor_pose(character,scene,line,t,walking)
        art=sprite(character,pose,size)
        tilt=(math.sin(local*math.pi*5)*1.8 if walking else math.sin(t*1.5+sign)*.45)
        art=art.rotate(tilt,resample=Image.Resampling.BICUBIC,expand=False)
        im.alpha_composite(art,(round(x-size/2),round(floor-size-bob)))
        positions[character]=(x,floor-size*.32)
    kind=scene.get('prop','none')
    if kind in ['food','tea','berry','flower','blanket','umbrella'] and scene.get('phase') in ['care','reconcile']:
        art=prop_image(kind,round(size*.28))
        giver=positions['puchu'][0]; receiver=positions['pihu'][0]
        transfer=(1-math.cos(min(1,max(0,(local-2.4)/1.8))*math.pi))/2
        px=giver+(receiver-giver)*transfer
        py=floor-size*.33-math.sin(transfer*math.pi)*size*.07
        im.alpha_composite(art,(round(px-art.width/2),round(py-art.height/2)))
    return im.convert('RGB')
