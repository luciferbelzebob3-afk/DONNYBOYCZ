import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/donny'))
import localization as loc
import pipeline

SCHEMA = {'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}

def response(value=None, reason='STOP'):
    return io.BytesIO(json.dumps({'candidates':[{'finishReason':reason,'content':{'parts':[{'text':json.dumps(value if value is not None else {'ok':True})}]}}]}).encode())

class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.cache=Path(self.folder.name)/'cache.json'
        env=patch.dict(os.environ,{'GEMINI_API_KEY':'fake-secret','GEMINI_TRANSLATION_MODEL':'gemini-2.5-flash','GEMINI_CACHE_PATH':str(self.cache)},clear=True)
        env.start();self.addCleanup(env.stop)

    def test_native_gemini_request_and_cache(self):
        with patch.object(loc.urllib.request,'urlopen',return_value=response()) as urlopen:
            self.assertEqual(loc.model_json('check',[],SCHEMA),{'ok':True})
            req=urlopen.call_args.args[0]
            self.assertEqual(req.full_url,'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent')
            headers={k.lower():v for k,v in req.header_items()}
            self.assertEqual(headers['x-goog-api-key'],'fake-secret')
            self.assertNotIn('authorization',headers)
            self.assertNotIn('fake-secret',req.full_url)
            payload=json.loads(req.data)
            self.assertEqual(payload['generationConfig']['responseJsonSchema'],SCHEMA)
            self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')
            self.assertEqual(loc.model_json('check',[],SCHEMA),{'ok':True})
            self.assertEqual(urlopen.call_count,1)
        self.assertNotIn('fake-secret',self.cache.read_text())

    def test_default_model_supports_new_google_projects(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.update(GEMINI_API_KEY='fake-secret', GEMINI_CACHE_PATH=str(self.cache))
            with patch.object(loc.urllib.request,'urlopen',return_value=response()) as urlopen:
                self.assertEqual(loc.model_json('check',[],SCHEMA),{'ok':True})
                req=urlopen.call_args.args[0]
                self.assertIn('/models/gemini-3.8-flash:generateContent',req.full_url)
                self.assertNotIn('thinkingConfig',json.loads(req.data)['generationConfig'])

    def test_openai_key_is_never_used_as_fallback(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'','OPENAI_API_KEY':'paid-key'}),patch.object(loc.urllib.request,'urlopen') as urlopen:
            with self.assertRaisesRegex(RuntimeError,'GEMINI_API_KEY'):loc.model_json('check',[],SCHEMA)
            urlopen.assert_not_called()

    def test_unknown_model_cannot_enable_paid_only_model(self):
        with patch.dict(os.environ,{'GEMINI_TRANSLATION_MODEL':'some-paid-model'}),patch.object(loc.urllib.request,'urlopen') as urlopen:
            with self.assertRaises(RuntimeError):loc.model_json('check',[],SCHEMA)
            urlopen.assert_not_called()

    def test_quota_defers_and_does_not_log_provider_body(self):
        error=urllib.error.HTTPError('https://generativelanguage.googleapis.com',429,'quota',{},io.BytesIO(json.dumps({'error':{'message':'fake-secret','details':[{'violations':[{'quotaId':'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}}).encode()))
        with patch.object(loc.urllib.request,'urlopen',side_effect=error) as urlopen:
            start=time.time()
            with self.assertRaises(loc.ModelDeferred) as caught:loc.model_json('check',[],SCHEMA)
            self.assertGreaterEqual(caught.exception.retry_at,start+86399)
            self.assertNotIn('fake-secret',str(caught.exception))
            self.assertEqual(urlopen.call_count,1)
            self.assertFalse(self.cache.exists())

    def test_service_errors_have_bounded_retry(self):
        def error(*args,**kwargs):raise urllib.error.HTTPError('url',503,'unavailable',{},io.BytesIO(b''))
        with patch.object(loc.urllib.request,'urlopen',side_effect=error) as urlopen,patch.object(loc.time,'sleep') as sleep:
            with self.assertRaises(loc.ModelDeferred):loc.model_json('check',[],SCHEMA)
            self.assertEqual(urlopen.call_count,3)
            self.assertEqual(sleep.call_count,2)

    def test_finished_batch_is_reused_after_later_quota_failure(self):
        error=urllib.error.HTTPError('url',429,'quota',{},io.BytesIO(b'{}'))
        with patch.object(loc.urllib.request,'urlopen',side_effect=[response(),error]) as urlopen:
            self.assertEqual(loc.model_json('first batch',[],SCHEMA),{'ok':True})
            with self.assertRaises(loc.ModelDeferred):loc.model_json('second batch',[],SCHEMA)
            self.assertEqual(loc.model_json('first batch',[],SCHEMA),{'ok':True})
            self.assertEqual(urlopen.call_count,2)

    def test_invalid_key_has_no_retry_and_no_secret_in_error(self):
        error=urllib.error.HTTPError('url',403,'fake-secret',{},io.BytesIO(b'fake-secret'))
        with patch.object(loc.urllib.request,'urlopen',side_effect=error) as urlopen:
            with self.assertRaises(RuntimeError) as caught:loc.model_json('check',[],SCHEMA)
            self.assertNotIn('fake-secret',str(caught.exception))
            self.assertEqual(urlopen.call_count,1)

    def test_incomplete_blocked_and_invalid_json_never_cached(self):
        for answer in [response(reason='MAX_TOKENS'),io.BytesIO(b'{"promptFeedback":{"blockReason":"SAFETY"}}'),response({'ok':'wrong type'})]:
            with patch.object(loc.urllib.request,'urlopen',return_value=answer):
                with self.assertRaises(RuntimeError):loc.model_json('check',[],SCHEMA)
                self.assertFalse(self.cache.exists())

    def test_schema_handles_nullable_integer_without_accepting_bool(self):
        loc.validate_json(None,{'type':['integer','null']})
        loc.validate_json(3,{'type':['integer','null']})
        with self.assertRaises(ValueError):loc.validate_json(True,{'type':['integer','null']})
        with self.assertRaises(ValueError):loc.validate_json({'ok':True,'extra':1},SCHEMA)

    def test_checkpoint_persists_completed_batches_and_retry_time(self):
        root=Path(self.folder.name)
        (root/'pending.json').write_text('{}')
        (root/'gemini-cache.json').write_text('{}')
        deferred=loc.ModelDeferred('quota',900)
        with patch.object(pipeline,'ROOT',root),patch.object(pipeline,'commit',return_value='checkpoint') as commit,patch.object(pipeline,'push_candidate') as push,patch.object(pipeline,'output'):
            pipeline.checkpoint_model('analyze',deferred)
            self.assertEqual(json.loads((root/'deferred.json').read_text())['retry_at'],deferred.retry_at)
            self.assertIn('.donny/gemini-cache.json',commit.call_args.args[1])
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
        with patch.object(pipeline,'ROOT',Path(self.folder.name)),patch.object(pipeline,'git',side_effect=git),patch.object(pipeline,'api',side_effect=api),patch.object(pipeline,'find_release',return_value=None),patch.object(pipeline,'read',side_effect=read),patch.object(pipeline,'push_candidate') as push,patch.object(pipeline,'output') as out:
            pipeline.prepare()
            out.assert_called_once_with(changed=False,deferred=True,retry_at=deferred['retry_at'])
            push.assert_not_called()

if __name__=='__main__':unittest.main()
