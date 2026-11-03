"""Anonymous access must never cross the private/public corpus boundary."""
import json

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings
from src.rag import Provider

TOKEN = "test-owner-token-for-public-demo-32-characters"


def config(tmp_path, **kwargs):
    return Settings(database_path=str(tmp_path/'workspace.sqlite'),provider='openai',
                    api_key='', token=TOKEN, production=True, demo_seed=False, **kwargs)


def client_with_private_data(tmp_path):
    settings=config(tmp_path)
    app=create_app(settings)
    private=app.state.store.add('Secret owner file','private.pdf',[(1,'PRIVATE_CANARY_ORBIT_729: private syllabus exam schedule')],'private-digest',pdf=b'private-pdf-bytes')
    return TestClient(app),private,app


def test_anonymous_library_and_citations_are_available_without_token(tmp_path):
    client,private,app=client_with_private_data(tmp_path)
    public=client.get('/api/demo/documents')
    assert public.status_code==200
    assert len(public.json()['documents'])==3
    assert private['id'] not in public.text and 'Secret owner file' not in public.text
    doc=public.json()['documents'][0]
    detail=client.get('/api/demo/documents/'+doc['id'])
    assert detail.status_code==200 and detail.json()['passages']
    assert 'embedding' not in detail.text and 'pdf-bytes' not in detail.text
    answer=client.post('/api/demo/ask',json={'query':'language identity'}).json()
    assert answer['mode']=='demo' and answer['access']=='public'
    assert answer['citations'] and '[1]' in answer['answer']
    citation=answer['citations'][0]
    assert client.get('/api/demo/documents/'+citation['document_id']).status_code==200
    assert client.get('/api/documents').status_code==401


@pytest.mark.parametrize('route',['/api/demo/search','/api/demo/ask'])
def test_guessed_private_document_ids_never_enter_demo_retrieval(tmp_path,route):
    client,private,app=client_with_private_data(tmp_path)
    for headers in ({},{'Authorization':'Bearer '+TOKEN}):
        response=client.post(route,headers=headers,json={'query':'PRIVATE_CANARY_ORBIT_729','document_ids':[private['id']]})
        assert response.status_code==404
    assert client.get('/api/demo/documents/'+private['id']).status_code==404
    response=client.post(route,json={'query':'PRIVATE_CANARY_ORBIT_729'})
    assert response.status_code==200
    assert 'private syllabus' not in response.text and 'Secret owner file' not in response.text
    assert private['id'] not in response.text


def test_public_routes_have_no_management_or_download_operations(tmp_path):
    client,private,app=client_with_private_data(tmp_path)
    doc=client.get('/api/demo/documents').json()['documents'][0]
    assert client.post('/api/demo/documents',files={'file':('fake.pdf',b'%PDF-fake')}).status_code in (404,405)
    assert client.patch('/api/demo/documents/'+doc['id'],json={'title':'Edited'}).status_code in (404,405)
    assert client.delete('/api/demo/documents/'+doc['id']).status_code in (404,405)
    assert client.get('/api/demo/documents/'+doc['id']+'/file').status_code==404
    assert client.post('/api/documents',files={'file':('fake.pdf',b'%PDF-fake')}).status_code==401
    assert client.patch('/api/documents/'+private['id'],json={'title':'Edited'}).status_code==401
    assert client.delete('/api/documents/'+private['id']).status_code==401
    assert client.get('/api/documents/'+private['id']+'/file').status_code==401
    assert len(app.state.store.list())==1
    assert len(client.get('/api/demo/documents').json()['documents'])==3


def test_owner_auth_still_works_and_private_edits_do_not_change_demo(tmp_path):
    client,private,app=client_with_private_data(tmp_path)
    headers={'Authorization':'Bearer '+TOKEN}
    assert client.get('/api/documents',headers=headers).json()['documents'][0]['id']==private['id']
    assert client.patch('/api/documents/'+private['id'],headers=headers,json={'title':'Renamed private syllabus'}).status_code==200
    assert 'Renamed private syllabus' not in client.get('/api/demo/documents').text
    assert client.get('/api/documents/'+private['id']+'/file',headers=headers).content==b'private-pdf-bytes'
    assert client.get('/api/demo/documents',headers={'Authorization':'Bearer invalid'}).status_code==200


class FakeAI:
    def __init__(self): self.embed_calls=0;self.answer_calls=0
    def embed(self,texts): self.embed_calls+=1;return [[1.,0.] for _ in texts]
    def answer(self,query,sources,language):
        self.answer_calls+=1
        assert all('PRIVATE_CANARY' not in r['text'] for r in sources)
        return 'Supported demo answer. [1]',[1]


def test_successful_public_answers_are_cached_without_new_model_calls(tmp_path):
    settings=config(tmp_path);settings.api_key='test-only'
    fake=FakeAI();app=create_app(settings,demo_provider=fake);client=TestClient(app)
    app.state.store.add('Private','private.pdf',[(1,'PRIVATE_CANARY')],'digest')
    body={'query':'语言与身份有什么关系？','language':'中文'}
    first=client.post('/api/demo/ask',json=body).json()
    assert first['mode']=='ai' and first['cached'] is False
    assert fake.embed_calls==2 and fake.answer_calls==1
    second=client.post('/api/demo/ask',json=body).json()
    assert second['cached'] is True and second['answer']==first['answer']
    assert fake.embed_calls==2 and fake.answer_calls==1
    assert 'Previously generated' in second['notice']
    assert 'Private' not in json.dumps(second)


@pytest.mark.parametrize('status',[429,502])
def test_public_provider_errors_fall_back_to_honest_excerpts(tmp_path,status):
    class Failed:
        def embed(self,texts): raise HTTPException(status,'private upstream details')
    settings=config(tmp_path);settings.api_key='test-only'
    client=TestClient(create_app(settings,demo_provider=Failed()))
    for route in ('/api/demo/search','/api/demo/ask'):
        response=client.post(route,json={'query':'language identity'})
        assert response.status_code==200
        assert response.json()['mode'] in ('lexical','demo')
        assert 'keyword-matched excerpts' in response.json()['notice']
        assert 'private upstream details' not in response.text
        if route.endswith('ask'):assert 'not an AI-generated answer' in response.json()['answer']


def test_public_model_allowance_leaves_global_budget_for_owner(tmp_path,monkeypatch):
    settings=config(tmp_path,max_demo_model_requests_per_day=2,max_model_requests_per_day=4)
    settings.api_key='test-only'
    original=httpx.Client;calls=[]
    def handle(request):
        calls.append(request)
        return httpx.Response(200,json={'data':[{'index':0,'embedding':[1.,0.]}]})
    monkeypatch.setattr(httpx,'Client',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
    public=Provider(settings,scope='demo');owner=Provider(settings)
    public.embed(['one']);public.embed(['two'])
    with pytest.raises(HTTPException) as error: public.embed(['three'])
    assert error.value.status_code==429
    owner.embed(['private one']);owner.embed(['private two'])
    assert len(calls)==4
    with pytest.raises(HTTPException):owner.embed(['limit'])


def test_public_demo_can_be_disabled_without_disabling_owner_auth(tmp_path):
    client=TestClient(create_app(config(tmp_path,public_demo_enabled=False)))
    assert client.get('/api/config').json()['public_demo_enabled'] is False
    assert client.get('/api/demo/documents').status_code==404
    assert client.get('/api/documents').status_code==401
    assert client.get('/api/documents',headers={'Authorization':'Bearer '+TOKEN}).status_code==200
