"""Growcline 'Java Full Stack + AI' motion-graphics reel (no photos).

Draws every frame with Pillow (1080x1920, 30 fps) and pipes raw RGB to ffmpeg -> video_only.mp4.
Scene timing matches the voiceover of the photo reel so the same audio track can be muxed on.
Usage: venv/bin/python motion.py OUT_DIR [--still SECONDS ...]   (--still writes PNG previews instead)
"""
import math
import os
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, FPS, TOTAL = 1080, 1920, 30, 30.0
KIT = os.path.expanduser("~/growcline_dm_agent/brand")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NAVY, NAVY2, CORAL, RED = (7, 26, 51), (12, 40, 76), (249, 95, 84), (255, 49, 49)
WHITE, MUTED, CARD, LINE = (255, 255, 255), (185, 196, 214), (18, 44, 80), (40, 70, 110)
GREEN, CODEBG = (63, 185, 80), (13, 17, 23)

# scene start times (s) from the voiceover timeline
STARTS = [0.0, 3.58, 7.21, 10.46, 13.34, 17.12, 22.51, TOTAL]

_fonts = {}


def F(size, weight=900, mono=False):
    key = (size, weight, mono)
    if key not in _fonts:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else f"{KIT}/fonts/nunito-{weight}.woff"
        _fonts[key] = ImageFont.truetype(path, size)
    return _fonts[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def ease(x):  # easeOutCubic
    return 1 - (1 - x) ** 3


def back(x):  # easeOutBack (slight overshoot); exactly 0 before the animation starts
    if x <= 0:
        return 0.0
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def mix(c1, c2, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c1, c2))


# ---------- static assets ----------
def make_bg():
    bg = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(bg)
    for y in range(0, H, 8):  # vertical gradient
        d.rectangle([0, y, W, y + 8], fill=mix(NAVY, NAVY2, y / H))
    for x in range(0, W, 90):  # faint grid
        d.line([x, 0, x, H], fill=mix(NAVY, LINE, .25), width=1)
    for y in range(0, H, 90):
        d.line([0, y, W, y], fill=mix(NAVY, LINE, .25), width=1)
    return bg


BG = make_bg()
BAR = Image.open(f"{HERE}/assets/footer_bar.png").convert("RGB")
LOGO = Image.open(f"{KIT}/logo.png").convert("RGBA")
LOGO_S = LOGO.resize((int(LOGO.width * 0.8), int(LOGO.height * 0.8)), Image.LANCZOS)
random.seed(4)
DOTS = [(random.uniform(0, W), random.uniform(0, H), random.uniform(2, 5), random.uniform(10, 35), random.random())
        for _ in range(40)]


# ---------- drawing helpers ----------
def layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def put(frame, lay, opacity=1.0):
    if opacity <= 0:
        return
    if opacity < 1:
        a = lay.getchannel("A").point(lambda v: int(v * opacity))
        lay.putalpha(a)
    frame.alpha_composite(lay)


def rich(d, x, y, text, font, color=WHITE, accent=CORAL, anchor_center=False):
    """Draw text with *accent* segments on one line. Returns width."""
    parts, on = [], False
    for i, seg in enumerate(text.split("*")):
        if seg:
            parts.append((seg, accent if on else color))
        on = not on
    width = sum(d.textlength(s, font=font) for s, _ in parts)
    if anchor_center:
        x -= width / 2
    for s, c in parts:
        d.text((x, y), s, font=font, fill=c)
        x += d.textlength(s, font=font)
    return width


def pill(d, x, y, text, font, fg, bg=None, outline=None, pad=(26, 12), center=False):
    tw = d.textlength(text, font=font)
    bb = font.getbbox("Ag")
    h = bb[3] - bb[1] + pad[1] * 2
    w = tw + pad[0] * 2
    if center:
        x -= w / 2
    d.rounded_rectangle([x, y, x + w, y + h], radius=h / 2, fill=bg, outline=outline, width=3 if outline else 0)
    d.text((x + pad[0], y + pad[1] - bb[1]), text, font=font, fill=fg)
    return w, h


def eyebrow(frame, t, text):
    lay = layer()
    d = ImageDraw.Draw(lay)
    k = ease(prog(t, 0.05, 0.45))
    pill(d, 86 - (1 - k) * 60, 250, text.upper(), F(30, 800), CORAL, outline=CORAL, pad=(26, 12))
    put(frame, lay, k)


