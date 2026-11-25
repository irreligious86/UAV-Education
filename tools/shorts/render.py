"""Shared renderer for the «Betaflight изнутри» short-video series (rebuilt 2026-11-24).

Vertical 1080x1920, 30 fps, silent, dark style. Scenes are functions f(t, dur) -> PIL.Image;
a video is a list of (name, fn, dur). render_video() renders scenes in parallel and concatenates.
"""
import math, os, subprocess, sys
from concurrent.futures import ProcessPoolExecutor
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
BG = (13, 15, 19); PANEL = (27, 31, 39); FG = (236, 238, 241); MUTED = (138, 147, 160)
OR = (255, 152, 48); TE = (46, 200, 205); GR = (96, 210, 122); RD = (238, 82, 82); PU = (170, 120, 230); YE = (240, 210, 80)
FONT_DIR = "/usr/share/fonts/opentype/inter"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
_fc = {}


def F(size, weight="SemiBold"):
    key = ("F", size, weight)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(f"{FONT_DIR}/Inter-{weight}.otf", size)
    return _fc[key]


def M(size):
    key = ("M", size)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(MONO, size)
    return _fc[key]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def mix(a, b, k):
    k = max(0.0, min(1.0, k))
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


def base():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    for y in range(0, H, 64):                      # faint HUD grid
        d.line([(0, y), (W, y)], fill=(18, 21, 26))
    for x in range(0, W, 64):
        d.line([(x, 0), (x, H)], fill=(18, 21, 26))
    return im, d


def text(d, xy, s, font, col, anchor="la", a=1.0):
    if a <= 0.01:
        return
    d.text(xy, s, font=font, fill=mix(BG, col, a), anchor=anchor)


def text_w(s, font):
    return font.getlength(s)


def wrap(s, font, width):
    out, line = [], ""
    for w in s.split(" "):
        t = (line + " " + w).strip()
        if font.getlength(t) <= width:
            line = t
        else:
            if line:
                out.append(line)
            line = w
    if line:
        out.append(line)
    return out


def wrap_text(d, x, y, s, font, width, col, a=1.0, lh=None, anchor="la"):
    lh = lh or int(font.size * 1.32)
    lines = wrap(s, font, width)
    for i, ln in enumerate(lines):
        text(d, (x, y + i * lh), ln, font, col, anchor, a)
    return y + len(lines) * lh


def topbar(n):
    """Return a drawer: section label at the top-left and n progress dots at the top-right."""
    def draw(d, label, i, a=1.0):
        text(d, (60, 62), label, F(26, "Bold"), OR, "lm", a)
        x0 = W - 60 - (n - 1) * 30
        for k in range(n):
            c = OR if k == i else (MUTED if k < i else (52, 58, 68))
            r = 8 if k == i else 6
            d.ellipse([x0 + k * 30 - r, 62 - r, x0 + k * 30 + r, 62 + r], fill=mix(BG, c, a))
        d.line([(60, 96), (W - 60, 96)], fill=mix(BG, (40, 46, 56), a), width=2)
    return draw


def title(d, s, y=150, col=FG, size=66, a=1.0):
    return wrap_text(d, 60, y, s, F(size, "Bold"), W - 120, col, a)


def chip(d, xy, s, font, col, a=1.0, width=W - 120):
    if a <= 0.01:
        return xy[1]
    x, y = xy
    lines = wrap(s, font, width - 56)
    h = len(lines) * int(font.size * 1.3) + 34
    d.rounded_rectangle([x, y, x + width, y + h], radius=18, fill=mix(BG, PANEL, a), outline=mix(BG, col, a), width=3)
    for i, ln in enumerate(lines):
        text(d, (x + 28, y + 17 + i * int(font.size * 1.3)), ln, font, col, "la", a)
    return y + h


def card(d, y, head, body, col, a, h=None, x=60, w=W - 120, hs=38, bs=31):
    """Card with a coloured left stripe. Returns bottom y."""
    bl = wrap(body, F(bs, "Medium"), w - 80) if body else []
    hh = h or (30 + int(hs * 1.3) + len(bl) * int(bs * 1.34) + 26)
    d.rounded_rectangle([x, y, x + w, y + hh], radius=20, fill=mix(BG, PANEL, a))
    d.rounded_rectangle([x, y, x + 14, y + hh], radius=6, fill=mix(BG, col, a))
    text(d, (x + 44, y + 24), head, F(hs, "Bold"), col, "la", a)
    for i, ln in enumerate(bl):
        text(d, (x + 44, y + 30 + int(hs * 1.3) + i * int(bs * 1.34)), ln, F(bs, "Medium"), FG, "la", a)
    return y + hh


def cards(d, t, rows, y0, gap=26, t0=0.4, step=0.9, hs=38, bs=31):
    y = y0
    for i, (head, body, col) in enumerate(rows):
        a = ease((t - t0 - i * step) / 0.5)
        y = card(d, y, head, body, col, max(a, 0.0), hs=hs, bs=bs) + gap
    return y


