"""Recover incomplete AI ranking without discarding the saved source or completed scores."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,'.')


def check(name,value):
    if not value:raise AssertionError(name)
    print('PASS '+name,flush=True)


def sections(n=10):
    return [{'id':i,'start':i*90,'end':i*90+90,'text':'A complete spoken event.'} for i in range(n)]


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'),DATABASE_URL='',PEAKCUT_ACCOUNTS='0',PEAKCUT_FETCH_MODEL='0',PEAKCUT_PUBLIC_URL='http://127.0.0.1:8765')
    from studio import auth,ctx,db,jobs,long_video,media,transcribe,server
    from fastapi.testclient import TestClient
    db.init();user=auth.local_user()
    rows=sections()
    calls=[];saved=[];progress=[]
    def partial(prompt,schema,purpose=None):
        ids=[int(i) for i in re.findall(r'SECTION (\d+)',prompt)]
        calls.append((schema['type'],ids))
        if schema['type']=='OBJECT':return {'score':88,'reason':'A complete event'},'test',1
        return {'sections':[{'id':i,'score':70,'reason':'Source event'} for i in ids if i!=3]},'test',1
    with patch.object(long_video.brain,'ask_ai',side_effect=partial):
        ranked=long_video.rank_sections(rows,progress.append,on_save=lambda r:saved.append(list(r)))
    check('a missing id is recovered with one single-section request',len(ranked)==10 and ranked[3]['score']==88 and calls==[('ARRAY',list(range(8))),('OBJECT',[3]),('ARRAY',[8,9])])
    check('valid partial answers are saved before recovery',len(saved[1])==7 and saved[-1]==ranked and progress[-1]==1)
    check('unknown, fractional and boolean ids or non-finite scores are rejected',long_video._batch_scores([{'id':99,'score':70},{'id':1.5,'score':70},{'id':True,'score':70},{'id':0,'score':float('nan')},{'id':1,'score':True}],{0,1})=={})
    check('numeric id strings are accepted without renumbering',0 in long_video._batch_scores([{'id':'0','score':75}],{0}))
    cache=[];attempts=[]
    def bad(prompt,schema,purpose=None):
        attempts.append(1)
        return ([{'id':0,'score':80,'reason':'Saved event'}] if schema['type']=='ARRAY' else {'score':'missing'}),'test',1
    with patch.object(long_video.brain,'ask_ai',side_effect=bad):
        try:long_video.rank_sections(rows[:2],on_save=lambda r:cache.__setitem__(slice(None),r))
        except RuntimeError as e:check('bounded failed recovery gives a resumable error','Resume compilation' in str(e) and len(attempts)==3)
        else:raise AssertionError('Bad AI scores silently accepted')
    check('scores completed before a failure remain cached',len(cache)==1 and cache[0]['id']==0)
    seen=[]
    def rest(prompt,schema,purpose=None):
        ids=[int(i) for i in re.findall(r'SECTION (\d+)',prompt)];seen.extend(ids)
        return [{'id':i,'score':77,'reason':'Remaining event'} for i in ids],'test',1
    with patch.object(long_video.brain,'ask_ai',side_effect=rest):
        recovered=long_video.rank_sections(rows[:2],cached=cache)
    check('resuming asks only for missing scores',seen==[1] and [r['score'] for r in recovered]==[80,77])
    changed=[dict(rows[0],end=91)]
    check('cached scores cannot be applied to changed section bounds',long_video.ranked_cache(changed,cache)=={})
    with patch.object(long_video.brain,'ask_ai',side_effect=AssertionError('Cancelled job called AI')):
        try:long_video.rank_sections(rows,check=lambda:(_ for _ in ()).throw(RuntimeError('Stopped')))
        except RuntimeError:pass
        else:raise AssertionError('Cancellation ignored')
    print('PASS cancellation stops before another AI request',flush=True)

    with ctx.as_user(user.id):
        job=jobs.create({'type':'file','path':'','name':'Saved source.mp4'},{'mode':'compilation','long_minutes':20},enqueue=False)
        job.update(status='error',cancel=True,error='AI skipped a section')
        with patch.object(jobs._q,'put') as queued:
            client=TestClient(server.app,base_url='http://127.0.0.1:8765')
            response=client.post('/api/jobs/'+job['id']+'/retry',json={},headers={'Origin':'http://127.0.0.1:8765'})
            check('owner can resume the same job and clear its stale cancellation',response.status_code==200 and job['status']=='queued' and not job['cancel'] and job['error'] is None and queued.call_count==1)
            duplicate=client.post('/api/jobs/'+job['id']+'/retry',json={},headers={'Origin':'http://127.0.0.1:8765'})
            check('double clicks do not queue duplicate compilations',duplicate.status_code==409 and queued.call_count==1)
            job['status']='error';jobs._active_compilations.add(job['id'])
            stopping=client.post('/api/jobs/'+job['id']+'/retry',json={},headers={'Origin':'http://127.0.0.1:8765'})
            jobs._active_compilations.discard(job['id'])
            check('a still-stopping worker cannot race a retry',stopping.status_code==409 and queued.call_count==1)
        with ctx.as_user('u_other'):
            try:jobs.retry_compilation(job['id'])
            except ValueError:pass
            else:raise AssertionError('Another owner resumed a job')
        print('PASS another owner cannot resume the compilation',flush=True)
        short=jobs.create({'type':'file','path':'','name':'Short.mp4'},{},enqueue=False);short['status']='error'
        with patch.object(jobs._q,'put') as queued:
            try:jobs.retry_compilation(short['id'])
            except ValueError:pass
            else:raise AssertionError('Shorts retry changed')
            check('existing Shorts workflows are not redirected to compilation retry',not queued.called)

        # Exercise the factory from a previously downloaded source and transcript, without network or ASR.
        job['status']='running';job['cancel']=False
        d=Path(job['dir']);source=d/'saved.mp4';source.write_bytes(b'saved source')
        job.update(original_source_path=str(source),title='Saved source',uploader='Source channel')
        words=[{'w':'Sentence.','s':i*90+1,'e':i*90+2} for i in range(30)]
        transcript=d/'words.json';transcript.write_text(json.dumps(words),encoding='utf-8');mtime=transcript.stat().st_mtime_ns
        def fake_join(src,ranges,destination,work,check=None,on_progress=None):
            destination.write_bytes(b'joined source');clock=0;out=[]
            for row in ranges:
                out.append({**row,'output_start':clock,'output_duration':row['end']-row['start']});clock+=row['end']-row['start']
            return out
        def probe(path):return {'width':320,'height':180,'duration':1260 if Path(path).name=='compilation-source.mp4' else 2700}
        def rendered(j,c,words):c.update(status='done',version=1,file='long01.mp4')
        def normal(prompt,schema,purpose=None):
            ids=[int(i) for i in re.findall(r'SECTION (\d+)',prompt)]
            return [{'id':i,'score':70,'reason':'A spoken event'} for i in ids],'test',1
        with patch.object(media,'download',side_effect=AssertionError('Source downloaded again')),patch.object(media,'extract_audio',side_effect=AssertionError('Transcript remade')),patch.object(transcribe,'transcribe',side_effect=AssertionError('ASR repeated')),patch.object(media,'probe',side_effect=probe),patch.object(long_video,'join_source',side_effect=fake_join),patch.object(jobs,'render_one',side_effect=rendered),patch.object(long_video.brain,'ask_ai',side_effect=normal):
            long_video.run(job)
        checkpoint=json.loads((d/'compilation-rank-progress.json').read_text(encoding='utf-8'))
        check('resumed factory keeps the original source and transcript',source.read_bytes()==b'saved source' and transcript.stat().st_mtime_ns==mtime and job['status']=='done')
        check('durable ranking checkpoint is bound to this source',checkpoint['version']==1 and len(checkpoint['source'])==64 and checkpoint['rows'])
    db.engine.dispose()


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='mc-rank-retry-') as folder:main(Path(folder))
