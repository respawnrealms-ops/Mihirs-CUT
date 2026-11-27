"""Profile cards, news and hook frames, drawn at the export's actual size."""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import config, editor, editor_assets, canvas_layout

DESIGNS = ("x_light", "x_dark", "breaking_news", "tiktok_hook", "youtube_video")


def typeface(size, bold=False):
    # System Arial matches the compact card typography. Bundled fonts are the portable fallback.
    files = [Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
             config.ROOT / "studio/fonts/Poppins-ExtraBold.ttf"]
    for file in files:
        if file.is_file():
            return ImageFont.truetype(str(file), max(8, round(size)))
    return ImageFont.load_default(size=max(8, round(size)))


def text(draw, value, box, size, fill, bold=False, max_lines=3, spacing=1.18, align="left"):
    x, y, width, height = box
    value = editor.text(value, 500)
    # Fit all lines before drawing. A long headline must not run into the video.
    while size >= 8:
        f = typeface(size, bold)
        lines, line = [], ""
        for word in value.split():
            trial = (line + " " + word).strip()
            if line and draw.textlength(trial, font=f) > width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        if len(lines) <= max_lines and len(lines)*size*spacing <= height and all(draw.textlength(l,font=f)<=width for l in lines):
            break
        size *= .94
    for i, line in enumerate(lines[:max_lines]):
        xx = x + (width-draw.textlength(line,font=f))/2 if align=="center" else x
        draw.text((round(xx),round(y+i*size*spacing)),line,font=f,fill=fill,anchor="lt")
    return size


def gradient(o, w, h):
    nx, ny = min(w,256), min(h,256)
    angle = math.radians(o["gradient_angle"])
    vx,vy=math.cos(angle),math.sin(angle)
    xx,yy=np.meshgrid(np.linspace(0,1,nx),np.linspace(0,1,ny))
    t=(xx*vx+yy*vy-min(0,vx)-min(0,vy))/max(.0001,abs(vx)+abs(vy))
    a=np.array(tuple(bytes.fromhex(o["color"][1:])))
    b=np.array(tuple(bytes.fromhex(o["color2"][1:])))
    pixels=np.rint(a+(b-a)*t[:,:,None]).astype(np.uint8)
    return Image.fromarray(pixels).resize((w,h),Image.Resampling.BILINEAR).convert("RGBA")


def video_box(o, w, h):
    padding=round(o["padding"]*w/1080)
    if o["template"]=="youtube_video":
        return padding,padding,w-2*padding,h-2*padding
    if w>h:
        return round(w*.36),round(h*.12),round(w*.60)-padding,round(h*.70)
    x=max(round(w*.025),padding)
    width=w-2*x
    return x,round(h*.36),width,min(round(width*9/16),round(h*.34))


def draw_avatar(im, o, x, y, diameter):
    d=ImageDraw.Draw(im)
    d.ellipse((x,y,x+diameter-1,y+diameter-1),fill="#d0dce1")
    if o["avatar"]:
        with Image.open(editor_assets.path(o["avatar"],("image",))) as photo:
            pic=ImageOps.fit(photo.convert("RGBA"),(diameter,diameter))
        mask=Image.new("L",pic.size)
        ImageDraw.Draw(mask).ellipse((0,0,diameter-1,diameter-1),fill=255)
        im.paste(pic,(x,y),mask)


