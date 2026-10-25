#!/usr/bin/env python3
"""Integration/quality gate on actual DONNY BOY UI patterns, without editing firmware."""
import json
import os
from pathlib import Path
import time

from local_inference import model_json
from localization import array_schema, validate
from model_runtime import lock_config


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
        report['passed'] = True
        print('Skutecne CPU overeni uspelo: ceske texty, printf, escape sekvence a rozliseni UI/technickych retezcu.', flush=True)
    finally:
        report['seconds'] = round(time.monotonic() - started, 2)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
