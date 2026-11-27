"""User-positioned canvas elements, shared by the preview's saved profile and exports."""
import re

from PIL import Image, ImageDraw


class Layers:
    """Draw each frame element separately so moving one never erases another."""

    def __init__(self, options, width, height):
        self.options, self.width, self.height = options, width, height
        self.layers = []

    def start(self, name, bounds=None):
        image = Image.new("RGBA", (self.width, self.height))
        self.layers.append((name, image, bounds))
        return image, ImageDraw.Draw(image)

    def bounds(self, name, bounds):
        for i, (key, image, _) in enumerate(self.layers):
            if key == name:
                self.layers[i] = (key, image, bounds)

    def finish(self):
        result = Image.new("RGBA", (self.width, self.height))
        for name, image, reference in self.layers:
            place = self.options.get("placements", {}).get(name)
            if place:
                if not place.get("enabled", True):
                    continue
                ink = image.getbbox()
                if not ink:
                    continue
                x, y, width, height = rectangle(place, self.width, self.height)
                # A placement describes the logical element box, including empty space.
                # Cropping tightly to the ink and stretching it into that box made a
                # normal headline hundreds of pixels tall after a simple drag.
                if reference:
                    rx, ry, rw, rh = reference
                    source_box = (round(rx), round(ry), round(rx + rw), round(ry + rh))
                else:
                    source_box = ink
                image = image.crop(source_box)
                scale = min(width / image.width, height / image.height)
                size = max(1, round(image.width * scale)), max(1, round(image.height * scale))
                image = image.resize(size, Image.Resampling.LANCZOS)
                result.alpha_composite(image, (x, y))
            else:
                result = Image.alpha_composite(result, image)
        return result


def rectangle(place, width, height):
    x = min(width - 2, round(place["x"] * width))
    y = min(height - 2, round(place["y"] * height))
    bw = max(2, min(width - x, round(place["w"] * width)))
    bh = max(2, min(height - y, round(place["h"] * height)))
    return x, y, bw, bh


def panels(boxes, options, width, height):
    out = []
    for i, box in enumerate(boxes):
        place = options.get("placements", {}).get(f"video{i}")
        if place:
            x, y, bw, bh = rectangle(place, width, height)
            # Even panel dimensions work with all supported video encoders.
            box = x, y, max(2, bw // 2 * 2), max(2, bh // 2 * 2)
        out.append(box)
    return out


def captions(make, words, clip, options, width, height, light):
    place = options.get("placements", {}).get("caption")
    if not place:
        return make(words, clip, options, width, height, light)
    options = dict(options, caption_y=place["y"] + place["h"] / 2,
                   caption_size=max(.1, min(3.6, options["caption_size"] * place["w"] / .9)))
    result = make(words if place.get("enabled", True) else [], clip, options, width, height, light)
    # ASS may use a 1080-wide reference canvas. Move both glyphs and caption plates.
    reference = int(re.search(r"PlayResX:\s*(\d+)", result)[1])
    shift = round((place["x"] + place["w"] / 2 - .5) * reference)
    return re.sub(r"\\pos\(([-\d.]+),([-\d.]+)\)",
                  lambda m: f"\\pos({float(m[1]) + shift:g},{m[2]})", result)
