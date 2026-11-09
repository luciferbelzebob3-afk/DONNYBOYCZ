"""Verify the twelve original animations inside the actual firmware update archive."""
from pathlib import Path
import hashlib
import io
import json
import struct
import tarfile

import heatshrink2
from PIL import Image

ANIMATIONS = {
    'DB_DS_Kapuce_128x64': (32, 8),
    'DB_DS_Vysilac_128x64': (32, 8),
    'DB_DS_Radar_128x64': (32, 8),
    'DB_DS_Logo_128x64': (32, 8),
    'DB_Kluk_Dech_128x64': (40, 10),
    'DB_Kluk_Matrix_128x64': (40, 10),
    'DB_Kluk_Stin_128x64': (40, 10),
    'DB_Kluk_3D_128x64': (40, 10),
    'DB_Auto_Noc_128x64': (8, 6),
    'DB_Auto_Garaz_128x64': (8, 6),
    'DB_Auto_Budiky_128x64': (8, 6),
    'DB_Auto_Jizda_128x64': (8, 6),
}


def fields(text):
    return dict(line.split(': ', 1) for line in text.splitlines()
                if ': ' in line and not line.startswith('#'))


def verify():
    pending = json.loads(Path('.donny/pending.json').read_text())
    version = pending['version']
    archive_path = Path(f'dist/f7-C/flipper-z-f7-update-{version}.tgz')
    with tarfile.open(archive_path) as update:
        resources = [m for m in update.getmembers() if m.name.endswith('/resources.ths')
                     or m.name == 'resources.ths']
        assert len(resources) == 1, 'Chybi jednoznacny archiv SD prostredku'
        compressed = update.extractfile(resources[0]).read()
    magic, revision, window, lookahead = struct.unpack('<IBBB', compressed[:7])
    assert magic == 0x53445348 and revision == 1
    payload = heatshrink2.decompress(compressed[7:], window_sz2=window, lookahead_sz2=lookahead)
    results = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as resources:
        members = {m.name.lstrip('./'): m for m in resources.getmembers() if m.isfile()}
        def data(name):
            assert name in members, 'Chybi soubor v instalaci: ' + name
            return resources.extractfile(members[name]).read()
        manifest = data('dolphin/manifest.txt').decode()
        for name, (count, fps) in ANIMATIONS.items():
            assert manifest.splitlines().count('Name: ' + name) == 1
            source = Path('assets/dolphin/external') / name
            meta = fields(data(f'dolphin/{name}/meta.txt').decode())
            assert (int(meta['Width']), int(meta['Height'])) == (128, 64)
            assert int(meta['Passive frames']) == count and int(meta['Active frames']) == 0
            assert int(meta['Frame rate']) == fps and int(meta['Duration']) == 12
            assert list(map(int, meta['Frames order'].split())) == list(range(count))
            assert len(list(source.glob('frame_*.png'))) == count
            bm_count = sum(p.startswith(f'dolphin/{name}/frame_') and p.endswith('.bm') for p in members)
            assert bm_count == count
            for frame in range(count):
                with Image.open(source / f'frame_{frame}.png') as image:
                    assert image.size == (128, 64) and image.mode == '1'
                    assert image.crop((0, 0, 128, 13)).getextrema() == (255, 255)
                    expected = bytes(sum((image.getpixel((x + bit, y)) == 0) << bit
                                         for bit in range(8))
                                     for y in range(64) for x in range(0, 128, 8))
                bm = data(f'dolphin/{name}/frame_{frame}.bm')
                if bm[0] == 0:
                    raw = bm[1:]
                else:
                    assert bm[:2] == b'\x01\x00'
                    assert int.from_bytes(bm[2:4], 'little') == len(bm) - 4
                    raw = heatshrink2.decompress(bm[4:], window_sz2=8, lookahead_sz2=4)
                assert raw == expected, f'Nesouhlasi bitmapa {name}/{frame}'
            results.append(dict(name=name, frames=count, fps=fps, comparison='OK'))
        assert not any('DB_Kluk_Nasazeni_' in p or 'DB_Kluk_Chuze_' in p for p in members)
    report = dict(version=version, animations=results, total_frames=sum(n for n, _ in ANIMATIONS.values()),
                  update_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(), physical_test=False)
    Path('release-assets').mkdir(exist_ok=True)
    Path('release-assets/animace-overeni.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Overeno {len(results)} animaci a {report["total_frames"]} snimku v instalacnim balicku {version}.')


if __name__ == '__main__':
    verify()
