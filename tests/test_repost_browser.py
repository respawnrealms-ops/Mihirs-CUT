"""Short-link UI checks against an isolated app; all publishing requests are mocked."""
import base64
import os
from pathlib import Path
import sys

if os.environ.get('MIHIS_BROWSER_TOOLS'):
    sys.path.insert(0,os.environ['MIHIS_BROWSER_TOOLS'])
from playwright.sync_api import sync_playwright, expect


def check(name, value):
    if not value:raise AssertionError(name)
    print('PASS '+name,flush=True)


def main(base):
    if base.endswith(':8765'):
        raise RuntimeError('Use an isolated test app, never the production app.')
    root=Path(__file__).resolve().parent.parent
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1365,'height':1000})
        errors=[];sent=[];clipping=[];pending=[]
        state={'fail':False,'hold':False}
        page.on('pageerror',lambda e:errors.append(str(e)))
        def status(route):
            data=route.fetch().json();data['tour']=False;data['speech']['en']['state']='missing';route.fulfill(json=data)
        page.route('**/api/status',status)
        picture='data:image/jpeg;base64,'+base64.b64encode((root/'web/brand/frame-source-v2.jpg').read_bytes()).decode()
        preview={'title':'A complete Short','uploader':'Test source','duration':45,'is_live':False,'thumb':picture}
        def lookup(route):
            if state['hold']:pending.append(route)
            else:route.fulfill(json=preview)
        page.route('**/api/preview?*',lookup)
        def post(route):
            sent.append(route.request.post_data_json)
            if state['fail']:state['fail']=False;route.abort('failed')
            else:route.fulfill(json={'id':'mock-import','kind':'repost','status':'queued'})
        page.route('**/api/repost-shorts',post)
        def jobs(route):
            if route.request.method=='POST':clipping.append(route.request.post_data_json);route.fulfill(json={'id':'no-real-job'})
            else:route.continue_()
        page.route('**/api/jobs',jobs)
        try:
            page.goto(base+'/app/videos',wait_until='domcontentloaded')
            page.wait_for_selector('#o_mode')
            page.locator('#o_mode').select_option('repost')
            expect(page.locator('#repost-options')).to_be_visible()
            check('direct upload is a distinct composer option',page.locator('#goBtn').inner_text()=='Upload Short')
            check('templates and upload-file controls stay out of the direct flow',not page.locator('[data-act=toggleopts]').is_visible() and not page.locator('[data-act=pickfile]').is_visible())
            page.locator('#url').fill('https://www.youtube.com/shorts/abcdefghijk')
            expect(page.locator('#attIn .lp .tx')).to_contain_text('A complete Short')
            page.locator('#goBtn').click()
            check('a channel is required before automatic publishing',not sent)
            page.locator('#r_account').select_option('test-youtube')
            page.locator('#r_privacy').select_option('private')
            page.locator('#r_title').fill('My Short title')
            page.locator('#r_description').fill('My description')
            page.locator('#r_hashtags').fill('#gaming #gta6')
            state['fail']=True
            page.locator('#goBtn').click()
            expect(page.locator('#goBtn')).to_be_enabled()
            check('a failed request leaves the upload button usable',len(sent)==1)
            page.locator('#goBtn').click()
            expect(page.locator('#attIn .lp')).to_have_count(0)
            check('request retries reuse the same idempotency key',len(sent)==2 and sent[0]['request_id']==sent[1]['request_id'])
            body=sent[1]
            check('selected channel, privacy and metadata are sent explicitly',body['account']=='test-youtube' and body['privacy']=='private' and body['title']=='My Short title' and body['description']=='My description' and body['hashtags']=='#gaming #gta6' and body['publish'] is True)
            check('direct uploading skips clipping and missing-speech-model prompts',not clipping and page.locator('#langnote').count()==0)
            page.locator('#r_action').select_option('save')
            check('save-only is available without a publishing account',page.locator('#r_account').is_disabled() and page.locator('#goBtn').inner_text()=='Import Short')
            page.locator('#url').fill('https://www.youtube.com/shorts/lmnopqrstuv')
            expect(page.locator('#attIn .lp .tx')).to_contain_text('A complete Short')
            page.locator('#goBtn').click()
            expect(page.locator('#attIn .lp')).to_have_count(0)
            check('save-only never requests publication',sent[-1]['publish'] is False)
            # Switching modes cancels an old pending start; metadata completion cannot publish on its own.
            page.locator('#o_mode').select_option('shorts')
            state['hold']=True
            page.locator('#url').fill('https://www.youtube.com/shorts/01234567890')
            page.locator('#goBtn').click()
            page.locator('#o_mode').select_option('repost')
            page.locator('#r_action').select_option('publish')
            before=len(sent)
            check('source lookup is pending for the mode-switch test',bool(pending))
            for request in pending:request.fulfill(json=preview)
            state['hold']=False
            expect(page.locator('#attIn .lp .tx')).to_contain_text('A complete Short')
            check('changing mode never auto-publishes a previously queued clipping request',len(sent)==before and not clipping)
            page.set_viewport_size({'width':390,'height':844})
            check('direct upload fields fit a phone-sized viewport',page.locator('#repost-options').evaluate('e=>e.scrollWidth<=e.clientWidth+2'))
            check('no uncaught browser exceptions',not errors)
            print('Short upload browser checks completed without a real upload.',flush=True)
        except Exception:
            print('Browser exceptions:',errors,flush=True)
            page.screenshot(path=str(root/'repost-ui-failure.png'),full_page=True)
            raise
        finally:browser.close()


if __name__=='__main__':main(sys.argv[1])
