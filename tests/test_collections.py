import sqlite3
from pathlib import Path
import pytest
from reading_shelf import create_app


def collection(client, name):
    return client.post('/api/collections', json={'name': name}).json


def add(client, c, a):
    return client.put(f"/api/collections/{c['id']}/articles/{a['id']}")


def test_names_normalize_and_keep_first_display_spelling(client):
    first = client.post('/api/collections', json={'name':' Food and cooking '})
    assert first.status_code == 201
    again = client.post('/api/collections', json={'name':' food AND cooking '})
    assert again.status_code == 200 and again.json == first.json
    german = collection(client, 'Straße')
    assert collection(client, 'STRASSE') == german
    assert len(client.get('/api/collections').json['collections']) == 2


@pytest.mark.parametrize('data', [{}, [], None, {'name':''}, {'name':'  '}, {'name':False}, {'name':'a'*101}, {'name':'x','extra':1}])
def test_invalid_collection_does_not_write(client, data):
    assert client.post('/api/collections', json=data).status_code == 400
    assert client.get('/api/collections').json['collections'] == []


def test_shared_edit_detach_and_restart(app, client, article):
    food, weekend = collection(client,'Food and cooking'), collection(client,'Weekend reading')
    add(client,food,article); add(client,weekend,article); add(client,food,article)
    saved=client.patch(f"/api/articles/{article['id']}",json={'note':'Bake Saturday','status':'reading'}).json
    assert saved['collection_ids'] == [food['id'],weekend['id']]
    for c in (food,weekend):
        assert client.get(f"/api/articles?collection_id={c['id']}&status=reading").json['articles'] == [saved]
    client.patch(f"/api/articles/{article['id']}",json={'status':'read'})
    for c in (food,weekend):
        assert client.get(f"/api/articles?collection_id={c['id']}&status=reading").json['articles'] == []
    path=f"/api/collections/{food['id']}/articles/{article['id']}"
    for _ in range(2): assert client.delete(path).status_code == 200
    assert client.get(f"/api/articles?collection_id={food['id']}").json['articles'] == []
    remaining=client.get(f"/api/articles?collection_id={weekend['id']}").json['articles'][0]
    assert remaining['note']=='Bake Saturday' and remaining['status']=='read'
    fresh=create_app(app.instance_path).test_client()
    assert fresh.get('/api/articles').json['articles']==[remaining]


def test_exact_filter_intersections(client, article):
    c=collection(client,'Food')
    add(client,c,article)
    b=client.post('/api/articles',json={'title':'Other','url':'https://example.com/other'}).json
    client.patch(f"/api/articles/{b['id']}",json={'status':'reading'})
    assert [a['id'] for a in client.get('/api/articles?status=reading').json['articles']]==[b['id']]
    assert client.get(f"/api/articles?collection_id={c['id']}&status=reading").json['articles']==[]
    assert [a['id'] for a in client.get(f"/api/articles?collection_id={c['id']}&status=to_read").json['articles']]==[article['id']]


@pytest.mark.parametrize('query',['status=done','status=','collection_id=','collection_id=0','collection_id=-1','collection_id=1.0','collection_id=true','collection_id=9223372036854775808','collection_id=1%20OR%201=1','other=1','status=read&status=reading'])
def test_invalid_filters(client, article, query):
    assert client.get('/api/articles?'+query).status_code==400
    assert client.get('/api/articles').json['articles']==[article]


def test_missing_entities_and_empty_collection(client, article):
    c=collection(client,'Empty')
    assert client.get(f"/api/articles?collection_id={c['id']}").json['articles']==[]
    assert client.get('/api/articles?collection_id=999').status_code==404
    for method in (client.put,client.delete):
        assert method(f"/api/collections/999/articles/{article['id']}").status_code==404
        assert method(f"/api/collections/{c['id']}/articles/999").status_code==404
        assert method(f"/api/collections/{c['id']}/articles/9999999999999999999999").status_code==404
    assert client.get('/api/articles').json['articles']==[article]


def test_membership_failure_and_foreign_keys(app, client, article):
    c=collection(client,'Food');add(client,c,article)
    path=Path(app.instance_path)/'reading-shelf.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER no_detach AFTER DELETE ON collection_articles BEGIN SELECT RAISE(ABORT,'stop'); END")
    assert client.delete(f"/api/collections/{c['id']}/articles/{article['id']}").status_code==503
    assert client.get('/api/articles').json['articles'][0]['collection_ids']==[c['id']]
    from reading_shelf.db import get_db
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            with get_db():get_db().execute('INSERT INTO collection_articles VALUES (?,?)',(c['id'],999))


def test_upgrade_from_populated_milestone_one(tmp_path):
    path=tmp_path/'old';path.mkdir()
    with sqlite3.connect(path/'reading-shelf.sqlite3') as db:
        db.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL UNIQUE,note TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'to_read' CHECK(status IN ('to_read','reading','read')))")
        db.execute('INSERT INTO articles VALUES (42,?,?,?,?)',('Focaccia','https://example.com/focaccia','Keep this','reading'))
    for _ in range(2):
        client=create_app(str(path)).test_client()
        assert client.get('/api/articles').json['articles']==[{'id':42,'title':'Focaccia','url':'https://example.com/focaccia','note':'Keep this','status':'reading','collection_ids':[], 'archived':False}]
    c=collection(client,'Food');assert add(client,c,{'id':42}).status_code==200