def overlay(o, clip, boxes, w, h, light):
    layers=canvas_layout.Layers(o,w,h)
    im,d=layers.start("border")
    template=o["template"]
    ink="#14171a" if light else "#ffffff"
    title=o["headline"] or clip.get("title") or clip.get("hook") or "Your headline above the video"
    left=round(w*.05)
    right=w-left
    scale=w/1080
    landscape=w>h
    text_width=round(w*.28) if landscape else w-2*left
    vx,vy,vw,vh=boxes[0]
    # A fine border makes the source shot read as part of the card.
    if template in ("breaking_news","tiktok_hook"):
        for x,y,bw,bh in boxes:
            d.rounded_rectangle((x-1,y-1,x+bw,y+bh),radius=max(2,round(o["radius"]*scale)),outline="#35404a",width=max(1,round(scale)))
    if template in ("x_light","x_dark"):
        im,d=layers.start("profile", (left,h*(.09 if landscape else .16),text_width,h*.1))
        top=round(h*(.09 if landscape else .16))
        diameter=round(w*(.035 if landscape else .13))
        draw_avatar(im,o,left,top,diameter)
        name=o["name"] or "Source channel"
        fs=w*(.022 if landscape else .046)
        tx=left+diameter+round(w*.035)
        available=max(30,text_width-diameter-round(w*.035))
        text(d,name,(tx,top+diameter*.08,available,diameter*.40),fs,ink,True,1)
        text(d,o["handle"],(tx,top+diameter*.52,available,diameter*.35),fs*.70,"#7b8791",False,1)
        if o["badge"]:
            name_width=min(available,d.textlength(name,font=typeface(fs,True)))
            r=max(4,round(fs*.30))
            bx=min(left+text_width-r*2,round(tx+name_width+fs*.25));by=round(top+diameter*.12)
            d.ellipse((bx,by,bx+r*2,by+r*2),fill="#1d9bf0")
            d.line([(bx+r*.48,by+r),(bx+r*.88,by+r*1.4),(bx+r*1.58,by+r*.62)],fill="white",width=max(1,round(r*.25)))
        headline_y=round(h*(.29 if landscape else .262))
        headline_h=round(h*(.35 if landscape else .085))
        im,d=layers.start("headline", (left,headline_y,text_width,headline_h))
        text(d,title,(left,headline_y,text_width,headline_h),w*(.027 if landscape else .050),ink,False,4 if landscape else 3)
    elif template=="breaking_news":
        by=round(h*(.07 if not landscape else .08));bh=round(h*.065)
        bar_width=text_width if landscape else w-2*left
        im,d=layers.start("news", (left,by,bar_width,bh))
        d.rounded_rectangle((left,by,left+bar_width,by+bh),radius=max(3,round(w*.014)),fill="#e5232d")
        dot=max(3,round(bh*.14));cx=left+round(bh*.32);cy=by+bh//2
        d.ellipse((cx-dot,cy-dot,cx+dot,cy+dot),fill="white")
        text(d,o["news_label"],(cx+dot*2,by+bh*.28,bar_width-bh*.65,bh*.60),bh*.37,"white",True,1)
        if o["news_live"]:
            lw=bh*.95;lx=left+bar_width-lw-bh*.15
            d.rounded_rectangle((lx,by+bh*.22,lx+lw,by+bh*.78),radius=2,fill="white")
            text(d,"LIVE",(lx+lw*.08,by+bh*.31,lw*.84,bh*.4),bh*.24,"#e5232d",True,1)
        hy=by+bh+round(h*.018)
        hh=round(h*(.33 if landscape else .15))
        im,d=layers.start("headline", (left,hy,text_width,hh))
        d.rectangle((left,hy,left+text_width,hy+hh),fill="#101b30")
        d.rectangle((left,hy,left+max(3,round(w*.014)),hy+hh),fill="#e5232d")
        text(d,title.upper(),(left+w*.045,hy+h*.013,text_width-w*.075,hh-h*.026),w*(.025 if landscape else .053),"white",True,5)
        im,d=layers.start("news_strap", (left,hy+hh+h*.015,text_width,h*.032))
        text(d,o["news_strap"],(left,hy+hh+h*.015,text_width,h*.032),w*(.012 if landscape else .030),"#ffe600",True,1)
    elif template=="tiktok_hook":
        by=round(h*.065);fs=w*(.016 if landscape else .035)
        label=o["hook_label"]
        lw=min(text_width,d.textlength(label,font=typeface(fs,True))+fs*.9)
        bh=fs*1.8
        im,d=layers.start("hook_label", (left,by,w*.36,h*.04))
        d.rounded_rectangle((left,by,left+lw,by+bh),radius=max(3,round(fs*.2)),fill="#e91c29")
        text(d,label,(left+fs*.4,by+fs*.42,lw-fs*.8,bh-fs*.5),fs,"white",True,1)
        hy=by+bh+round(h*.024)
        hh=round(h*(.35 if landscape else .16))
        im,d=layers.start("headline", (left,hy,text_width,hh))
        text(d,title,(left,hy,text_width,hh),w*(.029 if landscape else .067),ink,True,5)
        im,d=layers.start("profile", (left,h*.305,text_width,h*.032))
        text(d,o["handle"],(left,round(h*.305),text_width,h*.032),w*(.014 if landscape else .035),"#8b98a8",False,1)
    else:  # A regular YouTube video keeps the widescreen picture.
        im,d=layers.start("profile", (left,h*.045,w*.31,h*.09))
        diameter=round(min(w,h)*.065)
        top=round(h*.045)
        draw_avatar(im,o,left,top,diameter)
        name=o["name"] or "Your channel"
        d.rounded_rectangle((left+diameter*.7,top,left+diameter+w*.24,top+diameter),radius=diameter*.15,fill=(10,15,23,190))
        text(d,name,(left+diameter*1.2,top+diameter*.22,w*.22,diameter*.6),h*.028,"white",True,1)
        if o["headline"]:
            im,d=layers.start("headline", (left,h*.68,w*.70,h*.13))
            text(d,title,(left,h*.68,w*.70,h*.13),h*.05,"white",True,2)
    if o["subline"]:
        im,d=layers.start("subline", (left,h*(.68 if landscape else .72),w-2*left,h*.07))
        sy=h*(.68 if landscape else .72)
        text(d,o["subline"],(left,sy,w-2*left,h*.07),min(w*.045,h*.035),ink,False,3,align="center")
    if o["ticker"] and template=="breaking_news":
        im,d=layers.start("ticker", (left,h*.945,w-2*left,h*.035))
        d.rectangle((left,h*.945,right,h*.98),fill="#e5232d")
        text(d,o["ticker"],(left+w*.015,h*.952,right-left-w*.03,h*.025),h*.016,"white",True,1)
    if o["watermark"]:
        im,d=layers.start("watermark", (left,h*.965,w-2*left,h*.025))
        text(d,o["watermark"],(left,h*.965,w-2*left,h*.025),h*.014,ink,False,1)
    if o["logo"]:
        im,d=layers.start("logo")
        with Image.open(editor_assets.path(o["logo"],("image",))) as logo:
            pic=logo.convert("RGBA")
        side=round(w*o["logo_size"]);pic.thumbnail((side,side))
        pic.putalpha(pic.getchannel("A").point(lambda a:round(a*o["logo_opacity"])))
        x=left if o["logo_corner"].endswith("left") else right-pic.width
        y=round(h*.04) if o["logo_corner"].startswith("top") else round(h*.94)-pic.height
        layers.bounds("logo", (x,y,pic.width,pic.height))
        im.alpha_composite(pic,(x,y))
    return layers.finish()
