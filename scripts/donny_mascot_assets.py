#!/usr/bin/env python3
"""Native, pixel-aligned mascot variants; no firmware build required.

Keep icon names, bitmap sizes, animation frame order and timing for SDK/FAP
compatibility. DB_* scenes are existing original artwork and are preserved.
"""
import json
import io
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw
from donny_theme_assets import ROOT, hood, label

SOURCE_REF = '4443f37e0'


def original(path):
    """Read the reviewed baseline for partial edits; keep reruns lossless."""
    data = subprocess.check_output(
        ['git', 'show', f'{SOURCE_REF}:{path.relative_to(ROOT).as_posix()}'], cwd=ROOT)
    return Image.open(io.BytesIO(data)).convert('1')


def character(level=1, mood='okay', blink=False):
    im = hood()
    d = ImageDraw.Draw(im)
    d.rectangle((12, 17, 16, 27), fill=0)
    d.rectangle((23, 17, 27, 27), fill=0)
    if blink:
        for x in (13, 24):
            d.line((x, 22, x+2, 22), fill=255)
    else:
        for x in (13, 24):
            d.rectangle((x, 20 if mood == 'bad' else 18,
                         x+1, 23 if mood == 'bad' else 25), fill=255)
    if mood == 'happy':
        d.line([(14, 28), (19, 30), (24, 28)], fill=255)
    elif mood == 'bad':
        d.line([(14, 30), (19, 28), (24, 30)], fill=255)
        d.line((28, 23, 28, 27), fill=255)
    # Sleeve badges identify levels without changing the vertical-eye identity.
    for n in range(level):
        d.line((14+n*4, 38, 15+n*4, 39), fill=255)
    return im


