"""Video lighting: transparent picture area, shaped edges, and actual encoded output."""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, '.')


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('PASS '+name, flush=True)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'), DATABASE_URL='', PEAKCUT_ACCOUNTS='0', PEAKCUT_FETCH_MODEL='0')
    import numpy as np
    from PIL import Image
    from studio import auth, ctx, db, editor, panel_depth, studio_render, render, jobs
    from studio.media import run, probe
    db.init();user=auth.local_user()
    with ctx.as_user(user.id):
        render.install_fonts()
        defaults=editor.settings({'studio':{}})
        check('lighting is optional and keeps old profiles unchanged',not defaults['panel_light'] and editor.clean(defaults)=={})
        boxes=[(25,210,310,175)]
        back,rim=panel_depth.layers(defaults,boxes,360,640)
        check('disabled lighting creates no overlay',back.getbbox() is None and rim.getbbox() is None)
        options={**defaults,'panel_light':True,'panel_light_color':'#fff1db','panel_light_strength':.75,'radius':8}
        back,rim=panel_depth.layers(options,boxes,360,640)
        check('lighting has a real soft shadow and glow',back.getpixel((180,202))[3]>0 and back.getpixel((180,397))[3]>0)
        check('the bevel leaves the actual picture transparent',rim.getpixel((180,290))[3]==0)
        check('upper edge catches a brighter light than the lower edge',sum(rim.getpixel((180,208))[:3])>sum(rim.getpixel((180,386))[:3]))
        check('raised panel corners match the rendered video mask',panel_depth.radius(options,1080,900)==24)
        check('legacy radius is unchanged with lighting off',panel_depth.radius(defaults,1080,900)==0)
        for bad in ({'panel_light_strength':float('nan')},{'panel_light_strength':2},{'panel_light_color':'white'},{'panel_light':'yes'}):
            try:editor.clean(bad)
            except (TypeError,ValueError):pass
            else:raise AssertionError('Invalid lighting accepted')
        print('PASS invalid lighting settings rejected',flush=True)
        circle={**options,'pip_shape':'circle'}
        _,edge=panel_depth.layers(circle,[(10,100,200,300),(230,390,100,100)],360,640,'pip')
        check('circular PiP lighting has no rectangular corner or filled centre',edge.getpixel((231,391))[3]==0 and edge.getpixel((280,440))[3]==0)
        src=work/'source.mp4'
        run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=12','-f','lavfi','-i','sine=frequency=400:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)])
        clip={'id':'clip01','start':0,'end':3,'captions':False,'hook':'','title':'A raised video panel','style':'gaming','layout':'fit',
              'studio':{'template':'x_light','profile_source':'custom','name':'Your channel','handle':'@yourchannel','background':'gradient','color':'#fb7185','color2':'#f97316','padding':48,'radius':8,'resolution':'720','fps':'24','encoder':'cpu'}}
        rows=[]
        for enabled in (False,True):
            local={**clip,'studio':{**clip['studio'],'panel_light':enabled,'panel_light_color':'#fff1db','panel_light_strength':.75}}
            name='lit' if enabled else 'flat'
            out=render.render_clip(src,work/name,name,local,[],320,180)
            run(['ffmpeg','-y','-v','error','-ss','1','-i',str(work/name/out['file']),'-frames:v','1',str(work/(name+'.png'))])
            rows.append(np.array(Image.open(work/(name+'.png')).convert('RGB')))
            check(name+' exports a playable video with the same duration',abs(probe(work/name/out['file'])['duration']-3)<.1 and out['output_width']==720)
        x,y,w,h=studio_render.panel_boxes(editor.settings(clip),'fit',720,1280)[0]
        check('the encoded panel has a visible raised edge',np.abs(rows[1][y-16:y,x+20:x+w-20].astype(float)-rows[0][y-16:y,x+20:x+w-20]).mean()>4)
        check('the video centre is preserved',np.abs(rows[1][y+h//2,x+w//2].astype(float)-rows[0][y+h//2,x+w//2]).max()<10)
        saved=jobs.edited_clip(clip,{'studio':{**clip['studio'],'panel_light':True,'panel_light_strength':.8}})
        check('lighting choices save with the clip',saved['studio']['panel_light'] and saved['studio']['panel_light_strength']==.8)
    db.engine.dispose()


if __name__=='__main__':
    keep=os.environ.get('MIHIS_PANEL_TEST_KEEP')
    if keep:
        work=Path(keep);work.mkdir(parents=True,exist_ok=True);main(work)
    else:
        with tempfile.TemporaryDirectory(prefix='mc-depth-') as folder:main(Path(folder))
