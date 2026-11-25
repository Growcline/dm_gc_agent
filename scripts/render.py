#!/usr/bin/env python3
"""Render social creatives (posts + carousels) from a JSON spec to PNG.

Usage: python3 render.py spec.json OUT_DIR

Uses only the stdlib + wkhtmltoimage (+ ffmpeg to pre-shrink photos over 2000 px). Layout CSS avoids flexbox/grid because
wkhtmltoimage ships an old WebKit; everything is absolutely positioned.
Relative paths in the spec (logo, font_dir) resolve against the spec's folder.
"""
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile

SIZES = {
    "square": (1080, 1080),
    "portrait": (1080, 1350),
    "story": (1080, 1920),
    "landscape": (1200, 628),
}

THEMES = {
    "dark": {"bg1": "#0b0b14", "bg2": "#1c1733", "fg": "#ffffff", "muted": "#b7b3cc",
             "card": "rgba(255,255,255,0.06)", "line": "rgba(255,255,255,0.14)", "glow": .22},
    "navy": {"bg1": "#071a33", "bg2": "#0b2547", "fg": "#ffffff", "muted": "#b9c4d6",
             "card": "rgba(255,255,255,0.07)", "line": "rgba(255,255,255,0.16)", "glow": .20},
    "light": {"bg1": "#ffffff", "bg2": "#fff1ef", "fg": "#0b1f3a", "muted": "#4b5567",
              "card": "#ffffff", "line": "rgba(11,31,58,0.12)", "glow": .12},
}


def esc(text, accent):
    """Escape HTML and turn *word* into an accent-coloured span, \\n into <br>."""
    out = html.escape(str(text or ""))
    out = re.sub(r"\*(.+?)\*", rf'<span style="color:{accent}">\1</span>', out)
    return out.replace("\n", "<br>")


def rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def fit(text, base, w, shrink_after):
    """Shrink a font size as text gets longer so headlines don't overflow."""
    n = len(re.sub(r"\*", "", str(text or "")))
    size = base if n <= shrink_after else base * (shrink_after / n) ** 0.6
    return int(max(size, base * 0.45) * (w / 1080))


def font_faces(family, font_dir):
    """@font-face rules for files named <anything>-<weight>.(woff|ttf|otf) in font_dir."""
    rules = []
    for path in sorted(glob.glob(os.path.join(font_dir, "*"))):
        m = re.search(r"-(\d{3})\.(woff|ttf|otf)$", path)
        if m:
            fmt = {"woff": "woff", "ttf": "truetype", "otf": "opentype"}[m.group(2)]
            rules.append(f"@font-face{{font-family:'{family}';font-weight:{m.group(1)};"
                         f"src:url('file://{path}') format('{fmt}')}}")
    return "\n".join(rules)


class Style:
    def __init__(self, brand, base_dir, theme=None, colors=None):
        self.brand = brand
        self.t = dict(THEMES.get(theme or brand.get("theme", "dark"), THEMES["dark"]))
        self.t.update(brand.get("colors", {}))
        self.t.update(colors or {})  # per-post/slide background overrides (the footer bar is untouched)
        self.accent = brand.get("accent", "#7c3aed")
        self.accent2 = brand.get("accent2", self.accent)
        self.family = brand.get("font", "")
        self.faces = ""
        if brand.get("font_dir"):
            self.faces = font_faces(self.family, os.path.abspath(os.path.join(base_dir, brand["font_dir"])))
        self.base_dir = base_dir
        self.bar_h = 0  # set per page size in page()
        logo = brand.get("logo")
        self.logo = os.path.abspath(os.path.join(base_dir, logo)) if logo else None


def layout_offsets(s, w, h):
    """Bottom offsets shared by footer, CTA and photo cards (bigger when a footer bar is present)."""
    s.bar_h = int(w * 0.047) if s.brand.get("footer_bar") else 0
    s.foot_bottom = s.bar_h + int(w * 0.022) if s.bar_h else int(h * 0.05)


