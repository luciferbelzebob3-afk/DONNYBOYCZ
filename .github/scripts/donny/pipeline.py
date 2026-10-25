#!/usr/bin/env python3
"""Serial, resumable stable-release pipeline. All privileged inputs are validated here."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile

from localization import (SOURCE_EXT, apply_memory, array_schema, bootstrap, digest,
                          identity, literals, model_json, reverse_localized, validate, ModelDeferred)

REPO = 'luciferbelzebob3-afk/DONNYBOYCZ'
UPSTREAM = 'DarkFlippers/unleashed-firmware'
BRANCH = 'automation/stable-release'
from model_runtime import lock_config

MODEL_BATCH_SIZE = lock_config()['batch_size']
ROOT = Path('.donny')
OUT = Path(os.environ.get('DONNY_OUTPUT', '/tmp/donny-output'))
OUT.mkdir(parents=True, exist_ok=True)
PROTECTED = ('.github/', '.translation-audit/', '.donny/', 'site/', 'README.md', 'scripts/version.py')


def run(*args, check=True, **kwargs):
    return subprocess.run(args, check=check, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kwargs)


def git(*args, **kwargs):
    return run('git', *args, **kwargs).stdout.strip()


def read(ref, path):
    result = run('git', 'show', f'{ref}:{path}', check=False)
    return result.stdout if result.returncode == 0 else None


def api(path, method='GET', data=None):
    if not path.startswith('/repos/'):
        raise ValueError('Nepovolena cesta API')
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    if os.environ.get('GH_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    request = urllib.request.Request('https://api.github.com' + path, method=method,
        data=None if data is None else json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError(f'GitHub API {method} {path}: HTTP {error.code}') from None


def load(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


def find_release(version):
    release = api(f'/repos/{REPO}/releases/tags/v{version}')
    if release is not None:
        return release
    # GitHub does not create a tag for a draft. The tag endpoint can return 404
    # even though an authenticated releases listing already contains the draft.
    for page in range(1, 11):
        batch = api(f'/repos/{REPO}/releases?per_page=100&page={page}')
        if batch is None:
            raise RuntimeError('Nelze nacist seznam vydani')
        for item in batch:
            if item['tag_name'] == 'v' + version:
                return item
        if len(batch) < 100:
            return None
    raise RuntimeError('Seznam vydani prekrocil bezpecny limit stranek')


def controls_only(source, head):
    if run('git', 'merge-base', '--is-ancestor', source, head, check=False).returncode:
        return False
    paths = git('diff', '--name-only', source, head).splitlines()
    return all(x.startswith(('.github/scripts/donny/', '.github/workflows/', '.github/tests/'))
               or x == '.donny/README.md' for x in paths)


def recover_draft(release, pending, source):
    """Finish only a complete, previously verified draft; do not upload or rebuild."""
    if release['target_commitish'] != source:
        raise RuntimeError('Koncept vydani neodpovida overenemu zdroji')
    v = pending['version']
    mandatory = {f'flipper-z-f7-full-{v}.dfu', f'flipper-z-f7-updater-{v}.dfu',
                 f'flipper-z-f7-update-{v}.tgz', f'flipper-z-f7-full-{v}.json',
                 f'DONNY-BOY-{v}-firmware-package.zip', 'sestaveni.json', 'SHA256SUMS.txt'}
    assets = {x['name']: x for x in release['assets']}
    if not mandatory.issubset(assets):
        raise RuntimeError('Koncept neni kompletni; zustava zachovan pro opakovani publikace')
    with tempfile.TemporaryDirectory() as folder:
        run('gh', 'release', 'download', 'v' + v, '--repo', REPO, '--dir', folder,
            '--pattern', 'sestaveni.json', '--pattern', 'SHA256SUMS.txt')
        metadata = load(Path(folder) / 'sestaveni.json')
        if (metadata.get('source_sha') != source or metadata.get('version') != v or
                metadata.get('upstream', {}).get('upstream_sha') != pending['upstream_sha']):
            raise RuntimeError('Metadata konceptu neodpovidaji kandidatu')
        jobs = api(f'/repos/{REPO}/actions/runs/{int(metadata["run_id"])}/jobs?per_page=100')
        if not jobs or not any(j['name'] == 'Sestavení přesného českého zdroje / build' and
                               j['conclusion'] == 'success' for j in jobs['jobs']):
            raise RuntimeError('Nelze dolozit uspesny build konceptu')
        manifest = (Path(folder) / 'SHA256SUMS.txt').read_text()
        expected = {}
        for line in manifest.splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
            if not match:
                raise RuntimeError('Neplatny manifest kontrolnich souctu')
            checksum, name = match.groups()
            if name in expected:
                raise RuntimeError('Duplicitni soubor v manifestu')
            expected[name] = checksum
        if not (mandatory - {'SHA256SUMS.txt'}).issubset(expected):
            raise RuntimeError('Neuplny manifest kontrolnich souctu')
        expected['SHA256SUMS.txt'] = hashlib.sha256((Path(folder) / 'SHA256SUMS.txt').read_bytes()).hexdigest()
        if hashlib.sha256((Path(folder) / 'sestaveni.json').read_bytes()).hexdigest() != expected['sestaveni.json']:
            raise RuntimeError('Nesouhlasi soucet metadat sestaveni')
        for name, checksum in expected.items():
            if name not in assets or assets[name]['size'] <= 0 or assets[name].get('digest') != 'sha256:' + checksum:
                raise RuntimeError('Nesouhlasi serverovy soucet konceptu: ' + name)
    result = api(f'/repos/{REPO}/releases/{release["id"]}', 'PATCH', {'draft': False, 'make_latest': 'true'})
    if not result or result['draft']:
        raise RuntimeError('Koncept se nepodarilo publikovat')
    tag = api(f'/repos/{REPO}/git/ref/tags/v{v}')
    if not tag or tag['object']['sha'] != source:
        raise RuntimeError('Publikovany tag neodpovida sestaveni')
    return result


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def output(**values):
    for k, v in values.items():
        text = str(v).lower() if isinstance(v, bool) else str(v)
        print(f'{k}={text}')
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as file:
                file.write(f'{k}={text}\n')


def commit(message, paths):
    git('add', '--', *paths)
    if run('git', 'diff', '--cached', '--quiet', check=False).returncode:
        git('commit', '-m', message)
    return git('rev-parse', 'HEAD')


def push_candidate():
    if os.environ.get('DONNY_LOCAL_REVIEW') == '1' and not os.environ.get('GITHUB_ACTIONS'):
        return
    git('push', 'origin', f'HEAD:refs/heads/{BRANCH}')


def prepare():
    if os.environ.get('GITHUB_REPOSITORY', REPO) != REPO:
        raise RuntimeError('Publikace je povolena pouze v DONNYBOYCZ')
    latest = api(f'/repos/{UPSTREAM}/releases/latest')
    if not latest or latest['draft'] or latest['prerelease']:
        raise RuntimeError('Nelze zjistit stabilni upstream vydani')
    tag = latest['tag_name']
    if not re.fullmatch(r'unlshd-[0-9]+', tag):
        raise RuntimeError('Neznamy format upstream tagu')
    git('fetch', '--no-tags', 'https://github.com/' + UPSTREAM + '.git', f'refs/tags/{tag}')
    target = git('rev-parse', 'FETCH_HEAD^{commit}')
    base = git('rev-parse', 'HEAD')
    state = load(ROOT / 'completed.json', {})
    if state.get('upstream_sha') == target:
        output(changed=False)
        return
    # An unfinished candidate reserves its version and source across retries.
    branch = api(f'/repos/{REPO}/branches/{BRANCH}')
    if branch:
        git('fetch', '--no-tags', 'origin', BRANCH)
        pending_text = read('FETCH_HEAD', '.donny/pending.json')
        pending = json.loads(pending_text) if pending_text else None
        release = find_release(pending['version']) if pending else None
        candidate_sha = git('rev-parse', 'FETCH_HEAD')
        unfinished = pending and state.get('version') != pending['version']
        can_resume = pending and (base in (pending['base_sha'], candidate_sha) or
                                  (release and not release['draft']) or controls_only(candidate_sha, base))
        if pending and (pending['upstream_sha'] == target or unfinished) and can_resume:
            deferred_text = read('FETCH_HEAD', '.donny/deferred.json')
            deferred = json.loads(deferred_text) if deferred_text else {}
            import time
            if deferred.get('retry_at', 0) > time.time():
                output(changed=False, deferred=True, retry_at=deferred['retry_at'])
                return
            if release and release['draft'] and controls_only(candidate_sha, base):
                release = recover_draft(release, pending, candidate_sha)
            git('checkout', '--detach', 'FETCH_HEAD')
            if deferred_text:
                (ROOT / 'deferred.json').unlink()
                commit('Obnovit odlozeny beh lokalniho modelu', ['.donny/deferred.json'])
                push_candidate()
            output(changed=True, sha=git('rev-parse', 'HEAD'), version=pending['version'],
                   published=bool(release and not release['draft']))
            return
        # Never destroy a candidate or silently allocate a new version after a partial publish.
        if pending and (not state or state.get('version') != pending['version']):
            raise RuntimeError('Existuje nedokonceny kandidat s jinym zakladem; zachovan pro obnovu')
    releases = api(f'/repos/{REPO}/releases?per_page=100')
    versions = [tuple(map(int, m.groups())) for r in releases
                if (m := re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)', r['tag_name']))]
    major, minor, patch = max(versions, default=(1, 0, 0))
    version = f'{major}.{minor}.{patch + 1}'
    if api(f'/repos/{REPO}/git/ref/tags/v{version}'):
        raise RuntimeError('Kandidatni tag uz existuje')
    previous = state.get('upstream_sha') or git('merge-base', base, target)
    memory = load(ROOT / 'memory.json', [])
    known = {m['id'] for m in memory}
    paths = git('diff', '--name-only', previous, base).splitlines()
    for path in paths:
        if Path(path).suffix not in SOURCE_EXT or path.startswith(PROTECTED):
            continue
        en, cz = read(previous, path), read(base, path)
        if en is None or cz is None:
            continue
        for item in bootstrap(path, en, cz):
            if item['id'] not in known:
                known.add(item['id'])
                memory.append(item)
    git('checkout', '--detach', base)
    merged = run('git', 'merge', '--no-commit', '--no-ff', target, check=False)
    conflicts = git('diff', '--name-only', '--diff-filter=U').splitlines()
    unresolved = []
    for path in conflicts:
        if path.startswith(PROTECTED):
            # Project-owned workflows/docs are never executed from incoming source.
            ours = read(base, path)
            if ours is None:
                git('rm', '-f', '--ignore-unmatch', '--', path)
            else:
                Path(path).write_text(ours)
                git('add', '--', path)
            continue
        ancestor, ours, theirs = read(previous, path), read(base, path), read(target, path)
        if None in (ancestor, ours, theirs) or Path(path).suffix not in SOURCE_EXT:
            unresolved.append(path)
            continue
        normalized = reverse_localized(path, ours, memory)
        with tempfile.TemporaryDirectory() as folder:
            files = [Path(folder) / name for name in ('ours', 'base', 'theirs')]
            for file, text in zip(files, (normalized, ancestor, theirs)):
                file.write_text(text)
            result = run('git', 'merge-file', '-p', *map(str, files), check=False)
        if result.returncode:
            unresolved.append(path)
        else:
            text, _ = apply_memory(path, result.stdout, memory)
            Path(path).write_text(text)
            git('add', '--', path)
    if unresolved or (merged.returncode and not conflicts):
        save(OUT / 'conflicts.json', {'paths': unresolved, 'stderr': merged.stderr})
        run('git', 'merge', '--abort', check=False)
        raise RuntimeError('Nevyresene konflikty: ' + ', '.join(unresolved or ['merge selhal']))
    # Restore all project-owned paths, including nonconflicting incoming changes/deletions.
    for path in PROTECTED:
        if run('git', 'ls-tree', 'HEAD', '--', path, check=False).stdout:
            git('restore', '--source=' + base, '--staged', '--worktree', '--', path)
    changed_paths = git('diff', '--cached', '--name-only').splitlines()
    reused = 0
    for path in changed_paths:
        file = Path(path)
        if file.suffix in SOURCE_EXT and file.is_file():
            text, count = apply_memory(path, file.read_text(), memory)
            file.write_text(text)
            reused += count
            git('add', '--', path)
    if Path('.git/MERGE_HEAD').exists():
        git('commit', '-m', f'Prevzit stabilni Unleashed {tag} se zachovanim ceskych textu')
    pending = dict(version=version, base_sha=base, upstream_sha=target, previous_upstream_sha=previous,
                   upstream_tag=tag, upstream_release_id=latest['id'],
                   upstream_url=latest['html_url'], reused=reused,
                   upstream_changes=git('log', '--format=%s', f'{previous}..{target}').splitlines())
    save(ROOT / 'memory.json', memory)
    save(ROOT / 'pending.json', pending)
    sha = commit(f'Pripravit DONNY BOY CZ {version}', ['.donny'])
    push_candidate()
    output(changed=True, sha=sha, version=version, published=False)


def analyze():
    p = load(ROOT / 'pending.json')
    if load(ROOT / 'translation-report.json', {}).get('upstream_sha') == p['upstream_sha']:
        output(sha=git('rev-parse', 'HEAD'))
        return
    memory = load(ROOT / 'memory.json', [])
    reviewed = load(ROOT / 'reviewed.json', {})
    items = []
    paths = git('diff', '--name-only', '--diff-filter=ACMRT', p['previous_upstream_sha'], p['upstream_sha']).splitlines()
    for path in paths:
        if Path(path).suffix not in SOURCE_EXT or path.startswith(PROTECTED) or '/tests/' in path or '/unit_tests/' in path:
            continue
        before, after = read(p['previous_upstream_sha'], path) or '', read(p['upstream_sha'], path)
        if after is None or not Path(path).is_file():
            continue
        from collections import Counter
        old = Counter(x['literal'] for x in literals(before))
        current = Path(path).read_text()
        for item in literals(after):
            if old[item['literal']]:
                old[item['literal']] -= 1
                continue
            literal = item['literal']
            if not re.search('[A-Za-z]', literal) or literal not in current:
                continue
            start = max(0, after.rfind('\n', 0, item['start']) - 500)
            end = min(len(after), after.find('\n', item['end']) + 500)
            record = dict(id=identity(path, item), path=path, source=literal, context=item['context'],
                          code=after[start:end], file_hash=digest(current), kind='unknown', limit=None)
            # Include every new source literal; the classifier must account for every item.
            if record['id'] in reviewed:
                record.update(reviewed[record['id']])
            items.append(record)
    unknown = [x for x in items if x['kind'] == 'unknown']
    save(OUT / 'unclassified.json', unknown)
    for offset in range(0, len(unknown), MODEL_BATCH_SIZE):
        batch = unknown[offset:offset + MODEL_BATCH_SIZE]
        answer = model_json(
            'Classify EACH C/C++/JS/Flipper manifest literal as ui, technical or ambiguous. '
            'UI includes indirect flows via snprintf, status variables, render helpers, arrays and app labels. '
            'Trace the provided context. Protocol names, file keys, logs, include paths are technical. '
            'Use ambiguous if the display flow or safe maximum byte length cannot be established. '
            'limit is the proven safe maximum ASCII bytes excluding NUL (account for buffer, formatting and screen); '
            'use null for technical or ambiguous. Return exact ids and a brief reason.',
            batch, array_schema({'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': ['ui', 'technical', 'ambiguous']},
                'limit': {'type': ['integer', 'null']}, 'reason': {'type': 'string'}}))['items']
        if len(answer) != len(batch) or {x['id'] for x in answer} != {x['id'] for x in batch}:
            raise RuntimeError('Neuplna klasifikace')
        by_id = {x['id']: x for x in answer}
        for item in batch:
            item.update({k: v for k, v in by_id[item['id']].items() if k != 'id'})
    save(ROOT / 'analysis.json', dict(upstream_sha=p['upstream_sha'], source_sha=git('rev-parse', 'HEAD'), items=items))
    ambiguous = [x for x in items if x['kind'] == 'ambiguous' or (x['kind'] == 'ui' and not isinstance(x.get('limit'), int))]
    save(OUT / 'analysis.json', load(ROOT / 'analysis.json'))
    if ambiguous:
        raise RuntimeError(f'Je nutne posoudit {len(ambiguous)} nejasnych textu')
    paths = ['.donny/analysis.json']
    if (ROOT / 'model-cache.json').exists():
        paths.append('.donny/model-cache.json')
    sha = commit('Analyzovat nove texty stabilniho vydani', paths)
    push_candidate()
    output(sha=sha)


def translate():
    pending = load(ROOT / 'pending.json')
    report = load(ROOT / 'translation-report.json', {})
    if report.get('upstream_sha') == pending['upstream_sha']:
        output(sha=git('rev-parse', 'HEAD'))
        return
    analysis = load(ROOT / 'analysis.json')
    if analysis['upstream_sha'] != pending['upstream_sha']:
        raise RuntimeError('Analyza neodpovida upstream SHA')
    memory = load(ROOT / 'memory.json', [])
    known = {x['id']: x for x in memory}
    items = [x for x in analysis['items'] if x['kind'] == 'ui']
    if any(x['kind'] not in ('ui', 'technical') for x in analysis['items']):
        raise RuntimeError('Analyza obsahuje nevyresene polozky')
    reviewed = load(ROOT / 'reviewed.json', {})
    translations = {}
    todo = []
    for x in items:
        saved = known.get(x['id']) or reviewed.get(x['id'], {})
        if saved.get('translation'):
            translations[x['id']] = saved['translation']
        else:
            todo.append(x)
    for offset in range(0, len(todo), MODEL_BATCH_SIZE):
        batch = todo[offset:offset + MODEL_BATCH_SIZE]
        result = model_json('Translate EACH approved UI literal into concise Czech WITHOUT diacritics. '
            'Return ONLY its exact id and complete quoted C literal. Preserve format parameters and ALL escape '
            'sequences in their original order. Respect limit bytes excluding NUL. Never change code.', batch,
            array_schema({'id': {'type': 'string'}, 'translation': {'type': 'string'}}))['items']
        if len(result) != len(batch) or {x['id'] for x in result} != {x['id'] for x in batch}:
            raise RuntimeError('Neuplny preklad')
        translations.update({x['id']: x['translation'] for x in result})
    # Validate every file and edit before writing any source file.
    updates = {}
    for path in sorted({x['path'] for x in items}):
        text = Path(path).read_text()
        subset = [x for x in items if x['path'] == path]
        if any(x['file_hash'] != digest(text) for x in subset):
            raise RuntimeError('Zdroj se od analyzy zmenil: ' + path)
        spans = {identity(path, x): x for x in literals(text)}
        edits = []
        for item in subset:
            target = translations[item['id']]
            validate(item['source'], target, item['limit'])
            occurrence = spans.get(item['id'])
            if not occurrence or occurrence['literal'] != item['source']:
                raise RuntimeError('Nelze jednoznacne najit literal: ' + path + ' ' + item['source'])
            edits.append((occurrence['start'], occurrence['end'], target))
            known[item['id']] = {k: item[k] for k in ('id', 'path', 'context')}
            known[item['id']].update(source=item['source'], translation=target, origin='stable-release')
        for start, end, target in sorted(edits, reverse=True):
            text = text[:start] + target + text[end:]
        updates[path] = text
    for path, text in updates.items():
        Path(path).write_text(text)
    save(ROOT / 'memory.json', list(known.values()))
    report = dict(upstream_sha=pending['upstream_sha'], new=len(items), translated=len(todo),
                  reused=len(items)-len(todo)+pending['reused'], technical=len(analysis['items'])-len(items), ambiguous=0, errors=0)
    save(ROOT / 'translation-report.json', report)
    sha = commit('Prelozit nove texty do cestiny bez diakritiky', [*updates, '.donny'])
    push_candidate()
    output(sha=sha)


def package():
    p = load(ROOT / 'pending.json')
    v = p['version']
    source = git('rev-parse', 'HEAD')
    dist = Path('dist/f7-C')
    assets = Path('release-assets')
    assets.mkdir(exist_ok=True)
    names = [f'flipper-z-f7-full-{v}.dfu', f'flipper-z-f7-updater-{v}.dfu',
             f'flipper-z-f7-update-{v}.tgz', f'flipper-z-f7-full-{v}.json']
    for name in names:
        file = dist / name
        if not file.is_file() or not file.stat().st_size:
            raise RuntimeError('Chybi povinny vystup: ' + name)
        shutil.copy2(file, assets / name)
    metadata = load(dist / names[-1])
    if metadata.get('firmware_version') != v or not source.startswith(metadata.get('firmware_commit', 'INVALID')):
        raise RuntimeError('Metadata sestaveni neodpovidaji verzi nebo SHA')
    with tarfile.open(dist / names[2]) as archive:
        entries = archive.getnames()
        if not any(x.endswith('update.fuf') for x in entries):
            raise RuntimeError('Aktualizacni balik neobsahuje update.fuf')
    sdk = dist / f'flipper-z-f7-sdk-{v}.zip'
    if sdk.is_file():
        with zipfile.ZipFile(sdk) as archive:
            if archive.testzip():
                raise RuntimeError('Poskozeny SDK archiv')
        shutil.copy2(sdk, assets / sdk.name)
    save(assets / 'sestaveni.json', dict(version=v, source_sha=source, upstream=p,
        translation=load(ROOT / 'translation-report.json'), run_id=os.environ.get('GITHUB_RUN_ID')))
    shutil.make_archive(str(assets / f'DONNY-BOY-{v}-firmware-package'), 'zip', dist)
    checksums = ''.join(hashlib.sha256(x.read_bytes()).hexdigest() + '  ' + x.name + '\n'
                        for x in sorted(assets.iterdir()) if x.name != 'SHA256SUMS.txt')
    (assets / 'SHA256SUMS.txt').write_text(checksums)
    output(sha=source)


def publish():
    p = load(ROOT / 'pending.json')
    v, source = p['version'], git('rev-parse', 'HEAD')
    release = find_release(v)
    if release and not release['draft']:
        raise RuntimeError('Publikovane vydani se nesmi prepsat; pouzij obnovu webu')
    branch = api(f'/repos/{REPO}/branches/dev')
    if branch['commit']['sha'] not in (p['base_sha'], source):
        raise RuntimeError('Vetvi dev pribyly zmeny. Kandidat zachovan, je nutna nova integrace a build.')
    # Fast-forward to exactly the compiled source; a concurrent update is rejected by Git.
    git('push', 'origin', f'{source}:refs/heads/dev')
    report = load(ROOT / 'translation-report.json')
    notes = (f'# DONNY BOY CZ {v}\n\n'
        f'Základ: [{p["upstream_tag"]}]({p["upstream_url"]}).\n\n'
        f'Zdroj sestavení: `{source}`. Nové texty: {report["new"]}; '
        f'znovu použité překlady: {report["reused"]}; nevyřešené: 0.\n\n'
        '## Převzaté změny\n\n' + '\n'.join('- ' + x for x in load(ROOT / 'release-changes-cs.json', [])) + '\n\n'
        '## Instalace a ověření\n\n'
        'Pro běžnou aktualizaci použij aktualizační balíček `.tgz` přes qFlipper nebo aplikaci Flipper. '
        'DFU slouží pro obnovu, SDK pro vývoj aplikací. Před aktualizací zálohuj data.\n\n'
        'Kompilace, povinné soubory, verze, zdrojový commit a struktura balíčků byly ověřeny. '
        'Kontrolní součty jsou v `SHA256SUMS.txt`, podrobnosti v `sestaveni.json`. '
        'Tato nová verze zatím nebyla fyzicky otestována na zařízení. '
        'Dřívější fyzický test se týkal verze 1.0.1. Překlad celého staršího firmwaru zůstává průběžnou prací.\n')
    (OUT / 'release-notes.md').write_text(notes)
    # Draft assets can be recovered, but published releases/tags are immutable here.
    if release is None:
        run('gh', 'release', 'create', f'v{v}', '--repo', REPO, '--target', source,
            '--title', f'DONNY BOY CZ {v}', '--notes-file', str(OUT / 'release-notes.md'), '--draft')
    else:
        if release['target_commitish'] != source:
            raise RuntimeError('Koncept vydani ukazuje na jiny zdroj')
    files = [str(x) for x in sorted(Path('release-assets').iterdir())]
    run('gh', 'release', 'upload', f'v{v}', '--repo', REPO, '--clobber', *files)
    release = find_release(v)
    remote = {a['name']: a for a in release['assets']}
    for file in files:
        local = Path(file)
        asset = remote.get(local.name)
        if not asset or asset['size'] != local.stat().st_size:
            raise RuntimeError('Neuplne nahrane soubory vydani')
        if asset.get('digest') != 'sha256:' + hashlib.sha256(local.read_bytes()).hexdigest():
            raise RuntimeError('Nesouhlasi serverovy SHA-256: ' + local.name)
    run('gh', 'release', 'edit', f'v{v}', '--repo', REPO, '--draft=false', '--latest')
    output(version=v, sha=source)


def web():
    p = load(ROOT / 'pending.json')
    v = p['version']
    release = api(f'/repos/{REPO}/releases/tags/v{v}')
    if not release or release['draft']:
        raise RuntimeError('Vydani dosud neni publikovane')
    source = git('rev-parse', 'HEAD')
    remote_tag = api(f'/repos/{REPO}/git/ref/tags/v{v}')
    if remote_tag['object']['sha'] != source:
        raise RuntimeError('Web musi vychazet ze skutecne vydaneho zdroje')
    git('fetch', 'origin', 'dev')
    git('checkout', '--detach', 'FETCH_HEAD')
    metadata = dict(version=v, source_sha=source, upstream_tag=p['upstream_tag'],
                    release_url=release['html_url'], published_at=release['published_at'],
                    assets=[dict(name=a['name'], url=a['browser_download_url'], size=a['size']) for a in release['assets']],
                    physical_test=False)
    save('site/release.json', metadata)
    # Explicit template slots keep historical release references intact.
    for template, destination in [('README.md.in', 'README.md'), ('index.html.in', 'site/index.html')]:
        text = (ROOT / 'templates' / template).read_text()
        for key, value in {'VERSION': v, 'RELEASE_URL': release['html_url'], 'SOURCE_SHA': source,
                           'UPSTREAM_TAG': p['upstream_tag']}.items():
            text = text.replace('{{' + key + '}}', value)
        if re.search(r'\{\{[A-Z_]+\}\}', text):
            raise RuntimeError('Nenahrazena promenna sablony')
        existing = Path(destination).read_text()
        original = read(source, destination)
        if existing not in (original, text):
            raise RuntimeError('Web ma novejsi rucni zmeny, ktere nelze prepsat: ' + destination)
        Path(destination).write_text(text)
    run(sys.executable, '.github/scripts/bump_issue_template_version.py', 'v' + v)
    sha = commit(f'Aktualizovat web a odkazy pro DONNY BOY CZ {v}',
                 ['README.md', 'site', '.github/ISSUE_TEMPLATE/01_bug_report.yml'])
    git('push', 'origin', 'HEAD:refs/heads/dev')
    output(sha=sha, version=v)


def verify_web():
    p = load(ROOT / 'pending.json')
    v = p['version']
    url = 'https://luciferbelzebob3-afk.github.io/DONNYBOYCZ/'
    import time
    for attempt in range(12):
        try:
            with urllib.request.urlopen(url + 'release.json?run=' + os.environ.get('GITHUB_RUN_ID', 'local'), timeout=30) as response:
                served = json.load(response)
            with urllib.request.urlopen(url + '?run=' + os.environ.get('GITHUB_RUN_ID', 'local'), timeout=30) as response:
                index = response.read().decode()
            if served['version'] == v and f'VERZE {v}' in index and served['release_url'] in index:
                for asset in served['assets']:
                    req = urllib.request.Request(asset['url'], method='HEAD')
                    with urllib.request.urlopen(req, timeout=30) as response:
                        if response.status != 200:
                            raise RuntimeError('Odkaz na soubor neni dostupny')
                break
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(10)
    else:
        raise RuntimeError('Zivy web nebo odkazy neodpovidaji publikovanemu vydani. Opakuj pouze obnovu webu.')
    git('fetch', 'origin', 'dev')
    git('checkout', '--detach', 'FETCH_HEAD')
    save(ROOT / 'completed.json', dict(upstream_sha=p['upstream_sha'], upstream_tag=p['upstream_tag'],
                                      version=v, website=url, run_id=os.environ.get('GITHUB_RUN_ID')))
    commit(f'Potvrdit dokonceni vydani {v} a nasazeni webu', ['.donny/completed.json'])
    git('push', 'origin', 'HEAD:refs/heads/dev')
    output(completed=True, version=v)


def notes():
    p = load(ROOT / 'pending.json')
    # Human reviewed summaries can ship with the source; unseen releases require full model output.
    reviewed = load(ROOT / 'upstream-notes-cs.json', {})
    changes = reviewed.get(p['upstream_sha'])
    if not changes:
        changes = model_json('Summarize the supplied upstream commit subjects in Czech with diacritics. '
            'Return at most 12 concrete change descriptions. Do not invent changes or tests.',
            p['upstream_changes'], array_schema({'change': {'type': 'string'}}))['items']
        changes = [x['change'] for x in changes]
    save(ROOT / 'release-changes-cs.json', changes)
    paths = ['.donny/release-changes-cs.json']
    if (ROOT / 'model-cache.json').exists():
        paths.append('.donny/model-cache.json')
    sha = commit('Pripravit cesky prehled prevzatych zmen', paths)
    push_candidate()
    output(sha=sha)


def checkpoint_model(stage, deferred=None):
    """Preserve valid completed batches even when a later batch hits a quota."""
    if stage not in ('analyze', 'translate', 'notes') or not (ROOT / 'pending.json').exists():
        return
    paths = []
    if (ROOT / 'model-cache.json').exists():
        paths.append('.donny/model-cache.json')
    if deferred:
        save(ROOT / 'deferred.json', dict(stage=stage, retry_at=deferred.retry_at))
        paths.append('.donny/deferred.json')
    if paths:
        sha = commit('Ulozit hotove davky a odlozeni lokalniho modelu', paths)
        push_candidate()
        output(sha=sha, deferred=bool(deferred))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'analyze', 'translate', 'notes', 'package', 'publish', 'web', 'verify_web'])
    stage = parser.parse_args().stage
    try:
        globals()[stage]()
    except ModelDeferred as exc:
        checkpoint_model(stage, exc)
        print(f'::warning::{exc}', file=sys.stderr)
        sys.exit(75)
    except Exception as exc:
        checkpoint_model(stage)
        print(f'::error::{exc}', file=sys.stderr)
        raise
