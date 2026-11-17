import sqlite3
from pathlib import Path
import pytest
from reading_shelf import create_app


def groups(client, article):
    result=[]
    for name in ['Food and cooking','Weekend reading']:
        c=client.post('/api/collections',json={'name':name}).json
        client.put(f"/api/collections/{c['id']}/articles/{article['id']}")
        result.append(c['id'])
    return result


def test_exact_archive_restart_restore_round_trip(app, client, article):
    ids=groups(client,article)
    saved=client.patch(f"/api/articles/{article['id']}",json={'note':'Bake Saturday','status':'reading'}).json
    path=f"/api/articles/{article['id']}/archive"
    for _ in range(2):
        assert client.put(path).json == {**saved,'archived':True}
    for query in ['', '?status=reading']+[f'?collection_id={c}&status=reading' for c in ids]:
        assert client.get('/api/articles'+query).json['articles']==[]
    fresh=create_app(app.instance_path).test_client()
    for query in ['view=archive']+[f'view=archive&collection_id={c}&status=reading' for c in ids]:
        assert fresh.get('/api/articles?'+query).json['articles']==[{**saved,'archived':True}]
    for _ in range(2):assert fresh.delete(path).json == saved
    for c in ids:
        assert fresh.get(f'/api/articles?collection_id={c}&status=reading').json['articles']==[saved]
    assert fresh.get('/api/articles?view=archive').json['articles']==[]
    again=create_app(app.instance_path).test_client()
    assert again.get('/api/articles').json['articles']==[saved]
    with sqlite3.connect(Path(app.instance_path)/'reading-shelf.sqlite3') as db:
        assert db.execute('SELECT collection_id,article_id FROM collection_articles ORDER BY collection_id').fetchall()==[(c,article['id']) for c in ids]


@pytest.mark.parametrize('status',['to_read','reading','read'])
def test_archive_is_independent_of_reading_status(client, article, status):
    client.patch(f"/api/articles/{article['id']}",json={'status':status})
    client.put(f"/api/articles/{article['id']}/archive")
    assert client.get('/api/articles').json['articles']==[]
    assert len(client.get('/api/articles?view=archive&status='+status).json['articles'])==1
    other='read' if status!='read' else 'reading'
    assert client.get('/api/articles?view=archive&status='+other).json['articles']==[]
    assert client.delete(f"/api/articles/{article['id']}/archive").json['status']==status


def test_archive_projection_does_not_hide_other_articles(client, article):
    c=groups(client,article)[0]
    other=client.post('/api/articles',json={'title':'Other','url':'https://example.com/other'}).json
    client.put(f"/api/collections/{c}/articles/{other['id']}")
    client.put(f"/api/articles/{article['id']}/archive")
    assert [a['id'] for a in client.get('/api/articles').json['articles']]==[other['id']]
    assert [a['id'] for a in client.get(f'/api/articles?collection_id={c}').json['articles']]==[other['id']]
    assert [a['id'] for a in client.get('/api/articles?view=archive').json['articles']]==[article['id']]


def test_archived_context_readonly_and_duplicate_does_not_restore(client, article):
    ids=groups(client,article)
    archived=client.put(f"/api/articles/{article['id']}/archive").json
    assert client.patch(f"/api/articles/{article['id']}",json={'note':'Forbidden','status':'read'}).status_code==409
    for method in [client.put,client.delete]:
        assert method(f"/api/collections/{ids[0]}/articles/{article['id']}").status_code==409
    duplicate=client.post('/api/articles',json={'title':'New title','url':article['url']})
    assert duplicate.status_code==200 and duplicate.json==archived
    assert client.get('/api/articles?view=archive').json['articles']==[archived]
    assert client.get('/api/articles').json['articles']==[]


@pytest.mark.parametrize('query',['view=','view=all','view=true','view=1','view=archive&view=active'])
def test_invalid_archive_views(client, article, query):
    assert client.get('/api/articles?'+query).status_code==400
    assert client.get('/api/articles').json['articles']==[article]


def test_missing_archive_targets(client):
    for method in [client.put,client.delete]:
        assert method('/api/articles/999/archive').status_code==404
        assert method('/api/articles/9999999999999999999999999/archive').status_code==404


@pytest.mark.parametrize('start_archived',[False,True])
def test_failed_archive_or_restore_preserves_exact_state(app,client,article,start_archived):
    groups(client,article)
    path=f"/api/articles/{article['id']}/archive"
    if start_archived:client.put(path)
    query='/api/articles?view='+('archive' if start_archived else 'active')
    before=client.get(query).json
    with sqlite3.connect(Path(app.instance_path)/'reading-shelf.sqlite3') as db:
        db.execute("CREATE TRIGGER abort_archive AFTER UPDATE OF archived ON articles BEGIN SELECT RAISE(ABORT,'fail marker write'); END")
    response=(client.delete if start_archived else client.put)(path)
    assert response.status_code==503
    assert client.get(query).json==before


def test_upgrade_populated_milestone_two_and_repeat_startup(tmp_path):
    folder=tmp_path/'v2';folder.mkdir();path=folder/'reading-shelf.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE articles (id INTEGER PRIMARY KEY,title TEXT NOT NULL,url TEXT NOT NULL UNIQUE,note TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'to_read' CHECK(status IN ('to_read','reading','read')));
        CREATE TABLE collections (id INTEGER PRIMARY KEY,name TEXT NOT NULL,name_key TEXT NOT NULL UNIQUE);
        CREATE TABLE collection_articles (collection_id INTEGER NOT NULL REFERENCES collections(id),article_id INTEGER NOT NULL REFERENCES articles(id),PRIMARY KEY(collection_id,article_id));
        INSERT INTO articles VALUES(42,'Focaccia','https://example.com/focaccia','Bake Saturday','reading');
        INSERT INTO collections VALUES(3,'Food and cooking','food and cooking'),(8,'Weekend reading','weekend reading');
        INSERT INTO collection_articles VALUES(3,42),(8,42);
        """)
    expected={'id':42,'title':'Focaccia','url':'https://example.com/focaccia','note':'Bake Saturday','status':'reading','collection_ids':[3,8],'archived':False}
    for _ in range(2):
        client=create_app(str(folder)).test_client()
        assert client.get('/api/articles').json['articles']==[expected]
    assert client.put('/api/articles/42/archive').json=={**expected,'archived':True}
    client=create_app(str(folder)).test_client()
    assert client.get('/api/articles?view=archive').json['articles']==[{**expected,'archived':True}]
    assert client.delete('/api/articles/42/archive').json==expected
    with sqlite3.connect(path) as db:
        assert sum(r[1]=='archived' for r in db.execute('PRAGMA table_info(articles)'))==1
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE articles SET archived=2')
