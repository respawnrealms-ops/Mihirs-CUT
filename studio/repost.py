"""Import a complete YouTube Short and optionally queue it for the chosen channel."""
import json
import math
import re
import shutil
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import accounts, games, hashtags, media

_active = set()
_lock = threading.Lock()
MAX_SECONDS = 180.25  # allow container/audio padding on a three-minute video


def short_url(value):
    """Canonicalise supported YouTube links; never let the downloader open arbitrary hosts."""
    url = urlparse(str(value or '').strip())
    if url.scheme not in ('http', 'https') or url.username or url.password or url.port:
        raise ValueError('Paste a YouTube Short link.')
    host = (url.hostname or '').lower()
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        match = re.fullmatch(r'/shorts/([A-Za-z0-9_-]{11})/?', url.path)
        vid = match[1] if match else parse_qs(url.query).get('v', [''])[0] if url.path == '/watch' else ''
    elif host == 'youtu.be':
        vid = url.path.strip('/')
    else:
        vid = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
        raise ValueError('Paste one YouTube Short link, not a channel or playlist.')
    return 'https://www.youtube.com/shorts/' + vid


def clean(body):
    from . import jobs
    if not isinstance(body, dict):
        raise ValueError('Choose the Short and its upload settings.')
    intent = {'url': short_url(body.get('url'))}
    for key, limit in (('title', 100), ('description', 4400)):
        value = body.get(key, '')
        if value is None:
            value = ''
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f'{key.title()} can contain up to {limit} characters.')
        intent[key] = value.strip()
    value = body.get('hashtags', [])
    if value is None:
        value = []
    if not isinstance(value, (str, list)):
        raise ValueError('Hashtags must be text or a list.')
    if isinstance(value, str):
        value = re.split(r'[\s,]+', value)
    intent['hashtags'] = jobs.clean_hashtags(value)
    intent['privacy'] = body.get('privacy', 'public')
    if intent['privacy'] not in ('public', 'unlisted', 'private'):
        raise ValueError('Choose Public, Unlisted or Private.')
    intent['publish'] = body.get('publish', False)
    if not isinstance(intent['publish'], bool):
        raise ValueError('Choose Upload now or Save to library.')
    intent['account'] = str(body.get('account') or '')[:100]
    if intent['publish']:
        acc = accounts.get(intent['account'])
        if not acc or acc['platform'] != 'youtube':
            raise ValueError('Choose one of your connected YouTube accounts.')
    request = str(body.get('request_id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', request):
        raise ValueError('Refresh the page and try the upload again.')
    intent['request_id'] = request
    return intent


def metadata(intent, source):
    from . import jobs
    title = (intent['title'] or source.get('title') or 'Short')[:100]
    game = games.detect(source.get('title'), title)[0]
    suggested = hashtags.make('', source.get('title') or title, source.get('uploader') or '', game)
    tags = []
    candidates = ['Shorts', *intent['hashtags'], *re.findall(r'#(\w+)', intent['description'])]
    if not intent['hashtags']:
        candidates.extend(suggested)
    for tag in jobs.clean_hashtags(candidates):
        if tag.casefold() not in {x.casefold() for x in tags}:
            tags.append(tag)
    description = intent['description'] or '\n'.join(filter(None, [source.get('title'), 'Original: ' + intent['url']]))
    description = hashtags._TAG_IN_TEXT.sub('', description).strip()
    description = (description[:4400] + '\n\n' + ' '.join('#' + tag for tag in tags)).strip()
    return title, description, tags


def retry(job):
    from . import jobs
    if job.get('kind') != 'repost':
        raise ValueError('This is not an imported Short.')
    with _lock:
        if job['id'] in _active or job['status'] in ('queued', 'running'):
            raise ValueError('This Short is already being prepared.')
        if job['status'] != 'error':
            raise ValueError('Use the post queue to retry an upload. This Short is already ready.')
        job.update(status='queued', stage='Retrying Short import', error=None, cancel=False)
        jobs.enqueue(job)


def run(job):
    from . import jobs, posting
    with _lock:
        if job['id'] in _active:
            return
        _active.add(job['id'])
    try:
        return _run(job, jobs, posting)
    finally:
        with _lock:
            _active.discard(job['id'])


def _run(job, jobs, posting):
    intent = job['repost']
    d = Path(job['dir'])
    def check_cancel():
        if job.get('cancel') or job.get('status') == 'deleted':
            raise ValueError('Short import cancelled before upload.')
    check_cancel()
    jobs._set(job, status='running', stage='Checking the Short', progress=.05, error=None)
    clip = next((c for c in job.get('clips', []) if c.get('repost') and c.get('status') == 'done'
                 and (d / 'clips' / c.get('file', '')).is_file()), None)
    if not clip:
        source = media.info(intent['url'])
        duration = float(source.get('duration') or 0)
        if source.get('kind') != 'video' or source.get('is_live'):
            raise ValueError('Use a finished YouTube Short, not a live stream or playlist.')
        if not math.isfinite(duration) or not 0 < duration <= MAX_SECONDS:
            raise ValueError('A Short must be no longer than three minutes. Use Make clips for a longer video.')
        check_cancel()
        jobs._set(job, title=source['title'], uploader=source.get('uploader') or '', duration=duration,
                  stage='Downloading the complete Short', progress=.15)
        saved = job.get('source_path')
        video = Path(saved) if saved and Path(saved).is_file() else media.download(intent['url'], d, height=1080)
        check_cancel()
        probe = media.probe(video, require_audio=False)
        if not math.isfinite(probe['duration']) or not 0 < probe['duration'] <= MAX_SECONDS:
            raise ValueError('The downloaded video is longer than three minutes.')
        if probe['width'] > probe['height']:
            raise ValueError('This video is landscape. A YouTube Short must be square or vertical.')
        jobs._set(job, source_path=str(video), width=probe['width'], height=probe['height'], duration=probe['duration'],
                  stage='Preparing the title and hashtags', progress=.7)
        out = d / 'clips'
        out.mkdir(exist_ok=True)
        target = out / 'clip01.mp4'
        if video.suffix.lower() == '.mp4':
            shutil.copyfile(video, target)
        else:
            media.run(['ffmpeg', '-y', '-v', 'error', '-i', str(video), '-c', 'copy', '-movflags', '+faststart', str(target)])
        media.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(min(.5, probe['duration'] / 2)), '-i', str(target),
                   '-frames:v', '1', '-q:v', '3', str(out / 'clip01.jpg')])
        shutil.copyfile(out / 'clip01.jpg', d / 'thumb.jpg')
        title, description, tags = metadata(intent, source)
        clip = {'id':'clip01', 'start':0, 'end':probe['duration'], 'title':title, 'hook':'',
                'description':description, 'hashtags':tags, 'hashtags_in_description':True, 'score':0,
                'reason':'Imported complete Short. Original picture, audio and captions retained.',
                'style':'clean', 'layout':'fit', 'studio':{}, 'captions':False, 'caption_words':[],
                'src':str(video), 'src_offset':0, 'file':'clip01.mp4', 'cover':'clip01.jpg', 'status':'done',
                'version':1, 'repost':True, 'output_width':probe['width'], 'output_height':probe['height'],
                'output_duration':probe['duration'], 'made_at':time.time()}
        job.update(clips=[clip], thumb=True)
        (out / 'clip01.json').write_text(json.dumps({k:clip[k] for k in ('title','description','hashtags','start','end')}, indent=1), encoding='utf-8')
        jobs.save(job)
    check_cancel()
    if intent['publish']:
        acc = accounts.get(intent['account'])
        if not acc or acc['platform'] != 'youtube':
            raise ValueError('The selected YouTube account was disconnected. The Short is saved in your library.')
        posting.enqueue(job, clip, [intent['account']], now=True)
        job['repost_post_ids'] = list(clip.get('posts') or {})
        stage = 'Upload queued' if not accounts.settings()['paused'] else 'Upload queued — posting is paused in Settings'
    else:
        stage = 'Short saved to library'
    jobs._set(job, status='done', stage=stage, progress=1, error=None)
