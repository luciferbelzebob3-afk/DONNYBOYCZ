import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/donny'))
from localization import bootstrap, reverse_localized, apply_memory, validate, model_json, literals, identity, digest
import pipeline

class LocalizationTests(unittest.TestCase):
    def test_translation_only_merge_preserves_new_logic(self):
        old='void enter(){header("Enter seed"); save("Save");}\n'
        cz='void enter(){header("Zadejte seed"); save("Ulozit");}\n'
        new='void enter(){if(flag) header("Enter IC"); else header("Enter seed"); save("Save");}\n'
        memory=bootstrap('scene.c',old,cz)
        self.assertEqual(reverse_localized('scene.c',cz,memory),old)
        result,count=apply_memory('scene.c',new,memory)
        self.assertIn('if(flag)',result)
        self.assertIn('"Enter IC"',result)
        self.assertIn('"Zadejte seed"',result)
        self.assertIn('"Ulozit"',result)
        self.assertEqual(count,2)

    def test_conflicting_functional_changes_stay_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            files=[Path(directory)/str(i) for i in range(3)]
            for p,text in zip(files,['void f(){new_a();}\n','void f(){old();}\n','void f(){new_b();}\n']):
                p.write_text(text)
            p=subprocess.run(['git','merge-file','-p',*map(str,files)],capture_output=True)
            self.assertEqual(p.returncode,1)

    def test_placeholder_escape_ascii_and_length_guards(self):
        validate('"Value: %lu\\n"','"Hodn.: %lu\\n"',20)
        for value in ['"Hodn.: %u\\n"','"Hodn.: %lu"','"Číslo: %lu\\n"','"bad"; delete(); ""']:
            with self.assertRaises(ValueError): validate('"Value: %lu\\n"',value,20)
        with self.assertRaises(ValueError): validate('"Save"','"Ulozit"',5)
        with self.assertRaises(ValueError): validate('"Save"','"x\\q"',20)

    def test_comments_and_character_literals_are_not_ui(self):
        values=[x['literal'] for x in literals('/* "fake" */ char c=\'x\'; puts("real"); // "fake2"')]
        self.assertEqual(values,['"real"'])

    def test_missing_runtime_defers_without_api_keys(self):
        import local_inference
        from model_runtime import RuntimeUnavailable
        from localization import ModelDeferred
        with patch.dict(os.environ,{},clear=True),patch.object(local_inference,'ensure_server',side_effect=RuntimeUnavailable('not ready')):
            with self.assertRaises(ModelDeferred):model_json('classify',[],{})

    def test_no_candidates_succeeds_without_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            pending=dict(upstream_sha='abc',reused=0)
            (root/'pending.json').write_text(json.dumps(pending))
            (root/'analysis.json').write_text(json.dumps(dict(upstream_sha='abc',items=[])))
            with patch.object(pipeline,'ROOT',root),patch.object(pipeline,'git',return_value='abc'),patch.object(pipeline,'commit',return_value='abc'),patch.object(pipeline,'push_candidate'),patch.object(pipeline,'model_json',side_effect=AssertionError('model must not run')):
                pipeline.translate()
                report=json.loads((root/'translation-report.json').read_text())
                self.assertEqual(report['new'],0)
                pipeline.translate()  # Idempotent retry.
                self.assertEqual(json.loads((root/'translation-report.json').read_text()),report)

    def test_stale_source_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'scene.c';source.write_text('puts("Save");')
            item=literals(source.read_text())[0]
            entry=dict(id=identity(str(source),item),path=str(source),source=item['literal'],context=item['context'],file_hash='wrong',kind='ui',limit=20)
            (root/'pending.json').write_text(json.dumps(dict(upstream_sha='abc',reused=0)))
            (root/'analysis.json').write_text(json.dumps(dict(upstream_sha='abc',items=[entry])))
            (root/'reviewed.json').write_text(json.dumps({entry['id']:{'translation':'"Ulozit"'}}))
            with patch.object(pipeline,'ROOT',root),patch.object(pipeline,'git',return_value='abc'):
                with self.assertRaises(RuntimeError): pipeline.translate()
            self.assertEqual(source.read_text(),'puts("Save");')

    def test_development_release_does_not_reimport_included_stable(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'completed.json').write_text(json.dumps(dict(upstream_sha='newer-dev', version='1.0.5')))
            (root / 'pending.json').write_text(json.dumps(dict(version='1.0.5')))
            def git(*args, **kwargs):
                return 'stable' if args == ('rev-parse', 'FETCH_HEAD^{commit}') else 'released-source'
            latest = dict(tag_name='unlshd-094', draft=False, prerelease=False)
            with patch.object(pipeline, 'ROOT', root), patch.object(pipeline, 'git', side_effect=git), patch.object(pipeline, 'api', return_value=latest) as api, patch.object(pipeline, 'run', return_value=SimpleNamespace(returncode=0)), patch.object(pipeline, 'output') as out:
                pipeline.prepare()
                out.assert_called_once_with(changed=False, already_included=True)
                self.assertEqual(api.call_count, 1)

    def test_older_automation_candidate_cannot_replace_newer_release(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'completed.json').write_text(json.dumps(dict(upstream_sha='dev', version='1.0.5')))
            (root / 'pending.json').write_text(json.dumps(dict(version='1.0.5')))
            older = json.dumps(dict(version='1.0.4', upstream_sha='old-stable'))
            def api(path):
                if path.endswith('/releases/latest'):
                    return dict(tag_name='unlshd-095', draft=False, prerelease=False)
                if '/branches/' in path:
                    return dict(commit=dict(sha='old-candidate'))
                raise RuntimeError('fresh release lookup reached')
            with patch.object(pipeline, 'ROOT', root), patch.object(pipeline, 'git', return_value='new-stable'), patch.object(pipeline, 'run', return_value=SimpleNamespace(returncode=1)), patch.object(pipeline, 'api', side_effect=api), patch.object(pipeline, 'read', return_value=older), patch.object(pipeline, 'find_release', side_effect=AssertionError('old release must not resume')):
                # Stop at the next read-only phase, before any integration or version reservation.
                with self.assertRaisesRegex(RuntimeError, 'fresh release lookup reached'):
                    pipeline.prepare()

    def test_completed_release_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'completed.json').write_text(json.dumps(dict(upstream_sha='upstream')))
            def git(*args,**kwargs):
                return 'upstream' if args==('rev-parse','FETCH_HEAD^{commit}') else 'base'
            with patch.object(pipeline,'ROOT',root),patch.object(pipeline,'git',side_effect=git),patch.object(pipeline,'api',return_value=dict(tag_name='unlshd-094',draft=False,prerelease=False)),patch.object(pipeline,'output') as out,patch.object(pipeline,'push_candidate') as push:
                pipeline.prepare()
                out.assert_called_once_with(changed=False)
                push.assert_not_called()

    def test_published_release_resumes_only_website_after_dev_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            pending=dict(version='1.0.2',upstream_sha='upstream',base_sha='old-base')
            def git(*args,**kwargs):
                if args==('rev-parse','FETCH_HEAD^{commit}'): return 'upstream'
                if args==('rev-parse','HEAD'): return 'web-commit'
                if args==('rev-parse','FETCH_HEAD'): return 'compiled-source'
                return ''
            def api(path,*args,**kwargs):
                if path.endswith('/releases/latest'):return dict(tag_name='unlshd-094',draft=False,prerelease=False)
                if '/branches/' in path:return dict(commit=dict(sha='compiled-source'))
                if '/releases/tags/' in path:return dict(draft=False)
                raise AssertionError(path)
            with patch.object(pipeline,'ROOT',Path(directory)),patch.object(pipeline,'git',side_effect=git),patch.object(pipeline,'api',side_effect=api),patch.object(pipeline,'read',side_effect=lambda ref,path: json.dumps(pending) if path=='.donny/pending.json' else None),patch.object(pipeline,'output') as out,patch.object(pipeline,'push_candidate') as push:
                pipeline.prepare()
                out.assert_called_once_with(changed=True,sha='web-commit',version='1.0.2',published=True)
                push.assert_not_called()

    def test_published_assets_are_immutable(self):
        with patch.object(pipeline,'load',return_value=dict(version='1.0.2')),patch.object(pipeline,'git',return_value='compiled'),patch.object(pipeline,'api',return_value=dict(draft=False)),patch.object(pipeline,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'nesmi prepsat'): pipeline.publish()
            run.assert_not_called()

    def test_missing_build_output_stops_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            previous=os.getcwd()
            try:
                os.chdir(directory)
                with patch.object(pipeline,'load',return_value=dict(version='1.0.2')),patch.object(pipeline,'git',return_value='compiled'):
                    with self.assertRaisesRegex(RuntimeError,'Chybi povinny vystup'):pipeline.package()
                self.assertFalse(Path('release-assets/SHA256SUMS.txt').exists())
            finally: os.chdir(previous)

    def test_reviewed_unknown_protocol_type_stays_serialized_english(self):
        p=Path(__file__).resolve().parents[2]/'.donny/reviewed.json'
        if p.exists():
            records=json.loads(p.read_text())
            self.assertTrue(any('type_name' in x.get('reason','') and x['kind']=='technical' for x in records.values()))

    def test_draft_can_exist_before_tag(self):
        draft=dict(id=123,tag_name='v1.0.2',draft=True)
        with patch.object(pipeline,'api',side_effect=[None,[draft]]) as api:
            self.assertEqual(pipeline.find_release('1.0.2'),draft)
            self.assertIn('/releases?per_page=100',api.call_args.args[0])

    def test_incomplete_draft_is_not_published(self):
        with patch.object(pipeline,'api') as api:
            with self.assertRaisesRegex(RuntimeError,'neni kompletni'):
                pipeline.recover_draft(dict(target_commitish='source',assets=[]),dict(version='1.0.2'),'source')
            api.assert_not_called()

    def test_complete_draft_recovers_without_build_or_upload(self):
        import hashlib
        v='1.0.2'
        pending=dict(version=v,upstream_sha='upstream')
        metadata=json.dumps(dict(source_sha='source',version=v,upstream=pending,run_id=42)).encode()
        names=[f'flipper-z-f7-full-{v}.dfu',f'flipper-z-f7-updater-{v}.dfu',f'flipper-z-f7-update-{v}.tgz',f'flipper-z-f7-full-{v}.json',f'DONNY-BOY-{v}-firmware-package.zip']
        contents={name:b'build output' for name in names}
        contents['sestaveni.json']=metadata
        contents['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in contents.items()).encode()
        draft=dict(id=123,draft=True,target_commitish='source',assets=[dict(name=n,size=len(b),digest='sha256:'+hashlib.sha256(b).hexdigest()) for n,b in contents.items()])
        def run(*args,**kwargs):
            self.assertEqual(args[:3],('gh','release','download'))
            folder=Path(args[args.index('--dir')+1])
            for name in ('sestaveni.json','SHA256SUMS.txt'): (folder/name).write_bytes(contents[name])
        def api(path,method='GET',data=None):
            if '/actions/runs/' in path:return dict(jobs=[dict(name='Sestavení přesného českého zdroje / build',conclusion='success')])
            if method=='PATCH':return dict(draft=False)
            if '/git/ref/' in path:return dict(object=dict(sha='source'))
            raise AssertionError(path)
        with patch.object(pipeline,'run',side_effect=run) as run_mock,patch.object(pipeline,'api',side_effect=api):
            result=pipeline.recover_draft(draft,pending,'source')
            self.assertFalse(result['draft'])
            self.assertEqual(run_mock.call_count,1)

class PrepareCandidateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(tmp.name)
        self.root = Path('.donny')
        self.root.mkdir()
        self.g('init', '-q')
        self.g('config', 'user.name', 'Test')
        self.g('config', 'user.email', 'test@example.invalid')
        Path('firmware.c').write_text('int value = 1;\n')
        self.upstream = self.commit('Upstream release')
        pipeline.save(self.root / 'completed.json', {'version': '1.0.5', 'upstream_sha': self.upstream})
        self.base = self.commit('Released DONNY BOY')
        # The upstream stable tag is on a release branch, not an ancestor of dev.
        self.g('checkout', '--detach', self.upstream)
        self.g('commit', '--allow-empty', '-m', 'Stable upstream tag')
        self.stable = self.g('rev-parse', 'HEAD')
        self.latest = self.stable
        self.tag = 'unlshd-095'
        self.release = None

    @staticmethod
    def g(*args):
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.PIPE).strip()

    def commit(self, message):
        self.g('add', '-A')
        self.g('commit', '-qm', message)
        return self.g('rev-parse', 'HEAD')

    def setup_candidate(self, with_source_change=False):
        self.g('checkout', '--detach', self.base)
        self.g('merge', '--no-ff', '--no-edit', self.stable)
        if with_source_change:
            Path('firmware.c').write_text('int value = 2;\n')
        pipeline.save(self.root / 'pending.json', {
            'version': '1.0.6', 'base_sha': self.base, 'upstream_sha': self.stable,
        })
        pipeline.save(self.root / 'model-cache.json', {'previous': 'verified'})
        self.candidate = self.commit('Saved candidate')
        self.g('checkout', '--detach', self.base)
        Path('README.md').write_text('Aktualni galerie\n')
        Path('site').mkdir()
        (Path('site') / 'new.gif').write_bytes(b'GIF89a')
        self.dev = self.commit('New gallery on dev')

    def call_prepare(self, *, expected_error=None):
        def git(*args, **kwargs):
            if args[:2] == ('fetch', '--no-tags'):
                dest = self.candidate if args[2] == 'origin' else self.latest
                Path('.git/FETCH_HEAD').write_text(dest + '\n')
                return ''
            return self.g(*args)

        def api(path):
            if path.endswith('/releases/latest'):
                return dict(tag_name=self.tag, draft=False, prerelease=False, id=12, html_url='stable')
            if '/branches/' in path:
                return {'commit': {'sha': self.candidate}} if self.candidate else None
            if '/git/ref/' in path:
                return None
            if '/releases?' in path:
                return [{'tag_name': 'v1.0.5'}]
            raise AssertionError(path)

        with patch.object(pipeline, 'git', side_effect=git), patch.object(pipeline, 'api', side_effect=api), \
                patch.object(pipeline, 'find_release', return_value=self.release), \
                patch.object(pipeline, 'push_candidate') as push, patch.object(pipeline, 'output') as out:
            if expected_error:
                with self.assertRaisesRegex(RuntimeError, expected_error):
                    pipeline.prepare()
                out.assert_not_called()
            else:
                pipeline.prepare()
            return out.call_args.kwargs if out.called else None, push.call_count

    def test_unpublished_noop_preserves_saved_candidate_and_new_gallery(self):
        self.setup_candidate()
        out, pushes = self.call_prepare()
        self.assertEqual(out, dict(changed=False, no_source_changes=True, upstream_tag=self.tag))
        self.assertEqual(pushes, 0)
        self.assertEqual(self.g('rev-parse', 'HEAD'), self.dev)
        self.assertEqual(Path('README.md').read_text(), 'Aktualni galerie\n')
        self.assertIn('verified', self.g('show', self.candidate + ':.donny/model-cache.json'))

    def test_new_candidate_without_source_delta_is_recorded_on_automation_branch_only(self):
        self.setup_candidate()
        self.candidate = None
        out, pushes = self.call_prepare()
        self.assertEqual(out, dict(changed=False, no_source_changes=True, upstream_tag=self.tag))
        self.assertEqual(pushes, 1)
        self.assertEqual(Path('firmware.c').read_text(), 'int value = 1;\n')
        self.assertEqual(pipeline.load(self.root / 'pending.json')['base_sha'], self.dev)

    def test_real_candidate_keeps_its_work_and_absorbs_web_changes(self):
        self.setup_candidate(with_source_change=True)
        out, pushes = self.call_prepare()
        self.assertEqual(out, dict(changed=True, sha=self.g('rev-parse', 'HEAD'),
                                   version='1.0.6', published=False))
        self.assertEqual(pushes, 1)
        self.assertEqual(pipeline.load(self.root / 'pending.json')['base_sha'], self.dev)
        self.g('merge-base', '--is-ancestor', self.dev, out['sha'])
        self.g('merge-base', '--is-ancestor', self.candidate, out['sha'])
        self.assertEqual(Path('firmware.c').read_text(), 'int value = 2;\n')
        self.assertEqual((Path('site') / 'new.gif').read_bytes(), b'GIF89a')
        self.assertEqual(pipeline.load(self.root / 'model-cache.json'), {'previous': 'verified'})

    def test_concurrent_firmware_edits_still_block_nonempty_candidate(self):
        self.setup_candidate(with_source_change=True)
        Path('firmware.c').write_text('int value = 9;\n')
        self.dev = self.commit('Changed firmware on dev')
        _, pushes = self.call_prepare(expected_error='nedokonceny kandidat s jinym zakladem')
        self.assertEqual(pushes, 0)
        self.assertEqual(self.g('rev-parse', 'HEAD'), self.dev)

    def test_existing_draft_prevents_noop_or_reintegration(self):
        self.setup_candidate()
        self.release = {'draft': True}
        _, pushes = self.call_prepare(expected_error='nedokonceny kandidat s jinym zakladem')
        self.assertEqual(pushes, 0)
        self.assertEqual(self.g('rev-parse', 'HEAD'), self.dev)

    def test_new_upstream_leaves_redundant_candidate_in_history(self):
        self.setup_candidate()
        self.g('checkout', '--detach', self.stable)
        Path('firmware.c').write_text('int value = 3;\n')
        self.latest = self.commit('Genuine firmware changes in next stable release')
        self.tag = 'unlshd-096'
        self.g('checkout', '--detach', self.dev)
        out, pushes = self.call_prepare()
        self.assertEqual(out, dict(changed=True, sha=self.g('rev-parse', 'HEAD'),
                                   version='1.0.6', published=False))
        self.assertEqual(pushes, 1)
        self.g('merge-base', '--is-ancestor', self.candidate, out['sha'])
        self.g('merge-base', '--is-ancestor', self.dev, out['sha'])
        self.g('merge-base', '--is-ancestor', self.latest, out['sha'])
        self.assertEqual(Path('firmware.c').read_text(), 'int value = 3;\n')
        self.assertEqual(pipeline.load(self.root / 'pending.json')['upstream_sha'], self.latest)


if __name__=='__main__': unittest.main()
