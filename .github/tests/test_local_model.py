import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/donny'))
import local_inference as local
import model_runtime as runtime
import pipeline
from localization import ModelDeferred

SCHEMA={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}

def response(value=None,finish='stop'):
    return io.BytesIO(json.dumps({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value if value is not None else {'ok':True})}}]}).encode())

class LocalModelTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        self.cache=self.root/'cache.json'
        env=patch.dict(os.environ,{'LOCAL_MODEL_CACHE_PATH':str(self.cache),'OPENAI_API_KEY':'must-not-use','GEMINI_API_KEY':'must-not-use'},clear=True)
        env.start();self.addCleanup(env.stop)
        self.config=runtime.lock_config()

    def test_local_schema_response_and_persistent_cache(self):
        opener=Mock();opener.open.return_value=response()
        with patch.object(local,'ensure_server',return_value=('http://127.0.0.1:8765/v1/chat/completions',self.config)) as ensure,patch.object(local.urllib.request,'build_opener',return_value=opener):
            self.assertEqual(local.model_json('check',[],SCHEMA),{'ok':True})
            req=opener.open.call_args.args[0]
            self.assertEqual(req.full_url,'http://127.0.0.1:8765/v1/chat/completions')
            self.assertNotIn('authorization',{k.lower():v for k,v in req.header_items()})
            self.assertNotIn('must-not-use',req.data.decode())
            self.assertEqual(json.loads(req.data)['response_format']['json_schema']['schema'],SCHEMA)
            self.assertEqual(local.model_json('check',[],SCHEMA),{'ok':True})
            self.assertEqual(ensure.call_count,1)
            self.assertEqual(opener.open.call_count,1)
        self.assertNotIn('must-not-use',self.cache.read_text())

    def test_cannot_redirect_inference_to_remote_provider(self):
        for endpoint in ['https://api.openai.com/v1/chat/completions','http://example.com/v1/chat/completions','http://127.0.0.1:8765/v1/chat/completions?redirect=cloud']:
            with patch.object(local,'ensure_server',return_value=(endpoint,self.config)),patch.object(local.urllib.request,'build_opener') as opener:
                with self.assertRaises(RuntimeError):local.model_json('check',[],SCHEMA)
                opener.assert_not_called()
        self.assertIsNone(local.NoRedirect().redirect_request(None,None,302,'',{},'https://example.com'))

    def test_output_truncation_or_invalid_schema_cannot_be_cached(self):
        for answer in [response(finish='length'),response({'ok':'wrong'})]:
            opener=Mock();opener.open.return_value=answer
            with patch.object(local,'ensure_server',return_value=('http://127.0.0.1:8765/v1/chat/completions',self.config)),patch.object(local.urllib.request,'build_opener',return_value=opener):
                with self.assertRaises(RuntimeError):local.model_json('check',[],SCHEMA)
                self.assertFalse(self.cache.exists())

    def test_batch_schema_binds_exact_ids_and_count(self):
        schema={'type':'object','properties':{'items':{'type':'array','items':{'type':'object','properties':{'id':{'type':'string'}}}}}}
        bounded=local.bounded_schema([{'id':'a'},{'id':'b'}],schema)
        self.assertEqual(bounded['properties']['items']['minItems'],2)
        self.assertEqual(bounded['properties']['items']['maxItems'],2)
        self.assertEqual(bounded['properties']['items']['items']['properties']['id']['enum'],['a','b'])
        self.assertNotIn('minItems',schema['properties']['items'])
        with self.assertRaises(ValueError):local.bounded_schema([{'id':'a'},{'id':'a'}],schema)

    def test_czech_accents_only_are_normalized(self):
        self.assertEqual(local.ascii_czech('"Ulož číslo: %lu\\n"'),'"Uloz cislo: %lu\\n"')
        self.assertEqual(local.ascii_czech('"✓"'),'"✓"')

    def test_unavailable_runtime_defers_without_external_fallback(self):
        with patch.object(local,'ensure_server',side_effect=runtime.RuntimeUnavailable('download failed')),patch.object(local.urllib.request,'build_opener') as opener:
            with self.assertRaises(ModelDeferred):local.model_json('check',[],SCHEMA)
            opener.assert_not_called()

    def test_wrong_running_model_is_rejected(self):
        wrong=dict(self.config,model_sha256='wrong')
        with patch.object(local,'ensure_server',return_value=('http://127.0.0.1:8765/v1/chat/completions',wrong)):
            with self.assertRaises(RuntimeError):local.model_json('check',[],SCHEMA)

    def test_pinned_weights_have_to_match_sha256(self):
        p=self.root/'weights.gguf';p.write_bytes(b'bad model')
        self.assertFalse(runtime.verify_model(p,self.config['model_sha256']))
        bad=dict(self.config,model_file='bad.gguf',model_sha256='0'*64)
        with patch.object(runtime.urllib.request,'urlopen',return_value=io.BytesIO(b'bad model')):
            with self.assertRaisesRegex(RuntimeError,'SHA-256'):runtime.download_model(bad,self.root)
        self.assertFalse((self.root/'models/bad.gguf').exists())
        self.assertFalse((self.root/'models/bad.download').exists())

    def test_checkpoint_persists_completed_batches_and_retry_time(self):
        root=self.root
        (root/'pending.json').write_text('{}')
        (root/'model-cache.json').write_text('{}')
        deferred=ModelDeferred('quota',900)
        with patch.object(pipeline,'ROOT',root),patch.object(pipeline,'commit',return_value='checkpoint') as commit,patch.object(pipeline,'push_candidate') as push,patch.object(pipeline,'output'):
            pipeline.checkpoint_model('analyze',deferred)
            self.assertEqual(json.loads((root/'deferred.json').read_text())['retry_at'],deferred.retry_at)
            self.assertIn('.donny/model-cache.json',commit.call_args.args[1])
            self.assertIn('.donny/deferred.json',commit.call_args.args[1])
            push.assert_called_once()

    def test_scheduled_run_waits_until_quota_resets(self):
        pending=dict(version='1.0.3',upstream_sha='upstream',base_sha='base')
        deferred=dict(stage='analyze',retry_at=int(time.time())+900)
        def git(*args,**kwargs):
            if args==('rev-parse','FETCH_HEAD^{commit}'):return 'upstream'
            if args==('rev-parse','HEAD'):return 'base'
            if args==('rev-parse','FETCH_HEAD'):return 'candidate'
            return ''
        def read(ref,path):
            return json.dumps(pending) if path.endswith('pending.json') else json.dumps(deferred)
        def api(path,*args,**kwargs):
            if path.endswith('/releases/latest'):return dict(tag_name='unlshd-094',draft=False,prerelease=False)
            if '/branches/' in path:return dict(commit=dict(sha='candidate'))
            raise AssertionError(path)
        with patch.object(pipeline,'ROOT',self.root),patch.object(pipeline,'git',side_effect=git),patch.object(pipeline,'api',side_effect=api),patch.object(pipeline,'find_release',return_value=None),patch.object(pipeline,'read',side_effect=read),patch.object(pipeline,'push_candidate') as push,patch.object(pipeline,'output') as out:
            pipeline.prepare()
            out.assert_called_once_with(changed=False,deferred=True,retry_at=deferred['retry_at'])
            push.assert_not_called()


if __name__=='__main__':unittest.main()
