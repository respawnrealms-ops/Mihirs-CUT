"""Caption corrections survive rendering, and cards credit the source rather than the destination."""
import copy
import io
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, '.')


def check(name, value):
    if not value:
        raise AssertionError(name)
    print('PASS '+name, flush=True)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'), DATABASE_URL='', PEAKCUT_ACCOUNTS='0', PEAKCUT_FETCH_MODEL='0')
    from PIL import Image
    from studio import auth, config, ctx, db, creators, editor, editor_assets, jobs, media, render, server, source_profile
    db.init()
    user=auth.local_user()
    with ctx.as_user(user.id):
        render.install_fonts()
        c=creators.create({'name':'Unrelated creator'})
        j=jobs.create({'type':'url','url':'https://www.youtube.com/watch?v=abcdefghijk'}, {}, enqueue=False, creator=c['id'])
        j.update(uploader='Original Channel',title='Original source')
        buf=io.BytesIO();Image.new('RGB',(80,80),'#32cd32').save(buf,format='PNG')
        info={'uploader':'Original Channel','channel_url':'https://www.youtube.com/channel/UCsource','channel_handle':'@original'}
        with patch.object(media,'info',return_value=info) as metadata, patch.object(source_profile.profiles,'fetch',return_value={'name':'Original Channel','pic':(buf.getvalue(),'image/png')}) as public:
            p=source_profile.resolve(j)
            check('source channel metadata supplies name, handle and a real cached image',p['name']=='Original Channel' and p['handle']=='@original' and editor_assets.path(p['avatar']).is_file())
            check('source profile is cached per source job',source_profile.resolve(j)==p and metadata.call_count==1 and public.call_count==1)
        check('arbitrary image or local addresses cannot be channel sources',all(not source_profile.channel_url(u) for u in ('http://127.0.0.1/x','https://youtube.com.evil.test/@x','https://user@youtube.com/@x','https://youtube.com/watch?v=x')))
        clip={'id':'clip01','start':0,'end':3,'score':80,'hook':'','title':'Source test','description':'','hashtags':[],
              'captions':True,'style':'clean','layout':'fit','version':1,'status':'done',
              'studio':{'template':'x_light','name':'Posting Account','avatar':'','motion':'full_line','resolution':'720','fps':'24','encoder':'cpu'}}
        auto=source_profile.apply(j,clip)
        check('legacy posting-account defaults are replaced by source identity',auto['name']=='Original Channel' and auto['avatar']==p['avatar'])
        manual=copy.deepcopy(clip);manual['studio'].update(profile_source='custom',name='Chosen identity')
        check('explicit custom branding stays editable',source_profile.apply(j,manual)['name']=='Chosen identity')
        check('legacy no-frame clips stay on their existing renderer',source_profile.apply(j,{'studio':{}})=={})
        src=work/'source.mp4'
        media.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=navy:s=320x180:r=12','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)])
        j.update(source_path=str(src),width=320,height=180,duration=3,status='done',clips=[clip])
        clip['fixed_words']=[{'w':'incorrect','s':.2,'e':1}];clip['fixed_for']=[0,3,'en2']
        edited=jobs.edited_clip(clip,{'style':'gaming','studio':{**clip['studio'],'motion':'auto'},'caption_words':[{'w':'Corrected','s':.2,'e':1.1},{'w':'caption','s':1.1,'e':2.3}]})
        clip.update(edited)
        with patch.object(jobs.brain,'english_captions',side_effect=AssertionError('Manual captions must not be overwritten by AI')):
            jobs.render_one(j,clip,[])
        check('caption and style changes render successfully after an initial render',clip['status']=='done' and clip['version']==2)
        ass=(Path(j['dir'])/'clips'/'clip01.ass').read_text(encoding='utf-8')
        check('the rendered subtitle file uses corrected words and selected Gaming font','CORRECTED' in ass and 'CAPTION' in ass and 'incorrect' not in ass and ',Anton,' in ass)
        check('the rendered card keeps the source name and photo',clip['studio']['name']=='Original Channel' and clip['studio']['avatar']==p['avatar'])
        reloaded=server.editor_words(j['id'],clip['id'])
        check('reopening the word editor returns saved corrections',[w['w'] for w in reloaded['words']]==['Corrected','caption'])
        check('normal public job polling does not include private transcript payloads','caption_words' not in jobs.public(j)['clips'][0])
        calls=[]
        def worker_once():
            with patch.object(jobs._q,'get',side_effect=[('clip',j['id'],clip['id']),StopIteration()]):
                try:
                    jobs._worker(True)
                except StopIteration:
                    pass
        with patch.object(jobs,'render_one',side_effect=lambda job,c,ws:calls.append(ws)):
            worker_once()
        check('re-make worker accepts edited captions without the deleted full transcript',calls==[[]])
        broken=copy.deepcopy(clip);broken.pop('caption_words',None);broken.pop('fixed_words',None)
        j['clips']=[broken]
        worker_once()
        check('a missing transcript becomes an actionable error instead of staying queued',broken['status']=='error' and 'transcript' in broken['error'].lower())
        # Unknown source details never borrow the connected destination or an unrelated creator.
        unknown=jobs.create({'type':'url','url':'https://www.youtube.com/watch?v=abcdefghijl'}, {},enqueue=False,creator=c['id'])
        unknown['uploader']='Known Uploader'
        with patch.object(media,'info',side_effect=RuntimeError('temporarily offline')):
            fallback=source_profile.resolve(unknown)
        check('network failure keeps the known source name and no fabricated photo',fallback['name']=='Known Uploader' and not fallback['avatar'])
    db.engine.dispose()


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='mc-caption-source-') as folder:
        main(Path(folder))
