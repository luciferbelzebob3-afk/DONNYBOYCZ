#!/usr/bin/env python3
"""Generate native 1-bit DONNY BOY artwork; preserve all non-eye animation pixels."""
from pathlib import Path
import argparse
import io
import math
import subprocess
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REF = 'e07f0d6da79ad791b2677f06ca0a63617f0707b8'
NAMES = ('DB_DS_Kapuce_128x64', 'DB_Kluk_Dech_128x64',
         'DB_Kluk_Matrix_128x64', 'DB_Kluk_Stin_128x64', 'DB_Kluk_3D_128x64')
# A deliberately pixel-aligned 5x7 alphabet, with no antialiasing or font dependency.
FONT = {
 'A':['01110','10001','10001','11111','10001','10001','10001'],
 'B':['11110','10001','10001','11110','10001','10001','11110'],
 'C':['01111','10000','10000','10000','10000','10000','01111'],
 'D':['11110','10001','10001','10001','10001','10001','11110'],
 'E':['11111','10000','10000','11110','10000','10000','11111'],
 'F':['11111','10000','10000','11110','10000','10000','10000'],
 'G':['01111','10000','10000','10111','10001','10001','01110'],
 'H':['10001','10001','10001','11111','10001','10001','10001'],
 'I':['111','010','010','010','010','010','111'],
 'J':['00111','00010','00010','00010','10010','10010','01100'],
 'K':['10001','10010','10100','11000','10100','10010','10001'],
 'L':['10000','10000','10000','10000','10000','10000','11111'],
 'M':['10001','11011','10101','10101','10001','10001','10001'],
 'N':['10001','11001','10101','10011','10001','10001','10001'],
 'O':['01110','10001','10001','10001','10001','10001','01110'],
 'P':['11110','10001','10001','11110','10000','10000','10000'],
 'R':['11110','10001','10001','11110','10100','10010','10001'],
 'S':['01111','10000','10000','01110','00001','00001','11110'],
 'T':['11111','00100','00100','00100','00100','00100','00100'],
 'U':['10001','10001','10001','10001','10001','10001','01110'],
 'V':['10001','10001','10001','10001','10001','01010','00100'],
 'W':['10001','10001','10001','10101','10101','10101','01010'],
 'Y':['10001','10001','01010','00100','00100','00100','00100'],
 'Z':['11111','00001','00010','00100','01000','10000','11111'],
 '!':['1','1','1','1','1','0','1'],
 ',':['0','0','0','0','1','1','1'], '>':['100','010','001','001','001','010','100'],
 ' ':['000']*7, '.':['0','0','0','0','0','1','1'],
}

def label(draw, xy, text, color=0):
    x,y=xy
    for char in text:
        glyph=FONT[char]
        for yy,row in enumerate(glyph):
            for xx,bit in enumerate(row):
                if bit=='1':draw.point((x+xx,y+yy),fill=color)
        x+=len(glyph[0])+1
    assert x-1<=128, text

def hood(size=(38,42)):
    im=Image.new('1',size,255);d=ImageDraw.Draw(im)
    d.polygon([(19,0),(8,9),(3,27),(3,32),(0,41),(37,41),(34,32),(34,27),(29,9)],fill=0)
    d.line([(19,3),(11,11),(7,26),(9,32),(19,36),(29,32),(31,26),(27,11),(19,3)],fill=255,width=1)
    d.line([(8,30),(18,34),(29,30)],fill=255,width=2)
    # The same vertical-eye identity as the animated character.
    d.rectangle((13,19,14,25),fill=255);d.rectangle((24,19,25,25),fill=255)
    d.line([(9,35),(7,41)],fill=255);d.line([(29,35),(31,41)],fill=255)
    return im

def components(im):
    white={(x,y) for y in range(13,64) for x in range(128) if im.getpixel((x,y))}
    result=[]
    while white:
        q=[white.pop()];points=set(q)
        while q:
            x,y=q.pop()
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    p=(x+dx,y+dy)
                    if p in white:white.remove(p);points.add(p);q.append(p)
        xs,ys=zip(*points);result.append(((min(xs),min(ys),max(xs),max(ys)),points))
    return result

