/* Instant, local canvas editing. Previewing never starts a download, render or post. */
(() => {
  'use strict';
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const states = new WeakMap();
  const labels = {video0:'Video / shot 1', video1:'Shot 2 / facecam', video2:'Shot 3',
    profile:'Channel profile', headline:'Headline', caption:'Captions', subline:'Supporting line',
    news:'News bar', hook_label:'Hook label', news_strap:'News strapline', ticker:'News ticker',
    watermark:'Watermark', logo:'Logo'};
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  const round = v => Math.round(v * 10000) / 10000;
  const box = (x,y,w,h) => ({x,y,w,h});
  const rectStyle = (node, r) => {
    node.style.setProperty('left', `${r.x * 100}%`, 'important');
    node.style.setProperty('top', `${r.y * 100}%`, 'important');
    node.style.setProperty('width', `${r.w * 100}%`, 'important');
    node.style.setProperty('height', `${r.h * 100}%`, 'important');
    node.style.maxHeight = 'none'; node.style.aspectRatio = 'auto';
    node.style.transform = 'none'; node.style.bottom = 'auto';
  };
  function placementInput(el) { return $('[data-mc-placements]', el); }
  function placements(el) { return JSON.parse(placementInput(el).value || '{}'); }
  function setPlacements(el, value) { placementInput(el).value = JSON.stringify(value); }
  function isCustom(o) {
    const defaults = window.MihisBridge().status.studio.defaults;
    return Object.keys(defaults).some(k => JSON.stringify(o[k]) !== JSON.stringify(defaults[k]));
  }
  function panelBoxes(o, layout, ratio, custom, aspect) {
    const p = Number(o.padding) / 1080, py = p * ratio;
    let boxes;
    if (o.template !== 'none') {
      let r = o.template === 'youtube_video' ? box(p,py,1-2*p,1-2*py) :
        ratio > 1 ? box(.36,.12,.6-p,.7) :
        box(Math.max(.025,p),.36,1-2*Math.max(.025,p),Math.min((1-2*Math.max(.025,p))*ratio*9/16,.34));
      const children = panelBoxes({...o,template:'none',padding:0,placements:{}},layout,r.w/r.h*ratio,true,aspect);
      return ['duo','split','trio','pip','gameplay','facecam_top','split_top','split_bottom'].includes(layout) ?
        children.map(c=>box(r.x+c.x*r.w,r.y+c.y*r.h,c.w*r.w,c.h*r.h)) : [r];
    }
    if (['duo','split','facecam_top','split_top','split_bottom'].includes(layout)) {
      const half=(1-3*py)/2;
      boxes=[box(p,py,1-2*p,half),box(p,2*py+half,1-2*p,half)];
      if (layout==='split_top'||layout==='split_bottom') {
        const wide=Math.min(half,(1-2*p)*ratio*9/16),index=layout==='split_top'?0:1;
        boxes[index]=box(p,index===0?py:1-py-wide,1-2*p,wide);
        boxes[1-index]=box(p,index===0?wide+2*py:py,1-2*p,1-wide-3*py);
      }
    } else if(layout==='trio') {
      const h=(1-4*py)/3; boxes=[0,1,2].map(i=>box(p,py+i*(h+py),1-2*p,h));
    } else if(layout==='pip'||layout==='gameplay') {
      const w=Number(o.pip_size),h=w*ratio*(o.pip_shape==='circle'?1:.75);
      boxes=[box(p,py,1-2*p,1-2*py),box(o.pip_corner.endsWith('left')?p:1-p-w,o.pip_corner.startsWith('top')?py:1-py-h,w,h)];
    } else if(['fit','blur','zoom'].includes(layout)||layout.startsWith('canvas_')) {
      if(custom) boxes=[box(p,.28,1-2*p,.44)];
      else {
        const width=layout.startsWith('canvas_')?.92:1;
        const h=layout==='zoom'?1000/1920:Math.min(1,width*ratio/aspect);
        boxes=[box((1-width)/2,(1-h)/2,width,h)];
      }
    } else boxes=[box(p,py,1-2*p,1-2*py)];
    return boxes;
  }
  function defaultsFor(s, o, basic) {
    const ratio=Number(o.ratio.split(':')[0])/Number(o.ratio.split(':')[1]);
    const custom=isCustom(o), wide=ratio>1, tpl=o.template;
    const media=s.video.readyState>=2?s.video:s.image;
    const aspect=(media.videoWidth||media.naturalWidth||16)/(media.videoHeight||media.naturalHeight||9);
    const positions={};
    panelBoxes(o,basic.layout,ratio,custom,aspect).forEach((r,i)=>positions['video'+i]=r);
    positions.headline=box(.07,o.headline_y||.12,.86,.15);
    positions.caption=box(.05,(o.caption_y||.78)-.045,.9,.09);
    if(!custom&&['blur','fit','zoom'].includes(basic.layout)) {
      const r=positions.video0;
      positions.headline=box(.07,Math.max(230/1920,r.y-190/1920)-.04,.86,.09);
      positions.caption=box(.05,Math.min(1640/1920,r.y+r.h+180/1920)-.045,.9,.09);
    }
    if(basic.layout.startsWith('canvas_')) positions.caption=box(.05,.80,.9,.09);
    if(tpl!=='none') {
      positions.profile=wide?box(.05,.09,.28,.1):box(.05,.16,.9,.1);
      positions.headline=wide?box(.05,.29,.28,.35):box(.05,.16,.9,.16);
      positions.caption=box(.05,(o.caption_y||.84)-.045,.9,.09);
      if(['x_light','x_dark'].includes(tpl)) positions.headline=wide?box(.05,.29,.28,.35):box(.05,.262,.9,.085);
      if(tpl==='tiktok_hook') {
        positions.hook_label=box(.05,.065,.36,.04);
        positions.headline=box(.05,.13,wide?.28:.9,.16);
        positions.profile=box(.05,.305,wide?.28:.9,.032);
      }
      if(tpl==='breaking_news') {
        delete positions.profile;
        positions.news=box(.05,.07,wide?.28:.9,.065);
        positions.headline=box(.05,.153,wide?.28:.9,wide?.33:.15);
        positions.news_strap=box(.05,wide?.51:.32,wide?.28:.9,.032);
        if(o.ticker) positions.ticker=box(.05,.945,.9,.035);
      }
      if(tpl==='youtube_video') {
        positions.profile=box(.05,.045,.31,.09);
        positions.headline=box(.05,.68,.70,.13);
      }
    }
    if(o.subline) positions.subline=box(.05,wide?.68:.72,.9,.07);
    if(o.watermark) positions.watermark=box(.05,.965,.9,.025);
    if(o.logo) {
      const size=Number(o.logo_size),h=size*ratio;
      positions.logo=box(o.logo_corner.endsWith('left')?.05:.95-size,o.logo_corner.startsWith('top')?.04:.94-h,size,h);
    }
    const basis=Object.fromEntries(Object.entries(positions).map(([key,r])=>[key,{...r}]));
    Object.entries(o.placements||{}).forEach(([key, value])=>{if(positions[key])positions[key]={...positions[key],...value};});
    (o.stickers||[]).forEach((r,i)=>{
      const a=s.api.assets().find(a=>a.id===r.asset),aspect=r.asset?(a?.width||16)/(a?.height||9):600/180;
      const h=r.size*ratio/aspect;
      positions['sticker'+i]=box(r.x-r.size/2,r.y-h/2,r.size,h);
    });
    return {positions,ratio,custom,basis};
  }
  function updateSelection(s) {
    const r=s.positions[s.selected],node=s.nodes[s.selected];
    s.selection.hidden=!r||!node||node.hidden;
    $$('[data-live-number]',s.controls).forEach(i=>{i.disabled=!r;if(document.activeElement!==i)i.value=r?(r[i.dataset.liveNumber]*100).toFixed(1):'';});
    const visible=$('[data-live-visible]',s.controls);
    visible.disabled=!r||s.selected.startsWith('video')||s.selected.startsWith('sticker');
    visible.checked=r?.enabled!==false;
    if(!s.selection.hidden) rectStyle(s.selection,r);
    $('[data-live-layer]',s.controls).value=s.selected;
    const edit=$('[data-live-selected-text]',s.controls),o=s.api.read();
    const textKey={headline:'headline',subline:'subline',watermark:'watermark',hook_label:'hook_label',news:'news_label',news_strap:'news_strap',ticker:'ticker'}[s.selected];
    const sticker=s.selected.startsWith('sticker')?o.stickers[Number(s.selected.slice(7))]:null;
    edit.closest('label').hidden=!textKey&&!(sticker&&!sticker.asset);
    if(document.activeElement!==edit)edit.value=textKey?(o[textKey]||s.nodes[s.selected]?.textContent||''):sticker?.text||'';
    $('[data-live-delete]',s.controls).disabled=!sticker;
  }
  function select(s,key) {s.selected=key;updateSelection(s);}
  function saveBox(s,key,r,commit=true) {
    r={...r,x:round(clamp(r.x,0,.98)),y:round(clamp(r.y,0,.98))};
    r.w=round(clamp(r.w,.02,1-r.x));r.h=round(clamp(r.h,.02,1-r.y));
    if(key.startsWith('sticker')) {
      const index=Number(key.slice(7)),rows=$$('[data-mc-list=stickers] .mc-row',s.el),row=rows[index];
      if(!row)return;
      for(const [field,value] of Object.entries({x:r.x+r.w/2,y:r.y+r.h/2,size:r.w})) $('[data-row='+field+']',row).value=round(value);
    } else {
      const value=placements(s.el);value[key]=r;setPlacements(s.el,value);
    }
    refresh(s.el);
    if(commit)s.api.commit();
  }
  function drawCover(ctx,media,width,height,region,fit) {
    const sw=media.videoWidth||media.naturalWidth,sh=media.videoHeight||media.naturalHeight;
    if(!sw||!sh)return;
    const r=region||box(0,0,1,1),sx=r.x*sw,sy=r.y*sh,rw=r.w*sw,rh=r.h*sh;
    const scale=fit?Math.min(width/rw,height/rh):Math.max(width/rw,height/rh);
    ctx.drawImage(media,sx,sy,rw,rh,(width-rw*scale)/2,(height-rh*scale)/2,rw*scale,rh*scale);
  }
  function draw(s) {
    if(!s.el.isConnected)return;
    const o=s.api.read(),basic=s.api.basic(),media=s.video.readyState>=2?s.video:s.image;
    const cw=s.canvas.clientWidth||280,ch=cw/s.ratio;
    const bg=s.background;
    bg.width=Math.round(cw*2);bg.height=Math.round(ch*2);
    const context=bg.getContext('2d');
    const blurred=o.background==='blur'||(o.background==='layout'&&['blur','zoom'].includes(basic.layout));
    bg.hidden=!blurred;
    if(blurred) {
      context.filter=`blur(${Math.max(1,Number(o.blur)*cw/1080)*2}px) brightness(${1-Number(o.dim)})`;
      drawCover(context,media,bg.width,bg.height,null,false);
    }
    for(const [key,r] of Object.entries(s.positions)) {
      if(!key.startsWith('video'))continue;
      const index=Number(key.slice(5)),c=$('canvas',s.nodes[key]),w=Math.max(2,Math.round(cw*r.w*2)),h=Math.max(2,Math.round(ch*r.h*2));
      if(c.width!==w||c.height!==h){c.width=w;c.height=h;}
      const ctx=c.getContext('2d');ctx.fillStyle='#080b0e';ctx.fillRect(0,0,w,h);
      let regions=o.regions||[];
      if(o.swap)regions=[...regions].reverse();
      let region=regions[index];
      if(!region&&['duo','split','trio','split_top','split_bottom'].includes(basic.layout))region=box((index%2)*.5,0,.5,1);
      if(!region&&['pip','gameplay','facecam_top'].includes(basic.layout)&&index===(basic.layout==='facecam_top'?0:1)) {
        const source=s.api.source();
        if(source?.facecam&&source.width&&source.height) {
          const [x,y,fw,fh]=source.facecam;region=box(x/source.width,y/source.height,fw/source.width,fh/source.height);
        } else region=box(.68,.03,.3,.35);
      }
      if(!region&&basic.layout==='left')region=box(0,0,.5,1);
      if(!region&&basic.layout==='right')region=box(.5,0,.5,1);
      const fit=['fit','blur','zoom'].includes(basic.layout)||basic.layout.startsWith('canvas_')||(o.template!=='none'&&s.nodes.video1?.hidden);
      const slot=(o.slots||[]).find(r=>r.slot===index&&r.asset),asset=slot&&s.media.get(slot.asset);
      drawCover(ctx,asset&&(asset.complete||asset.readyState>=2)?asset:media,w,h,slot?null:region,fit);
    }
    if(s.cropCanvas&&!s.cropDetails.hidden&&s.cropDetails.open) {
      const c=s.cropCanvas,ctx=c.getContext('2d');c.width=640;c.height=Math.round(640*((media.videoHeight||media.naturalHeight||9)/(media.videoWidth||media.naturalWidth||16)));
      drawCover(ctx,media,c.width,c.height,null,true);
      (o.regions||[]).forEach((r,i)=>{ctx.strokeStyle='#ff8b2b';ctx.lineWidth=3;ctx.strokeRect(r.x*c.width,r.y*c.height,r.w*c.width,r.h*c.height);ctx.fillStyle='#ff8b2b';ctx.fillText(String(i+1),r.x*c.width+6,r.y*c.height+16);});
    }
  }
  function loadSource(el) {
    const s=states.get(el);if(!s)return;
    const source=s.api.source(),key=source?.key||source?.url||source?.thumb||'demo';
    if(s.sourceKey===key)return;
    s.sourceKey=key;s.video.pause();s.video.removeAttribute('src');s.video.load();
    s.image.onload=()=>{refresh(el);draw(s);};
    s.image.src=source?.thumb||'/brand/frame-source-v2.jpg';
    if(source?.url) {
      s.video.src=source.url;s.video.preload='metadata';
      s.video.onloadedmetadata=()=>{s.video.currentTime=clamp(source.seek||0,0,Math.max(0,s.video.duration-.05));refresh(el);};
      s.video.onseeked=()=>draw(s);s.video.ontimeupdate=()=>draw(s);
      s.video.onerror=()=>{$('[data-live-note]',s.aside).textContent='Source video is unavailable. Showing a sample; your edits still apply to the export.';};
    }
    $('[data-live-play]',s.controls).disabled=!source?.url;
    $('[data-live-note]',s.aside).textContent=source?.kind==='thumbnail'?
      'Instant styling on this link’s thumbnail. Video and real subtitle timing are available after processing.':source?.url?
      'Instant arrangement preview. Sample caption text is for preview only; exact timing is available in Render preview.':
      'Demo frame. Paste a link or add a video to preview your source. Caption text below is a sample.';
  }
  function refresh(el) {
    const s=states.get(el);if(!s)return;
    const o=s.api.read(),basic=s.api.basic(),layout=defaultsFor(s,o,basic);
    s.positions=layout.positions;s.ratio=layout.ratio;s.custom=layout.custom;
    s.canvas.dataset.layout=basic.layout;s.canvas.dataset.template=o.template;
    $('[data-live-style]',s.quick).value=basic.style;
    $('[data-live-layout]',s.quick).value=basic.layout;
    $('[data-live-captions]',s.quick).checked=basic.captions;
    s.canvas.style.aspectRatio=o.ratio.replace(':','/');
    let color=o.color;
    if(o.background==='layout')color=o.template==='x_light'?'#fff':basic.layout==='canvas_white'?'#fff':basic.layout==='canvas_cream'?'#fff3df':o.template==='none'?'#000':o.template==='breaking_news'?'#0b0f18':'#111';
    if(o.background==='layout'||o.background==='solid')s.canvas.style.background=color;
    s.canvas.classList.toggle('is-light',/^#fff/i.test(color)&&['solid','layout'].includes(o.background));
    const caption=s.nodes.caption;
    caption.hidden=!basic.captions;
    const name=o.name||s.api.source()?.uploader||'Source channel';
    $('[data-mc-card-name]',el).textContent=name;
    const title=o.headline||basic.hook||s.api.source()?.title||'Your headline above the video';
    s.nodes.headline.textContent=title;
    const text=$('[data-live-sample]',s.controls).value||s.api.caption()||'Clip this moment';
    const signature=basic.style+'|'+text+'|'+o.caption_size;
    if(s.captionSignature!==signature) {
      s.captionSignature=signature;
      caption.innerHTML=window.MihisBridge().capPreview(basic.style);
      const parts=text.trim().split(/\s+/),last=parts.pop()||'moment';
      $('.cap-words',caption).replaceChildren(document.createTextNode(parts.join(' ')+(parts.length?' ':'')),Object.assign(document.createElement('b'),{textContent:last}));
    }
    caption.style.fontSize=`${5*Number(o.caption_size)*(o.placements?.caption?.w||.9)/.9}cqw`;
    for(const [key,node] of Object.entries(s.nodes)) {
      const r=s.positions[key];
      node.hidden=!r||r.enabled===false||(key==='caption'&&!basic.captions)||(key==='headline'&&o.template==='youtube_video'&&!o.headline);
      if(r) {
        rectStyle(node,r);
        const reference=layout.basis[key];
        const scale=reference?Math.min(r.w/reference.w,r.h/reference.h):1;
        node.style.setProperty('--mc-fit',scale);
        if(['headline','subline','watermark','news','news_strap','ticker','hook_label'].includes(key)) {
          node.style.fontSize='';
          if(Math.abs(scale-1)>.001&&s.canvas.clientWidth>0){
            const base=parseFloat(getComputedStyle(node).fontSize)/s.canvas.clientWidth*100;
            node.style.fontSize=`${base*scale}cqw`;
          }
        }
        // Override template-specific display declarations when an element is present.
        node.style.display=node.hidden?'none':key==='profile'||key==='news'?'flex':'block';
      } else node.style.display='none';
      if(key.startsWith('video')&&r) {
        const i=Number(key.slice(5));
        node.style.borderRadius=i===1&&['pip','gameplay'].includes(basic.layout)&&o.pip_shape==='circle'?'50%':`${o.radius/1080*100}cqw`;
      }
    }
    s.nodes.watermark.textContent=o.watermark;
    if(o.logo) s.nodes.logo.src='/api/editor/assets/'+o.logo;
    for(const [i,r] of (o.stickers||[]).entries()) {
      const key='sticker'+i;let node=s.nodes[key];
      if(!node){node=document.createElement('div');node.className='mc-live-sticker';node.dataset.mcElement=key;s.canvas.append(node);s.nodes[key]=node;}
      const signature=JSON.stringify(r);
      if(node.dataset.signature!==signature){node.replaceChildren();if(r.asset){const img=document.createElement('img');img.src='/api/editor/assets/'+r.asset;img.alt='Sticker';node.append(img);}else node.textContent=r.text||'';node.dataset.signature=signature;}
      rectStyle(node,s.positions[key]);node.hidden=false;node.style.display='grid';node.style.fontSize=`${15*r.size}cqw`;
    }
    for(const [key,node] of Object.entries(s.nodes))if(key.startsWith('sticker')&&!s.positions[key]){node.remove();delete s.nodes[key];}
    const selectBox=$('[data-live-layer]',s.controls),entries=Object.keys(s.positions).filter(k=>s.nodes[k]);
    const sig=entries.join('|');
    if(s.layerSignature!==sig){selectBox.replaceChildren(...entries.map(key=>new Option(labels[key]||'Sticker '+(Number(key.slice(7))+1),key)));s.layerSignature=sig;}
    if(!s.positions[s.selected])s.selected=entries[0]||'';
    const mediaSelect=$('[data-live-media]',s.controls),images=s.api.assets().filter(a=>a.kind==='image');
    const mediaSig=images.map(a=>a.id).join('|');
    if(s.mediaSignature!==mediaSig){const value=mediaSelect.value;mediaSelect.replaceChildren(new Option('Choose an image from Media & audio',''),...images.map(a=>new Option(a.name,a.id)));mediaSelect.value=value;s.mediaSignature=mediaSig;}
    for(const slot of o.slots||[])if(slot.asset&&!s.media.has(slot.asset)){
      const asset=s.api.assets().find(a=>a.id===slot.asset),media=asset?.kind==='video'?document.createElement('video'):new Image();
      if(asset?.kind==='video'){media.muted=true;media.loop=true;media.playsInline=true;media.onloadeddata=()=>{media.currentTime=slot.offset||0;draw(s);};media.onseeked=()=>draw(s);}
      else media.onload=()=>draw(s);
      media.src='/api/editor/assets/'+slot.asset;s.media.set(slot.asset,media);
    }
    updateSelection(s);loadSource(el);draw(s);
  }
  function controlsHTML() {
    return `<div class="mc-direct-tools"><h4>Arrange your canvas</h4><p>Drag an element to move it. Drag its corner to resize. Use arrow keys for small moves.</p>
      <label>Selected element<select data-live-layer aria-label="Selected canvas element"></select></label>
      <div class="mc-position-grid">${['x','y','w','h'].map((key,i)=>`<label>${['Left','Top','Width','Height'][i]} %<input type="number" min="0" max="100" step="0.1" data-live-number="${key}"></label>`).join('')}</div>
      <label class="mc-check"><input type="checkbox" data-live-visible checked>Show this element</label>
      <label hidden>Selected text<input type="text" data-live-selected-text maxlength="200"></label>
      <div class="mc-tools"><button type="button" class="mc-btn" data-live-reset>Reset position</button><button type="button" class="mc-btn" data-live-play>Play source</button></div>
      <button type="button" class="mc-btn" data-live-delete disabled>Remove selected text / image</button>
      <label>Sample subtitle text <input type="text" data-live-sample placeholder="Clip this moment" maxlength="120"></label>
      <label>Add your own text<input type="text" data-live-text placeholder="Your text or emoji" maxlength="30"></label>
      <button type="button" class="mc-btn" data-live-add-text>Add text to video</button>
      <label>Add an image<select data-live-media></select></label><button type="button" class="mc-btn" data-live-add-image>Add image to video</button>
      <p>Upload photos, logos or music in Media & audio. These additions and their positions are saved with your clip.</p>
      <details data-live-crop-details><summary>Crop the original source manually</summary><label>Shot<select data-live-crop-shot><option value="0">Shot 1</option><option value="1">Shot 2 / facecam</option><option value="2">Shot 3</option></select></label><p>Drag a rectangle on the source picture. It becomes the crop for the selected shot.</p><canvas data-live-crop tabindex="0" aria-label="Draw a source crop"></canvas><button type="button" class="mc-btn" data-live-clear-crop>Reset source crops</button></details>
    </div>`;
  }
  function mount(el,api) {
    if(states.has(el))return;
    const aside=$('.mc-poster-sticky',el),canvas=$('[data-mc-live]',el);
    if(!aside||!canvas)return;
    const workspace=document.createElement('div');workspace.className='mc-live-workspace';
    const settings=document.createElement('div');settings.className='mc-live-settings';
    const tabs=$('.mc-tabs',el);el.insertBefore(workspace,tabs);workspace.append(aside,settings);
    settings.append(tabs,...$$(':scope > .mc-pane',el));
    const root=el.closest('#addform,#cform,#clipdlg');
    // Keep the preview beside the choices instead of below two screens of tiles.
    if(root?.id==='addform') {
      const captionPanel=$('#o_style',root)?.closest('.ob'),layoutPanel=$('#o_layout',root)?.closest('.ob');
      if(captionPanel){captionPanel.classList.add('mc-full');$('[data-mc-pane=captions]>.mc-grid',el).prepend(captionPanel);}
      if(layoutPanel){layoutPanel.classList.add('mc-full');$('[data-mc-pane=frame]>.mc-grid',el).prepend(layoutPanel);}
      el.parentElement.prepend(el);
    }
    const quick=document.createElement('div');quick.className='mc-live-quick';
    quick.innerHTML='<label>Caption style<select data-live-style></select></label><label>Layout<select data-live-layout></select></label><label class="mc-check"><input type="checkbox" data-live-captions>Generate captions</label>';
    const bridge=window.MihisBridge();
    $('[data-live-style]',quick).replaceChildren(...Object.entries(bridge.status.styles).map(([key,name])=>new Option(name,key)));
    $('[data-live-layout]',quick).replaceChildren(...Object.entries(bridge.status.layouts).map(([key,name])=>new Option(name,key)));
    settings.prepend(quick);
    aside.insertAdjacentHTML('beforeend',controlsHTML());
    const note=$('.mc-live-help',aside);note.dataset.liveNote='';note.setAttribute('role','status');
    const controls=$('.mc-direct-tools',aside);
    const nodes={video0:$('.mc-card-video',el),profile:$('.mc-card-profile',el),headline:$('.mc-card-headline',el),caption:$('.mc-card-caption',el),subline:$('.mc-card-subline',el),news:$('.mc-card-news',el),hook_label:$('.mc-card-kicker',el),news_strap:$('.mc-card-strap',el),ticker:$('.mc-card-ticker',el)};
    const video=$('video',nodes.video0);video.hidden=true;video.muted=true;
    $('.mc-card-video > img',el).hidden=true;$('.mc-card-video > span',el).hidden=true;
    for(let i=0;i<3;i++) {
      let node=nodes['video'+i];
      if(!node){node=document.createElement('div');node.className='mc-card-video mc-extra-shot';canvas.append(node);nodes['video'+i]=node;}
      node.append(document.createElement('canvas'));
    }
    nodes.watermark=document.createElement('div');nodes.watermark.className='mc-card-watermark';canvas.append(nodes.watermark);
    nodes.logo=document.createElement('img');nodes.logo.alt='Logo';nodes.logo.className='mc-card-logo';canvas.append(nodes.logo);
    Object.entries(nodes).forEach(([key,node])=>{node.dataset.mcElement=key;node.classList.add('mc-manipulable');});
    const background=document.createElement('canvas');background.className='mc-live-background';canvas.prepend(background);
    const selection=document.createElement('div');selection.className='mc-live-selection';selection.hidden=true;
    selection.innerHTML='<span class="mc-resize-handle" data-live-resize aria-label="Resize selected element"></span>';canvas.append(selection);
    canvas.tabIndex=0;canvas.setAttribute('aria-label','Editable video layout preview');
    const s={el,api,aside,controls,quick,canvas,background,selection,nodes,video,image:new Image(),media:new Map(),positions:{},selected:'video0',cropDetails:$('[data-live-crop-details]',controls),cropCanvas:$('[data-live-crop]',controls)};
    states.set(el,s);
    quick.addEventListener('input',e=>{
      if(e.target.matches('[data-live-style]'))api.setBasic('style',e.target.value);
      if(e.target.matches('[data-live-layout]'))api.setBasic('layout',e.target.value);
      if(e.target.matches('[data-live-captions]'))api.setBasic('captions',e.target.checked);
      refresh(el);api.commit();
    });
    let dragging=null;
    canvas.addEventListener('pointerdown',e=>{
      const node=e.target.closest('[data-mc-element]'),resize=e.target.closest('[data-live-resize]');
      if(!node&&!resize)return;
      e.preventDefault();e.stopPropagation();
      if(node)select(s,node.dataset.mcElement);
      const r=s.positions[s.selected];if(!r)return;
      dragging={key:s.selected,rect:{...r},x:e.clientX,y:e.clientY,resize:!!resize};
      canvas.setPointerCapture(e.pointerId);canvas.focus({preventScroll:true});
    });
    canvas.addEventListener('pointermove',e=>{
      if(!dragging)return;const bounds=canvas.getBoundingClientRect(),r={...dragging.rect},dx=(e.clientX-dragging.x)/bounds.width,dy=(e.clientY-dragging.y)/bounds.height;
      if(dragging.resize){const factor=Math.max(.1,1+Math.max(dx/r.w,dy/r.h));r.w=clamp(r.w*factor,.02,1-r.x);r.h=clamp(r.h*factor,.02,1-r.y);}
      else {r.x=clamp(r.x+dx,0,1-r.w);r.y=clamp(r.y+dy,0,1-r.h);}
      saveBox(s,dragging.key,r,false);
    });
    const finish=()=>{if(dragging){dragging=null;api.commit();}};
    canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);
    canvas.addEventListener('keydown',e=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)||!s.positions[s.selected])return;
      e.preventDefault();const r={...s.positions[s.selected]},step=e.shiftKey?.05:.005;
      if(e.key==='ArrowLeft')r.x-=step;if(e.key==='ArrowRight')r.x+=step;if(e.key==='ArrowUp')r.y-=step;if(e.key==='ArrowDown')r.y+=step;
      r.x=clamp(r.x,0,1-r.w);r.y=clamp(r.y,0,1-r.h);saveBox(s,s.selected,r);
    });
    controls.addEventListener('input',e=>{
      // Select/checkbox input fires before change; update state before the parent redraws.
      if(e.target.matches('[data-live-layer]'))select(s,e.target.value);
      if(e.target.matches('[data-live-visible]')&&s.positions[s.selected])saveBox(s,s.selected,{...s.positions[s.selected],enabled:e.target.checked});
      if(e.target.matches('[data-live-sample]'))refresh(el);
      if(e.target.matches('[data-live-selected-text]')) {
        const key={headline:'headline',subline:'subline',watermark:'watermark',hook_label:'hook_label',news:'news_label',news_strap:'news_strap',ticker:'ticker'}[s.selected];
        if(key)api.set(key,e.target.value);
        else if(s.selected.startsWith('sticker')){const row=$$('[data-mc-list=stickers] .mc-row',el)[Number(s.selected.slice(7))];if(row)$('[data-row=text]',row).value=e.target.value.slice(0,30);api.commit();}
      }
      if(e.target.matches('[data-live-number]')&&s.positions[s.selected]) {
        const r={...s.positions[s.selected]},key=e.target.dataset.liveNumber,value=Number(e.target.value)/100;
        if(!Number.isFinite(value))return;r[key]=value;saveBox(s,s.selected,r);
      }
    });
    controls.addEventListener('change',e=>{
      if(e.target.matches('[data-live-layer]'))select(s,e.target.value);
    });
    controls.addEventListener('click',async e=>{
      if(e.target.closest('[data-live-reset]')){const value=placements(el);delete value[s.selected];setPlacements(el,value);api.commit();refresh(el);}
      if(e.target.closest('[data-live-play]')){if(video.paused){await video.play().catch(()=>{});for(const media of s.media.values())if(media.tagName==='VIDEO')media.play().catch(()=>{});}else{video.pause();for(const media of s.media.values())if(media.tagName==='VIDEO')media.pause();}$('[data-live-play]',controls).textContent=video.paused?'Play source':'Pause source';}
      if(e.target.closest('[data-live-delete]')&&s.selected.startsWith('sticker')){const row=$$('[data-mc-list=stickers] .mc-row',el)[Number(s.selected.slice(7))];row?.remove();api.commit();refresh(el);}
      const text=e.target.closest('[data-live-add-text]'),image=e.target.closest('[data-live-add-image]');
      if(text||image) {
        const value=text?$('[data-live-text]',controls).value.trim():$('[data-live-media]',controls).value;
        if(!value)return;
        if((api.read().stickers||[]).length>=20)return;
        api.addRow('stickers',{text:text?value:'',asset:image?value:'',time:0,duration:180,x:.5,y:.7,size:text?.55:.3});
        refresh(el);select(s,'sticker'+(api.read().stickers.length-1));
      }
      if(e.target.closest('[data-live-clear-crop]')){api.setRows('regions',[]);refresh(el);}
    });
    s.cropDetails.addEventListener('toggle',()=>draw(s));
    let cropStart=null;
    const cropPoint=e=>{const r=s.cropCanvas.getBoundingClientRect();return {x:clamp((e.clientX-r.left)/r.width,0,1),y:clamp((e.clientY-r.top)/r.height,0,1)};};
    s.cropCanvas.addEventListener('pointerdown',e=>{e.preventDefault();cropStart=cropPoint(e);s.cropCanvas.setPointerCapture(e.pointerId);});
    s.cropCanvas.addEventListener('pointerup',e=>{
      if(!cropStart)return;const to=cropPoint(e),r=box(Math.min(cropStart.x,to.x),Math.min(cropStart.y,to.y),Math.abs(to.x-cropStart.x),Math.abs(to.y-cropStart.y));cropStart=null;
      if(r.w<.02||r.h<.02)return;
      const rows=[...(api.read().regions||[])],index=Number($('[data-live-crop-shot]',controls).value);
      while(rows.length<=index)rows.push(box(0,0,1,1));rows[index]=r;api.setRows('regions',rows);refresh(el);
    });
    video.addEventListener('play',()=>{const tick=()=>{if(!el.isConnected||video.paused)return;if(!canvas.getClientRects().length||document.hidden){video.pause();return;}if(s.lastVideoTime!==video.currentTime){s.lastVideoTime=video.currentTime;draw(s);}s.animation=requestAnimationFrame(tick);};tick();});
    video.addEventListener('pause',()=>cancelAnimationFrame(s.animation));
    const observer=new ResizeObserver(()=>refresh(el));observer.observe(canvas);
    refresh(el);
  }
  window.MihisLive={mount,refresh,loadSource};
})();
