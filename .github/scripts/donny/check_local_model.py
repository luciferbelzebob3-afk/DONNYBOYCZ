#!/usr/bin/env python3
"""Integration/quality gate on actual DONNY BOY UI patterns, without editing firmware."""
import json
import os
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from local_inference import model_json
from localization import array_schema, validate, digest, identity, literals, tokens
from model_runtime import lock_config
import pipeline


def main():
    started = time.monotonic()
    report = {'model': lock_config(), 'passed': False, 'translations': [], 'classification': []}
    output = Path(os.environ.get('LOCAL_MODEL_REPORT', '/tmp/donny-local-model-report.json'))
    try:
        samples = [
            {'id': 'save', 'source': '"Save"', 'limit': 10, 'context': 'elements_button_center(canvas, "Save");'},
            {'id': 'cancel', 'source': '"Cancel"', 'limit': 10, 'context': 'elements_button_left(canvas, "Cancel");'},
            {'id': 'unknown', 'source': '"Unknown"', 'limit': 12, 'context': 'popup_set_header(popup, "Unknown", 64, 12, AlignCenter, AlignCenter);'},
            {'id': 'value', 'source': '"Value: %lu\\n"', 'limit': 24, 'context': 'char buf[32]; snprintf(buf, sizeof(buf), "Value: %lu\\n", value); canvas_draw_str(canvas, 0, 20, buf);'},
        ]
        answer = model_json('Translate EACH approved UI literal into concise native Czech WITHOUT diacritics. '
            'Return exact ids and complete double-quoted C literals. Preserve printf parameters and ALL escape '
            'sequences in order. Respect limit bytes excluding NUL.', samples,
            array_schema({'id': {'type': 'string'}, 'translation': {'type': 'string'}}))['items']
        mapping = {x['id']: x['translation'] for x in answer}
        if len(answer) != len(samples) or set(mapping) != {x['id'] for x in samples}:
            raise RuntimeError('Model nevratil vsechny vzorky presne jednou.')
        accepted = {'save': {'ulozit', 'uloz'}, 'cancel': {'zrusit', 'zrus', 'storno'},
                    'unknown': {'neznamy', 'nezname', 'neznam', 'neznamo'}}
        for sample in samples:
            target = mapping[sample['id']]
            validate(sample['source'], target, sample['limit'])
            report['translations'].append(dict(source=sample['source'], translation=target))
            if sample['id'] in accepted and target[1:-1].lower() not in accepted[sample['id']]:
                raise RuntimeError('Cesky vyznam zakladniho UI textu neprosel kontrolou: ' + sample['id'])
            if sample['id'] == 'value' and not any(x in target.lower() for x in ('hodnot', 'hodn.')):
                raise RuntimeError('Cesky vyznam formatovaneho textu neprosel kontrolou.')
        cases = [
            {'id': 'visible-menu', 'source': '"Settings"', 'code': 'submenu_add_item(submenu, "Settings", SettingsIndex, callback, app); // One visible 21-character menu line.'},
            {'id': 'internal-log', 'source': '"Write failed"', 'code': 'FURI_LOG_E(TAG, "Write failed");'},
            {'id': 'file-key', 'source': '"Protocol"', 'code': 'flipper_format_write_string_cstr(ff, "Protocol", protocol_name);'},
            {'id': 'serialized-type', 'source': '"Unknown"', 'code': 'features.type_name = "Unknown"; flipper_format_write_string_cstr(ff, TEXKOM_TYPE_KEY, features.type_name);'},
        ]
        classified = model_json('Classify EACH source literal as ui, technical or ambiguous. '
            'Only user-visible natural language is ui. Internal logs, file keys and serialized protocol '
            'values are technical, even when they can also appear on a display. Trace each provided code '
            'snippet; do not translate code or identifiers. Return exact ids and a brief reason.', cases,
            array_schema({'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['ui', 'technical', 'ambiguous']},
                          'reason': {'type': 'string'}}))['items']
        report['classification'] = classified
        kinds = {x['id']: x['kind'] for x in classified}
        expected = {'visible-menu': 'ui', 'internal-log': 'technical', 'file-key': 'technical', 'serialized-type': 'technical'}
        if len(classified) != len(expected) or kinds != expected:
            raise RuntimeError('Model nedokazal oddelit UI od logu a serializovanych hodnot.')
        # Exercise the real guarded translation stage with real inference, but a
        # disposable source fixture and disabled Git writes (job has read-only access).
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'scene.c'
            before = ('void draw(void) { popup_set_text(popup, "Read failed", 0, 0, AlignLeft, AlignTop); '
                      'dialog_set_text(dialog, "No installer code\\r\\n"); '
                      'byte_input_set_header_text(input, "Enter IC in hex"); '
                      'FURI_LOG_E(TAG, "Write failed"); '
                      'flipper_format_write_string_cstr(ff, "Protocol", protocol_name); }\n')
            source.write_text(before)
            entries = []
            for literal in literals(before)[:3]:
                entries.append(dict(id=identity(str(source), literal), path=str(source),
                                    source=literal['literal'], context=literal['context'],
                                    file_hash=digest(before), kind='ui', limit=24))
            (root / 'pending.json').write_text(json.dumps(dict(upstream_sha='test-upstream', reused=0)))
            (root / 'analysis.json').write_text(json.dumps(dict(upstream_sha='test-upstream', items=entries)))
            with patch.object(pipeline, 'ROOT', root), patch.object(pipeline, 'commit', return_value='fixture-only'), \
                    patch.object(pipeline, 'push_candidate'), patch.object(pipeline, 'output'):
                pipeline.translate()
            after = source.read_text()
            shape = lambda text: ['<TEXT>' if t[0].startswith('"') else t[0] for t in tokens(text)]
            if shape(before) != shape(after):
                raise RuntimeError('Aplikace prekladu zasahla technicky kod fixture.')
            if '"Write failed"' not in after or '"Protocol"' not in after:
                raise RuntimeError('Aplikace prekladu zasahla log nebo formatovy klic.')
            translated = [x['literal'] for x in literals(after)[:3]]
            for original, target in zip(entries, translated):
                validate(original['source'], target, original['limit'])
                if target == original['source']:
                    raise RuntimeError('Model ponechal novy UI text v anglictine.')
            if not ('cten' in translated[0].lower() and any(x in translated[0].lower() for x in ('selh', 'chyb', 'nepoda'))):
                raise RuntimeError('Cesky vyznam chyboveho hlaseni neprosel kontrolou.')
            if not ('kod' in translated[1].lower() and any(x in translated[1].lower() for x in ('chybi', 'zadny', 'neni', 'bez'))):
                raise RuntimeError('Cesky vyznam chybejiciho instalacniho kodu neprosel kontrolou.')
            if not ('IC' in translated[2] and any(x in translated[2].lower() for x in ('zadej', 'vloz', 'zadat'))):
                raise RuntimeError('Cesky vyznam hlavicky hex vstupu neprosel kontrolou.')
            translated_report = json.loads((root / 'translation-report.json').read_text())
            if translated_report['translated'] != 3 or translated_report['errors']:
                raise RuntimeError('Pipeline nevyhodnotila spravne pocet prekladu.')
            report['pipeline_fixture'] = dict(translations=translated, technical_code_unchanged=True,
                                               git_writes=False, report=translated_report)
        report['passed'] = True
        print('Skutecne CPU overeni uspelo: ceske texty, printf, escape sekvence a rozliseni UI/technickych retezcu.', flush=True)
    finally:
        report['seconds'] = round(time.monotonic() - started, 2)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
