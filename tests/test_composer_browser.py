"""Real Chromium checks: choices, immediate preview, saved positions and a mocked submission.

Run against an isolated app with an empty data folder, never a production account:
    python tests/test_composer_browser.py http://127.0.0.1:8804
Requires Playwright and a locally installed Chrome browser. No video is downloaded or posted.
"""
import base64
import json
import os
from pathlib import Path
import sys

if os.environ.get('MIHIS_BROWSER_TOOLS'):
    sys.path.insert(0, os.environ['MIHIS_BROWSER_TOOLS'])
from playwright.sync_api import sync_playwright, expect


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print('PASS '+name, flush=True)


def main(base):
    root=Path(__file__).resolve().parent.parent
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome', headless=True)
        page=browser.new_page(viewport={'width':1500,'height':1100})
        page.set_default_timeout(12000)
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        sent=[]
        def jobs(route):
            if route.request.method=='POST':
                sent.append(route.request.post_data_json)
                route.fulfill(json={'id':'browser-test-only'})
            else:
                route.continue_()
        page.route('**/api/jobs',jobs)
        thumb='data:image/jpeg;base64,'+base64.b64encode((root/'web/brand/frame-source-v2.jpg').read_bytes()).decode()
        page.route('**/api/preview?*', lambda route:route.fulfill(json={'title':'Preview source title','uploader':'Test source channel','duration':1200,'is_live':False,'thumb':thumb}))
        try:
            # Suppress the first-run guided tour in this empty test account.
            def status(route):
                data=route.fetch().json()
                data['tour']=False
                data['speech']['en']['state']='ready'
                route.fulfill(json=data)
            page.route('**/api/status',status)
            page.goto(base+'/app/videos',wait_until='domcontentloaded')
            page.wait_for_selector('#addform .mc-studio',state='attached')
            page.locator('[data-act=toggleopts]').click()
            page.locator('[data-mc-tab=captions]').click()
            page.locator('[data-seg=o_style][data-v=neon]').click()
            page.locator('[data-mc-tab=frame]').click()
            page.locator('[data-seg=o_layout][data-v=duo]').click()
            check('caption and layout tiles update their actual form values',page.locator('#o_style').input_value()=='neon' and page.locator('#o_layout').input_value()=='duo')
            check('compact composer visibly marks its selected tile',page.locator('[data-seg=o_style][data-v=neon]').evaluate("e=>getComputedStyle(e).outlineStyle")=='solid')
            check('layout selection updates preview immediately',page.locator('[data-mc-live]').get_attribute('data-layout')=='duo' and page.locator('[data-mc-element=video1]').is_visible())
            check('caption style updates the real canvas sample',page.locator('[data-mc-card-caption] [data-effect=glow]').count()==1)
            page.locator('[data-live-style]').select_option('gaming')
            check('quick caption selector stays in sync with the original tiles',page.locator('#o_style').input_value()=='gaming')
            page.locator('[data-live-captions]').uncheck()
            check('caption toggle immediately hides subtitles',not page.locator('[data-mc-card-caption]').is_visible())
            page.locator('[data-live-captions]').check()
            page.locator('[data-live-style]').select_option('neon')
            page.locator('[data-mc-padding]').fill('4.5')
            check('fractional padding cannot silently block the form',page.locator('#addform').evaluate('e=>e.checkValidity()'))
            page.locator('[data-mc-template=x_light]').click()
            page.locator('[data-mc=headline]').fill('An instant headline')
            check('headline text appears before making a clip',page.locator('[data-mc-card-headline]').inner_text()=='An instant headline')
            page.locator('[data-mc-tab=captions]').click()
            check('preview stays visible while changing caption controls',page.locator('[data-mc-live]').is_visible())
            page.locator('[data-mc=caption_size]').fill('1.3')
            page.locator('[data-mc-tab=frame]').click()
            page.locator('[data-live-layer]').select_option('headline')
            page.locator('[data-live-number=x]').fill('12')
            place=page.locator('[data-mc-placements]').input_value()
            check('numeric positioning saves a normalised canvas rectangle',abs(json.loads(place)['headline']['x']-.12)<.001)
            node=page.locator('[data-mc-element=headline]')
            node.scroll_into_view_if_needed()
            r=node.bounding_box()
            page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2)
            page.mouse.down();page.mouse.move(r['x']+r['width']/2+15,r['y']+r['height']/2+18,steps=5);page.mouse.up()
            check('dragging the canvas changes its saved export position',json.loads(page.locator('[data-mc-placements]').input_value())['headline']['y']>.262)
            old_width=json.loads(page.locator('[data-mc-placements]').input_value())['headline']['w']
            handle=page.locator('[data-live-resize]');handle.scroll_into_view_if_needed();h=handle.bounding_box()
            page.mouse.move(h['x']+h['width']/2,h['y']+h['height']/2);page.mouse.down();page.mouse.move(h['x']-20,h['y']-20,steps=5);page.mouse.up()
            check('the corner handle resizes the saved element',json.loads(page.locator('[data-mc-placements]').input_value())['headline']['w']<old_width)
            page.locator('[data-live-text]').fill('Your custom text')
            page.locator('[data-live-add-text]').click()
            check('manual text is added to both the preview and saved profile',page.locator('[data-mc-element=sticker0]').inner_text()=='Your custom text' and page.locator('[data-mc-list=stickers] .mc-row').count()==1)
            page.locator('[data-live-selected-text]').fill('Edited custom text')
            check('added text can be edited directly in the preview inspector',page.locator('[data-mc-element=sticker0]').inner_text()=='Edited custom text')
            page.locator('[data-live-selected-text]').fill('Your custom text')
            page.locator('[data-live-layer]').select_option('headline')
            page.locator('[data-live-visible]').uncheck()
            check('an element can be hidden in the preview and export profile',not page.locator('[data-mc-element=headline]').is_visible() and json.loads(page.locator('[data-mc-placements]').input_value())['headline']['enabled'] is False)
            page.locator('[data-live-visible]').check()
            page.locator('#url').fill('https://www.youtube.com/watch?v=abcdefghijk')
            expect(page.locator('[data-mc-card-name]')).to_have_text('Test source channel')
            check('new links preview their own source rather than a previous job',page.locator('[data-mc-card-name]').inner_text()=='Test source channel')
            check('thumbnail previews disclose that they are not rendered video','thumbnail' in page.locator('[data-live-note]').inner_text())
            page.locator('[data-mc-tab=media]').click()
            with page.expect_response('**/api/editor/assets') as upload:
                page.locator('[data-mc-upload]').set_input_files(str(root/'web/brand/frame-source-v2.jpg'))
            media_id=upload.value.json()['id']
            expect(page.locator(f'[data-live-media] option[value="{media_id}"]')).to_have_count(1)
            page.locator('[data-live-media]').select_option(media_id)
            page.locator('[data-live-add-image]').click()
            check('uploaded images can be added and positioned in the live canvas',page.locator('[data-mc-element=sticker1] img').count()==1)
            page.locator('[data-live-crop-details]>summary').click()
            crop=page.locator('[data-live-crop]');crop.scroll_into_view_if_needed();r=crop.bounding_box()
            page.mouse.move(r['x']+r['width']*.2,r['y']+r['height']*.2);page.mouse.down();page.mouse.move(r['x']+r['width']*.8,r['y']+r['height']*.8,steps=5);page.mouse.up()
            check('manual source crops are saved before a clip is made',page.locator('[data-mc-list=regions] .mc-row').count()==1)
            page.locator('[data-live-crop-details]>summary').click()
            page.locator('[data-mc-tab=frame]').click()
            page.locator('[data-mc-live]').scroll_into_view_if_needed()
            page.screenshot(path=str(root/'composer-live-preview.png'))
            page.locator('[data-act=toggleopts]').click()
            page.locator('#goBtn').click()
            expect(page.locator('#goBtn')).to_be_enabled()
            check('Make clips submits once after changing and closing options',len(sent)==1)
            options=sent[0]['options']
            check('submitted profile includes manual text and dragged positions',options['studio']['stickers'][0]['text']=='Your custom text' and options['studio']['placements']['headline']['x']>=.12)
            check('Shorts workflow and selected captions remain in the request',options['mode']=='shorts' and options['captions'] and options['style']=='clean')
            check('image additions and source crops survive submission',options['studio']['stickers'][1]['asset']==media_id and len(options['studio']['regions'])==1)
            # Errors in option collection must not leave the composer permanently busy.
            page.locator('#url').fill('https://www.youtube.com/watch?v=lmnopqrstuv')
            expect(page.locator('#attIn .lp')).to_be_visible()
            page.evaluate("() => {window.MihisStudio.read=()=>{throw Error('Test option failure')};}")
            page.locator('#goBtn').click()
            check('option errors leave Make clips usable',not page.locator('#goBtn').is_disabled() and len(sent)==1)
            check('no uncaught browser exceptions',not errors)
            # Upload attachments are playable locally before uploading or making clips.
            page.reload(wait_until='domcontentloaded')
            page.wait_for_selector('#addform .mc-studio',state='attached')
            page.locator('#file').set_input_files(str(root/'web/brand/demo-bounce.mp4'))
            page.locator('[data-act=toggleopts]').click()
            expect(page.locator('[data-live-play]')).to_be_enabled()
            source_video=page.locator('.mc-card-video > video')
            expect(source_video).to_have_attribute('src',__import__('re').compile(r'^blob:'))
            page.locator('[data-live-play]').click()
            check('uploaded videos play in the canvas before Make clips',source_video.evaluate('e=>!e.paused'))
            check('no browser exceptions during local upload preview',not errors)
            print('Browser checks completed.',flush=True)
        except Exception:
            print('Browser errors:',errors,flush=True)
            page.screenshot(path=str(root/'composer-test-failure.png'),full_page=True)
            raise
        finally:
            browser.close()


if __name__=='__main__':
    main(sys.argv[1])