def patch_eyes(source,name,index):
    im=source.copy();d=ImageDraw.Draw(im)
    if name=='DB_Kluk_Matrix_128x64':
        # Glasses use the same breathing offset as this source character.
        dy=round(math.sin(index*math.tau/40))
        d.rectangle((54,31+dy,74,35+dy),fill=0)
        centers=[(58,33+dy),(71,33+dy)]
        closed=index in (28,29)
    else:
        expected={'DB_DS_Kapuce_128x64':35,'DB_Kluk_Dech_128x64':33,
                  'DB_Kluk_Stin_128x64':38,'DB_Kluk_3D_128x64':36}[name]
        eyes=[]
        for (x0,y0,x1,y1),pts in components(source):
            if 50<=x0<=74 and x1<=77 and expected-1<=y0<=expected+1 and 3<=x1-x0<=7 and 0<=y1-y0<=3 and 4<=len(pts)<=14:
                eyes.append(((x0+x1)//2,(y0+y1)//2,pts))
        if not eyes and ((name=='DB_DS_Kapuce_128x64' and index in (22,23)) or (name=='DB_Kluk_3D_128x64' and index in (28,29))):
            return im  # Preserve the original fully closed blink.
        assert len(eyes)==2,(name,index,[(x,y) for x,y,_ in eyes])
        closed=all(len({p[1] for p in pts})==1 for _,_,pts in eyes)
        centers=[]
        for x,y,pts in sorted(eyes):
            for p in pts:d.point(p,fill=0)
            centers.append((x,y))
    blink=22 if name=='DB_DS_Kapuce_128x64' else 28
    height=1 if closed else 3 if index in (blink-1,blink+2) else 6
    for x,y in centers:
        d.rectangle((x,y-height//2,x+1,y+(height-1)//2),fill=255)
    assert im.mode=='1' and im.size==(128,64)
    assert im.crop((0,0,128,13)).tobytes()==source.crop((0,0,128,13)).tobytes()
    return im

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-ref',default=SOURCE_REF);args=parser.parse_args()
    for name in NAMES:
        folder=ROOT/'assets/dolphin/external'/name
        for file in sorted(folder.glob('frame_*.png')):
            path=file.relative_to(ROOT).as_posix()
            original=subprocess.check_output(['git','show',args.source_ref+':'+path],cwd=ROOT)
            with Image.open(io.BytesIO(original)) as source:
                patch_eyes(source,name,int(file.stem.split('_')[1])).save(file,optimize=False)
    # One post-update slide; OK returns straight to the desktop (native one-page behavior).
    splash=Image.new('1',(128,64),255);d=ImageDraw.Draw(splash)
    splash.paste(hood(),(3,7))
    label(d,(47,8),'DONNY BOY')
    label(d,(47,20),'CZ FIRMWARE')
    d.line((47,31,124,31),fill=0)
    label(d,(47,36),'AKTUALIZOVANO')
    label(d,(4,54),'TVUJ TEMNY SIGNAL.')
    d.rounded_rectangle((107,49,126,62),radius=2,outline=0)
    label(d,(111,52),'OK')
    folder=ROOT/'assets/slideshow/update_default'
    splash.save(folder/'frame_00.png',optimize=False)
    for file in folder.glob('frame_*.png'):
        if file.name!='frame_00.png':file.unlink()
    # Localize the first-start tutorial without touching its dolphin illustrations.
    tutorials = [
        ((73,17,122,57), (78,21), ['AHOJ!', 'STISKNI', 'VPRAVO']),
        ((0,14,62,59), (4,18), ['JSEM', 'DONNY BOY', 'TVUJ', 'SIGNAL.']),
        ((55,15,126,62), (59,19), ['TVUJ', 'TEMNY', 'SIGNAL', 'V KAPSE']),
        ((62,16,124,63), (66,20), ['CIM VIC', 'ME VIDIS,', 'TIM VIC', 'DOVEDU.']),
        ((0,15,75,52), (4,19), ['CTI, ZAPISUJ', 'A EMULUJ', 'S DONNY BOY']),
        ((0,12,82,58), (4,16), ['UROVEN A', 'NALADU NAJDES', 'V NABIDCE', 'PAS.']),
    ]
    for index, (box, xy, lines) in enumerate(tutorials):
        path = f'assets/slideshow/first_start/frame_{index:02d}.png'
        original = subprocess.check_output(['git', 'show', args.source_ref+':'+path], cwd=ROOT)
        with Image.open(io.BytesIO(original)) as source:
            frame=source.copy(); ink=ImageDraw.Draw(frame)
            clear = (0,10,86,63) if index==5 else (0,12,77,54) if index==4 else (55,14,127,63) if index==2 else box
            ink.rectangle(clear, fill=255)
            ink.rectangle(box, fill=255, outline=0)
            for row,text in enumerate(lines):label(ink,(xy[0],xy[1]+row*10),text)
            frame.save(ROOT/path,optimize=False)
    logo=ROOT/'assets/icons/Update/DonnyBoy_32x40.png'
    # Keep the updater's existing 32x40 slot and avoid changing shared upstream icons.
    small=hood().resize((32,40),Image.Resampling.NEAREST)
    small.save(logo,optimize=False)
    print('Updated 192 animation frames, 1 post-update slide and 1 private updater logo.')

if __name__=='__main__':main()