def page(w, h, s, inner):
    t, accent = s.t, s.accent
    fam = f"'{s.family}'," if s.family else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{s.faces}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{w}px;height:{h}px;overflow:hidden}}
body{{font-family:{fam}'Ubuntu Sans','Ubuntu','DejaVu Sans',sans-serif;color:{t['fg']};
  background:{t['bg1']};background:linear-gradient(150deg,{t['bg1']} 0%,{t['bg2']} 100%);position:relative}}
.glow{{position:absolute;width:{int(w*0.9)}px;height:{int(w*0.9)}px;border-radius:50%;
  right:-{int(w*0.35)}px;top:-{int(w*0.35)}px;background:{accent};opacity:{t['glow']}}}
.glow2{{position:absolute;width:{int(w*0.6)}px;height:{int(w*0.6)}px;border-radius:50%;
  left:-{int(w*0.3)}px;bottom:-{int(w*0.3)}px;background:{accent};opacity:{t['glow'] / 2}}}
.pad{{position:absolute;left:{int(w*0.08)}px;right:{int(w*0.08)}px}}
.eyebrow{{display:inline-block;font-size:{int(w*0.026)}px;letter-spacing:3px;text-transform:uppercase;
  font-weight:800;color:{accent};border:2px solid {accent};border-radius:999px;padding:{int(w*0.01)}px {int(w*0.024)}px}}
.muted{{color:{t['muted']}}}
.cta{{display:inline-block;background:{accent};background:linear-gradient(90deg,{accent},{s.accent2});color:#fff;
  font-weight:800;border-radius:999px;font-size:{int(w*0.034)}px;padding:{int(w*0.02)}px {int(w*0.045)}px}}
.chip{{display:inline-block;font-size:{int(w*0.026)}px;font-weight:700;border:2px solid {t['line']};background:{t['card']};
  border-radius:999px;padding:{int(w*0.009)}px {int(w*0.022)}px;margin:0 {int(w*0.012)}px {int(w*0.012)}px 0}}
.foot{{position:absolute;left:{int(w*0.08)}px;right:{int(w*0.08)}px;bottom:{s.foot_bottom}px;
  font-size:{int(w*0.026)}px;color:{t['muted']};border-top:2px solid {t['line']};padding-top:{int(w*0.025)}px;
  height:{int(w*0.085)}px;line-height:{int(w*0.042)}px}}
.foot b{{color:{t['fg']}}}
.foot img{{height:{int(w*0.042*float(s.brand.get('logo_scale', 1)))}px;vertical-align:middle}}
.foot .right{{position:absolute;right:0;top:{int(w*0.025)}px;font-weight:700}}
.badge{{position:absolute;right:{int(w*0.08)}px;width:{int(w*0.2)}px;height:{int(w*0.2)}px;border-radius:50%;
  background:{accent};background:linear-gradient(135deg,{accent},{s.accent2});color:#fff;text-align:center;
  font-weight:900;font-size:{int(w*0.034)}px;line-height:1.1;padding-top:{int(w*0.062)}px;
  -webkit-transform:rotate(-8deg)}}
