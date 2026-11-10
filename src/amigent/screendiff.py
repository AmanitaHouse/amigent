"""Two pictures of the Amiga's screen compared: how much changed, and where.

For testing programs: a baseline once, then after each change a comparison
that says the share of changed pixels, the boxes around the changed areas
(16x16 blocks joined into regions), and a picture: the screen dimmed, changed
pixels in magenta, the boxes in yellow.
"""

from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

BLOCK = 16


def compare(a: Image.Image, b: Image.Image, threshold: int = 24) -> tuple[dict, Image.Image]:
    a, b = a.convert("RGB"), b.convert("RGB")
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > threshold else 0)
    w, h = a.size
    changed = sum(1 for v in diff.getdata() if v)
    cols, rows = (w + BLOCK - 1) // BLOCK, (h + BLOCK - 1) // BLOCK
    hot = set()
    for by in range(rows):
        for bx in range(cols):
            box = (bx * BLOCK, by * BLOCK, min(w, bx * BLOCK + BLOCK), min(h, by * BLOCK + BLOCK))
            if diff.crop(box).getbbox():
                hot.add((bx, by))
    regions = []
    seen = set()
    for start in sorted(hot):
        if start in seen:
            continue
        stack, cells = [start], []
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            cells.append((cx, cy))
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in hot and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        xs, ys = [c[0] for c in cells], [c[1] for c in cells]
        regions.append((min(xs) * BLOCK, min(ys) * BLOCK, min(w, (max(xs) + 1) * BLOCK) - min(xs) * BLOCK,
                        min(h, (max(ys) + 1) * BLOCK) - min(ys) * BLOCK))
    regions.sort(key=lambda r: -r[2] * r[3])
    picture = Image.blend(b, Image.new("RGB", b.size, (0, 0, 0)), 0.6)
    picture.paste((255, 0, 255), mask=diff)
    draw = ImageDraw.Draw(picture)
    for x, y, rw, rh in regions[:20]:
        draw.rectangle((x, y, x + rw - 1, y + rh - 1), outline=(255, 255, 0))
    report = {"size": [w, h], "changed_pixels": changed,
              "changed_percent": round(changed * 100 / max(w * h, 1), 3),
              "regions": [{"x": x, "y": y, "width": rw, "height": rh} for x, y, rw, rh in regions[:20]],
              "more_regions": max(0, len(regions) - 20)}
    return report, picture
