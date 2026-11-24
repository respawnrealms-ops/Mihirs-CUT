"""Exercise actual media output, settings inheritance, and editing boundaries."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0,'.')

def check(name, ok):
    if not ok: raise AssertionError(name)
    print('PASS '+name,flush=True)

def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'), DATABASE_URL='', PEAKCUT_ACCOUNTS='0', PEAKCUT_FETCH_MODEL='0')
    from studio import auth, config, ctx, db, creators, jobs, render, editor, editor_assets, studio_render, server
    from studio.media import run
    db.init()
    user=auth.local_user()
    with ctx.as_user(user.id):
        render.install_fonts()
        check('caption styles and the expanded frame catalogue are independent',len(render.STYLES)==15 and len(editor.TEMPLATES)==16)
        check('defaults keep legacy renderer',editor.clean(editor.DEFAULTS)=={})
        for bad in ({'ratio':'2:0'},{'music':'../../private'},{'color':"red;movie=x"},{'caption_size':float('nan')},{'regions':[{'x':.9,'y':0,'w':.5,'h':1}]},{'cuts':[{'start':2,'end':1}]}):
            try: editor.clean(bad)
            except (ValueError,TypeError): pass
            else: raise AssertionError('invalid editor settings accepted')
        print('PASS invalid paths, filters, non-finite numbers and framing boxes rejected')
        profile={'ratio':'1:1','template':'x_light','motion':'build_up'}
        creator=creators.create({'name':'Studio tests','studio':profile})
        job=jobs.create({'kind':'url','url':'https://www.youtube.com/watch?v=abcdefghijk'}, {},enqueue=False,creator=creator['id'])
        check('creator profile is inherited by new video jobs',job['options']['studio']==profile)
        original={'id':'clip01','start':10,'end':20,'style':'bounce','layout':'blur','studio':profile}
        edited=jobs.edited_clip(original,{'studio':{'template':'breaking_news'},'caption_words':[{'w':'hello','s':11,'e':12,'bold':True}]})
        check('preview edits never mutate original clip',original['studio']==profile and 'caption_words' not in original and edited['caption_words'][0]['bold'])
        imported=editor.import_subtitles('1\n00:00:00,000 --> 00:00:01,000\nHello world\n',offset=10)
        check('SRT import uses source clock and estimated word timing',imported[0]['s']==10 and imported[1]['e']==11)
        ass=editor.import_subtitles('Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,{\\b1}Hello\\Nworld',offset=10)
        check('ASS import strips override tags',ass[0]['w']=='Hello' and ass[1]['w']=='world')
        mapped=editor.remap_words([{'w':'keep','s':10.5,'e':11},{'w':'drop','s':11.5,'e':12},{'w':'last','s':12.5,'e':13}],10,[(0,1),(2,3)])
        check('multi-cut captions retain only kept words and join clocks',[x['w'] for x in mapped]==['keep','last'] and mapped[1]['s']==1.5)
        src=work/'source.mp4'
        run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=12,drawbox=x=160:y=0:w=160:h=180:color=blue:t=fill','-f','lavfi','-i','sine=frequency=500:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)])
        music=work/'music.wav'
        studio_render.sound(music,'ping')
        audio=editor_assets.inspect(music,'music.wav')
        video=editor_assets.inspect(src,'broll.mp4')
        from PIL import Image
        photo=work/'image.png';Image.new('RGB',(100,100),'lime').save(photo)
        image=editor_assets.inspect(photo,'background.png')
        check('media library normalises images and probes audio/video',{r['kind'] for r in editor_assets.listing()}=={'image','audio','video'})
        other='u_editor_other'
        with ctx.as_user(other):
            try: editor_assets.get(image['id'])
            except ValueError: pass
            else: raise AssertionError('another user can read an asset')
        print('PASS media library cannot read another user’s file')
        words=[{'w':'HELLO','s':.15,'e':.7},{'w':'WORLD','s':.75,'e':1.3,'bold':True,'color':'#00ffff'}]
        for motion in list(editor.MOTIONS)[1:]:
            text=studio_render.ass_words(words,{'style':'bounce'},editor.settings({'studio':{'motion':motion}}),720,1280,False)
            check('ASS caption motion '+motion,'HELLO' in text and 'Dialogue:' in text and '\\c&Hffff00&' in text)
        for template in ('x_light','tiktok_hook'):
            o=editor.settings({'studio':{'template':template,'background':'solid','color':'#ffffff'}})
            background,is_light=studio_render.backdrop(o,100,100)
            check('custom background overrides frame colour '+template,background.getpixel((0,0))[:3]==(255,255,255) and is_light)
        sheets=[]
        for tpl in list(editor.TEMPLATES)[1:]:
            o=editor.settings({'studio':{'template':tpl,'name':'Mihis Cut','handle':'@yourchannel','subline':'Words below the video','ticker':'Your news text'}})
            bg,light=studio_render.backdrop(o,360,640)
            boxes=studio_render.panel_boxes(o,'duo',360,640)
            check('template keeps multi-shot layout '+tpl,len(boxes)==2)
            overlay=studio_render.frame(o,{'hook':'Your title above the video'},boxes,360,640,light)
            bg.alpha_composite(overlay);sheets.append(bg)
        gallery=Image.new('RGB',(360*7,640*3),'#888888')
        for i,im in enumerate(sheets):gallery.paste(im.convert('RGB'),((i%7)*360,(i//7)*640))
        gallery.save(work/'frames.jpg')
        cases=[('duo','1:1',{'motion':'pop_line','regions':[{'x':0,'y':0,'w':.5,'h':1},{'x':.5,'y':0,'w':.5,'h':1}]}),
               ('pip','9:16',{'pip_shape':'circle','radius':30,'background':'gradient','music':audio['id'],'sfx':[{'sound':'pop','time':.5,'duration':.4,'volume':.3}],'slots':[{'slot':1,'asset':video['id'],'offset':0}]}),
               ('trio','4:5',{'template':'x_light','avatar':image['id'],'logo':image['id'],'follow':'Follow Mihis Cut','outro':.5}),
               ('solo','16:9',{'background':'image','background_asset':image['id'],'cuts':[{'start':0,'end':.7},{'start':1.2,'end':2.2}],'broll':[{'asset':image['id'],'time':.3,'duration':.4,'x':.5,'y':.5,'size':.2}],'stickers':[{'text':'WOW','time':.5,'duration':.5,'x':.5,'y':.2,'size':.3}]}),
               ('canvas_white','3:4',{'template':'breaking_news','ticker':'Your news text','subline':'A supporting line','motion':'highlight'}),
               ('solo','9:16',{'template':'tiktok_hook','outro':.5,'follow':'Follow Mihis Cut'})]
        for i,(layout,ratio,options) in enumerate(cases):
            clip={'start':0,'end':2.5,'layout':layout,'style':'bounce','hook':'A truthful title','captions':True,'studio':{'resolution':'720','fps':'24','ratio':ratio,**options}}
            result=render.render_clip(src,work/'out',f'case{i}',clip,words,320,180)
            p=json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(work/'out'/result['file'])]))
            v=next(s for s in p['streams'] if s['codec_type']=='video')
            check('real render '+layout+' '+ratio,v['width']==result['output_width'] and v['height']==result['output_height'] and any(s['codec_type']=='audio' for s in p['streams']) and abs(float(p['format']['duration'])-result['output_duration'])<.16)
            check('preview output is never added to posting jobs '+layout,not job['clips'])
        print('PASS Studio media render checks completed')
        # Exercise the actual HTTP gate as well as storage helpers.
        from fastapi.testclient import TestClient
        from unittest.mock import patch
        import io
        config.ACCOUNTS=True
        other_user,_=auth._create('studio-other@example.com','Other',password_hash='test-only')
        a=TestClient(server.app,base_url=config.PUBLIC_URL)
        b=TestClient(server.app,base_url=config.PUBLIC_URL)
        anon=TestClient(server.app,base_url=config.PUBLIC_URL)
        a.cookies.set(auth.COOKIE,auth.start_session(user.id))
        b.cookies.set(auth.COOKIE,auth.start_session(other_user.id))
        check('library requires a session',anon.get('/api/editor/assets').status_code==401)
        check('asset endpoint checks owner',b.get('/api/editor/assets/'+image['id']).status_code==404)
        # Upload enough bytes to exercise the separate media body limit.
        import numpy as np
        payload=io.BytesIO();Image.fromarray(np.random.default_rng(7).integers(0,255,(420,420,3),dtype=np.uint8)).save(payload,format='PNG')
        auth._verified.add(user.id)
        r=a.post('/api/editor/assets',files={'file':('test-image.png',payload.getvalue(),'image/png')},headers={'Origin':config.PUBLIC_URL})
        check('a media upload over 256 KB is accepted',r.status_code==200 and r.json().get('kind')=='image')
        check('media upload rejects cross-site requests',a.post('/api/editor/assets',files={'file':('x.png',payload.getvalue(),'image/png')},headers={'Origin':'https://foreign.invalid'}).status_code==403)
        clip={'id':'clip01','start':0,'end':3,'style':'bounce','layout':'solo','status':'done','version':1,'fixed_words':words}
        job.update(status='done',width=320,height=180,duration=3,source_path=str(src),clips=[clip])
        jobs.save(job)
        base=f"/api/jobs/{job['id']}/clips/clip01"
        for route in ('source','words'):
            check('source and captions are private: '+route,b.get(base+'/'+route).status_code==404 and a.get(base+'/'+route).status_code==200)
        check('preview checks clip owner',b.post(base+'/preview',json={},headers={'Origin':config.PUBLIC_URL}).status_code==404)
        before=copy.deepcopy(clip)
        with patch('studio.render.render_clip',return_value={'file':'preview-test.mp4'}) as mocked:
            r=a.post(base+'/preview',json={'studio':{'template':'x_light'}},headers={'Origin':config.PUBLIC_URL})
            check('preview runs the compositor without changing clip or queue',r.status_code==200 and mocked.called and clip==before and len(job['clips'])==1)
        check('malformed word edits are rejected',a.post(base+'/render',json={'caption_words':['bad']},headers={'Origin':config.PUBLIC_URL}).status_code==400)
        a.close();b.close();anon.close()
    db.engine.dispose()

if __name__=='__main__':
    target=os.environ.get('MIHIS_TEST_KEEP')
    if target:
        work=Path(target);work.mkdir(parents=True,exist_ok=True);main(work)
    else:
        with tempfile.TemporaryDirectory(prefix='mc-test-') as d:main(Path(d))
