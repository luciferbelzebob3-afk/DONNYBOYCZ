"""Check actual translated printf output against the embedded app's fixed buffers."""
import ast
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.github/scripts/donny'))
from localization import tokens, FORMAT


def format_calls(path):
    ts = tokens(path.read_text())
    for i, token in enumerate(ts[:-1]):
        if token[0] != 'snprintf' or ts[i + 1][0] != '(':
            continue
        args = [[]]
        depth = 0
        for t in ts[i + 2:]:
            value = t[0]
            if value == ')' and depth == 0:
                break
            if value in ('(', '[', '{'):
                depth += 1
            elif value in (')', ']', '}'):
                depth -= 1
            if value == ',' and depth == 0:
                args.append([])
            else:
                args[-1].append(value)
        if len(args) >= 3 and all(x.startswith('"') for x in args[2]):
            yield args, ''.join(ast.literal_eval(x) for x in args[2])


def largest_output(fmt, args):
    values = iter(args)
    def value(match):
        spec = match[0]
        if spec == '%%':
            return '%'
        expression = ' '.join(next(values))
        if spec.endswith('s'):
            return '+'  # the only variable string in these list labels
        if spec.endswith(('x', 'X')):
            return 'FFFFFFFF'
        # Progress burst counters are uint32_t; block/frame indices are uint8_t.
        return '4294967295' if 'l' in spec or 'dropped' in expression else '255'
    return FORMAT.sub(value, fmt)


class DisplayBufferLimits(unittest.TestCase):
    def test_t5577_translated_output_fits_fixed_buffers(self):
        scenes = ROOT / 'applications/system/t5577/scenes'
        checked = 0
        for name in ('scene_restore_result.c', 'scene_sniff.c', 'scene_sniff_frames.c'):
            for args, fmt in format_calls(scenes / name):
                destination = ' '.join(args[0])
                capacity = 40 if ''.join(args[0]) == 'app->progress' else 24
                output = largest_output(fmt, args[3:])
                with self.subTest(file=name, format=fmt):
                    self.assertLess(len(output.encode('ascii')), capacity)
                checked += 1
        self.assertGreaterEqual(checked, 10)
