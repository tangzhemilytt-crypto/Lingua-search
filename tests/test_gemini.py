"""Gemini wire-format and cost-control tests. Never contact a real provider."""
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from src.rag import Provider, retrieve
from src.store import Store


def settings(tmp_path, **kwargs):
    return Settings(database_path=str(tmp_path/'gemini.sqlite'), provider='gemini',
                    gemini_api_key='gemini-test-secret', api_key='unused-openai-secret',
                    demo_seed=False, production=False, token='', **kwargs)


def intercept(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_explicit_provider_does_not_fall_back_to_openai(tmp_path):
    config = Settings(provider='gemini', gemini_api_key='', api_key='paid-openai-secret',
                      database_path=str(tmp_path/'test.sqlite'), demo_seed=False)
    assert config.api_key == ''
    assert TestClient(create_app(config)).get('/api/config').json()['mode'] == 'demo'
    with pytest.raises(ValueError): Settings(provider='other')
    with pytest.raises(ValueError): Settings(max_model_requests_per_day=0)


def test_gemini_embeddings_use_header_not_url_and_small_vectors(tmp_path, monkeypatch):
    config = settings(tmp_path)
    def handler(request):
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert request.url.path.endswith('/gemini-embedding-001:batchEmbedContents')
        assert request.url.query == b''
        assert request.headers['x-goog-api-key'] == config.api_key
        assert 'Authorization' not in request.headers
        body = json.loads(request.content)
        assert len(body['requests']) == 2
        assert body['requests'][0]['outputDimensionality'] == 768
        assert body['requests'][0]['taskType'] == 'SEMANTIC_SIMILARITY'
        return httpx.Response(200,json={'embeddings':[{'values':[1.,0.]},{'values':[0.,1.]}]})
    intercept(monkeypatch,handler)
    assert Provider(config).embed(['English passage','中文问题']) == [[1.,0.],[0.,1.]]


def test_gemini_answer_keeps_page_citations_and_language(tmp_path, monkeypatch):
    config = settings(tmp_path)
    def handler(request):
        assert request.url.path.endswith('/gemini-2.5-flash-lite:generateContent')
        body = json.loads(request.content)
        assert '中文' in body['systemInstruction']['parts'][0]['text']
        assert body['generationConfig']['responseMimeType'] == 'application/json'
        assert 'tools' not in body # No paid search grounding, caching, or other extra tools.
        evidence = json.loads(body['contents'][0]['parts'][0]['text'])['evidence']
        assert evidence[0]['page'] == 3
        return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'answer':'语言塑造身份。 [1]','citation_ids':[1]})}]}}]})
    intercept(monkeypatch,handler)
    assert Provider(config).answer('语言与身份？',[{'title':'Paper','page':3,'text':'Language shapes identity.'}],'中文') == ('语言塑造身份。 [1]',[1])


def test_daily_cap_persists_across_provider_instances(tmp_path, monkeypatch):
    config = settings(tmp_path,max_model_requests_per_day=1)
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(200,json={'embeddings':[{'values':[1.,0.]}]})
    intercept(monkeypatch,handler)
    Provider(config).embed(['First'])
    with pytest.raises(HTTPException) as error: Provider(config).embed(['Second'])
    assert error.value.status_code == 429 and len(calls) == 1


def test_daily_cap_resets_by_utc_date(tmp_path, monkeypatch):
    config = settings(tmp_path,max_model_requests_per_day=1)
    store=Store(config.database_path)
    with store.db() as db: db.execute("INSERT INTO metadata VALUES ('model-requests:2000-01-01','1')")
    intercept(monkeypatch,lambda request: httpx.Response(200,json={'embeddings':[{'values':[1.,0.]}]}))
    assert Provider(config).embed(['Today'])


def test_remote_quota_errors_never_retry_or_use_paid_fallback(tmp_path, monkeypatch):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,json={'error':{'message':'private upstream details'}})
    intercept(monkeypatch,handler)
    with pytest.raises(HTTPException) as error: Provider(settings(tmp_path)).embed(['test'])
    assert error.value.status_code == 429 and len(calls) == 1
    assert 'private upstream details' not in error.value.detail


@pytest.mark.parametrize('reply',[
    {'candidates':[]},
    {'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'partial'}]}}]},
    {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"answer":"Invented [9]","citation_ids":[9]}'}]}}]},
])
def test_gemini_rejects_blocked_truncated_or_invalid_citations(tmp_path, monkeypatch, reply):
    intercept(monkeypatch,lambda request:httpx.Response(200,json=reply))
    with pytest.raises(HTTPException) as error:
        Provider(settings(tmp_path)).answer('Question',[{'title':'Paper','page':1,'text':'Evidence'}],'English')
    assert error.value.status_code == 502


def test_gemini_reindexes_incompatible_openai_vectors(tmp_path):
    config=settings(tmp_path)
    store=Store(config.database_path)
    doc=store.add('Identity','identity.txt',[(1,'Language shapes identity.')],'digest',embeddings=[[0.,1.]],model='text-embedding-3-small')
    class Fake:
        def __init__(self): self.calls=[]
        def embed(self,texts): self.calls.append(texts);return [[1.,0.] for text in texts]
    fake=Fake()
    assert retrieve(store,fake,config,'身份',[],5)[0]['document_id'] == doc['id']
    assert len(fake.calls)==2
    assert store.chunks()[0]['embedding_model'] == config.embedding_cache_key
    retrieve(store,fake,config,'身份',[],5)
    assert len(fake.calls)==3 # cached passages reused


@pytest.mark.parametrize("status,reason", [(400,"API_KEY_INVALID"),(403,"SERVICE_DISABLED"),(404,"NOT_FOUND")])
def test_safe_provider_diagnostics_never_echo_secrets(tmp_path, monkeypatch, status, reason):
    reply={"error":{"status":"INVALID_ARGUMENT","message":"secret-key and private document text", "details":[{"reason":reason,"metadata":{"consumer":"private-project"}}]}}
    intercept(monkeypatch,lambda request:httpx.Response(status,json=reply))
    with pytest.raises(HTTPException) as error:Provider(settings(tmp_path)).embed(['Test'])
    assert f"HTTP {status}" in error.value.detail and reason in error.value.detail
    assert 'secret-key' not in error.value.detail and 'private-project' not in error.value.detail
    assert 'private document text' not in error.value.detail