def headline(frame, t, lines, y=340, size=104, t0=0.15, step=0.18):
    for i, line in enumerate(lines):
        k = ease(prog(t, t0 + i * step, t0 + i * step + 0.45))
        if k <= 0:
            continue
        lay = layer()
        d = ImageDraw.Draw(lay)
        rich(d, 86, y + i * int(size * 1.12) + (1 - k) * 50, line, F(size))
        put(frame, lay, k)


def window(d, x, y, w, h, title=""):
    d.rounded_rectangle([x, y, x + w, y + h], radius=26, fill=CODEBG, outline=(48, 54, 61), width=2)
    d.rounded_rectangle([x, y, x + w, y + 64], radius=26, fill=(22, 27, 34))
    d.rectangle([x, y + 40, x + w, y + 64], fill=(22, 27, 34))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([x + 26 + i * 32, y + 22, x + 46 + i * 32, y + 42], fill=c)
    if title:
        d.text((x + w / 2, y + 32), title, font=F(26, 700), fill=(139, 148, 158), anchor="mm")


def check(d, cx, cy, r, color=GREEN):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    d.line([cx - r * .45, cy, cx - r * .1, cy + r * .35, cx + r * .5, cy - r * .35], fill=WHITE, width=max(3, int(r / 4)))


def cloud(d, cx, cy, s, fill):
    for dx, dy, r in [(-0.55, 0.1, 0.42), (-0.1, -0.2, 0.55), (0.45, 0.05, 0.45)]:
        d.ellipse([cx + (dx - r) * s, cy + (dy - r) * s, cx + (dx + r) * s, cy + (dy + r) * s], fill=fill)
    d.rounded_rectangle([cx - 0.95 * s, cy, cx + 0.88 * s, cy + 0.5 * s], radius=0.25 * s, fill=fill)


def cylinder(d, cx, cy, w, h, fill, top):
    d.rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], fill=fill)
    d.ellipse([cx - w / 2, cy + h / 2 - w * .18, cx + w / 2, cy + h / 2 + w * .18], fill=fill)
    for k in (0.0, 0.33, 0.66):
        yy = cy - h / 2 + h * k
        d.arc([cx - w / 2, yy - w * .18, cx + w / 2, yy + w * .18], 0, 180, fill=top, width=4)
    d.ellipse([cx - w / 2, cy - h / 2 - w * .18, cx + w / 2, cy - h / 2 + w * .18], fill=top)


def type_text(s, t, a, b):
    n = int(len(s) * prog(t, a, b))
    return s[:n]


# ---------- scenes (t = seconds since scene start, dur = scene length) ----------
def s1_hook(fr, t, dur):
    eyebrow(fr, t, "Java Full Stack + AI")
    headline(fr, t, ["Become a", "*full-stack*", "*developer.*"], y=330, size=118)
    # laptop with code lines writing themselves
    k = back(prog(t, 0.6, 1.2))
    if k > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        cx, cy, s = W / 2, 1150, 0.75 + 0.25 * k
        sw, sh = 640 * s, 400 * s
        x0, y0 = cx - sw / 2, cy - sh / 2
        d.rounded_rectangle([x0 - 18, y0 - 18, x0 + sw + 18, y0 + sh + 18], radius=28, fill=(30, 52, 86))
        d.rectangle([x0, y0, x0 + sw, y0 + sh], fill=CODEBG)
        d.rounded_rectangle([x0 - 90, y0 + sh + 18, x0 + sw + 90, y0 + sh + 52], radius=14, fill=(44, 70, 110))
        widths = [0.55, 0.8, 0.42, 0.7, 0.6, 0.35, 0.75]
        cols = [CORAL, MUTED, GREEN, MUTED, (121, 192, 255), MUTED, CORAL]
        for i, (wf, c) in enumerate(zip(widths, cols)):
            lk = prog(t, 1.0 + i * 0.14, 1.3 + i * 0.14)
            if lk > 0:
                ly = y0 + 34 + i * 50 * s
                d.rounded_rectangle([x0 + 36 + (i % 3) * 28, ly, x0 + 36 + (i % 3) * 28 + (sw - 120) * wf * lk, ly + 20 * s],
                                    radius=10, fill=c)
        put(fr, lay, clamp(k))
    # AI badge pops onto the laptop corner
    k = back(prog(t, 1.9, 2.3))
    if k > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        r = 92 * k
        cx, cy = W / 2 + 330, 900
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=CORAL)
        d.text((cx, cy), "AI", font=F(max(10, int(84 * k))), fill=WHITE, anchor="mm")
        put(fr, lay)
    k = ease(prog(t, 2.2, 2.7))
    lay = layer(); d = ImageDraw.Draw(lay)
    rich(d, W / 2, 1480 + (1 - k) * 30, "with *AI* on your side", F(54, 800), MUTED, anchor_center=True)
    put(fr, lay, k)


