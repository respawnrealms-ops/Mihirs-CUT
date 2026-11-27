"""Saved manual placements must survive validation and change the actual encoded output."""
import os
from pathlib import Path
import sys
import tempfile
import re
from contextlib import ExitStack

sys.path.insert(0,'.')


def check(name, ok):
    if not ok:raise AssertionError(name)
    print('PASS '+name,flush=True)


def main(work):
    os.environ.update(PEAKCUT_DATA=str(work/'data'),PEAKCUT_FETCH_MODEL='0',PEAKCUT_ACCOUNTS='0',DATABASE_URL='')
    from PIL import Image
    import numpy as np
    from studio import editor, studio_render, render, auth, ctx, db, jobs
    from studio.media import run, probe
    db.init()
    user=auth.local_user()
    with ctx.as_user(user.id), ExitStack() as cleanup:
        cleanup.callback(db.engine.dispose)
        check('new placements stay opt-in for existing clips',editor.clean(editor.DEFAULTS)=={})
        for value in ([], {'unknown':{'x':0,'y':0,'w':1,'h':1}},
                      {'video0':{'x':.9,'y':0,'w':.2,'h':1}},
                      {'headline':{'x':float('nan'),'y':0,'w':.3,'h':.2}},
                      {'caption':{'x':0,'y':0,'w':0,'h':1}},
                      {'video0':{'x':0,'y':0,'w':1,'h':1,'enabled':False}}):
            try:editor.clean({'placements':value})
            except (TypeError,ValueError):pass
            else:raise AssertionError('unsafe placement accepted')
        print('PASS invalid elements, non-finite values and out-of-bounds rectangles rejected',flush=True)
        placement={'x':.1,'y':.1,'w':.4,'h':.3}
        options=editor.settings({'studio':{'placements':{'video0':placement}}})
        check('video geometry uses the saved destination rectangle',studio_render.panel_boxes(options,'fit',720,1280)==[(72,128,288,384)])
        source={'id':'test','start':0,'end':3,'style':'clean','layout':'fit','captions':False,'title':'A manual title',
                'studio':{'template':'x_light','name':'Source name','handle':'@source','profile_source':'custom','resolution':'720','fps':'24'}}
        before=editor.settings(source)
        hidden=editor.settings({'studio':{**source['studio'],'placements':{'headline':dict(placement,enabled=False)}}})
        boxes=studio_render.panel_boxes(before,'fit',360,640)
        normal=studio_render.frame(before,source,boxes,360,640,True)
        removed=studio_render.frame(hidden,source,boxes,360,640,True)
        check('hiding the headline affects its own layer only',np.array_equal(np.asarray(normal)[:160],np.asarray(removed)[:160]) and np.abs(np.asarray(normal)[167:225].astype(int)-np.asarray(removed)[167:225]).sum()>0)
        moved=editor.settings({'studio':{**source['studio'],'placements':{'profile':placement,'headline':dict(placement,enabled=False)}}})
        im=studio_render.frame(moved,source,boxes,360,640,True)
        bounds=im.getbbox()
        check('profile name, photo and handle move together without stretching',bounds is not None and bounds[0]>=36 and bounds[1]>=64 and bounds[2]<=180 and bounds[3]<130)
        heading={'hook':'I DID NOT MEAN TO','title':'','layout':'blur','studio':{}}
        original_options=editor.settings(heading)
        original=studio_render.frame(original_options,heading,[(0,230,360,200)],360,640,False)
        position={'x':.0102,'y':.2253,'w':.86,'h':.15}
        moved_options=editor.settings({'studio':{'placements':{'headline':position}}})
        translated=studio_render.frame(moved_options,heading,[(0,230,360,200)],360,640,False)
        ink_bounds=lambda image:image.getchannel('A').point(lambda a:255 if a>127 else 0).getbbox()
        a,b=ink_bounds(original),ink_bounds(translated)
        check('dragging a headline preserves its exact glyph width and height',abs((a[2]-a[0])-(b[2]-b[0]))<=1 and abs((a[3]-a[1])-(b[3]-b[1]))<=1)
        smaller=editor.settings({'studio':{'placements':{'headline':dict(position,w=.43,h=.075)}}})
        c=ink_bounds(studio_render.frame(smaller,heading,[(0,230,360,200)],360,640,False))
        check('resizing text scales both axes uniformly',abs((c[2]-c[0])/(a[2]-a[0])-.5)<.1 and abs((c[3]-c[1])/(a[3]-a[1])-.5)<.15)
        words=[{'w':'Hello','s':.2,'e':.9},{'w':'world','s':1,'e':1.6}]
        cap=editor.settings({'studio':{'placements':{'caption':{'x':.05,'y':.2,'w':.5,'h':.1}}}})
        ass=studio_render.ass_words(words,{'style':'clean'},cap,720,1280,False)
        anchors=[tuple(map(float,p)) for p in re.findall(r'\\pos\(([-\d.]+),([-\d.]+)\)',ass)]
        check('caption positions update the exported ASS coordinates',bool(anchors) and abs(sum(p[0] for p in anchors)/len(anchors)-324)<20 and all(abs(p[1]-480)<20 for p in anchors))
        no_cap=editor.settings({'studio':{'placements':{'caption':{'x':.05,'y':.2,'w':.5,'h':.1,'enabled':False}}}})
        check('hidden captions produce no subtitle events','Dialogue:' not in studio_render.ass_words(words,{'style':'clean'},no_cap,720,1280,False))
        saved=jobs.edited_clip(source,{'studio':{**source['studio'],'placements':{'video0':placement}}})
        check('manual positions persist through clip editing',saved['studio']['placements']['video0']==placement)
        src=work/'source.mp4'
        run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=12','-f','lavfi','-i','sine=frequency=500:sample_rate=48000','-t','3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(src)])
        clip={**source,'title':'','studio':{'resolution':'720','fps':'24','background':'solid','color':'#101010','placements':{'video0':{'x':.1,'y':.1,'w':.4,'h':.2}}}}
        out=render.render_clip(src,work/'out','positioned',clip,[],320,180)
        frame=work/'output.png'
        run(['ffmpeg','-y','-v','error','-ss','1','-i',str(work/'out'/out['file']),'-frames:v','1',str(frame)])
        pixels=np.array(Image.open(frame).convert('RGB'))
        check('encoded video appears at its manually placed destination',pixels[250,200,0]>180 and pixels[250,200,1]<40)
        check('old video position is empty after moving the panel',pixels[650,360].max()<50)
        check('manual editing preserves duration and the audio stream',abs(probe(work/'out'/out['file'])['duration']-3)<.15 and out['output_width']==720)
    db.engine.dispose()


if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='mc-pos-') as folder:main(Path(folder))
