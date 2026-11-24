"""Reference frame layout, gradient, long-video selection and unchanged Shorts posting."""
import copy
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,'.')
def check(name,condition):
    if not condition:raise AssertionError(name)
    print('PASS '+name,flush=True)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'),DATABASE_URL='',PEAKCUT_ACCOUNTS='0',PEAKCUT_FETCH_MODEL='0')
    from PIL import Image
    import numpy as np
    from studio import auth,ctx,db,creators,jobs,editor,render,studio_render,frame_designs,long_video,posting,accounts,media
    db.init();user=auth.local_user()
    with ctx.as_user(user.id):
        render.install_fonts()
        for key in ('x_light','breaking_news','tiktok_hook','youtube_video'):
            o=editor.settings({'studio':{'template':key,'name':'Your channel','handle':'@yourhandle','badge':True,'headline':'What is the most valuable lesson you learned this year?','news_live':True}})
            boxes=studio_render.panel_boxes(o,'fit',360,640)
            bg,light=studio_render.backdrop(o,360,640)
            fg=studio_render.frame(o,{},boxes,360,640,light)
            check(key+' has actual text and design graphics',np.count_nonzero(np.array(fg)[:,:,3])>1500)
            if key!='youtube_video':check(key+' leaves a clear middle video panel',abs(boxes[0][1]/640-.36)<.01 and boxes[0][2]>300)
            bg.alpha_composite(fg);bg.save(work/(key+'.png'))
        o=editor.settings({'studio':{'background':'gradient','color':'#2563eb','color2':'#0f172a','gradient_angle':90}})
        bg,_=studio_render.backdrop(o,100,200)
        check('blue-night gradient uses blue at top and navy below',bg.getpixel((50,0))[2]>bg.getpixel((50,199))[2])
        o['gradient_angle']=0;bg,_=studio_render.backdrop(o,100,200)
        check('gradient direction can change to horizontal',bg.getpixel((0,100))[2]>bg.getpixel((99,100))[2])
        a=frame_designs.video_box(dict(o,template='youtube_video',padding=0),1280,720)
        b=frame_designs.video_box(dict(o,template='youtube_video',padding=54),1280,720)
        check('5 percent padding visibly insets the video',a==(0,0,1280,720) and b[0]==64 and b[2]==1152)
        c=creators.create({'name':'Long-video test'})
        j=jobs.create({'type':'file','path':'','name':'source.mp4'},{'mode':'compilation','long_minutes':30},enqueue=False,creator=c['id'])
        short=jobs.create({'type':'file','path':'','name':'short.mp4'},{},enqueue=False,creator=c['id'])
        check('long compilations use a separate job kind',j['kind']=='long_video' and short['kind']=='video')
        raw={'id':'long01','start':0,'end':1800,'style':'clean','layout':'fit','long_video':True}
        check('long editing accepts a 30 minute timeline',jobs.edited_clip(raw,{'end':1800})['end']==1800)
        try:jobs.edited_clip({**raw,'long_video':False},{'end':1800})
        except ValueError:pass
        else:raise AssertionError('the Shorts duration limit changed')
        print('PASS existing Shorts duration limits are unchanged')
        ranked=[{'start':i*100,'end':i*100+90,'score':100-(i%3)*10} for i in range(60)]
        selected=long_video.select_sections(ranked,1800)
        check('selected highlights stay in time order without overlap',all(a['end']<=b['start'] for a,b in zip(selected,selected[1:])))
        check('compilation selection stays within 20–40 minutes',1200<=long_video.duration(selected)<=2400)
        def score(prompt,schema,purpose=None):
            ids=[int(x) for x in re.findall(r'SECTION (\d+)',prompt)]
            return [{'id':x,'score':75,'reason':'Spoken example'} for x in ids],'test',1
        with patch('studio.brain.ask_ai',side_effect=score):
            out=long_video.rank_sections([{'id':i,'start':i*90,'end':i*90+90,'text':'Example spoken words'} for i in range(10)])
        check('ranking handles several AI batches and validates every id',len(out)==10 and all(r['score']==75 for r in out))
        words=[{'w':'first','s':.1,'e':.4},{'w':'removed','s':.8,'e':1},{'w':'last','s':1.2,'e':1.6}]
        mapped=long_video.mapped_words(words,[{'start':0,'end':.6,'output_start':0},{'start':1.1,'end':1.8,'output_start':.6}])
        check('compilation captions drop omitted footage and follow the joined clock',[w['w'] for w in mapped]==['first','last'] and abs(mapped[1]['s']-.7)<.01)
        source=work/'source.mp4'
        media.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=12','-f','lavfi','-i','sine=frequency=440:sample_rate=16000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)])
        joined=work/'joined.mp4'
        plan=long_video.join_source(source,[{'start':0,'end':.7},{'start':1.2,'end':2.1}],joined,work)
        probe=media.probe(joined)
        check('real selected sections join with audio and matching duration',len(plan)==2 and 1.5<probe['duration']<2.1)
        clip={'start':0,'end':probe['duration'],'style':'clean','layout':'fit','captions':True,'hook':'Headline','studio':{'template':'breaking_news','news_live':True,'name':'Your channel','resolution':'720','fps':'24'}}
        result=render.render_clip(joined,work/'out','news',clip,[{'w':'A','s':.1,'e':.5},{'w':'STORY','s':.55,'e':1}],320,180)
        check('Breaking News renders through the real video pipeline',(work/'out'/result['file']).is_file())
        # Posting stand-ins never contact a real account.
        calls=[]
        def uploaded(*args,**kwargs):
            calls.append((args,kwargs));return 'test-id','https://example.invalid/test'
        done={'id':'clip','status':'done','file':'joined.mp4','title':'Title','description':'Description','hashtags':[]}
        fakejob={'id':'job','kind':'video','creator':c['id'],'dir':str(work),'clips':[done]}
        with patch('studio.jobs.get',return_value=fakejob),patch('studio.accounts.get',return_value={'platform':'youtube','name':'Test account'}),patch('studio.accounts.youtube_upload',side_effect=uploaded),patch('studio.posting._save'),patch('studio.posting._mirror'):
            p={'job':'job','clip':'clip','account':'test','creator':c['id'],'tries':0}
            posting._post(p)
            check('Shorts still add #Shorts and keep the existing upload call',calls[-1][0][3].endswith('#Shorts') and calls[-1][1]=={})
            fakejob['kind']='long_video';posting._post(p)
            check('only long compilations use the normal YouTube upload',calls[-1][0][3]=='Description' and calls[-1][1]=={'shorts':False})
        with patch('studio.posting.enqueue') as enqueue:
            posting.on_clip_ready({'kind':'long_video'},done)
            check('long compilations are never posted unattended',not enqueue.called)
        class Reply:
            status_code=200;text='';headers={'Location':'https://example.invalid/upload'}
            def json(self):return {'id':'test-id'}
        with patch('studio.accounts._yt_token',return_value='test-placeholder'),patch('studio.accounts.httpx.post',return_value=Reply()),patch('studio.accounts.httpx.put',return_value=Reply()):
            _,url=accounts.youtube_upload({},source,'Title','Description',[],'private')
            check('existing Shorts links are unchanged',url=='https://www.youtube.com/shorts/test-id')
            _,url=accounts.youtube_upload({},source,'Title','Description',[],'private',shorts=False)
            check('long-video links open the regular watch page',url=='https://www.youtube.com/watch?v=test-id')
    db.engine.dispose()

if __name__=='__main__':
    keep=os.environ.get('MIHIS_REFERENCE_KEEP')
    if keep:
        work=Path(keep);work.mkdir(parents=True,exist_ok=True);main(work)
    else:
        with tempfile.TemporaryDirectory(prefix='mc-reference-') as folder:main(Path(folder))