def code_block(d, x, y, lines, a, size=25, w=W - 120, col=FG, comment=MUTED):
    lh = int(size * 1.45)
    h = len(lines) * lh + 40
    d.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=mix(BG, (8, 10, 13), a), outline=mix(BG, (44, 50, 60), a), width=2)
    for i, ln in enumerate(lines):
        code, _, cm = ln.partition("#")
        text(d, (x + 26, y + 20 + i * lh), code, M(size), col, "la", a)
        if cm:
            text(d, (x + 26 + M(size).getlength(code), y + 20 + i * lh), "#" + cm, M(size), comment, "la", a)
    return y + h


def arrow(d, p0, p1, col, a=1.0, w=4, head=16):
    if a <= 0.01:
        return
    c = mix(BG, col, a)
    d.line([p0, p1], fill=c, width=w)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        q = (p1[0] - head * math.cos(ang + s * 0.45), p1[1] - head * math.sin(ang + s * 0.45))
        d.line([p1, q], fill=c, width=w)


def polyline(d, pts, col, a=1.0, w=5):
    if len(pts) > 1 and a > 0.01:
        d.line(pts, fill=mix(BG, col, a), width=w, joint="curve")


def fade(im, t, dur, fin=0.35, fout=0.35):
    k = min(1.0, t / fin if fin else 1.0, (dur - t) / fout if fout else 1.0)
    if k >= 1.0:
        return im
    return Image.blend(Image.new("RGB", (W, H), BG), im, max(0.0, k))


def hook(t, dur, h1, h2, lead, tags, draw=None):
    im, d = base()
    a = ease(t / 0.6)
    text(d, (60, 230), "BETAFLIGHT ИЗНУТРИ · ТЮНИНГ И ПЕРСОНАЛИЗАЦИЯ", F(24, "Bold"), MUTED, "la", a)
    y = wrap_text(d, 60, 290, h1, F(84, "Bold"), W - 120, FG, a, lh=96)
    y = wrap_text(d, 60, y + 10, h2, F(46, "Bold"), W - 120, OR, ease((t - 0.4) / 0.6), lh=58)
    if draw:
        draw(d, t, ease((t - 0.8) / 0.6))
    wrap_text(d, 60, 1330, lead, F(32, "Medium"), W - 120, FG, ease((t - 1.6) / 0.7), lh=44)
    text(d, (60, 1700), tags, F(24, "Medium"), MUTED, "la", ease((t - 2.4) / 0.6))
    return fade(im, t, dur)


def end_card(t, dur, lines, sub):
    im, d = base()
    for i, (s, col) in enumerate(lines):
        a = ease((t - 0.3 - i * 0.35) / 0.5)
        d.rounded_rectangle([60, 300 + i * 130, 80, 360 + i * 130], radius=5, fill=mix(BG, col, a))
        wrap_text(d, 110, 300 + i * 130, s, F(36, "Bold"), W - 180, FG, a, lh=44)
    a = ease((t - 2.6) / 0.6)
    text(d, (W / 2, 1360), "Betaflight", F(96, "Bold"), FG, "ma", a)
    text(d, (W / 2, 1470), "изнутри", F(96, "Bold"), OR, "ma", a)
    text(d, (W / 2, 1610), sub, F(30, "Medium"), MUTED, "ma", a)
    return fade(im, t, dur, fout=0.8)


def _render_scene(args):
    mod, name, idx, out = args
    m = __import__(mod)
    _, fn, dur = m.SCENES[idx]
    tmp = f"{out}/tmp_{name}.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(dur * FPS)):
        p.stdin.write(fn(i / FPS, dur).tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"{name} failed")
    os.replace(tmp, f"{out}/{name}.mp4")
    return name


def render_video(mod, out, final):
    """Render every scene of module `mod` into `out`, then concatenate into `final`."""
    m = __import__(mod)
    os.makedirs(out, exist_ok=True)
    jobs = [(mod, n, i, out) for i, (n, _, _) in enumerate(m.SCENES)]
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        for n in ex.map(_render_scene, jobs):
            print("ok", n, flush=True)
    with open(f"{out}/list.txt", "w") as fh:
        fh.writelines(f"file '{out}/{n}.mp4'\n" for n, _, _ in m.SCENES)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{out}/list.txt", "-c", "copy",
                    "-movflags", "+faststart", final], check=True)


def preview(mod, out, fracs=(0.55, 0.95)):
    m = __import__(mod)
    os.makedirs(out, exist_ok=True)
    for n, fn, dur in m.SCENES:
        for f in fracs:
            fn(dur * f, dur).save(f"{out}/prev_{n}_{int(f * 100)}.jpg", quality=85)