JAVA = [("@RestController", CORAL), ("public class StudentApi {", WHITE), ('  @GetMapping("/students")', CORAL),
        ("  List<Student> all() {", WHITE), ("    return repo.findAll();", (121, 192, 255)), ("  }", WHITE), ("}", WHITE)]


def s2_java(fr, t, dur):
    eyebrow(fr, t, "01  Java + Spring Boot")
    headline(fr, t, ["Start with *Java.*", "Build real *APIs.*"], size=100)
    k = ease(prog(t, 0.35, 0.75))
    lay = layer(); d = ImageDraw.Draw(lay)
    x, y, w, h = 70, 640 + (1 - k) * 60, 940, 560
    window(d, x, y, w, h, "StudentApi.java")
    total = sum(len(s) for s, _ in JAVA)
    shown = int(total * prog(t, 0.6, 2.4))
    for i, (s, c) in enumerate(JAVA):
        part = s[:max(0, shown)]
        shown -= len(s)
        d.text((x + 40, y + 100 + i * 62), part, font=F(36, mono=True), fill=c)
        if 0 < len(part) < len(s) or (len(part) == len(s) and shown <= 0 and shown > -1):
            cw = d.textlength(part, font=F(36, mono=True))
            if int(t * 4) % 2 == 0:
                d.rectangle([x + 42 + cw, y + 102 + i * 62, x + 60 + cw, y + 140 + i * 62], fill=CORAL)
    put(fr, lay, k)
    k = back(prog(t, 2.5, 2.9))
    if k > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        cw, chh = pill(d, W / 2, 1290 + (1 - k) * 40, "GET /students   200 OK", F(46, 800), WHITE, bg=GREEN, center=True, pad=(40, 18))
        put(fr, lay, clamp(k))


def s3_react(fr, t, dur):
    eyebrow(fr, t, "02  React + MongoDB")
    headline(fr, t, ["Design it.", "*Connect it all.*"], size=100)
    # three nodes stacked: React UI -> API -> MongoDB, with travelling data packets
    nodes = [(W / 2, 800), (W / 2, 1110), (W / 2, 1400)]
    ks = [back(prog(t, 0.35 + i * 0.25, 0.75 + i * 0.25)) for i in range(3)]
    lay = layer(); d = ImageDraw.Draw(lay)
    for i in range(2):  # connectors
        lk = prog(t, 0.8 + i * 0.3, 1.2 + i * 0.3)
        if lk > 0:
            (x1, y1), (x2, y2) = nodes[i], nodes[i + 1]
            ya, yb = y1 + 105, y2 - 95
            d.line([x1, ya, x1, ya + (yb - ya) * lk], fill=CORAL, width=6)
            if lk >= 1:
                for p in range(3):  # packets moving down/up
                    ph = ((t * 0.9 + p / 3) % 1)
                    py = ya + (yb - ya) * (ph if i == 0 else 1 - ph)
                    d.ellipse([x1 - 13, py - 13, x1 + 13, py + 13], fill=WHITE)
    put(fr, lay)
    # React UI card (mini app)
    if ks[0] > 0:
        lay = layer(); d = ImageDraw.Draw(lay); s = clamp(ks[0])
        cx, cy = nodes[0]
        bw, bh = 620 * (0.85 + 0.15 * ks[0]), 210
        d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], radius=28, fill=WHITE)
        d.text((cx - bw / 2 + 36, cy - bh / 2 + 26), "React UI", font=F(40), fill=NAVY)
        # React atom icon
        ax, ay = cx + bw / 2 - 80, cy - 58
        for ang in (0, 60, 120):
            box = Image.new("RGBA", (120, 120), (0, 0, 0, 0)); bd = ImageDraw.Draw(box)
            bd.ellipse([8, 42, 112, 78], outline=(97, 218, 251), width=5)
            box = box.rotate(ang, resample=Image.BICUBIC)
            lay.alpha_composite(box, (int(ax - 60), int(ay - 60)))
        d.ellipse([ax - 9, ay - 9, ax + 9, ay + 9], fill=(97, 218, 251))
        for j in range(3):  # student cards filling in
            ck = prog(t, 1.2 + j * 0.25, 1.5 + j * 0.25)
            if ck > 0:
                x0 = cx - bw / 2 + 36 + j * 185
                d.rounded_rectangle([x0, cy + 6, x0 + 165 * ck, cy + 76], radius=14, fill=(255, 235, 233))
                d.ellipse([x0 + 14, cy + 22, x0 + 52, cy + 60], fill=CORAL)
        put(fr, lay, s)
    if ks[1] > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        cx, cy = nodes[1]
        pill(d, cx, cy - 45, "Spring Boot API", F(48), WHITE, bg=CARD, outline=CORAL, center=True, pad=(46, 20))
        put(fr, lay, clamp(ks[1]))
    if ks[2] > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        cx, cy = nodes[2]
        cylinder(d, cx - 170, cy, 110, 110 * clamp(ks[2]) + 1, (19, 170, 82), (77, 201, 120))
        d.text((cx - 80, cy - 34), "MongoDB", font=F(58), fill=WHITE)
        put(fr, lay, clamp(ks[2]))