.term{{background:#0d1117;border-radius:{int(w*0.02)}px;border:2px solid rgba(255,255,255,.12);
  font-family:'Ubuntu Mono','DejaVu Sans Mono',monospace;color:#e6edf3;overflow:hidden}}
.term .bar{{background:#161b22;padding:{int(w*0.016)}px {int(w*0.022)}px}}
.dot{{display:inline-block;width:{int(w*0.016)}px;height:{int(w*0.016)}px;border-radius:50%;margin-right:{int(w*0.008)}px}}
.term .body{{padding:{int(w*0.03)}px;font-size:{int(w*0.03)}px;line-height:1.55}}
.item{{background:{t['card']};border:2px solid {t['line']};border-radius:{int(w*0.02)}px;
  padding:{int(w*0.022)}px {int(w*0.03)}px;margin-bottom:{int(w*0.018)}px;font-size:{int(w*0.034)}px;line-height:1.3;font-weight:600}}
.num{{color:{accent};font-weight:900;margin-right:{int(w*0.015)}px}}
.stats td{{padding-right:{int(w*0.06)}px;vertical-align:top}}
.stats .v{{font-size:{int(w*0.085)}px;font-weight:900;color:{accent};line-height:1}}
.stats .l{{font-size:{int(w*0.026)}px;color:{t['muted']};font-weight:700;margin-top:{int(w*0.008)}px}}
</style></head><body><div class="glow"></div><div class="glow2"></div>{inner}{footer_bar(s, w, h) if s.bar_h else ""}</body></html>"""


BAR_ICONS = {
    "web": '<circle cx="12" cy="12" r="6.5" fill="none" stroke="{c}" stroke-width="1.4"/>'
           '<ellipse cx="12" cy="12" rx="2.8" ry="6.5" fill="none" stroke="{c}" stroke-width="1.2"/>'
           '<path d="M5.5 12h13M6.6 8.8h10.8M6.6 15.2h10.8" stroke="{c}" stroke-width="1.1"/>',
    "instagram": '<rect x="6.3" y="6.3" width="11.4" height="11.4" rx="3.4" fill="none" stroke="{c}" stroke-width="1.5"/>'
                 '<circle cx="12" cy="12" r="2.7" fill="none" stroke="{c}" stroke-width="1.5"/>'
                 '<circle cx="15.2" cy="8.8" r=".9" fill="{c}"/>',
    "linkedin": '<rect x="6.5" y="6.5" width="11" height="11" rx="1.6" fill="none" stroke="{c}" stroke-width="1.4"/>'
                '<path d="M9.3 11v4.3M12.1 15.3V11m0 1.7c0-1 .8-1.7 1.6-1.7s1.5.6 1.5 1.7v2.6" stroke="{c}" stroke-width="1.4" fill="none"/>'
                '<circle cx="9.3" cy="9.2" r=".85" fill="{c}"/>',
    "facebook": '<path d="M12.9 18v-5.2h1.8l.3-2.1h-2.1V9.4c0-.6.2-1 1-1h1.1V6.6c-.2 0-.9-.1-1.6-.1-1.6 0-2.7 1-2.7 2.8v1.4H8.9v2.1h1.8V18z" fill="{c}"/>',
    "phone": '<path d="M8.6 6.5l1.7-.3 1.2 2.9-1.3 1c.6 1.4 1.6 2.4 3 3l1-1.3 2.9 1.2-.3 1.7c-.1.6-.6 1-1.2 1C10.4 15.5 8.5 13.6 8.4 8.4c0-.6.5-1.1 1.1-1.2z" fill="{c}"/>',
    "email": '<rect x="6" y="7.8" width="12" height="8.4" rx="1.2" fill="none" stroke="{c}" stroke-width="1.4"/>'
             '<path d="M6.5 8.5l5.5 4.2 5.5-4.2" fill="none" stroke="{c}" stroke-width="1.4"/>',
    "whatsapp": '<path d="M12 5.8a6.2 6.2 0 0 0-5.3 9.4L6 18l2.9-.7A6.2 6.2 0 1 0 12 5.8z" fill="none" stroke="{c}" stroke-width="1.4"/>'
                '<path d="M9.9 9.3c.2-.4.4-.4.6-.4h.4l.7 1.5-.5.7c.4.8 1 1.4 1.8 1.8l.7-.5 1.5.7v.4c0 .3-.3.8-.9.9-1.7.2-4.6-2.4-4.5-4.4 0-.3.1-.5.2-.7z" fill="{c}"/>',
    "youtube": '<rect x="5.8" y="8" width="12.4" height="8.4" rx="2.4" fill="none" stroke="{c}" stroke-width="1.4"/>'
               '<path d="M10.8 10.3v3.8l3.2-1.9z" fill="{c}"/>',
    "x": '<path d="M7 6.8h2.9l2.4 3.4 2.9-3.4h1.3l-3.6 4.2 4.1 6.2h-2.9l-2.6-3.8-3.3 3.8H6.9l4-4.6z" fill="{c}"/>',
    "location": '<path d="M12 5.6a4.4 4.4 0 0 0-4.4 4.4c0 3.3 4.4 8.2 4.4 8.2s4.4-4.9 4.4-8.2A4.4 4.4 0 0 0 12 5.6z" fill="{c}"/>'
                '<circle cx="12" cy="10" r="1.6" fill="#fff"/>',
}


def footer_bar(s, w, h):
    bar = s.brand["footer_bar"]
    color, bh = bar.get("color", s.accent), s.bar_h
    icon = int(bh * 0.6)
    cells = "".join(
        f'<td style="text-align:center;white-space:nowrap">'
        f'<span style="display:inline-block;width:{icon}px;height:{icon}px;border-radius:50%;background:#fff;'
        f'vertical-align:middle;margin-right:{int(w*0.01)}px"><svg width="{icon}" height="{icon}" viewBox="0 0 24 24">'
        f'{BAR_ICONS.get(it.get("icon"), "").replace("{c}", color)}</svg></span>'
        f'<span style="vertical-align:middle">{html.escape(it["text"])}</span></td>'
        for it in bar["items"])
    return (f'<div style="position:absolute;left:0;bottom:0;width:{w}px;height:{bh}px;background:{color}">'
            f'<table style="position:absolute;left:{int(w*0.02)}px;width:{w - int(w*0.04)}px;height:{bh}px;border-collapse:collapse;color:#fff;font-weight:600;'
            f'font-size:{int(bh*0.4)}px;letter-spacing:.5px"><tr>{cells}</tr></table></div>')


def footer(s, right=""):
    b = s.brand
    left = (f'<img src="file://{s.logo}">' if s.logo
            else f'<b>{html.escape(b.get("name", ""))}</b>')
    if b.get("handle") and not s.bar_h:
        left += f'&nbsp;&nbsp;<span style="vertical-align:middle;position:relative;top:2px">{html.escape(b["handle"])}</span>'
    right = right or ("" if s.bar_h else b.get("contact", ""))
    return f'<div class="foot">{left}<span class="right">{html.escape(right)}</span></div>'


def terminal(lines, accent):
    rows = []
    for ln in lines:
        e = html.escape(ln)
        if ln.startswith(("> ", "$ ")):
            e = f'<span style="color:{accent}">{html.escape(ln[0])}</span>{html.escape(ln[1:])}'
        elif ln.startswith(("✓", "✔")):
            e = f'<span style="color:#3fb950">{e}</span>'
        rows.append(e)
    return (f'<div class="term"><div class="bar"><span class="dot" style="background:#ff5f56"></span>'
            f'<span class="dot" style="background:#ffbd2e"></span><span class="dot" style="background:#27c93f"></span>'
            f'</div><div class="body" style="white-space:pre">{"<br>".join(rows)}</div></div>')


PHOTO_MAX = 2000  # longest side; wkhtmltoimage downscales big photos badly (blotchy skin, banding)


def fit_photo(path):
    """Return a Lanczos-downscaled cached copy of path if its longest side exceeds PHOTO_MAX (needs ffprobe/ffmpeg)."""
    try:
        dims = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                        "stream=width,height", "-of", "csv=p=0", path], text=True).strip().split(",")
        pw, ph = int(dims[0]), int(dims[1])
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return path
    if max(pw, ph) <= PHOTO_MAX:
        return path
    cache = os.path.join(os.path.dirname(path), ".fit")
    out = os.path.join(cache, f"{os.path.splitext(os.path.basename(path))[0]}-{PHOTO_MAX}.jpg")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(path):
        os.makedirs(cache, exist_ok=True)
        scale = f"scale={PHOTO_MAX}:-2" if pw >= ph else f"scale=-2:{PHOTO_MAX}"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", path, "-vf", scale + ":flags=lanczos",
                        "-q:v", "2", out], check=True)
    return out


def photo(c, s, w, h):
    """Photo layer. photo_pos: "full" (edge-to-edge from photo_top down, faded into the background)
    or "card" (rounded card from photo_top down to just above the CTA/footer).
    photo_focus is a CSS background-position, e.g. "center 30%"."""
    src = "file://" + fit_photo(os.path.abspath(os.path.join(s.base_dir, c["photo"])))
    focus = c.get("photo_focus", "center center")
    img = (f"background-image:url('{src}');background-size:cover;-webkit-background-size:cover;"
           f"background-position:{focus};background-repeat:no-repeat")
    if c.get("photo_pos", "card") == "full":
        bg, top = s.t["bg1"], int(h * c.get("photo_top", 0.4))
        fade = (f"linear-gradient(180deg,{bg} 0%,{rgba(bg, 0)} 28%,{rgba(bg, 0)} 62%,"
                f"{rgba(bg, .92)} 88%,{bg} 100%)")
        return (f'<div style="position:absolute;left:0;top:{top}px;width:{w}px;height:{h - top}px;{img}"></div>'
                f'<div style="position:absolute;left:0;top:{top}px;width:{w}px;height:{h - top}px;background:{fade}"></div>')
    top = int(h * c.get("photo_top", 0.5))
    bottom = int(s.foot_bottom + w * (0.31 if c.get("cta") else 0.12))
    label = ""
    if c.get("photo_label"):
        label = (f'<span class="chip" style="position:absolute;left:{int(w*0.025)}px;bottom:{int(w*0.012)}px;'
                 f'background:{rgba("#071a33", .78)};color:#fff;border-color:rgba(255,255,255,.25)">'
                 f'{html.escape(c["photo_label"])}</span>')
    return (f'<div style="position:absolute;left:{int(w*0.08)}px;right:{int(w*0.08)}px;top:{top}px;'
            f'height:{h - top - bottom}px;border-radius:{int(w*0.03)}px;overflow:hidden;{img}">{label}</div>')


def render_photo_post(c, s, w, h):
    """layout "photo": a product photo edge to edge, the logo as a corner watermark, optional faint tiled
    handle watermark (wm_tile), optional tag chip (tag) and bottom headline; the footer bar stays."""
    accent, bar = s.accent, s.bar_h
    src = "file://" + fit_photo(os.path.abspath(os.path.join(s.base_dir, c["photo"])))
    img = (f"background-image:url('{src}');background-size:cover;-webkit-background-size:cover;"
           f"background-position:{c.get('photo_focus', 'center center')};background-repeat:no-repeat")
    ph = h - bar
    parts = [f'<div style="position:absolute;left:0;top:0;width:{w}px;height:{ph}px;{img}"></div>']
    if c.get("wm_tile", False):
        text = html.escape(c.get("wm_text") or s.brand.get("handle", s.brand.get("name", "")))
        row = ("&nbsp;" * 6).join([text] * 6)
        rows = "".join(f'<div style="white-space:nowrap;margin-left:{-(i % 2) * int(w*0.25)}px">{row}</div>' for i in range(14))
        parts.append(f'<div style="position:absolute;left:0;top:0;width:{w}px;height:{ph}px;overflow:hidden">'
                     f'<div style="position:absolute;left:-{w}px;top:-{int(h*0.3)}px;width:{w*3}px;'
                     f'-webkit-transform:rotate(-24deg);transform:rotate(-24deg);font-size:{int(w*0.028)}px;'
                     f'font-weight:700;line-height:{int(w*0.16)}px;color:#fff;opacity:{c.get("wm_opacity", 0.16)}">{rows}</div></div>')
    head = c.get("headline")
    if head:  # legibility gradient + headline over the photo bottom
        parts.append(f'<div style="position:absolute;left:0;top:{int(ph*0.55)}px;width:{w}px;height:{ph - int(ph*0.55)}px;'
                     f'background:linear-gradient(180deg,rgba(0,0,0,0) 0%,rgba(0,0,0,.55) 100%)"></div>')
        hsize = fit(head, c.get("headline_size", 76), w, 28)
        sub = (f'<div style="font-size:{int(w*0.032)}px;font-weight:600;margin-top:{int(w*0.012)}px;opacity:.95">'
               f'{esc(c["body"], "#fff")}</div>' if c.get("body") else "")
        parts.append(f'<div style="position:absolute;left:{int(w*0.06)}px;right:{int(w*0.36)}px;bottom:{bar + int(w*0.05)}px;'
                     f'color:#fff;font-size:{hsize}px;font-weight:900;line-height:1.08">{esc(head, "#fff")}{sub}</div>')
    if c.get("tag"):
        parts.append(f'<div style="position:absolute;left:{int(w*0.05)}px;top:{int(w*0.05)}px;background:{accent};color:#fff;'
                     f'font-weight:700;font-size:{int(w*0.032)}px;border-radius:999px;padding:{int(w*0.012)}px {int(w*0.03)}px">'
                     f'{esc(c["tag"], "#fff")}</div>')
    handle = c.get("wm_handle", s.brand.get("handle", ""))
    shadow = "text-shadow:0 2px 6px rgba(0,0,0,.55),0 0 2px rgba(0,0,0,.4)"
    if c.get("wm_pos", "corner") == "center":  # big faded logo in the middle + white handle under it
        lh = int(w * c.get("wm_logo_size", 0.42))
        parts.append(f'<div style="position:absolute;left:0;width:{w}px;top:{int(ph/2 - lh*0.62)}px;text-align:center;'
                     f'opacity:{c.get("wm_logo_opacity", 0.35)}"><img src="file://{s.logo}" style="height:{lh}px"></div>'
                     if s.logo else "")
        if handle:
            parts.append(f'<div style="position:absolute;left:0;width:{w}px;top:{int(ph/2 + lh*0.45)}px;text-align:center;'
                         f'color:#fff;font-weight:700;font-size:{int(w*0.042)}px;opacity:{c.get("wm_handle_opacity", 0.9)};{shadow}">'
                         f'{html.escape(handle)}</div>')
    elif c.get("wm_pos") == "left":  # left edge, logo centred at wm_y (default 70%) of the photo height, handle under it
        lh = int(w * c.get("wm_logo_size", 0.2))
        hs = int(w * 0.03)
        cy = int(ph * c.get("wm_y", 0.7))
        top = cy - lh // 2
        if s.logo:
            parts.append(f'<div style="position:absolute;left:{int(w*0.04)}px;top:{top}px;opacity:{c.get("wm_logo_opacity", 0.92)}">'
                         f'<img src="file://{s.logo}" style="height:{lh}px;display:block"></div>')
        if handle:
            parts.append(f'<div style="position:absolute;left:{int(w*0.04)}px;top:{top + lh + int(hs*0.3)}px;color:#fff;'
                         f'font-weight:700;font-size:{hs}px;{shadow}">{html.escape(handle)}</div>')
    else:  # corner (bottom-right): logo (no backing by default) with the white handle under it
        lh = int(w * c.get("wm_logo_size", 0.17))
        bg = c.get("wm_logo_bg", 0)
        disc = (f"border-radius:50%;background:rgba(255,255,255,{bg});" if bg else "")
        hs = int(w * 0.03)
        right, bottom = int(w * 0.04), bar + int(w * 0.035)
        if handle:
            parts.append(f'<div style="position:absolute;right:{right}px;bottom:{bottom}px;color:#fff;font-weight:700;'
                         f'font-size:{hs}px;{shadow}">{html.escape(handle)}</div>')
            bottom += int(hs * 1.5)
        if s.logo:
            parts.append(f'<div style="position:absolute;right:{right}px;bottom:{bottom}px;{disc}'
                         f'opacity:{c.get("wm_logo_opacity", 0.92)}"><img src="file://{s.logo}" style="height:{lh}px;'
                         f'display:block{";padding:" + str(int(lh*0.1)) + "px" if bg else ""}"></div>')
    return page(w, h, s, "".join(parts))


def render_post(c, s, w, h, right=""):
    """Layouts: hero, terminal, stat, stats, list, versus, cta, photo (product photo + watermark)."""
    accent = s.accent
    layout_offsets(s, w, h)
    layout = c.get("layout", "hero")
    if layout == "photo":
        return render_photo_post(c, s, w, h)
    top = int(h * (0.16 if h / w > 1.5 else 0.08))
    parts = []
    logo_top = s.logo and s.brand.get("logo_top") == "center"
    if logo_top:  # brand kit "logo_top": "center" puts the logo top-centre and drops it from the footer row
        lh = int(w * (0.15 if h / w > 1.5 else 0.1) * float(s.brand.get("logo_scale", 1)) / 1.75)
        parts.append(f'<div style="position:absolute;left:0;right:0;top:{int(w*0.035)}px;text-align:center">'
                     f'<img src="file://{s.logo}" style="height:{lh}px"></div>')
        top = max(top, int(w * 0.035) + lh + int(w * 0.04))
    if c.get("photo"):
        parts.append(photo(c, s, w, h))
    if c.get("watermark"):
        parts.append(f'<div style="position:absolute;right:{int(w*0.05)}px;bottom:{int(h*0.1)}px;font-size:{int(w*0.55)}px;'
                     f'font-weight:900;line-height:1;color:{accent};opacity:.12">{html.escape(c["watermark"])}</div>')
    if c.get("badge"):
        parts.append(f'<div class="badge" style="top:{top - int(w*0.01)}px">{esc(c["badge"], "#fff")}</div>')
    if c.get("eyebrow"):
        parts.append(f'<div class="pad" style="top:{top}px"><span class="eyebrow">{esc(c["eyebrow"], accent)}</span></div>')
        top += int(w * 0.11)
    headline = c.get("headline", "")
    hsize = fit(headline, c.get("headline_size", 92 if layout != "list" else 72), w, 28)
    body = c.get("body", "")
    bsize = int(w * 0.036)

    if layout == "stat":
        parts.append(f'<div class="pad" style="top:{top}px;font-size:{int(w*0.22)}px;font-weight:900;'
                     f'line-height:1;color:{accent}">{esc(c.get("stat", ""), accent)}</div>')
        top += int(w * 0.26)

    extra = ""
    if c.get("chips"):
        extra += f'<div style="margin-top:{int(w*0.035)}px">' + "".join(
            f'<span class="chip">{esc(x, accent)}</span>' for x in c["chips"]) + "</div>"
    if layout == "terminal":
        lines = c.get("terminal") or [f"> {c.get('command', '/skill')}"]
        extra += f'<div style="margin-top:{int(w*0.07)}px">{terminal(lines, accent)}</div>'
    elif layout == "list":
        check = c.get("marker") == "check"
        extra += f'<div style="margin-top:{int(w*0.05)}px">' + "".join(
            f'<div class="item"><span class="num">{"✓" if check else f"{i:02d}"}</span>{esc(x, accent)}</div>'
            for i, x in enumerate(c.get("items", []), 1)) + "</div>"
    elif layout == "versus":  # e.g. MYTH vs REALITY: cards of {"label", "text", "note"?, "tone": "bad"|"good", "color"?}
        for v in c.get("versus", []):
            good = v.get("tone") == "good"
            col = v.get("color") or ("#22a06b" if good else accent)
            mark = "✓" if good else "✕"
            note = (f'<div style="font-size:{int(w*0.03)}px;font-weight:800;margin-top:{int(w*0.014)}px">'
                    f'{esc(v["note"], accent)}</div>' if v.get("note") else "")
            extra += (f'<div style="margin-top:{int(w*0.03)}px;background:{s.t["card"]};border:2px solid {s.t["line"]};'
                      f'border-left:{int(w*0.012)}px solid {col};border-radius:{int(w*0.025)}px;'
                      f'padding:{int(w*0.026)}px {int(w*0.04)}px">'
                      f'<div style="font-size:{int(w*0.03)}px;font-weight:900;letter-spacing:3px;color:{col}">'
                      f'{mark}&nbsp; {esc(v.get("label", ""), accent)}</div>'
                      f'<div style="font-size:{int(w*0.035)}px;font-weight:700;line-height:1.32;margin-top:{int(w*0.01)}px'
                      f'{";opacity:.85" if not good else ""}">{esc(v.get("text", ""), accent)}</div>{note}</div>')
    elif layout == "stats":
        cells = "".join(f'<td><div class="v">{esc(v, accent)}</div><div class="l">{esc(l, accent)}</div></td>'
                        for v, l in c.get("stats", []))
        extra += f'<table class="stats" style="margin-top:{int(w*0.07)}px"><tr>{cells}</tr></table>'

    parts.append(f'<div class="pad" style="top:{top}px"><div style="font-size:{hsize}px;font-weight:900;'
                 f'line-height:1.08;letter-spacing:-1px;padding-right:{int(w*0.2) if c.get("badge") else 0}px">'
                 f'{esc(headline, accent)}</div>'
                 + (f'<div class="muted" style="font-size:{bsize}px;line-height:1.4;margin-top:{int(w*0.03)}px">'
                    f'{esc(body, accent)}</div>' if body else "") + extra + "</div>")

    if c.get("cta"):
        sub = (f'<div class="muted" style="font-size:{int(w*0.026)}px;margin-top:{int(w*0.016)}px;font-weight:700">'
               f'{esc(c["cta_note"], accent)}</div>' if c.get("cta_note") else "")
        parts.append(f'<div class="pad" style="bottom:{int(s.foot_bottom + w*0.14)}px">'
                     f'<span class="cta">{esc(c["cta"], accent)}</span>{sub}</div>')
    if not (logo_top and s.bar_h):
        parts.append(footer(s, right))
    return page(w, h, s, "".join(parts))


def to_png(doc, w, h, out):
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(doc)
        src = f.name
    try:
        subprocess.run(["wkhtmltoimage", "--quiet", "--width", str(w), "--height", str(h),
                        "--disable-smart-width", "--enable-local-file-access", src, out],
                       check=True, stderr=subprocess.DEVNULL)
    finally:
        os.unlink(src)


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: render.py spec.json OUT_DIR")
    spec_path = os.path.abspath(sys.argv[1])
    spec = json.load(open(spec_path, encoding="utf-8"))
    out_dir = sys.argv[2]
    os.makedirs(os.path.join(out_dir, "html"), exist_ok=True)
    brand, base = spec.get("brand", {}), os.path.dirname(spec_path)
    if brand.get("kit"):
        kit_path = os.path.abspath(os.path.join(base, brand["kit"]))
        kit = json.load(open(kit_path, encoding="utf-8"))
        for key in ("logo", "font_dir"):
            if key in kit:
                kit[key] = os.path.join(os.path.dirname(kit_path), kit[key])
        brand = {**kit, **{k: v for k, v in brand.items() if k != "kit"}}
    if brand.get("enforce_footer") and not (brand.get("footer_bar") or {}).get("items"):
        sys.exit("error: this brand requires its footer_bar (enforce_footer is set in the brand kit)")
    styles = {}

    def style(theme, colors=None):
        key = (theme, json.dumps(colors or {}, sort_keys=True))
        if key not in styles:
            styles[key] = Style(brand, base, theme, colors)
        return styles[key]
    made = []

    def emit(doc, w, h, name):
        png = os.path.join(out_dir, name + ".png")
        to_png(doc, w, h, png)
        with open(os.path.join(out_dir, "html", name + ".html"), "w", encoding="utf-8") as f:
            f.write(doc)
        made.append(png)

    for p in spec.get("posts", []):
        w, h = SIZES[p.get("size", "square")]
        emit(render_post(p, style(p.get("theme"), p.get("colors")), w, h), w, h, p["id"])

    for car in spec.get("carousels", []):
        w, h = SIZES[car.get("size", "portrait")]
        slides = car["slides"]
        for i, sl in enumerate(slides, 1):
            right = f"{i}/{len(slides)}" + ("  swipe →" if i < len(slides) else "")
            emit(render_post(sl, style(sl.get("theme", car.get("theme")), sl.get("colors", car.get("colors"))), w, h, right), w, h, f"{car['id']}-{i:02d}")

    print("\n".join(made))


if __name__ == "__main__":
    main()
