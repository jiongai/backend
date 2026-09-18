"""Exercise real clip storage, splice timing and failure safety without paid TTS or R2."""
import asyncio
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydub.generators import Sine

from app.services import segment_edits as edits
from app.api.routes import segment_edits as routes
from app.api.dependencies import verify_secret_key


class MemoryStorage:
    bucket_name = 'test'
    def __init__(self):
        self.objects = {}
        self.s3_client = self
    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = bytes(Body)
    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        return {'Body': io.BytesIO(self.objects[Key])}
    def upload_file(self, *args, **kwargs):
        if 'project_id' in kwargs or (len(args) > 3 and args[3] in ('audio/mpeg', 'application/x-subrip')):
            path, project, chapter, mime, folder = args
            key = f'projects/{project}/{folder}/{chapter}' + ('.srt' if mime == 'application/x-subrip' else '.mp3')
            self.objects[key] = Path(path).read_bytes()
            return key
        path, bucket, key = args[:3]
        self.objects[key] = Path(path).read_bytes()
    def download_file(self, bucket, key, target):
        Path(target).write_bytes(self.objects[key])
    def build_public_url(self, key):
        return 'https://audio.example/' + key
    def generate_presigned_url(self, action, Params, ExpiresIn):
        return 'https://signed.example/' + Params['Key']


class SegmentEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.owner = str(uuid4())
        self.storage = MemoryStorage()
        self.patch = patch.object(edits, 'r2_storage', self.storage)
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.script = []
        for i in range(3):
            path = str(Path(self.temp.name) / f'{i}.wav')
            Sine(300 + i * 100).to_audio_segment(duration=500).export(path, format='wav').close()
            self.script.append(dict(type='dialogue', text=f'Line {i}', character='Alice', gender='female',
                                    emotion='neutral', pacing=1.0, voice_id='google:test', pause_after_ms=300, audio_file_path=path))
        self.metadata = edits.create_edit(self.owner, self.script, self.temp.name)
        self.base = edits.load_edit(self.owner, self.metadata['edit_id'])
        self.middle = self.base['segments'][1]
        self.new_script = {**self.middle['script'], 'text': 'Changed line', 'emotion': 'angry'}

    def generate(self, script=None, user_tier="vip", generation_reserved=False):
        async def tts(**kwargs):
            path = str(Path(kwargs['output_dir']) / 'new.wav')
            Sine(700).to_audio_segment(duration=1200).export(path, format='wav').close()
            return path
        with patch.object(edits.tts_manager, 'prepare_script', side_effect=lambda script, **kw: copy.deepcopy(script)), \
             patch.object(edits.tts_manager, 'get_required_providers', return_value={'google'}), \
             patch.object(edits.tts_manager, 'get_missing_provider_credentials', return_value=[]), \
             patch.object(edits, 'generate_segment_audio', side_effect=tts) as mock:
            result = asyncio.run(edits.regenerate(self.owner, self.metadata['edit_id'], self.middle['id'],
                                                  script or self.new_script, self.temp.name, user_tier=user_tier, generation_reserved=generation_reserved))
            return result, mock.call_count

    def test_replaces_only_middle_line_and_retimes_subtitles(self):
        before = copy.deepcopy(self.storage.objects)
        candidate, calls = self.generate()
        self.assertEqual(calls, 1)
        self.assertEqual(candidate['generated_ms'], 1200)
        self.assertEqual(edits.load_edit(self.owner, self.metadata['edit_id']), self.base)
        result = edits.accept(self.owner, self.metadata['edit_id'], candidate['candidate_id'], self.temp.name)
        after = edits.load_edit(self.owner, result['edit_id'])
        self.assertEqual(after['segments'][0], self.base['segments'][0])
        self.assertEqual(after['segments'][2], self.base['segments'][2])
        for index in [0, 2]:
            clip = edits.key(self.owner, self.base['segments'][index]['clip_id'], 'wav')
            self.assertEqual(self.storage.objects[clip], before[clip])
        self.assertEqual(result['timeline'], [dict(index=1, start=0, end=500), dict(index=2, start=800, end=2000), dict(index=3, start=2300, end=2800)])
        srt = self.storage.objects[result['srt_url'].replace('https://audio.example/', '')].decode()
        self.assertIn('00:00:02,300 --> 00:00:02,800', srt)
        self.assertIn('Changed line', srt)
        again = edits.accept(self.owner, self.metadata['edit_id'], candidate['candidate_id'], self.temp.name)
        self.assertEqual(again, result)

    def test_pause_only_edit_reuses_audio_and_does_not_call_tts(self):
        candidate, calls = self.generate({**self.middle['script'], 'pause_after_ms': 1000})
        self.assertEqual(calls, 0)
        self.assertEqual(candidate['generated_ms'], 0)
        result = edits.accept(self.owner, self.metadata['edit_id'], candidate['candidate_id'], self.temp.name)
        self.assertEqual(result['timeline'][2]['start'], 2300)

    def test_account_and_version_isolation(self):
        with self.assertRaises(HTTPException) as error:
            edits.load_edit(str(uuid4()), self.metadata['edit_id'])
        self.assertEqual(error.exception.status_code, 404)
        candidate, _ = self.generate()
        other = edits.create_edit(self.owner, self.script, self.temp.name)
        with self.assertRaises(HTTPException) as error:
            edits.accept(self.owner, other['edit_id'], candidate['candidate_id'], self.temp.name)
        self.assertEqual(error.exception.status_code, 409)

    def test_failed_merge_keeps_old_edit_unchanged_and_can_retry(self):
        candidate, _ = self.generate()
        with patch.object(edits, 'merge_audio_and_generate_srt', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                edits.accept(self.owner, self.metadata['edit_id'], candidate['candidate_id'], self.temp.name)
        self.assertEqual(edits.load_edit(self.owner, self.metadata['edit_id']), self.base)
        self.assertIsNotNone(edits.accept(self.owner, self.metadata['edit_id'], candidate['candidate_id'], self.temp.name)['audio_url'])

    def test_full_synthesis_preserves_legacy_response_and_passes_signed_in_owner(self):
        from app.api.routes import synthesis
        app = FastAPI(); app.include_router(synthesis.router)
        app.dependency_overrides[verify_secret_key] = lambda: None
        client = TestClient(app)
        output = dict(audio_url="https://audio.example/a.mp3", srt_url="https://audio.example/a.srt", timeline=[dict(index=1, start=0, end=500)])
        with patch.object(synthesis.tts_manager, 'prepare_script', side_effect=lambda script, **kw: script), \
             patch.object(synthesis.tts_manager, 'get_required_providers', return_value=set()), \
             patch.object(synthesis.tts_manager, 'get_missing_provider_credentials', return_value=[]), \
             patch.object(synthesis, 'synthesize_drama', new_callable=AsyncMock, return_value=output) as mock:
            response = client.post('/synthesize', json={'script': [self.middle['script']]})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('edit_id', response.json())
            self.assertNotIn('segment_ids', response.json())
            self.assertNotIn('edit_owner', mock.await_args.kwargs)
            mock.return_value = {**output, 'edit_id': self.metadata['edit_id'], 'segment_ids': [self.middle['id']]}
            for tier in ['free', 'vip']:
                response = client.post('/synthesize', json={'script': [self.middle['script']]}, headers={'x-user-id': self.owner, 'x-user-tier': tier})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['edit_id'], self.metadata['edit_id'])
                self.assertEqual(mock.await_args.kwargs['edit_owner'], self.owner)

    def test_cannot_expand_total_project_beyond_character_allowance(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(edits.regenerate(self.owner, self.metadata['edit_id'], self.middle['id'], self.new_script, self.temp.name, character_limit=1))
        self.assertEqual(error.exception.status_code, 403)

    def test_free_generation_requires_reservation_and_reports_only_new_duration(self):
        with self.assertRaises(HTTPException) as error:
            self.generate(user_tier="free")
        self.assertEqual(error.exception.status_code, 403)
        result, calls = self.generate(user_tier="free", generation_reserved=True)
        self.assertEqual(calls, 1)
        self.assertEqual(result['generated_ms'], 1200)
        candidate = edits.read_manifest(self.owner, result['candidate_id'])
        self.assertEqual(candidate['script']['emotion'], 'neutral')

    def test_free_pause_only_change_needs_no_reservation_or_tts(self):
        result, calls = self.generate({**self.middle['script'], 'pause_after_ms': 1000}, user_tier="free")
        self.assertEqual(calls, 0)
        self.assertEqual(result['generated_ms'], 0)

    def test_free_planning_rejects_premium_provider_before_tts(self):
        with patch.object(edits.tts_manager, 'prepare_script', side_effect=lambda script, **kw: script), \
             patch.object(edits.tts_manager, 'get_required_providers', return_value={'elevenlabs'}), \
             patch.object(edits, 'generate_segment_audio', new_callable=AsyncMock) as tts:
            with self.assertRaises(HTTPException) as error:
                asyncio.run(edits.prepare_regeneration(self.owner, self.metadata['edit_id'], self.middle['id'], self.new_script, user_tier='free'))
            self.assertEqual(error.exception.status_code, 403)
            tts.assert_not_called()

    def test_planning_is_read_only_and_account_scoped(self):
        before = copy.deepcopy(self.storage.objects)
        with patch.object(edits.tts_manager, 'prepare_script', side_effect=lambda script, **kw: script), \
             patch.object(edits.tts_manager, 'get_required_providers', return_value={'google'}):
            _, _, requires = asyncio.run(edits.prepare_regeneration(self.owner, self.metadata['edit_id'], self.middle['id'], self.new_script, user_tier='free'))
            self.assertTrue(requires)
            self.assertEqual(before, self.storage.objects)
            with self.assertRaises(HTTPException) as error:
                asyncio.run(edits.prepare_regeneration(str(uuid4()), self.metadata['edit_id'], self.middle['id'], self.new_script, user_tier='free'))
            self.assertEqual(error.exception.status_code, 404)

    def test_api_requires_account_and_rejects_arbitrary_sources(self):
        app = FastAPI(); app.include_router(routes.router)
        app.dependency_overrides[verify_secret_key] = lambda: None
        client = TestClient(app)
        payload = dict(edit_id=self.metadata['edit_id'], segment_id=self.middle['id'], segment=self.new_script)
        with patch.object(routes.segment_edits, 'regenerate', new_callable=AsyncMock) as mock:
            response = client.post('/regenerate_segment', json=payload, headers={'x-user-tier': 'free'})
            self.assertEqual(response.status_code, 422); mock.assert_not_called()
            self.assertEqual(client.post('/regenerate_segment', json={**payload, 'audio_url': 'http://localhost/private'}, headers={'x-user-id': self.owner, 'x-user-tier': 'vip'}).status_code, 422)
            mock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