TERM = ["$ ssh ubuntu@aws-server", "$ java -jar student-app.jar", "Started on port 8080", "✓ Live on AWS"]


def s4_aws(fr, t, dur):
    eyebrow(fr, t, "03  Linux + AWS")
    headline(fr, t, ["Run it on *Linux.*", "Ship it to *AWS.*"], size=100)
    k = ease(prog(t, 0.3, 0.6))
    lay = layer(); d = ImageDraw.Draw(lay)
    x, y, w, h = 70, 630 + (1 - k) * 50, 940, 400
    window(d, x, y, w, h, "ubuntu@aws: ~")
    starts = [0.45, 1.0, 1.5, 1.9]
    for i, (s, st) in enumerate(zip(TERM, starts)):
        txt = type_text(s, t, st, st + (0.45 if s.startswith("$") else 0.05))
        col = GREEN if s.startswith("✓") else (CORAL if s.startswith("$") else MUTED)
        d.text((x + 40, y + 100 + i * 66), txt, font=F(38, mono=True), fill=col)
    put(fr, lay, k)
    # cloud + upload arrow + progress
    k = back(prog(t, 0.8, 1.3))
    if k > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        cx, cy = W / 2, 1250
        cloud(d, cx, cy, 190 * clamp(k, 0, 1.2), (255, 153, 0))
        d.text((cx, cy + 40), "AWS", font=F(64), fill=WHITE, anchor="mm")
        pk = prog(t, 1.2, 2.2)
        ay = 1500 - 90 * ((t * 1.6) % 1) if pk < 1 else 1430
        d.polygon([(cx, ay - 40), (cx - 34, ay), (cx + 34, ay)], fill=WHITE)
        d.rectangle([cx - 11, ay, cx + 11, ay + 40], fill=WHITE)
        d.rounded_rectangle([cx - 300, 1520, cx + 300, 1546], radius=13, fill=CARD)
        d.rounded_rectangle([cx - 300, 1520, cx - 300 + 600 * pk, 1546], radius=13, fill=GREEN if pk >= 1 else CORAL)
        put(fr, lay, clamp(k))


def s5_qodo(fr, t, dur):
    eyebrow(fr, t, "04  AI vibe coding")
    headline(fr, t, ["Code faster", "with *Qodo.*"], size=104)
    lay = layer(); d = ImageDraw.Draw(lay)
    # user prompt bubble (right)
    k = ease(prog(t, 0.3, 0.6))
    if k > 0:
        msg = type_text("Build a student records app", t, 0.4, 1.2)
        bw = 760
        x0 = W - 70 - bw
        d.rounded_rectangle([x0, 640, W - 70, 760], radius=36, fill=CORAL)
        d.text((x0 + 40, 676), msg, font=F(44, 700), fill=WHITE)
    # Qodo reply bubble with streaming code bars
    k2 = ease(prog(t, 1.2, 1.5))
    if k2 > 0:
        d.rounded_rectangle([70, 800, 870, 1250], radius=36, fill=CARD)
        d.ellipse([100, 826, 160, 886], fill=(127, 90, 240))
        d.text((130, 856), "Q", font=F(40), fill=WHITE, anchor="mm")
        d.text((180, 832), "Qodo", font=F(42), fill=WHITE)
        random.seed(11)
        for i in range(7):
            lk = prog(t, 1.5 + i * 0.12, 1.75 + i * 0.12)
            wf = random.uniform(0.35, 0.9)
            c = random.choice([CORAL, (121, 192, 255), GREEN, MUTED])
            if lk > 0:
                d.rounded_rectangle([110 + (i % 3) * 30, 920 + i * 44, 110 + (i % 3) * 30 + 620 * wf * lk, 944 + i * 44], radius=12, fill=c)
    # checklist pops
    items = ["Spring Boot API", "MongoDB model", "React UI", "Deployed to AWS"]
    for i, it in enumerate(items):
        ck = back(prog(t, 2.4 + i * 0.25, 2.7 + i * 0.25))
        if ck > 0:
            yy = 1300 + i * 62
            check(d, 110, yy + 24, 22 * clamp(ck, 0, 1.2))
            d.text((150, yy), it, font=F(42, 800), fill=WHITE)
    put(fr, lay)


