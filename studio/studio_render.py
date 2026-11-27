"""The optional Mihis Cut compositor. Legacy clips keep their original renderer."""
import json
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config, editor, editor_assets, render, frame_designs, panel_depth, canvas_layout
from .media import NO_WINDOW, run


def font(size, bold=True):
    paths = [config.FONTS_DIR / "Poppins-ExtraBold.ttf", config.ROOT / "studio/fonts/Poppins-ExtraBold.ttf"]
    paths += list((config.ROOT / "studio/fonts").glob("*Poppins*.ttf"))
    for p in paths:
        if p.is_file():
            return ImageFont.truetype(str(p), max(10, int(size)))
    return ImageFont.load_default(size=max(10, int(size)))


def draw_text(draw, text, box, size, fill, align="left", max_lines=4):
    x, y, w, h = box
    words, lines, line = editor.text(text, 600).split(), [], ""
    f = font(size)
    longest = max((draw.textlength(word, font=f) for word in words), default=0)
    if longest > w:
        size = max(10, size * w / longest)
        f = font(size)
    for word in words:
        trial = (line + " " + word).strip()
        if line and draw.textlength(trial, font=f) > w:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "…"
    lh = int(size * 1.35)
    for i, line in enumerate(lines):
        if y+i*lh+lh > y+h:
            break
        px = x + (w-draw.textlength(line, font=f))/2 if align == "center" else x
        draw.text((px, y+i*lh), line, font=f, fill=fill)


def panel_boxes(o, layout, w, h):
    return canvas_layout.panels(_panel_boxes(o, layout, w, h), o, w, h)


def _panel_boxes(o, layout, w, h):
    p = round(o["padding"] * w / 1080)
    if o["template"] != "none":
        if o["template"] in frame_designs.DESIGNS:
            x,y,iw,ih = frame_designs.video_box(o,w,h)
        else:
            x,y,iw,ih = p+int(w*.04), int(h*.34), w-2*p-int(w*.08), int(h*.31)
        if layout in ("duo", "split", "trio", "pip", "gameplay", "facecam_top", "split_top", "split_bottom"):
            return [(x+bx,y+by,bw,bh) for bx,by,bw,bh in _panel_boxes(dict(o,template="none",padding=0),layout,iw,ih)]
        return [(x,y,iw,ih)]
    if layout in ("duo", "split", "facecam_top", "split_top", "split_bottom"):
        half = (h-3*p)//2
        boxes = [(p, p, w-2*p, half), (p, 2*p+half, w-2*p, h-3*p-half)]
        if layout in ("split_top", "split_bottom"):
            wide_h = min(half, int((w-2*p)*9/16))
            index = 0 if layout == "split_top" else 1
            boxes[index] = (p, p if index == 0 else h-p-wide_h, w-2*p, wide_h)
            boxes[1-index] = (p, wide_h+2*p if index == 0 else p, w-2*p, h-wide_h-3*p)
        return boxes
    if layout == "trio":
        sh = (h-4*p)//3
        return [(p, p+i*(sh+p), w-2*p, sh) for i in range(3)]
    if layout in ("pip", "gameplay"):
        size = int(w*o["pip_size"])
        ph = size if o["pip_shape"] == "circle" else int(size*.75)
        x = p if o["pip_corner"].endswith("left") else w-p-size
        y = p if o["pip_corner"].startswith("top") else h-p-ph
        return [(p, p, w-2*p, h-2*p), (x, y, size, ph)]
    if layout in ("fit", "blur", "zoom", *render.CANVASES):
        return [(p, int(h*.28), w-2*p, int(h*.44))]
    return [(p, p, w-2*p, h-2*p)]


