"""Soft studio lighting and a bevel around video panels; never paints over the picture."""
from PIL import Image, ImageChops, ImageDraw, ImageFilter


def radius(o, width, panel_width, index=0, layout='fit'):
    r = max(o['radius'], 24 if o.get('panel_light') else 0) * width / 1080
    if index == 1 and layout in ('pip', 'gameplay') and o['pip_shape'] == 'rounded':
        r = max(r, panel_width * .08)
    return int(r)


def layers(o, boxes, width, height, layout='fit'):
    back = Image.new('RGBA', (width, height))
    rim = Image.new('RGBA', (width, height))
    if not o.get('panel_light'):
        return back, rim
    scale = width / 1080
    amount = o['panel_light_strength']
    tint = tuple(bytes.fromhex(o['panel_light_color'][1:]))
    bright = tuple(round(c * .35 + 255 * .65) for c in tint)
    for index, (x, y, w, h) in enumerate(boxes):
        circle = index == 1 and layout in ('pip', 'gameplay') and o['pip_shape'] == 'circle'
        curve = radius(o, width, w, index, layout)
        pad = max(2, round(6 * scale))
        bounds = (x-pad, y-pad, x+w+pad-1, y+h+pad-1)
        def mask(expand=0, dx=0, dy=0):
            m = Image.new('L', (width, height))
            box = (bounds[0]-expand+dx, bounds[1]-expand+dy, bounds[2]+expand+dx, bounds[3]+expand+dy)
            d = ImageDraw.Draw(m)
            if circle:
                d.ellipse(box, fill=255)
            else:
                d.rounded_rectangle(box, radius=max(1, curve+pad+expand), fill=255)
            return m
        # A wide, soft cast shadow lifts the panel off the background.
        shadow = mask(dx=round(5*scale), dy=round(16*scale)).filter(ImageFilter.GaussianBlur(max(1, 20*scale)))
        shadow = shadow.point(lambda a: round(a * (.30+.38*amount)))
        layer = Image.new('RGBA', (width, height), (2, 8, 20, 0));layer.putalpha(shadow)
        back = Image.alpha_composite(back, layer)
        # A thin halo remains outside the picture, rather than tinting its contents.
        outer = mask(round(2*scale))
        inner = mask(-max(1, round(3*scale)))
        glow = ImageChops.subtract(outer, inner).filter(ImageFilter.GaussianBlur(max(1, 11*scale)))
        glow = glow.point(lambda a: round(a * 2*amount))
        layer = Image.new('RGBA', (width, height), (*tint, 0));layer.putalpha(glow)
        back = Image.alpha_composite(back, layer)
        # Directional bevel: lit top/left, darker lower/right, with a clean bright inner rim.
        ring = ImageChops.subtract(mask(), mask(-pad))
        gradient = Image.new('RGBA', (2, 128))
        gd = ImageDraw.Draw(gradient)
        for row in range(128):
            t = row / 127
            color = tuple(round(c*(1-t)+b*t) for c,b in zip(bright,(31,45,68)))
            gd.line((0,row,2,row), fill=(*color,round(205+amount*45)))
        bevel = Image.new('RGBA', (width, height))
        bw,bh = max(1,bounds[2]-bounds[0]+1), max(1,bounds[3]-bounds[1]+1)
        bevel.paste(gradient.resize((bw,bh)), (bounds[0],bounds[1]))
        bevel.putalpha(ImageChops.multiply(bevel.getchannel('A'),ring))
        rim = Image.alpha_composite(rim, bevel)
        edge = Image.new('RGBA', (width, height));d = ImageDraw.Draw(edge)
        line = max(1,round(1.5*scale))
        if circle:
            d.ellipse((x-1,y-1,x+w,y+h),outline=(*bright,round(125+100*amount)),width=line)
        else:
            d.rounded_rectangle((x-1,y-1,x+w,y+h),radius=max(1,curve),outline=(*bright,round(125+100*amount)),width=line)
            corner = max(2,curve+pad)
            d.arc((bounds[0],bounds[1],bounds[0]+corner*2,bounds[1]+corner*2),180,270,fill=(255,255,255,round(145+90*amount)),width=max(1,round(2*scale)))
        rim = Image.alpha_composite(rim, edge)
    return back, rim