def s6_format(fr, t, dur):
    eyebrow(fr, t, "Online + offline")
    headline(fr, t, ["Learn it", "*your way.*"], size=118)
    lay = layer(); d = ImageDraw.Draw(lay)
    # big counter
    n = int(round(3 * ease(prog(t, 0.5, 1.3))))
    k = ease(prog(t, 0.4, 0.7))
    if k > 0:
        d.text((86, 640), str(n), font=F(260), fill=CORAL)
        d.text((290, 760), "MONTHS", font=F(64, 800), fill=WHITE)
        d.text((290, 840), "Java Full Stack + AI", font=F(40, 600), fill=MUTED)
    # two batch cards slide in
    for i, (title, sub, icon) in enumerate([("Online batch", "Learn from home", "monitor"), ("Offline batch", "Learn in class", "building")]):
        ck = ease(prog(t, 1.3 + i * 0.35, 1.8 + i * 0.35))
        if ck <= 0:
            continue
        x0 = 70 + i * 480 + (1 - ck) * (-300 if i == 0 else 300)
        y0 = 1000
        d.rounded_rectangle([x0, y0, x0 + 460, y0 + 330], radius=32, fill=WHITE)
        ix, iy = x0 + 50, y0 + 50
        if icon == "monitor":
            d.rounded_rectangle([ix, iy, ix + 110, iy + 72], radius=10, outline=NAVY, width=7)
            d.rectangle([ix + 45, iy + 72, ix + 65, iy + 92], fill=NAVY)
            d.rectangle([ix + 25, iy + 92, ix + 85, iy + 100], fill=NAVY)
        else:
            d.polygon([(ix + 55, iy - 6), (ix, iy + 28), (ix + 110, iy + 28)], fill=NAVY)
            for c in range(4):
                d.rectangle([ix + 8 + c * 27, iy + 34, ix + 22 + c * 27, iy + 86], fill=NAVY)
            d.rectangle([ix, iy + 88, ix + 110, iy + 100], fill=NAVY)
        d.text((x0 + 50, y0 + 170), title, font=F(48), fill=NAVY)
        d.text((x0 + 50, y0 + 236), sub, font=F(36, 600), fill=(90, 100, 120))
    pk = back(prog(t, 2.6, 3.0))
    if pk > 0:
        w_, h_ = pill(d, W / 2, 1420, "      Placement support", F(50, 800), WHITE, bg=GREEN, center=True, pad=(40, 22))
        check(d, W / 2 - w_ / 2 + 58, 1420 + h_ / 2, 24, WHITE)
        d.line([W / 2 - w_ / 2 + 48, 1420 + h_ / 2, W / 2 - w_ / 2 + 55, 1420 + h_ / 2 + 8, W / 2 - w_ / 2 + 70, 1420 + h_ / 2 - 8], fill=GREEN, width=5)
    put(fr, lay)


