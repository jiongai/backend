"""Immutable, account-scoped source clips for non-destructive dialogue edits.

Edit API access is account-scoped; callers never supply object keys.
Clip playback uses short-lived signed S3 URLs. The existing bucket visibility
still applies: a prefix alone does not make a public bucket private.
"""
import asyncio
import copy
import json
import os
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
from fastapi import HTTPException
from pydub import AudioSegment

from app.core.settings import get_settings
from app.models import ScriptSegment
from .audio_engine import generate_segment_audio, tts_manager
from .post_production import merge_audio_and_generate_srt
from .storage import r2_storage


def prefix(owner):
    return f"private-edits/{UUID(str(owner))}/"


def key(owner, identifier, extension="json"):
    return f"{prefix(owner)}{UUID(str(identifier))}.{extension}"


def put_manifest(owner, identifier, value):
    r2_storage.s3_client.put_object(Bucket=r2_storage.bucket_name, Key=key(owner, identifier),
                                  Body=json.dumps(value).encode(), ContentType="application/json")


def read_manifest(owner, identifier):
    try:
        response = r2_storage.s3_client.get_object(Bucket=r2_storage.bucket_name, Key=key(owner, identifier))
        with response["Body"] as body:
            return json.loads(body.read())
    except ClientError as exc:
        if exc.response["Error"]["Code"] in {"NoSuchKey", "404", "AccessDenied"}:
            raise HTTPException(404, "Editable audio not found. Generate the full audio again.") from exc
        raise


def store_clip(owner, path, temp_dir):
    identifier = str(uuid4())
    target = os.path.join(temp_dir, f"{identifier}.wav")
    with open(path, "rb") as source:
        audio = AudioSegment.from_file(source)
    # Keep lossless source audio so repeated edits never re-encode other lines.
    audio.export(target, format="wav").close()
    object_key = key(owner, identifier, "wav")
    r2_storage.s3_client.upload_file(target, r2_storage.bucket_name, object_key,
                                    ExtraArgs={"ContentType": "audio/wav"})
    return {"clip_id": identifier, "duration_ms": len(audio)}


def create_edit(owner, script, temp_dir):
    identifier = str(uuid4())
    segments = []
    for segment in script:
        segments.append({"id": str(uuid4()),
                         "script": ScriptSegment.model_validate({k: v for k, v in segment.items() if k in ScriptSegment.model_fields}).model_dump(exclude_none=True),
                         **store_clip(owner, segment["audio_file_path"], temp_dir)})
    put_manifest(owner, identifier, {"kind": "edit", "segments": segments})
    return {"edit_id": identifier, "segment_ids": [s["id"] for s in segments]}


def load_edit(owner, identifier):
    result = read_manifest(owner, identifier)
    if result.get("kind") != "edit":
        raise HTTPException(404, "Editable audio not found")
    return result


def speech_settings(script):
    return {k: v for k, v in script.items() if k != "pause_after_ms"}


async def regenerate(owner, edit_id, segment_id, script, temp_dir, character_limit=2000):
    base = await asyncio.to_thread(load_edit, owner, edit_id)
    original = next((s for s in base["segments"] if s["id"] == segment_id), None)
    if original is None:
        raise HTTPException(404, "Dialogue not found")
    total = sum(len(s["script"]["text"]) for s in base["segments"] if s["id"] != segment_id) + len(script["text"])
    if total > character_limit:
        raise HTTPException(403, "The edited script exceeds your character limit")
    prepared = tts_manager.prepare_script([script], user_tier="vip")[0]
    if speech_settings(prepared) == speech_settings(original["script"]) and prepared.get("pause_after_ms", 300) != original["script"].get("pause_after_ms", 300):
        clip = {k: original[k] for k in ("clip_id", "duration_ms")}
        generated_ms = 0
    else:
        providers = tts_manager.get_required_providers([prepared])
        missing = tts_manager.get_missing_provider_credentials(providers, elevenlabs_key=get_settings().elevenlabs_api_key)
        if missing:
            raise HTTPException(503, "The selected voice provider is unavailable")
        path = await generate_segment_audio(segment=prepared, output_dir=temp_dir,
                                           elevenlabs_api_key=get_settings().elevenlabs_api_key, user_tier="vip")
        clip = await asyncio.to_thread(store_clip, owner, path, temp_dir)
        generated_ms = clip["duration_ms"]
    candidate_id = str(uuid4())
    candidate = {"kind": "candidate", "edit_id": edit_id, "segment_id": segment_id, "script": prepared, **clip}
    await asyncio.to_thread(put_manifest, owner, candidate_id, candidate)
    audio_url = await asyncio.to_thread(r2_storage.s3_client.generate_presigned_url, "get_object",
        Params={"Bucket": r2_storage.bucket_name, "Key": key(owner, clip["clip_id"], "wav")}, ExpiresIn=3600)
    return {"candidate_id": candidate_id, "audio_url": audio_url, "duration_ms": clip["duration_ms"], "generated_ms": generated_ms}


def accept(owner, edit_id, candidate_id, temp_dir):
    base = load_edit(owner, edit_id)
    candidate = read_manifest(owner, candidate_id)
    if candidate.get("kind") != "candidate" or candidate.get("edit_id") != edit_id:
        raise HTTPException(409, "This preview belongs to a different audio version")
    segments = copy.deepcopy(base["segments"])
    found = False
    for segment in segments:
        if segment["id"] == candidate["segment_id"]:
            segment.update({k: candidate[k] for k in ("script", "clip_id", "duration_ms")})
            found = True
    if not found:
        raise HTTPException(409, "Dialogue no longer exists")
    script = []
    for segment in segments:
        path = os.path.join(temp_dir, f'{segment["id"]}.wav')
        r2_storage.s3_client.download_file(r2_storage.bucket_name, key(owner, segment["clip_id"], "wav"), path)
        script.append({**segment["script"], "audio_file_path": path})
    audio_path, srt_path, timeline = merge_audio_and_generate_srt(script, temp_dir)
    # Deterministic artifact names make adoption retries safe. Source manifests/clips are immutable.
    project = get_settings().r2_project_id
    audio_key = r2_storage.upload_file(audio_path, project, candidate_id, "audio/mpeg", "temp")
    srt_key = r2_storage.upload_file(srt_path, project, candidate_id, "application/x-subrip", "temp")
    # A distinct deterministic ID prevents overwriting the candidate on retries.
    from uuid import uuid5, NAMESPACE_URL
    new_id = str(uuid5(NAMESPACE_URL, f"fictalk:{owner}:{edit_id}:{candidate_id}"))
    put_manifest(owner, new_id, {"kind": "edit", "segments": segments})
    return {"message": "Dialogue replaced", "segments_count": len(segments),
            "audio_url": r2_storage.build_public_url(audio_key), "srt_url": r2_storage.build_public_url(srt_key),
            "timeline": timeline, "audio_duration_ms": max(t["end"] for t in timeline),
            "edit_id": new_id, "segment_ids": [s["id"] for s in segments]}