def scene(size, action='idle', frame=0, level=1, mood='okay', right=False):
    w, h = size
    im = Image.new('1', size, 255)
    d = ImageDraw.Draw(im)
    ch = min(42, h-2)
    cw = min(38, w-2, round(ch*38/42))
    if action == 'warning':
        cw = min(cw, w-15)
    person = character(level, mood, frame % 8 == 3).resize((cw, ch), Image.Resampling.NEAREST)
    x = w-cw-3 if right else 2 if w >= 59 else (w-cw)//2
    y = h-ch-1-(frame % 3 == 1)
    im.paste(person, (x, y))
    if action in ('send', 'receive', 'scan'):
        # Handheld transmitter and moving radio waves.
        bx = x+cw-4 if not right else x-10
        by = min(h-18, y+ch//2+5)
        d.line((bx+4, by-8, bx+4, by), fill=0)
        d.rounded_rectangle((bx, by, bx+9, by+15), radius=2, outline=0, fill=255)
        d.rectangle((bx+2, by+3, bx+7, by+8), outline=0)
        d.line((x+cw//2, y+ch-6, bx+3, by+11), fill=0, width=2)
        if w > 65:
            for n in range(1, 4):
                if frame and n > 1+frame % 3:
                    continue
                r = 5+n*5
                d.arc((bx+8-r, by-r, bx+8+r, by+r), -55, 55, fill=0)
            tx = w-14
            d.rectangle((tx, max(1, by-3), tx+11, by+12), outline=0)
            d.rectangle((tx+3, by, tx+8, by+7), outline=0)
            ay = min(h-4, by+21)
            if action == 'receive':
                d.line((tx+8, ay, bx+16, ay), fill=0)
                d.line([(bx+20, ay-3), (bx+16, ay), (bx+20, ay+3)], fill=0)
            else:
                d.line((bx+16, ay, tx+8, ay), fill=0)
                d.line([(tx+4, ay-3), (tx+8, ay), (tx+4, ay+3)], fill=0)
    elif action == 'success':
        sx = min(w-19, x+cw+5)
        d.line([(sx, h//2), (sx+5, h//2+5), (sx+14, h//2-7)], fill=0, width=2)
    elif action == 'save':
        sx = w-25
        d.rectangle((sx, h//2-9, sx+20, h//2+12), fill=0)
        d.rectangle((sx+4, h//2-7, sx+15, h//2-1), fill=255)
        d.rectangle((sx+4, h//2+3, sx+16, h//2+10), fill=255)
    elif action == 'warning':
        sx = w-10
        d.line((sx, 4, sx, 14), fill=0, width=2)
        d.rectangle((sx, 18, sx+1, 19), fill=0)
    elif action == 'delete':
        sx = w-26
        d.rectangle((sx, h//2-2, sx+17, h//2+18), outline=0, width=2)
        d.line((sx-2, h//2-5, sx+19, h//2-5), fill=0, width=2)
        d.line((sx+5, h//2-8, sx+12, h//2-8), fill=0)
    elif action in ('laptop', 'read', 'music'):
        sx = x-44 if right else x+cw+6
        sy = h-23
        if action == 'laptop':
            d.rectangle((sx, sy-12, sx+31, sy+8), outline=0, width=2)
            d.line((sx-4, sy+11, sx+35, sy+11), fill=0, width=2)
            for n in range(3):
                d.line((sx+5, sy-7+n*4, sx+12+(frame+n)%4*3, sy-7+n*4), fill=0)
        elif action == 'read':
            d.line([(sx, sy-7), (sx+14, sy-4), (sx+28, sy-7),
                    (sx+28, sy+14), (sx+14, sy+17), (sx, sy+14), (sx, sy-7)], fill=0)
            d.line((sx+14, sy-4, sx+14, sy+17), fill=0)
        else:
            d.ellipse((sx, sy+8, sx+7, sy+13), fill=0)
            d.line((sx+7, sy+10, sx+7, sy-9), fill=0, width=2)
            d.line((sx+7, sy-9, sx+20, sy-12), fill=0, width=2)
            d.line((sx+20, sy-12, sx+20, sy+7), fill=0, width=2)
            d.ellipse((sx+13, sy+5, sx+20, sy+10), fill=0)
    return im


def main():
    changed = []

    def save(path, image):
        with Image.open(path) as old:
            assert old.size == image.size, path
        assert image.mode == '1'
        image.save(path, optimize=False)
        changed.append(path.relative_to(ROOT).as_posix())

    icons = ROOT/'assets/icons'
    for path in icons.rglob('*.png'):
        name = path.stem.lower()
        action = None
        if 'dolphin' in name or name.startswith('dolph_'):
            action = ('receive' if 'receive' in name else 'send' if 'send' in name or 'emulation' in name
                      else 'save' if 'saved' in name else 'delete' if 'mafia' in name
                      else 'warning' if 'warning' in name else 'success' if 'success' in name or 'done' in name
                      else 'idle')
        elif path.parent.name == 'SubGhz' and name.startswith(('scanning_', 'fishing_')):
            action = 'receive'
        elif path.parent.name == 'U2F' and name.startswith(('auth_', 'connected_', 'error_', 'connect_me_')):
            action = 'warning' if name.startswith('error') else 'success' if name.startswith('connected') else 'send'
        elif path.parent.name == 'Passport' and name.startswith(('passport_bad', 'passport_okay', 'passport_happy')):
            mood, level = re.search(r'passport_(bad|okay|happy)([123])', name).groups()
            with Image.open(path) as old:
                portrait = scene(old.size, level=int(level), mood=mood)
            # Keep the passport's original rounded frame.
            ImageDraw.Draw(portrait).rounded_rectangle((0, 0, 45, 48), radius=5, outline=0)
            save(path, portrait)
            continue
        elif path.parent.name.startswith('Levelup'):
            frame = int(path.stem.split('_')[-1])
            with Image.open(path) as old:
                im = scene(old.size, frame=frame, level=2 if 'Levelup1' in str(path) else 3, mood='happy')
            label(ImageDraw.Draw(im), (48, 18), 'DONNY BOY')
            label(ImageDraw.Draw(im), (48, 32), 'LEVEL UP!')
            save(path, im)
            continue
        if action is not None:
            with Image.open(path) as old:
                save(path, scene(old.size, action, mood='bad' if 'cry' in name else 'okay'))

    # Remaining illustrations carry functional text/device parts: retain those pixels.
    regions = {
        'ErasePin/Erase_pin_128x64.png': (0, 0, 56, 64),
        'Common/DFU_128x50.png': (0, 0, 128, 50),
        'BLE/BLE_Pairing_128x64.png': (0, 20, 128, 64),
        'Power/Unplug_bg_top_128x14.png': (0, 0, 128, 14),
        'Power/Unplug_bg_bottom_128x10.png': (0, 0, 128, 10),
    }
    for rel, box in regions.items():
        path = icons/rel
        im = original(path)
        d = ImageDraw.Draw(im)
        d.rectangle((box[0], box[1], box[2]-1, box[3]-1), fill=255)
        if rel.startswith('Power/'):
            # A split hood border around the separate battery widget.
            d.line((2, 1, 125, 1), fill=0)
            for x in (3, 122):
                d.line((x, 2, x, im.height-2), fill=0)
            if 'top' in rel:
                im.paste(character().resize((12, 13), Image.Resampling.NEAREST), (57, 1))
        else:
            patch = scene((box[2]-box[0], box[3]-box[1]), 'send' if rel.startswith('BLE/') else 'idle')
            im.paste(patch, box[:2])
        save(path, im)

    # Tutorial speech panels remain byte-for-byte outside each character region.
    boxes = [(0, 12, 71, 64), (64, 12, 128, 64), (0, 14, 54, 64),
             (0, 14, 61, 64), (79, 12, 128, 64), (84, 12, 128, 64)]
    for index, box in enumerate(boxes):
        path = ROOT/f'assets/slideshow/first_start/frame_{index:02d}.png'
        im = original(path)
        im.paste(scene((box[2]-box[0], box[3]-box[1]), mood='happy'), box[:2])
        save(path, im)

    # Legacy scenes are replaced completely, including dormant fallback scenes.
    # Existing DB_* originals (hood, Matrix, radio, cars) remain unchanged.
    for parent in ('internal', 'blocking', 'external'):
        for folder in sorted((ROOT/'assets/dolphin'/parent).iterdir()):
            if not folder.is_dir() or folder.name.startswith('DB_'):
                continue
            meta = (folder/'meta.txt').read_text()
            bubble_x = re.search(r'^X: (\d+)', meta, re.M)
            right = bool(bubble_x and int(bubble_x[1]) < 65)
            level = int(folder.name[1]) if folder.name.startswith(('L1', 'L2', 'L3')) else 1
            mood = 'bad' if any(s in folder.name.lower() for s in ('bad', 'sad', 'cry', 'mad', 'nosd', 'nodb')) else 'okay'
            name = folder.name.lower()
            action = ('laptop' if any(s in name for s in ('coding', 'hacking', 'laptop', 'mods', 'doom'))
                      else 'read' if any(s in name for s in ('book', 'lab'))
                      else 'music' if any(s in name for s in ('song', '_dj', 'showtime'))
                      else 'receive' if any(s in name for s in ('radio', 'recording')) and not right
                      else 'warning' if parent == 'blocking' and not right else 'idle')
            for path in sorted(folder.glob('frame_*.png')):
                frame = int(path.stem.split('_')[-1])
                with Image.open(path) as old:
                    im = scene(old.size, action, frame=frame, level=level, mood=mood, right=right)
                save(path, im)

    # FAP and debug apps compile private copies rather than the shared icon table.
    for path in (ROOT/'applications').rglob('*.png'):
        if 'dolph' in path.name.lower():
            with Image.open(path) as old:
                im = scene(old.size, 'success' if 'success' in path.name.lower() or 'done' in path.name.lower() else 'idle')
            save(path, im)

    (ROOT/'documentation/DonnyMascotAssets.json').write_text(
        json.dumps({'format': '1-bit PNG', 'assets': sorted(changed)}, indent=2)+'\n')
    print(f'Updated {len(changed)} mascot bitmaps; sizes and timing preserved.')


if __name__ == '__main__':
    main()