def s7_cta(fr, t, dur):
    lay = layer(); d = ImageDraw.Draw(lay)
    k = back(prog(t, 0.05, 0.5))
    if k > 0:
        lg = LOGO.resize((int(LOGO.width * 2.2 * clamp(k, 0, 1.1)) + 1, int(LOGO.height * 2.2 * clamp(k, 0, 1.1)) + 1), Image.LANCZOS)
        lay.alpha_composite(lg, (int(W / 2 - lg.width / 2), int(330 - lg.height / 2)))
    put(fr, lay)
    headline_y = 520
    for i, line in enumerate(["Book your", "*FREE demo.*"]):
        hk = ease(prog(t, 0.35 + i * 0.18, 0.8 + i * 0.18))
        if hk > 0:
            lay = layer(); d = ImageDraw.Draw(lay)
            rich(d, W / 2, headline_y + i * 132 + (1 - hk) * 40, line, F(122), anchor_center=True)
            put(fr, lay, hk)
    # rotating date badge
    bk = back(prog(t, 1.0, 1.4))
    if bk > 0:
        r = int(150 * clamp(bk, 0, 1.15))
        badge = Image.new("RGBA", (2 * r + 4, 2 * r + 4), (0, 0, 0, 0)); bd = ImageDraw.Draw(badge)
        bd.ellipse([2, 2, 2 * r + 2, 2 * r + 2], fill=RED)
        bd.text((r + 2, r - r * .22), "STARTS", font=F(max(8, int(r * .3))), fill=WHITE, anchor="mm")
        bd.text((r + 2, r + r * .2), "OCT 15", font=F(max(8, int(r * .38))), fill=WHITE, anchor="mm")
        badge = badge.rotate(-10 + 4 * math.sin(t * 3), resample=Image.BICUBIC)
        fr.alpha_composite(badge, (int(W / 2 - badge.width / 2), int(1000 - badge.height / 2)))
    lay = layer(); d = ImageDraw.Draw(lay)
    for i, c in enumerate(["Online", "Offline", "Placement support"]):
        ck = ease(prog(t, 1.4 + i * 0.15, 1.8 + i * 0.15))
        if ck > 0:
            xs = [W / 2 - 330, W / 2 - 115, W / 2 + 195][i]
            pill(d, xs, 1200 + (1 - ck) * 30, c, F(36, 800), WHITE, bg=CARD, outline=LINE, center=True)
    put(fr, lay)
    # pulsing CTA button
    ck = ease(prog(t, 1.9, 2.3))
    if ck > 0:
        lay = layer(); d = ImageDraw.Draw(lay)
        pulse = 1 + 0.04 * math.sin(t * 6) * prog(t, 2.3, 2.6)
        f = F(int(64 * pulse))
        tw = d.textlength("growcline.in", font=f)
        bw, bh = tw + 140, 130 * pulse
        d.rounded_rectangle([W / 2 - bw / 2, 1340 - bh / 2, W / 2 + bw / 2, 1340 + bh / 2], radius=bh / 2, fill=CORAL)
        d.text((W / 2, 1340), "growcline.in", font=f, fill=WHITE, anchor="mm")
        d.text((W / 2, 1480), "Call / WhatsApp +91 91827 13892", font=F(44, 800), fill=MUTED, anchor="mm")
        put(fr, lay, ck)


SCENES = [s1_hook, s2_java, s3_react, s4_aws, s5_qodo, s6_format, s7_cta]


def frame_at(T):
    fr = BG.copy().convert("RGBA")
    d = ImageDraw.Draw(fr)
    for x, y, r, sp, ph in DOTS:  # drifting particles
        yy = (y - T * sp) % H
        d.ellipse([x - r, yy - r, x + r, yy + r], fill=mix(NAVY, CORAL, 0.25 + 0.2 * math.sin(T + ph * 6)))
    i = max(j for j in range(7) if STARTS[j] <= T)
    t, dur = T - STARTS[i], STARTS[i + 1] - STARTS[i]
    SCENES[i](fr, t, dur)
    # branded wipe between scenes: coral panel enters at the end of a scene and leaves at the start of the next
    WIPE = 0.22
    if i < 6 and dur - t < WIPE:
        k = ease(1 - (dur - t) / WIPE)
        ImageDraw.Draw(fr).rectangle([W - W * k, 0, W, H], fill=CORAL + (255,))
    if i > 0 and t < WIPE:
        k = ease(t / WIPE)
        ImageDraw.Draw(fr).rectangle([0, 0, W - W * k, H], fill=CORAL + (255,))
    # persistent brand footer: logo row + red contact bar (never covered by the wipe)
    fr.alpha_composite(LOGO_S, (86, H - BAR.height - 40 - LOGO_S.height))
    fr = fr.convert("RGB")
    fr.paste(BAR, (0, H - BAR.height))
    return fr


def main():
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else HERE
    if "--still" in sys.argv:
        os.makedirs(f"{out}/stills", exist_ok=True)
        for s in sys.argv[sys.argv.index("--still") + 1:]:
            frame_at(float(s)).save(f"{out}/stills/t{float(s):05.2f}.png")
        return
    n = int(TOTAL * FPS)
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
                          f"{out}/video_only.mp4"], stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(frame_at(f / FPS).tobytes())
        if f % 150 == 0:
            print(f"frame {f}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    print("wrote", f"{out}/video_only.mp4")


if __name__ == "__main__":
    main()
