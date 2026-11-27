"""Direct imports preserve the source and publish only to an explicitly selected owned account."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, '.')


def check(name, value):
    if not value:
        raise AssertionError(name)
    print('PASS ' + name, flush=True)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'), PEAKCUT_FETCH_MODEL='0', PEAKCUT_ACCOUNTS='0', DATABASE_URL='')
    from studio import accounts, auth, config, ctx, db, jobs, media, posting, repost, server
    from fastapi.testclient import TestClient
    db.init()
    owner=auth.local_user()
    with ctx.as_user(owner.id), ExitStack() as cleanup:
        cleanup.callback(db.engine.dispose)
        accounts._put({'id':'youtube-own','platform':'youtube','name':'My test channel','added':0})
        accounts._put({'id':'instagram-own','platform':'instagram','name':'Other platform','added':0})
        other,_=auth._create('repost-other@example.com','Other',password_hash='test-only')
        with ctx.as_user(other.id):
            accounts._put({'id':'youtube-other','platform':'youtube','name':'Other channel','added':0})
        config.ACCOUNTS=True
        auth._verified.update((owner.id,other.id))
        a=TestClient(server.app,base_url=config.PUBLIC_URL)
        b=TestClient(server.app,base_url=config.PUBLIC_URL)
        anon=TestClient(server.app,base_url=config.PUBLIC_URL)
        for client in (a,b,anon):cleanup.callback(client.close)
        a.cookies.set(auth.COOKIE,auth.start_session(owner.id))
        b.cookies.set(auth.COOKIE,auth.start_session(other.id))
        headers={'Origin':config.PUBLIC_URL}
        base={'url':'https://www.youtube.com/shorts/abcdefghijk?si=share','request_id':'repost-test-request-01',
              'publish':False,'privacy':'public','title':'','description':'','hashtags':''}
        for url in ('https://youtu.be/abcdefghijk','https://www.youtube.com/watch?v=abcdefghijk','https://m.youtube.com/shorts/abcdefghijk'):
            check('normalises supported Short sharing links '+url.split('/')[2],repost.short_url(url)=='https://www.youtube.com/shorts/abcdefghijk')
        for url in ('file:///private','http://127.0.0.1/shorts/abcdefghijk','https://youtube.com.evil.example/shorts/abcdefghijk',
                    'https://www.youtube.com/@channel','https://www.youtube.com/playlist?list=abc','https://user@youtube.com/shorts/abcdefghijk'):
            try:repost.short_url(url)
            except ValueError:pass
            else:raise AssertionError('unsafe Short URL accepted')
        print('PASS arbitrary hosts, local files, channels and playlists rejected',flush=True)
        for changes in ({'account':'youtube-other','publish':True},{'account':'instagram-own','publish':True},
                        {'account':'missing','publish':True},{'privacy':'friends'},{'publish':'yes'},
                        {'title':'x'*101},{'description':'x'*4401},{'hashtags':{}},{'request_id':'../bad'}):
            r=a.post('/api/repost-shorts',json={**base,**changes},headers=headers)
            check('invalid upload settings rejected '+next(iter(changes)),r.status_code==400)
        check('upload creation requires sign-in',anon.post('/api/repost-shorts',json=base,headers=headers).status_code==401)
        with patch('studio.jobs.enqueue') as enqueue,patch('studio.media.check_youtube'):
            first=a.post('/api/repost-shorts',json=base,headers=headers)
            again=a.post('/api/repost-shorts',json=base,headers=headers)
            check('double clicks create exactly one durable import',first.status_code==200 and again.json()['id']==first.json()['id'] and enqueue.call_count==1)
            changed=a.post('/api/repost-shorts',json={**base,'privacy':'private'},headers=headers)
            check('reusing a request id with different settings is rejected',changed.status_code==409)
        job=jobs.get(first.json()['id'])
        check('repost has its own pipeline and no inherited editing',job['kind']=='repost' and not job['options']['captions'] and job['options']['studio']=={})
        fixture=work/'original.mp4'
        media.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=64x96:r=12','-t','1.5','-c:v','libx264','-pix_fmt','yuv420p',str(fixture)])
        def download(url, folder, height):
            target=folder/'source.mp4';shutil.copyfile(fixture,target);return target
        source={'kind':'video','title':'GTA 6 rooftop jump #Shorts','uploader':'Example channel','duration':1.5,'is_live':False}
        with patch('studio.media.info',return_value=source),patch('studio.media.download',side_effect=download), \
             patch('studio.transcribe.model_ready',side_effect=AssertionError('Speech model used')), \
             patch('studio.render.render_clip',side_effect=AssertionError('Re-rendered original')):
            jobs._run_job(job)
        clip=job['clips'][0]
        check('whole Short is preserved byte for byte',(Path(job['dir'])/'clips'/clip['file']).read_bytes()==fixture.read_bytes())
        check('source captions are not burned in twice',not clip['captions'] and clip['caption_words']==[])
        check('silent Shorts work without transcription',clip['output_width']==64 and clip['output_height']==96 and job['status']=='done')
        check('save-only never queues an upload',not posting._mine())
        wrong_platform=a.post('/api/posts',json={'job':job['id'],'clip':clip['id'],'accounts':['instagram-own'],'now':True},headers=headers)
        check('manual reposting rejects other platforms with a useful error',wrong_platform.status_code==400 and not posting._mine())
        check('metadata has a truthful title, original link and one Shorts hashtag',clip['title']==source['title'] and 'Original: https://www.youtube.com/shorts/abcdefghijk' in clip['description'] and clip['description'].lower().count('#shorts')==1)
        custom=repost.clean({**base,'hashtags':'#Gaming, #GTA6 #gaming','description':'My description #GTA6'})
        _,desc,tags=repost.metadata(custom,source)
        check('custom hashtags are sanitised and deduplicated',tags==['Shorts','Gaming','GTA6'] and desc.count('#GTA6')==1)
        # A new explicit upload uses only the account and privacy selected by this user.
        publish={**base,'request_id':'repost-test-request-02','publish':True,'account':'youtube-own','privacy':'unlisted'}
        with patch('studio.jobs.enqueue'),patch('studio.media.check_youtube'):
            result=a.post('/api/repost-shorts',json=publish,headers=headers)
        live=jobs.get(result.json()['id'])
        with patch('studio.media.info',return_value=source),patch('studio.media.download',side_effect=download):
            jobs._run_job(live)
        posts=[p for p in posting._mine() if p['job']==live['id']]
        check('download completion queues one chosen YouTube account',len(posts)==1 and posts[0]['account']=='youtube-own' and posts[0]['platform']=='youtube')
        duplicate=a.post('/api/repost-shorts',json={**publish,'request_id':'new-key-after-page-reload'},headers=headers)
        check('reloading the page cannot upload the same Short twice',duplicate.status_code==409)
        with patch('studio.accounts.youtube_upload',return_value=('mock-remote','https://www.youtube.com/shorts/mock-remote')) as upload:
            posting._post(posts[0])
            args=upload.call_args.args
            check('publishing uses selected privacy and complete hashtags',args[5]=='unlisted' and 'Shorts' in args[4] and args[3].lower().count('#shorts')==1)
        check('successful publication saves its remote id',posts[0]['status']=='posted' and posts[0]['remote_id']=='mock-remote')
        # Emulate a restart between download completion and saving its final state.
        live.update(status='running');jobs.save(live)
        jobs._load_file(Path(live['dir'])/'job.json',owner.id)
        resumed=jobs.get(live['id'])
        with patch('studio.media.download',side_effect=AssertionError('Downloaded twice')),patch('studio.media.info',side_effect=AssertionError('Looked up twice')):
            jobs._run_job(resumed)
        check('restart recovery does not upload or download twice',len([p for p in posting._mine() if p['job']==live['id']])==1)
        posts[0]['status']='cancelled'
        jobs._run_job(resumed)
        check('a cancelled post is not silently revived',len([p for p in posting._mine() if p['job']==live['id']])==1 and posts[0]['status']=='cancelled')
        # A dropped upload reply could mean YouTube already accepted the file; require review.
        error_post=dict(posts[0],id='upload-error-test',job=job['id'],status='posting',tries=0)
        job['repost'].update(account='youtube-own',privacy='private',publish=True)
        posting._posts.append(error_post)
        with patch('studio.accounts.youtube_upload',side_effect=TimeoutError('Connection dropped')) as upload:
            posting._post(error_post)
            check('ambiguous upload failures are not retried automatically',upload.call_count==1 and error_post['status']=='failed' and error_post['tries']==1 and 'Check your YouTube channel' in error_post['error'])
        check('repost imports never trigger creator auto-posting',not posting.on_clip_ready(job,clip))
        # Metadata and downloaded geometry must both describe a genuine Short.
        for i,change in enumerate(({'duration':181},{'duration':float('nan')},{'is_live':True},{'kind':'playlist'})):
            candidate=jobs.create({'type':'url','url':base['url'],'name':'test'}, {},enqueue=False,kind='repost')
            candidate['repost']=repost.clean({**base,'request_id':'reject-request-'+str(i)})
            with patch('studio.media.info',return_value={**source,**change}),patch('studio.media.download') as downloaded:
                try:jobs._run_job(candidate)
                except ValueError:pass
                else:raise AssertionError('invalid Short accepted')
                check('non-Short metadata rejected before downloading '+str(i),not downloaded.called and not candidate['clips'])
        candidate=jobs.create({'type':'url','url':base['url'],'name':'test'}, {},enqueue=False,kind='repost');candidate['repost']=repost.clean({**base,'request_id':'reject-landscape-01'})
        with patch('studio.media.info',return_value=source),patch('studio.media.download',side_effect=download),patch('studio.media.probe',return_value={'width':96,'height':64,'duration':1.5}):
            try:jobs._run_job(candidate)
            except ValueError:pass
            else:raise AssertionError('landscape Short accepted')
        check('landscape video is never queued for direct Short upload',not candidate['clips'])
        # Cancellation during a download must never turn into a later upload.
        candidate=jobs.create({'type':'url','url':base['url'],'name':'test'}, {},enqueue=False,kind='repost');candidate['repost']=repost.clean({**publish,'request_id':'cancel-repost-request'})
        def cancelled(url,folder,height):
            result=download(url,folder,height);candidate['cancel']=True;return result
        with patch('studio.media.info',return_value=source),patch('studio.media.download',side_effect=cancelled),patch('studio.posting.enqueue') as send:
            try:jobs._run_job(candidate)
            except ValueError:pass
            else:raise AssertionError('cancelled Short continued')
            check('cancelling preparation prevents publishing',not send.called)
        candidate.update(status='error',cancel=False);jobs.save(candidate)
        check('retry checks the original job owner',b.post('/api/jobs/'+candidate['id']+'/repost/retry',json={},headers=headers).status_code==404)
        with patch('studio.jobs.enqueue') as enqueue:
            result=a.post('/api/jobs/'+candidate['id']+'/repost/retry',json={},headers=headers)
            twice=a.post('/api/jobs/'+candidate['id']+'/repost/retry',json={},headers=headers)
            check('a failed import can be retried once, without concurrent duplicates',result.status_code==200 and twice.status_code==409 and enqueue.call_count==1)
        print('Repost checks completed; no external uploads performed.',flush=True)


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='mc-repost-') as folder:
        main(Path(folder))