def backdrop(o, w, h):
    light = o["template"] in ("x_light", "poll", "comment", "quote", "review", "announcement", "headline")
    dark = o["template"] != "none" and not light
    bg = "#ffffff" if light else "#0e1320" if o["template"] == "breaking_news" else "#111111" if dark else o["color"]
    if o["background"] == "solid":
        bg = o["color"]
        light = sum(bytes.fromhex(bg[1:])) > 570
    im = Image.new("RGBA", (w, h), bg)
    if o["background"] == "gradient":
        im = frame_designs.gradient(o,w,h)
    if o["background"] == "image" and o["background_asset"]:
        from PIL import ImageOps
        with Image.open(editor_assets.path(o["background_asset"], ("image",))) as pic:
            im = ImageOps.fit(pic.convert("RGBA"), (w,h)).filter(ImageFilter.GaussianBlur(o["blur"]*w/1080))
        if o["dim"]:
            im = Image.alpha_composite(im, Image.new("RGBA", (w,h), (0,0,0,round(o["dim"]*255))))
    if o["background"] in ("gradient", "image"):
        light = sum(im.getpixel((w//2,int(h*.81)))[:3]) > 570
    if o["background"] == "blur":
        light = False
    return im, light


def frame(o, clip, boxes, w, h, light):
    if o["template"] in frame_designs.DESIGNS:
        return frame_designs.overlay(o,clip,boxes,w,h,light)
    layers = canvas_layout.Layers(o,w,h)
    im,d = layers.start("decoration")
    ink = "#151515" if light else "#ffffff"
    accent = o["color2"]
    p, size = int(w*.07), w*.049
    tpl = o["template"]
    title = o["headline"] or clip.get("hook") or clip.get("title") or ""
    if tpl in ("headline", "gaming", "announcement"):
        d.rectangle((p,int(h*.045),w-p,int(h*.053)),fill=accent)
    if tpl == "quote":
        d.rectangle((p,int(h*.11),p+8,int(h*.29)),fill=accent)
        draw_text(d,'“',(p+18,int(h*.09),w-2*p,int(h*.1)),size*2,accent,max_lines=1)
    if tpl == "podcast":
        for i in range(25):
            x=int(p+i*(w-2*p)/25)
            ah=int((.5+.5*math.sin(i*1.7))*h*.035)
            d.rounded_rectangle((x,int(h*.9)-ah,x+max(2,int(w*.01)),int(h*.9)+ah),radius=3,fill=accent)
    if tpl == "spotlight":
        d.ellipse((int(w*.2),int(h*.04),int(w*.8),int(h*.32)),outline=accent,width=max(2,int(w*.003)))
    if tpl in ("x_light", "x_dark", "comment", "poll", "review"):
        im,d = layers.start("profile", (p,h*.1,w-2*p,h*.1))
        r = int(w*.045)
        d.ellipse((p, int(h*.1), p+2*r, int(h*.1)+2*r), fill=accent)
        if o["avatar"]:
            from PIL import ImageOps
            with Image.open(editor_assets.path(o["avatar"], ("image",))) as photo:
                pic = ImageOps.fit(photo.convert("RGBA"), (2*r,2*r))
            mask = Image.new("L", pic.size)
            ImageDraw.Draw(mask).ellipse((0,0,2*r,2*r), fill=255)
            im.paste(pic, (p,int(h*.1)), mask)
        draw_text(d, o["name"] or "Your name", (p+2*r+20, int(h*.1), w-p*2-2*r-20, h*.06), size*.8, ink, max_lines=1)
        draw_text(d, o["handle"], (p+2*r+20, int(h*.14), w-p*2-2*r-20, h*.05), size*.6, "#808080", max_lines=1)
        if o["badge"]:
            d.ellipse((w-p-24,int(h*.1),w-p,int(h*.1)+24), fill="#2288ee")
        im,d = layers.start("headline", (p,int(h*.22),w-2*p,int(h*.105)))
        draw_text(d, title, (p,int(h*.22),w-2*p,int(h*.105)),size,ink,max_lines=3)
    elif tpl == "breaking_news":
        im,d = layers.start("news", (p,h*.07,w-2*p,h*.05))
        d.rounded_rectangle((p,int(h*.07),w-p,int(h*.12)),radius=8,fill="#d9232e")
        draw_text(d, "NEWS", (p+16,int(h*.075),w-2*p-32,int(h*.06)), size*.7,"white",max_lines=1)
        im,d = layers.start("headline", (p,int(h*.15),w-2*p,int(h*.15)))
        draw_text(d, title,(p,int(h*.15),w-2*p,int(h*.15)),size,ink,max_lines=4)
        if o["ticker"]:
            im,d = layers.start("ticker", (p,h*.94,w-2*p,h*.04))
            d.rectangle((p,int(h*.94),w-p,int(h*.98)),fill="#d9232e")
            draw_text(d,o["ticker"],(p+12,int(h*.945),w-2*p-24,h*.04),size*.55,"white",max_lines=1)
    elif tpl != "none":
        im,d = layers.start("hook_label", (p,h*.075,w-2*p,h*.045))
        tag = {"tiktok_hook":"WATCH THIS", "podcast":"ON THE MIC", "gaming":"GAMEPLAY", "code":"NOTES", "announcement":"ANNOUNCEMENT"}.get(tpl,"")
        if tag:
            d.rounded_rectangle((p,int(h*.075),w-p,int(h*.12)),radius=8,fill=accent)
            draw_text(d,tag,(p+14,int(h*.079),w-p*2-28,int(h*.05)),size*.65,"#111111",max_lines=1)
        im,d = layers.start("headline", (p,int(h*.16),w-2*p,int(h*.16)))
        draw_text(d,title,(p,int(h*.16),w-2*p,int(h*.16)),size*1.12,ink,max_lines=4)
        im,d = layers.start("profile", (p,h*.3,w-2*p,h*.035))
        draw_text(d,o["handle"],(p,int(h*.3),w-2*p,h*.035),size*.55,"#888888",max_lines=1)
    else:
        ypos = int((o["headline_y"] or (.12 if boxes[0][1] else .14))*h)
        im,d = layers.start("headline", (p,ypos,w-2*p,h*.15))
        draw_text(d,title,(p,ypos,w-2*p,h*.15),size*1.1,ink,"center",3)
    if o["subline"]:
        im,d = layers.start("subline", (p,h*.68,w-2*p,h*.12))
        draw_text(d,o["subline"],(p,int(h*.68),w-2*p,h*.12),size*.85,ink,"center",3)
    if tpl == "poll":
        im,d = layers.start("decoration")
        for i, label in enumerate([o["poll_a"], o["poll_b"]]):
            yy = int(h*(.85+i*.045))
            d.rounded_rectangle((p,yy,w-p,yy+int(h*.035)),radius=12,outline=accent,width=3)
            draw_text(d,label,(p+12,yy,w-2*p-24,h*.04),size*.55,ink,max_lines=1)
    if tpl == "review":
        im,d = layers.start("decoration")
        draw_text(d,"★ ★ ★ ★ ★",(p,h*.89,w-2*p,h*.06),size*.8,accent,"center",1)
    if tpl == "code" and o["code_text"]:
        im,d = layers.start("decoration")
        d.rounded_rectangle((p,int(h*.84),w-p,int(h*.94)),radius=10,fill="#202b37")
        draw_text(d,o["code_text"],(p+12,h*.85,w-2*p-24,h*.08),size*.55,"#9aefc0",max_lines=3)
    if o["watermark"]:
        im,d = layers.start("watermark", (p,h*.955,w-2*p,h*.04))
        draw_text(d,o["watermark"],(p,h*.955,w-2*p,h*.04),size*.45,ink,max_lines=1)
    if o["logo"]:
        im,d = layers.start("logo")
        with Image.open(editor_assets.path(o["logo"], ("image",))) as logo:
            pic=logo.convert("RGBA")
        side=int(w*o["logo_size"])
        pic.thumbnail((side,side))
        pic.putalpha(pic.getchannel("A").point(lambda a: round(a*o["logo_opacity"])))
        x = p if o["logo_corner"].endswith("left") else w-p-pic.width
        y = p if o["logo_corner"].startswith("top") else h-p-pic.height
        layers.bounds("logo", (x,y,pic.width,pic.height))
        im.alpha_composite(pic,(x,y))
    return layers.finish()


def ass_words(words, clip, o, w, h, light):
    return canvas_layout.captions(_ass_words, words, clip, o, w, h, light)


def _ass_words(words, clip, o, w, h, light):
    st = dict(render.STYLES.get(clip.get("style"), render.STYLES["bounce"]))
    if o["template"] in frame_designs.DESIGNS and clip.get("style", "clean") == "clean":
        st.update(size=100, outline=0, pop=100, per=5)
        if o["template"] in ("breaking_news", "tiktok_hook"):
            st.update(base="00E6FF",active="00E6FF",strong="00E6FF",upper=o["template"]=="breaking_news")
            if light:
                st["outline"]=2
            if o["template"]=="breaking_news":
                st["plate"]="301B10"
    # Keep every existing caption effect when no separate motion or word styling was selected.
    if o["motion"] == "auto" and not any(row.get(k) for row in words for k in ("bold", "italic", "color", "box")):
        ref_h = round(h * 1080 / w)
        st["size"] = round(st["size"] * .66 * o["caption_size"])
        cap_y = (o["caption_y"] or (.84 if o["template"] in frame_designs.DESIGNS else .81 if o["template"] != "none" or clip.get("layout") in render.CANVASES else .78)) * ref_h
        return render.build_ass(words, 0, max([x["e"] for x in words] or [1])+.3, "", clip.get("style", "bounce"),
                                clip.get("highlight_words", []), 0, cap_y,
                                canvas={"light":light,"ink":"161616" if light else "FFFFFF"},
                                frame=(1080, ref_h), style_override=st)
    fs = round(st["size"]*.66*w/1080*o["caption_size"])
    cy = int((o["caption_y"] or (.84 if o["template"] in frame_designs.DESIGNS else .81 if o["template"] != "none" or clip.get("layout") in render.CANVASES else .78))*h)
    motion=o["motion"]
    if motion == "auto":
        motion = {"typewriter":"build_up", "static":"full_line", "karaoke":"highlight"}.get(st.get("effect"),"pop_in")
    ink = "161616" if light and st["base"] == "FFFFFF" else st["base"]
    edge = "FFFFFF" if light else st.get("edge","000000")
    head = f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Cap,{st['font']},{fs},&H00{ink},&H00{ink},&H00{edge},&H80000000,0,0,0,0,100,100,0,0,1,{max(1,round(st['outline']*w/1080))},0,5,0,0,0,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    ev=[]
    def add(a,b,line,tags=""):
        if b>a:
            ev.append(f"Dialogue: 1,{render._ts(a)},{render._ts(b)},Cap,,0,0,0,,{{\\an5\\pos({w//2},{cy}){tags}}}{line}")
    def token(row, active=False):
        t=render._clean(row["w"])
        if st["upper"]: t=t.upper()
        color = row.get("color")
        col = color[5:7]+color[3:5]+color[1:3] if color else st["active"] if active else ink
        tags=f"\\c&H{col}&\\b{1 if row.get('bold') else 0}\\i{1 if row.get('italic') else 0}"
        if row.get("box"):
            tags += "\\bord10\\3c&H202020&"
        if st.get("effect")=="glow": tags+="\\blur3\\shad2"
        if st.get("effect")=="underline" and active: tags+="\\u1"
        return "{"+tags+"}"+t+"{\\rCap\\fs"+str(size)+"}"
    for group in render._groups(words, 1 if motion=="one_by_one" else st["per"]):
        a,b=max(0,group[0]["s"]),group[-1]["e"]+.12
        size=fs
        f=font(size)
        measure=" ".join(x["w"] for x in group)
        width=f.getlength(measure)
        if width>w*.87: size=max(15,int(size*w*.87/width))
        tags=f"\\fs{size}"
        if st.get("plate"):
            plate_w=min(w*.90,font(size).getlength(measure)+size*.45)
            ev.append(render._caption_box(a,b,(w-plate_w)/2,cy-size*.6,(w+plate_w)/2,cy+size*.6,st["plate"]))
        if motion in ("pop_line","full_line"):
            add(a,b," ".join(token(x) for x in group),tags+("\\fscx85\\fscy85\\t(0,100,\\fscx100\\fscy100)" if motion=="pop_line" else ""))
        elif motion=="build_up":
            for i,x in enumerate(group):
                add(max(a,x["s"]),group[i+1]["s"] if i+1<len(group) else b," ".join(token(z) for z in group[:i+1]),tags)
        else:
            for i,x in enumerate(group):
                add(max(a,x["s"]),group[i+1]["s"] if i+1<len(group) else b," ".join(token(z,k==i) for k,z in enumerate(group)),tags+("\\fscx93\\fscy93\\t(0,80,\\fscx100\\fscy100)" if motion=="pop_in" else ""))
    return head+"\n".join(ev)+"\n"


def sound(path, kind):
    rate=48000
    samples=[]
    for i in range(int(rate*.45)):
        t=i/rate
        env=math.exp(-t*(15 if kind != "whoosh" else 7))
        hz={"ping":950,"click":1800,"pop":180,"whoosh":600}[kind]
        v=math.sin(2*math.pi*(hz*t+(-450*t*t if kind=="whoosh" else 0)))
        samples.append(struct.pack("<h",int(9000*env*v)))
    with wave.open(str(path),"wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate); f.writeframes(b"".join(samples))


def render_clip(src, out_dir, name, clip, words, src_w, src_h, cancel=None):
    o=editor.settings(clip)
    editor_assets.validate_profile(o)
    work_root = None
    if clip.get("long_video"):
        work_root = config.ROOT / ".render-work"
        work_root.mkdir(exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix="mc", dir=work_root))
    try:
        return _render(work,Path(src).resolve(),out_dir,name,clip,words,src_w,src_h,o,cancel)
    finally:
        shutil.rmtree(work,ignore_errors=True)


def _render(work, src, out_dir, name, clip, words, sw, sh, o, cancel=None):
    probe=json.loads(run(["ffprobe","-v","error","-show_streams","-of","json",str(src)]))
    vs=next(s for s in probe["streams"] if s["codec_type"]=="video")
    sw,sh=vs["width"],vs["height"]
    n,d=vs.get("avg_frame_rate","30/1").split("/")
    fps=min(60,max(1,float(n)/max(1,float(d)))) if o["fps"]=="source" else int(o["fps"])
    rw,rh=editor.RATIOS[o["ratio"]]
    short=int(o["resolution"])
    w,h=(round(rw*short/min(rw,rh)/2)*2,round(rh*short/min(rw,rh)/2)*2)
    start,end=clip["start"],clip["end"]
    ranges=editor.keep_ranges(o,end-start)
    duration=sum(b-a for a,b in ranges)
    total=duration+o["outro"]
    layout=clip.get("layout","blur")
    if layout in ("pip", "gameplay", "facecam_top") and not clip.get("facecam") and len(o["regions"]) < 2 and not any(r["slot"] == (0 if layout == "facecam_top" else 1) and r.get("asset") for r in o["slots"]):
        raise ValueError("No facecam was found. Load the original in Mihis Studio and draw both framing boxes, or replace the facecam panel with media.")
    # Canvas layouts are useful without any other custom controls.
    if layout in render.CANVASES and o["background"]=="layout":
        o=dict(o,color="#"+render.CANVASES[layout]["color"])
    boxes=panel_boxes(o,layout,w,h)
    bg,light=backdrop(o,w,h)
    if o["template"]=="none":
        text_on_background = layout in ("fit", "blur", "zoom", *render.CANVASES)
        video_background = o["background"] == "blur" or (o["background"] == "layout" and layout in ("blur", "zoom"))
        light = text_on_background and not video_background and sum(bg.getpixel((w//2,int(h*.81)))[:3]) > 570
    shadow=Image.new("RGBA",(w,h))
    if o["shadow"] and not o["panel_light"]:
        sd=ImageDraw.Draw(shadow)
        for x,y,bw,bh in boxes:
            sd.rounded_rectangle((x+8,y+12,x+bw+8,y+bh+12),radius=o["radius"]*w/1080,fill=(0,0,0,140))
        bg=Image.alpha_composite(bg,shadow.filter(ImageFilter.GaussianBlur(18*w/1080)))
    bg.save(work/"bg.png")
    illumination, bevel = panel_depth.layers(o,boxes,w,h,layout)
    Image.alpha_composite(bevel,frame(o,clip,boxes,w,h,light)).save(work/"frame.png")
    if o["panel_light"]:
        illumination.save(work/"panel-light.png")
    caption_words=editor.remap_words(words,start,ranges) if clip.get("captions",True) else []
    (work/"cap.ass").write_text(ass_words(caption_words,clip,o,w,h,light),encoding="utf-8")
    (work/"fonts").mkdir()
    for f in config.FONTS_DIR.glob("*.ttf"): shutil.copyfile(f,work/"fonts"/f.name)
    inputs=["-ss",str(start),"-t",str(end-start),"-i",str(src)]
    count=1
    def inp(path, kind="image", offset=0):
        nonlocal count
        i=count; count+=1
        if kind=="image": inputs.extend(["-loop","1","-framerate",str(fps),"-i",str(path)])
        else: inputs.extend(["-stream_loop","-1","-ss",str(offset),"-i",str(path)])
        return i
    def asset(aid,offset=0):
        row,p=editor_assets.get(aid)
        return inp(p,row["kind"],offset)
    bgid,frameid=inp(work/"bg.png"),inp(work/"frame.png")
    fc=[]
    if len(ranges)==1 and ranges[0]==(0,end-start):
        fc.append("[0:v]setpts=PTS-STARTPTS[srcv]")
        if any(s["codec_type"]=="audio" for s in probe["streams"]): fc.append("[0:a]asetpts=PTS-STARTPTS[srca]")
        else: fc.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={duration}[srca]")
    else:
        has_audio=any(s["codec_type"]=="audio" for s in probe["streams"])
        fc.append(f"[0:v]split={len(ranges)}"+"".join(f"[cv{i}]" for i in range(len(ranges))))
        if has_audio: fc.append(f"[0:a]asplit={len(ranges)}"+"".join(f"[ca{i}]" for i in range(len(ranges))))
        for i,(a,b) in enumerate(ranges):
            fc.append(f"[cv{i}]trim=start={a}:end={b},setpts=PTS-STARTPTS[vk{i}]")
            fc.append(f"[ca{i}]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[ak{i}]" if has_audio else f"anullsrc=r=48000:cl=stereo,atrim=duration={b-a}[ak{i}]")
        fc.append("".join(f"[vk{i}][ak{i}]" for i in range(len(ranges)))+f"concat=n={len(ranges)}:v=1:a=1[srcv][srca]")
    blurred=o["background"]=="blur" or (o["background"]=="layout" and layout in ("blur","zoom"))
    slots={r["slot"]:r for r in o["slots"] if r.get("asset")}
    source_slots=[i for i in range(len(boxes)) if i not in slots]
    copies=len(source_slots)+int(blurred)
    if copies:
        fc.append(f"[srcv]split={copies}"+"".join(f"[sv{i}]" for i in range(copies)))
    else: fc.append("[srcv]nullsink")
    if blurred:
        fc.append(f"[sv{copies-1}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur={max(1,int(o['blur']*w/1080))}:1,eq=brightness={-o['dim']},setsar=1[base]")
    else:
        fc.append(f"[{bgid}:v]trim=duration={total},setpts=PTS-STARTPTS[base]")
    if o["panel_light"]:
        lightid=inp(work/"panel-light.png")
        fc.append(f"[base][{lightid}:v]overlay=0:0:format=auto[litbase]")
    regions=o["regions"]
    if not regions and layout in ("split","duo","trio","split_top","split_bottom"):
        regions=[{"x":(i%2)*.5,"y":0,"w":.5,"h":1} for i in range(len(boxes))]
    if o["swap"] and regions: regions=list(reversed(regions))
    previous="litbase" if o["panel_light"] else "base"
    for i,(x,y,bw,bh) in enumerate(boxes):
        from_asset=i in slots
        if from_asset:
            index=asset(slots[i]["asset"],slots[i]["offset"])
            source=f"{index}:v"
            crop=""
        else:
            source=f"sv{source_slots.index(i)}"
            r=regions[i] if i<len(regions) else None
            if r is None and layout in ("pip","gameplay","facecam_top") and clip.get("facecam") and i==(0 if layout=="facecam_top" else 1):
                fx,fy,fw,fh=clip["facecam"]
                r={"x":fx/sw,"y":fy/sh,"w":fw/sw,"h":fh/sh}
            if r is None and layout in ("split","duo","trio","split_top","split_bottom"):
                r={"x":(i%2)*.5,"y":0,"w":.5,"h":1}
            crop=f"crop={max(2,int(r['w']*sw)//2*2)}:{max(2,int(r['h']*sh)//2*2)}:{int(r['x']*sw)}:{int(r['y']*sh)}," if r else ""
        fit=layout in ("fit","blur","zoom",*render.CANVASES) or (o["template"]!="none" and len(boxes)==1)
        scale=(f"scale={bw}:{bh}:force_original_aspect_ratio=decrease,pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2:color=black" if fit else f"scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh}")
        fc.append(f"[{source}]{crop}{scale},setsar=1,fps={fps},format=rgba[panel{i}]")
        radius=panel_depth.radius(o,w,bw,i,layout)
        circle=i==1 and layout in ("pip","gameplay") and o["pip_shape"]=="circle"
        if i==1 and layout in ("pip","gameplay") and o["pip_shape"]=="rounded": radius=max(radius,int(bw*.08))
        if radius or circle:
            mask=Image.new("L",(bw,bh))
            md=ImageDraw.Draw(mask)
            if circle: md.ellipse((0,0,bw-1,bh-1),fill=255)
            else: md.rounded_rectangle((0,0,bw-1,bh-1),radius=radius,fill=255)
            mask.save(work/f"mask{i}.png")
            mi=inp(work/f"mask{i}.png")
            fc.append(f"[{mi}:v]format=gray[mask{i}]")
            fc.append(f"[panel{i}][mask{i}]alphamerge[rounded{i}]")
            pic=f"rounded{i}"
        else: pic=f"panel{i}"
        fc.append(f"[{previous}][{pic}]overlay={x}:{y}:shortest=1:format=auto[p{i}]")
        previous=f"p{i}"
    if o["divider"] and len(boxes)>1:
        fc.append(f"[{previous}]drawbox=x=0:y={boxes[0][1]+boxes[0][3]}:w=iw:h={o['divider']*w/1080}:color={o['divider_color']}:t=fill[div]")
        previous="div"
    for i,r in enumerate(o["broll"]+o["stickers"]):
        if r.get("asset"):
            idx=asset(r["asset"])
        elif r.get("text"):
            sticker=Image.new("RGBA",(600,180))
            sd=ImageDraw.Draw(sticker)
            emoji=Path("C:/Windows/Fonts/seguiemj.ttf")
            sf=ImageFont.truetype(str(emoji),90) if emoji.is_file() else font(90)
            sd.text((10,10),r["text"],font=sf,fill="white",stroke_width=3,stroke_fill="black")
            sticker.save(work/f"sticker{i}.png")
            idx=inp(work/f"sticker{i}.png")
        else: continue
        size=max(2,int(w*r["size"])//2*2)
        fc.append(f"[{idx}:v]scale={size}:-2,setpts=PTS-STARTPTS+{r['time']}/TB[roll{i}]")
        fc.append(f"[{previous}][roll{i}]overlay=x=W*{r['x']}-w/2:y=H*{r['y']}-h/2:enable='between(t,{r['time']},{r['time']+r['duration']})':eof_action=pass[r{i}]")
        previous=f"r{i}"
    fc.append(f"[{previous}][{frameid}:v]overlay=0:0:format=auto,ass=cap.ass:fontsdir=fonts,tpad=stop_mode=clone:stop_duration={o['outro']}[captioned]")
    previous="captioned"
    if o["follow"]:
        ribbon=Image.new("RGBA",(w,int(h*.085)),(255,139,43,245))
        draw_text(ImageDraw.Draw(ribbon),o["follow"],(20,5,w-40,ribbon.height-5),w*.047,"#18110c","center",1)
        ribbon.save(work/"follow.png")
        idx=inp(work/"follow.png")
        begin=max(0,duration-3)
        fc.append(f"[{previous}][{idx}:v]overlay=x=0:y='H-h+max(0,1-(t-{begin})/.35)*h':enable='gte(t,{begin})':format=auto[followed]")
        previous="followed"
    if o["outro"]:
        outro_color = bg.getpixel((0,0))
        outro=Image.new("RGBA",(w,h),outro_color)
        outro_light = sum(outro_color[:3]) > 570
        draw_text(ImageDraw.Draw(outro),o["follow"] or o["name"] or "Thanks for watching",(w*.08,h*.43,w*.84,h*.25),w*.07,"#151515" if outro_light else "white","center",3)
        outro.save(work/"outro.png")
        idx=inp(work/"outro.png")
        fc.append(f"[{previous}][{idx}:v]overlay=0:0:enable='gte(t,{duration})':format=auto[outro]")
        previous="outro"
    fc.append(f"[{previous}]trim=duration={total},fps={fps},format=yuv420p[v]")
    fc.append(f"[srca]aresample=48000,volume={o['voice_volume']},apad,atrim=duration={total}[voice]")
    tracks=["voice"]
    if o["music"]:
        idx=asset(o["music"])
        vol=f"{o['music_volume']}+({o['music_peak']}-{o['music_volume']})*max(0,min(1,(t-{max(0,duration-3)})/3))" if o["music_riser"] else str(o["music_volume"])
        fc.append(f"[{idx}:a]aresample=48000,atrim=duration={total},asetpts=PTS-STARTPTS,volume='{vol}':eval=frame,afade=t=out:st={max(0,total-.5)}:d=0.5[music]")
        if o["duck"]:
            fc.append("[voice]asplit=2[voice_mix][side]")
            tracks=["voice_mix"]
            fc.append("[music][side]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=300[ducked]")
            tracks.append("ducked")
        else: tracks.append("music")
    for i,r in enumerate(o["sfx"]):
        if r["asset"]: idx=asset(r["asset"])
        else:
            sound(work/f"sfx{i}.wav",r["sound"])
            idx=inp(work/f"sfx{i}.wav","audio")
        delay=round(r["time"]*1000)
        fc.append(f"[{idx}:a]atrim=duration={min(r['duration'],2)},asetpts=PTS-STARTPTS,volume={r['volume']},adelay={delay}:all=1,apad,atrim=duration={total}[sfx{i}]")
        tracks.append(f"sfx{i}")
    fc.append("".join(f"[{t}]" for t in tracks)+f"amix=inputs={len(tracks)}:normalize=0,alimiter=limit=.95,atrim=duration={total}[a]")
    fcpath=work/"filter.txt"
    fcpath.write_text(";\n".join(fc),encoding="utf-8")
    base=["ffmpeg","-y","-v","error","-filter_complex_threads","1",*inputs,"-filter_complex",";".join(fc),"-map","[v]","-map","[a]","-t",str(total),"-c:a","aac","-b:a","160k","-ar","48000","-movflags","+faststart"]
    for k in ("title","description"):
        if clip.get(k): base += ["-metadata",f"{k}={clip[k]}"]
    # Software is the reliable default for alpha composition on older Intel GPUs.
    # Explicit hardware choices still fall back to software when the driver refuses them.
    hardware={"nvenc":["-c:v","h264_nvenc","-preset","fast","-cq","22"],
              "amf":["-c:v","h264_amf","-quality","speed"],
              "qsv":["-c:v","h264_qsv","-global_quality","23"]}
    choices=([(o["encoder"],hardware[o["encoder"]])] if o["encoder"] in hardware else [])
    choices.append(("cpu",["-c:v","libx264","-preset","veryfast","-crf","21","-threads","2"]))
    error=""
    used="cpu"
    for used,args in choices:
        if cancel is None:
            p=subprocess.run(base+args+["out.mp4"],cwd=work,capture_output=True,text=True,encoding="utf-8",errors="replace",creationflags=NO_WINDOW,timeout=max(1800,total*6))
            code,stderr=p.returncode,p.stderr
        else:
            import time
            p=subprocess.Popen(base+args+["out.mp4"],cwd=work,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,encoding="utf-8",errors="replace",creationflags=NO_WINDOW)
            began=time.monotonic()
            while True:
                if cancel() or time.monotonic()-began>max(1800,total*6):
                    p.terminate()
                    try:p.communicate(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.communicate()
                    raise RuntimeError("Compilation rendering stopped.")
                try:
                    _,stderr=p.communicate(timeout=1)
                    code=p.returncode
                    break
                except subprocess.TimeoutExpired:pass
        if code==0: break
        error=stderr[-1500:]
    else: raise RuntimeError("Studio render failed: "+error)
    run(["ffmpeg","-y","-v","error","-ss",str(min(1,duration/2)),"-i","out.mp4","-frames:v","1","-q:v","3","out.jpg"],cwd=work)
    out_dir.mkdir(parents=True,exist_ok=True)
    for srcname,ext in (("out.mp4","mp4"),("out.jpg","jpg"),("cap.ass","ass")):
        shutil.move(str(work/srcname),str(out_dir/f"{name}.{ext}"))
    return {"file":f"{name}.mp4","cover":f"{name}.jpg","layout":layout,"rendered_layout":layout,
            "layout_warning":"", "output_width":w,"output_height":h,"output_fps":round(fps,3),
            "output_duration":round(total,3),"encoder_used":used,
            "studio_note": "4K export enlarges this source; it cannot add missing source detail." if short==2160 and min(sw,sh)<2160 else ""}
