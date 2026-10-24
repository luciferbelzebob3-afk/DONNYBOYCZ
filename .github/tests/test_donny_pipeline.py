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

    def test_missing_key_is_failure(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError): model_json('classify',[],{})

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
            with patch.object(pipeline,'ROOT',Path(directory)),patch.object(pipeline,'git',side_effect=git),patch.object(pipeline,'api',side_effect=api),patch.object(pipeline,'read',return_value=json.dumps(pending)),patch.object(pipeline,'output') as out,patch.object(pipeline,'push_candidate') as push:
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

if __name__=='__main__': unittest.main()
