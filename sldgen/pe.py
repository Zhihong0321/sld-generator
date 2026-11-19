"""PE drawing: A3 "MODULE LAYOUT PLAN (RETROFITTED)" sheet for the mounting structure.

One sheet per job. Left half: the PV module layout (roof outlines, modules, rails, hooks).
Right half: hook detail, section A-A, section B-B and the legend, which depend only on the
roof type ("tile" or "metal_deck"). Right column: notes and the Eternalgy title block.

Nothing here ever refuses to draw. Anything wrong with the input is collected in
`problems`, printed in red on the sheet and returned to the caller; the sheet is still made.

Layout units: 1 unit = the module's short side. A portrait module is 1 wide and
`aspect` tall, a landscape module is `aspect` wide and 1 tall. y grows downwards.
"""

import base64
import math
from pathlib import Path
from xml.sax.saxutils import escape

from .project import ROOT, load_library
from .render import CHAR_W, FONT, RED, f, wrap

W, H = 420, 297
DEFAULT_ASPECT = 2.1          # module long side / short side when the library has no size
LOGO = ROOT / "app" / "assets" / "eternalgy-logo-white.png"

ROOF = {
    "tile": {"hook": "TILE HOOK", "roof": "ROOF TILES", "detail": "4MM THK. STAINLESS STEEL TILE HOOK"},
    "metal_deck": {"hook": "KLIP-LOK HOOK", "roof": "METAL DECK", "detail": "KLIP-LOK HOOK"},
}
ROOF_ALIASES = {"tile": "tile", "roof_tile": "tile", "tiles": "tile", "clay": "tile", "concrete_tile": "tile",
                "metal_deck": "metal_deck", "metal": "metal_deck", "metaldeck": "metal_deck", "deck": "metal_deck",
                "klip-lok": "metal_deck", "kliplok": "metal_deck", "metal deck": "metal_deck"}

CONFIRM = ["We hereby confirmed that the design of the solar mounting structure for the project is design in",
           "accordance with the following :",
           "1.) Malaysian Uniform Building By - Laws 1984, where relevant;",
           "2.) Wind velocity of 33 m/s, in compliance with 25 years cycle;",
           "3.) That the material shall be free from corrosion."]

CSS = f"""
.l{{stroke:#000;stroke-width:.25;fill:none;stroke-linejoin:round;stroke-linecap:round}}
.t{{stroke:#000;stroke-width:.15;fill:none;stroke-linejoin:round;stroke-linecap:round}}
.k{{stroke:#000;stroke-width:.5;fill:none}}
.w{{stroke:#000;stroke-width:.25;fill:#fff}}
.g{{stroke:#000;stroke-width:.2;fill:#d9d9d9}}
text{{font-family:{FONT};fill:#000}}
"""


def num(v, default=0.0):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


class Svg:
    def __init__(self):
        self.parts = []

    def add(self, s):
        self.parts.append(s)

    def line(self, x1, y1, x2, y2, cls="l"):
        self.add(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" class="{cls}"/>')

    def poly(self, pts, cls="l", closed=True):
        tag = "polygon" if closed else "polyline"
        self.add(f'<{tag} points="{" ".join(f"{x:.2f},{y:.2f}" for x, y in pts)}" class="{cls}"/>')

    def rect(self, x, y, w, h, cls="l"):
        self.add(f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" class="{cls}"/>')

    def circle(self, cx, cy, r, cls="l"):
        self.add(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" class="{cls}"/>')

    def path(self, d, cls="l"):
        self.add(f'<path d="{d}" class="{cls}"/>')

    def text(self, x, y, s, size=1.8, anchor="start", bold=False, fill=None, max_w=None, under=False, rotate=None):
        s = str(s)
        if max_w and len(s) * size * CHAR_W > max_w:
            size = max_w / (len(s) * CHAR_W)
        a = f'x="{x:.2f}" y="{y:.2f}" font-size="{size:.2f}"'
        if anchor != "start":
            a += f' text-anchor="{anchor}"'
        if bold:
            a += ' font-weight="bold"'
        if fill:
            a += f' fill="{fill}"'
        if under:
            a += ' text-decoration="underline"'
        if rotate is not None:
            a += f' transform="rotate({rotate:.2f} {x:.2f} {y:.2f})"'
        self.add(f"<text {a}>{escape(s)}</text>")

    def svg(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{W}mm" height="{H}mm" viewBox="0 0 {W} {H}">\n<defs><style>{CSS}</style></defs>\n'
                f'<rect width="{W}" height="{H}" fill="#fff"/>\n' + "\n".join(self.parts) + "\n</svg>\n")


# --- input ---------------------------------------------------------------------------

def prepare_pe(raw):
    """Normalise a PE project dict. Never raises: problems are returned for labelling."""
    problems = []
    raw = raw if isinstance(raw, dict) else {}
    pr = raw.get("project") if isinstance(raw.get("project"), dict) else {}

    rt_in = str(raw.get("roof_type") or "").strip().lower()
    roof_type = ROOF_ALIASES.get(rt_in)
    if not roof_type:
        roof_type = "tile"
        problems.append(f"roof_type '{rt_in or '(blank)'}' unknown: drawn as roof tile. Use 'tile' or 'metal_deck'.")

    module = {}
    spec = raw.get("pv_module")
    if isinstance(spec, str) and spec.strip():
        try:
            module = dict(load_library("pv_module").get(spec.strip().lower()) or {})
        except Exception as e:  # unreadable library: keep going
            problems.append(f"Module library could not be read: {e}")
        if not module:
            problems.append(f"pv_module '{spec}' not in library/modules.json: give brand and wattage_wp inline.")
    elif isinstance(spec, dict):
        ref = spec.get("ref")
        if ref:
            try:
                module = dict(load_library("pv_module").get(str(ref).lower()) or {})
            except Exception:
                module = {}
        module.update({k: v for k, v in spec.items() if k != "ref"})
    else:
        problems.append("pv_module is missing: module brand and wattage left blank.")

    length, width = num(module.get("length_mm")), num(module.get("width_mm"))
    aspect = length / width if length > 0 and width > 0 else DEFAULT_ASPECT
    if not 1.2 <= aspect <= 3.0:
        problems.append(f"Module size {length} x {width} mm looks wrong: drawn at {DEFAULT_ASPECT}:1.")
        aspect = DEFAULT_ASPECT

    return {"project": pr, "roof_type": roof_type, "module": module, "aspect": aspect,
            "module_label": str(raw.get("module_label") or module.get("brand") or "").upper(),
            "expected_modules": raw.get("expected_modules"),
            "layout": raw.get("layout") if isinstance(raw.get("layout"), dict) else {},
            "problems": problems}


# --- layout geometry -------------------------------------------------------------------

def build_layout(pe):
    """Return outlines, modules and rails in layout units."""
    lay, aspect, problems = pe["layout"], pe["aspect"], pe["problems"]
    outlines, modules, rails = [], [], []

    for i, o in enumerate(lay.get("outlines") or [], 1):
        try:
            if isinstance(o, dict) and o.get("rect") is not None:
                x, y, w, h = (num(v) for v in o["rect"])
                outlines.append([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])
            elif isinstance(o, dict) and o.get("points"):
                pts = [(num(p[0]), num(p[1])) for p in o["points"]]
                if len(pts) >= 2:
                    outlines.append(pts)
                else:
                    problems.append(f"outline {i} has fewer than 2 points: skipped.")
            else:
                problems.append(f"outline {i} needs 'rect' [x, y, w, h] or 'points': skipped.")
        except Exception as e:
            problems.append(f"outline {i} could not be read ({e}): skipped.")

    entries = [("array", i, a) for i, a in enumerate(lay.get("arrays") or [], 1)]
    # single modules, e.g. traced from a PV drawing: {"rect": [x, y, w, h]} (orientation from
    # the shape, drawn at standard size around the same centre) or {"at": [x, y], "orientation"}
    for i, m in enumerate(lay.get("modules") or [], 1):
        if isinstance(m, dict) and m.get("rect") is not None:
            try:
                x, y, w, h = (num(v) for v in m["rect"])
                orient = "portrait" if h >= w else "landscape"
                mw, mh = (1.0, aspect) if orient == "portrait" else (aspect, 1.0)
                m = {"at": [x + w / 2 - mw / 2, y + h / 2 - mh / 2], "orientation": orient, "hook_side": m.get("hook_side")}
            except Exception as e:
                problems.append(f"module {i} could not be read ({e}): skipped.")
                continue
        entries.append(("module", i, m))

    for kind, i, a in entries:
        try:
            if not isinstance(a, dict):
                raise ValueError("not an object")
            at = a.get("at") or [0, 0]
            x0, y0 = num(at[0]), num(at[1])
            rows, cols = max(0, int(num(a.get("rows"), 1))), max(0, int(num(a.get("cols"), 1)))
            orient = str(a.get("orientation") or "portrait").lower()
            if orient not in ("portrait", "landscape"):
                problems.append(f"{kind} {i}: orientation '{orient}' unknown, drawn portrait.")
                orient = "portrait"
            gap = num(a.get("gap"), 0.03)
            skip = {(int(num(s[0])), int(num(s[1]))) for s in (a.get("skip") or []) if isinstance(s, (list, tuple)) and len(s) >= 2}
            hook_end = str(a.get("hook_side") or "start").lower() == "end"
            mw, mh = (1.0, aspect) if orient == "portrait" else (aspect, 1.0)
            for r in range(1, rows + 1):
                for c in range(1, cols + 1):
                    if (r, c) not in skip:
                        modules.append({"x": x0 + (c - 1) * (mw + gap), "y": y0 + (r - 1) * (mh + gap),
                                        "w": mw, "h": mh, "orient": orient, "hook_end": hook_end})
        except Exception as e:
            problems.append(f"{kind} {i} could not be read ({e}): skipped.")

    rails = make_rails(modules)
    if not modules:
        problems.append("Layout has no modules: give layout.arrays or layout.modules.")
    return outlines, modules, rails


def make_rails(modules, over=0.2, gap_max=0.2):
    """Rails cross each module's long side at 25 % and 75 %. Modules of the same orientation
    that sit in one line with small gaps share continuous rails; a wider gap breaks the run."""
    rails = []
    for orient in ("portrait", "landscape"):
        port = orient == "portrait"
        ms = [m for m in modules if m["orient"] == orient]
        # a "line" = same row (portrait) or same column (landscape)
        key = (lambda m: m["y"]) if port else (lambda m: m["x"])
        along = (lambda m: m["x"]) if port else (lambda m: m["y"])
        size = (lambda m: m["w"]) if port else (lambda m: m["h"])
        lines = []
        for m in sorted(ms, key=key):
            if lines and abs(key(m) - key(lines[-1][0])) < 0.3:
                lines[-1].append(m)
            else:
                lines.append([m])
        for line in lines:
            line.sort(key=along)
            run = [line[0]]
            for m in line[1:] + [None]:
                if m is not None and along(m) - (along(run[-1]) + size(run[-1])) <= gap_max:
                    run.append(m)
                    continue
                a = along(run[0]) - over
                b = along(run[-1]) + size(run[-1]) + over
                base = sum(key(x) for x in run) / len(run)
                span = run[0]["h"] if port else run[0]["w"]
                for fr in (0.25, 0.75):
                    c = base + fr * span
                    rails.append(((a, c), (b, c)) if port else ((c, a), (c, b)))
                run = [m] if m is not None else []
    return rails


def draw_layout(s, pe, box):
    outlines, modules, rails = build_layout(pe)
    rot = int(num(pe["layout"].get("rotate"), 0)) % 360
    if rot not in (0, 90, 180, 270):
        pe["problems"].append(f"layout.rotate {rot} must be 0, 90, 180 or 270: drawn without rotation.")
        rot = 0

    def R(p):
        x, y = p
        return {0: (x, y), 90: (-y, x), 180: (-x, -y), 270: (y, -x)}[rot]   # 90 = clockwise on screen

    pts = [R(p) for o in outlines for p in o] + [R(p) for m in modules for p in
                                                 ((m["x"], m["y"]), (m["x"] + m["w"], m["y"] + m["h"]))]
    pts += [R(p) for r in rails for p in r]
    bx, by, bw, bh = box
    if not pts:
        s.text(bx + bw / 2, by + bh / 2, "LAYOUT NOT GIVEN", 5, "middle", True, RED)
        return len(modules)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    w, h = max(max(xs) - min(xs), 1e-6), max(max(ys) - min(ys), 1e-6)
    k = min(bw * 0.84 / w, bh * 0.84 / h)
    ox = bx + bw / 2 - (min(xs) + max(xs)) / 2 * k
    oy = by + bh / 2 - (min(ys) + max(ys)) / 2 * k

    def T(p):
        x, y = R(p)
        return ox + x * k, oy + y * k

    for o in outlines:
        s.poly([T(p) for p in o], "l", closed=len(o) > 2)
    for m in modules:
        x, y, w_, h_ = m["x"], m["y"], m["w"], m["h"]
        s.poly([T(p) for p in ((x, y), (x + w_, y), (x + w_, y + h_), (x, y + h_))], "w")
    for a, b in rails:
        s.line(*T(a), *T(b), "t")
    # Chevron and hook are placed on the finished (rotated) sheet: the samples always put them
    # at the top of a portrait module and the left of a landscape one ("hook_side": "end" flips).
    r = max(0.6, min(2.2, 0.17 * k))
    for m in modules:
        cs = [T(p) for p in ((m["x"], m["y"]), (m["x"] + m["w"], m["y"] + m["h"]))]
        x0, x1 = sorted(c[0] for c in cs)
        y0, y1 = sorted(c[1] for c in cs)
        end = m["hook_end"]
        if y1 - y0 >= x1 - x0:
            ey, hy = (y1, y1 - 0.25 * (y1 - y0)) if end else (y0, y0 + 0.25 * (y1 - y0))
            hx = (x0 + x1) / 2
            s.poly([(x0, ey), (hx, hy), (x1, ey)], "t", closed=False)
        else:
            ex, hx = (x1, x1 - 0.25 * (x1 - x0)) if end else (x0, x0 + 0.25 * (x1 - x0))
            hy = (y0 + y1) / 2
            s.poly([(ex, y0), (hx, hy), (ex, y1)], "t", closed=False)
        s.circle(hx, hy, r, "t")
    return len(modules)


# --- fixed details ---------------------------------------------------------------------

def clip_circle(s, cid, cx, cy, r, body):
    s.add(f'<clipPath id="{cid}"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>')
    s.add(f'<g clip-path="url(#{cid})">')
    body()
    s.add("</g>")
    s.circle(cx, cy, r, "l")


def xbox(s, x, y, w, h, cls="t"):
    s.rect(x, y, w, h, cls)
    s.line(x, y, x + w, y + h, cls)
    s.line(x + w, y, x, y + h, cls)


def detail_tile_hook(s, x, y):
    s.poly([(x, y), (x + 3, y), (x + 3, y + 17), (x, y + 17)], "l")          # upright
    s.rect(x + 1, y + 3, 1, 7, "t")                                            # slot
    s.poly([(x + 3, y), (x + 6, y), (x + 6, y + 2)], "l", closed=False)        # top lip
    s.poly([(x + 3, y + 17), (x + 9, y + 17), (x + 11, y + 20)], "l", closed=False)
    s.poly([(x, y + 17), (x + 4, y + 20), (x + 30, y + 20), (x + 36, y + 24), (x + 10, y + 24), (x + 4, y + 20)], "l")
    for i in range(5):
        s.circle(x + 12 + i * 4.6, y + 22, 0.45, "t")
    s.line(x + 6, y + 1, x + 20, y + 1, "t")
    s.text(x + 21, y + 1.6, ROOF["tile"]["detail"], 1.7, bold=True)


def detail_kliplok(s, x, y):
    s.poly([(x, y + 6), (x + 18, y), (x + 22, y + 2), (x + 4, y + 8)], "l")             # rail clamp top
    s.poly([(x, y + 6), (x, y + 9), (x + 4, y + 11), (x + 4, y + 8)], "l")
    s.poly([(x + 22, y + 2), (x + 22, y + 5), (x + 4, y + 11)], "l", closed=False)
    s.poly([(x + 5, y + 10), (x + 14, y + 7), (x + 14, y + 19), (x + 5, y + 22)], "l")   # body plate
    s.circle(x + 9.5, y + 14.5, 1.6, "l")
    s.circle(x + 9.5, y + 14.5, 0.7, "t")
    s.poly([(x + 14, y + 12), (x + 17, y + 11), (x + 17, y + 14), (x + 14, y + 15)], "l")  # bolt head
    s.path(f"M{x + 6},{y + 22} c-2,1 -3,4 -1,6 M{x + 12},{y + 20} c2,1 3,4 1,6", "l")       # legs
    s.line(x + 19, y + 12, x + 26, y + 12, "t")
    s.text(x + 27, y + 12.6, ROOF["metal_deck"]["detail"], 1.7, bold=True)


def section_aa(s, rt, cx, cy, r):
    ang = -18 if rt == "tile" else -7

    def body():
        s.add(f'<g transform="translate({cx} {cy + (4 if rt == "tile" else 8)}) rotate({ang})">')
        s.rect(-14, -11, 60, 3, "w")                          # PV module
        s.rect(-48, -11, 31, 3, "w")
        s.poly([(-17, -12), (-14, -12), (-14, -8), (-17, -8)], "g")   # clamp
        s.rect(-48, -8, 96, 2.4, "w")                         # rail
        if rt == "tile":
            xbox(s, -10, -5.6, 2.2, 2.2)                       # tile hook
            s.line(-12, -3.4, 30, -3.4, "t")
            s.poly([(-10, -3.4), (-10, -1.2), (2, -1.2)], "t", closed=False)
            for bx in (-30, -12, 8, 28):
                xbox(s, bx, -1.2, 3, 3)                        # battens
            s.rect(-48, 1.8, 96, 6, "t")                       # top chord truss
            labels = [(-14, -14, "CLAMP"), (-6, -8.6, "PV MODULE"), (14, -5.6, "ALUMINIUM RAIL"),
                      (2, -2.2, "TILE HOOK"), (-26, 0.8, "BATTEN"), (-12, 6.5, "TOP CHORD TRUSS")]
        else:
            xbox(s, -10, -5.6, 2.2, 1.6)
            s.rect(-48, -4, 96, 1.6, "w")                      # metal deck
            s.line(-48, -0.6, 48, -0.6, "t")
            labels = [(-14, -14, "CLAMP"), (-6, -8.6, "PV MODULE"), (-6, -5.9, "ALUMINIUM RAIL"),
                      (-4, 1.6, "METAL DECK")]
        for lx, ly, t in labels:
            s.text(lx, ly, t, 1.35, bold=True)
        s.line(-14, -13.6, -15.5, -10, "t")
        s.add("</g>")

    clip_circle(s, "aa", cx, cy, r, body)
    # whole-rafter view with the enlarged spot circled
    x1, x2 = cx + r + 12, cx + r + 66
    if rt == "tile":
        y1, y2 = cy + 14, cy - 8
    else:
        y1, y2 = cy - 2, cy - 7
    s.line(x1, y1 + 1.2, x2, y2 + 1.2, "t")
    s.line(x1, y1, x2, y2, "l")
    s.line(x1 + 6, y1 - 2.4, x2 - 2, y2 - 2.4, "t")
    for i in range(1, 6):
        t = i / 6
        s.rect(x1 + (x2 - x1) * t - 0.6, y1 + (y2 - y1) * t - 2.0, 1.2, 0.9, "t")
    sx, sy = x1 + (x2 - x1) * 0.18, y1 + (y2 - y1) * 0.18 - 1
    s.circle(sx, sy, 4.2, "t")
    s.line(cx + r * math.cos(math.radians(-15)), cy + r * math.sin(math.radians(-15)), sx - 4, sy - 1, "t")
    s.line(sx + (x2 - x1) * 0.45, sy + (y2 - y1) * 0.45 - 1, sx + (x2 - x1) * 0.45 + 2, sy + 6, "t")
    s.text(sx + (x2 - x1) * 0.45 + 2, sy + 8, "SEE DETAIL 'A'", 1.3, bold=True)


def roof_profile(s, rt, cx, cy, r, y):
    if rt == "tile":
        x = cx - r
        d = f"M{x},{y}"
        while x < cx + r:
            d += f" q3,-3.2 6,0"
            x += 6
        s.path(d, "l")
        s.line(cx - r, y + 1.5, cx + r, y + 1.5, "t")
        s.text(cx, y + 5, "ROOF TILES", 1.4, "middle", True)
    else:
        x = cx - r
        d = f"M{x},{y}"
        while x < cx + r:
            d += " h4 l1.4,-3 h2.4 l1.4,3 h4"
            x += 13.2
        s.path(d, "l")
        s.line(cx - r, y + 1.2, cx + r, y + 1.2, "t")
        s.text(cx, y + 5, "METAL DECK", 1.4, "middle", True)


def section_bb(s, rt, cx1, cx2, cy, r):
    def mid():
        s.rect(cx1 - r, cy - 10, r - 2.2, 4, "w")
        s.rect(cx1 + 2.2, cy - 10, r, 4, "w")
        s.rect(cx1 - 2.6, cy - 11.2, 5.2, 1.2, "g")            # mid clamp cap
        s.rect(cx1 - 0.7, cy - 10, 1.4, 4, "g")                # bolt
        s.rect(cx1 - r, cy - 6, 2 * r, 6, "w")                 # rail
        s.text(cx1 - 14, cy - 7.4, "PV MODULE", 1.35, "middle", True)
        s.text(cx1 + 14, cy - 7.4, "PV MODULE", 1.35, "middle", True)
        s.text(cx1, cy - 2.2, "ALUMINIUM RAIL", 1.35, "middle", True)
        roof_profile(s, rt, cx1, cy, r, cy + 7)

    def end():
        s.rect(cx2 - r, cy - 10, r + 6, 4, "w")
        s.poly([(cx2 + 6, cy - 11.4), (cx2 + 9, cy - 11.4), (cx2 + 9, cy - 6), (cx2 + 6, cy - 6)], "g")  # end clamp
        s.rect(cx2 + 7, cy - 12.6, 1, 1.2, "g")
        s.rect(cx2 - r, cy - 6, r + 12, 6, "w")                # rail ends past the module
        s.rect(cx2 + 1, cy - 5, 4, 8, "w")                     # hook upright on the rail face
        s.rect(cx2 + 2.5, cy - 4, 1, 4, "t")
        s.line(cx2 + 3, cy + 3, cx2 + 3, cy + 6.5, "l")
        s.text(cx2 - 10, cy - 7.4, "PV MODULE", 1.35, "middle", True)
        s.text(cx2 - 12, cy - 2.2, "ALUMINIUM RAIL", 1.35, "middle", True)
        roof_profile(s, rt, cx2, cy, r, cy + 7)

    clip_circle(s, "bb1", cx1, cy, r, mid)
    clip_circle(s, "bb2", cx2, cy, r, end)


def rail_strip(s, x1, x2, y):
    s.rect(x1, y, x2 - x1, 1.6, "w")
    s.line(x1 - 2, y + 2.4, x2 + 2, y + 2.4, "l")
    s.line(x1 - 2, y + 3.0, x2 + 2, y + 3.0, "t")
    n = 9
    for i in range(n):
        x = x1 + 3 + i * (x2 - x1 - 6) / (n - 1)
        s.line(x, y - 0.6, x, y, "t")


def legend(s, rt, x, y):
    s.text(x, y, "NOTE :", 1.9, bold=True, under=True)
    yy = y + 7
    s.rect(x, yy - 3, 9, 4.4, "w")
    s.poly([(x, yy - 3), (x + 3.5, yy - 0.8), (x, yy + 1.4)], "t", closed=False)
    s.text(x + 18, yy, "PV MODULE", 1.9, bold=True)
    yy += 8.5
    s.circle(x + 4.5, yy - 0.8, 1.2, "t")
    s.text(x + 18, yy, ROOF[rt]["hook"], 1.9, bold=True)
    yy += 8.5
    s.line(x, yy - 0.8, x + 9, yy - 0.8, "l")
    s.text(x + 18, yy, "ALUMINIUM RAIL", 1.9, bold=True)


# --- title column ----------------------------------------------------------------------

def logo_data_uri():
    try:
        return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")
    except OSError:
        return None


def address_lines(addr, width):
    if isinstance(addr, list):
        return [str(a) for a in addr if str(a).strip()]
    addr = str(addr or "").strip()
    if not addr:
        return []
    if "\n" in addr:
        return [a.strip() for a in addr.splitlines() if a.strip()]
    out = []
    for part in [p.strip() for p in addr.split(",") if p.strip()]:
        piece = part + ","
        if out and len(out[-1] + " " + piece) * 1.7 * CHAR_W <= width:
            out[-1] += " " + piece
        else:
            out.extend(wrap(piece, width, 1.7))
    if out:
        out[-1] = out[-1].rstrip(",") + "."
    return out


def title_column(s, pe, n_modules, x, w):
    pr = pe["project"]
    xr = x + w
    tx = x + 1.5

    def label(y, t):
        s.text(tx, y, t, 1.0, bold=True)

    s.text(tx, 13.5, "THIS DRAWING IS COPYRIGHT PROTECTED", 1.25, bold=True)
    s.add(f'<g>')
    for i, t in enumerate(["CONTRACTORS MUST CHECK ALL DIMENSIONS ON", "SITE . ONLY FIGURED",
                           "DIMENSIONS ARE TO BE WORKED. DISCREPANCIES", "MUST BE REPORTED IMMEDIATELY TO",
                           "ARCHITECT/ENGINEER BEFORE PROCEEDING."]):
        s.text(tx, 18 + i * 1.6, t, 1.15, bold=True)
    s.add("</g>")
    s.line(x, 28, xr, 28, "l")
    for i, t in enumerate(["COPYING & DUPLICATING OF THESE DESIGN", "DRAWINGS ARE STRICTLY PROHIBITED WITHOUT THE",
                           "WRITTEN CONSENT FROM ETERNALGY SDN. BHD."]):
        s.text(tx, 33 + i * 1.6, t, 1.15, bold=True)
    s.line(x, 43, xr, 43, "l")

    # designer
    y0 = 108
    s.line(x, y0, xr, y0, "l")
    label(y0 + 2.2, "DESIGNER :")
    s.rect(x + 2, y0 + 4, w - 4, 10, "")
    s.add(f'<rect x="{x + 2:.2f}" y="{y0 + 4:.2f}" width="{w - 4:.2f}" height="10" fill="#1d1d1b"/>')
    uri = logo_data_uri()
    if uri:
        lw = w - 10
        s.add(f'<image x="{x + 5:.2f}" y="{y0 + 9 - lw * 85 / 640 / 2:.2f}" width="{lw:.2f}" '
              f'height="{lw * 85 / 640:.2f}" href="{uri}" xlink:href="{uri}"/>')
    else:
        s.text(x + w / 2, y0 + 10.5, "ETERNALGY", 3.2, "middle", True, "#fff")
    s.text(tx + 2, y0 + 18, "ETERNALGY SDN. BHD.", 1.9, bold=True)
    for i, t in enumerate(["21-01, Jln Mutiara Emas 10 /", "19, Tmn Mount Austin, 81100", "Johor Bahru."]):
        s.text(tx + 4, y0 + 21 + i * 1.6, t, 1.2, bold=True)

    # client
    y1 = 146
    s.line(x, y1, xr, y1, "l")
    label(y1 + 2.2, "CLIENT :")
    s.text(tx + 1, y1 + 8, pr.get("client_name", ""), 1.9, max_w=w - 4)
    addr = address_lines(pr.get("address", ""), w - 5)
    if len(addr) > 7:   # keep every word: squeeze the overflow onto the last line
        addr = addr[:6] + [" ".join(addr[6:])]
    for i, t in enumerate(addr):
        s.text(tx + 1, y1 + 13 + i * 2.3, t, 1.7, max_w=w - 4)

    # project title
    y2 = 182
    s.line(x, y2, xr, y2, "l")
    label(y2 + 2.2, "PROJECT TITLE :")
    kwp = n_modules * num(pe["module"].get("wattage_wp")) / 1000
    proj = pr.get("project_title") or (f"{f(round(kwp, 3), 3)}kWp Solar System" if kwp > 0 else "Solar System")
    s.text(x + w / 2, y2 + 19, proj, 2.6, "middle", max_w=w - 4)

    # drawing title
    y3 = 219
    s.line(x, y3, xr, y3, "l")
    label(y3 + 2.2, "DRAWING TITLE :")
    title = str(pr.get("title") or "MODULE LAYOUT PLAN (RETROFITTED)")
    for i, t in enumerate(wrap(title, w - 6, 2.6)[:3]):
        s.text(tx + 1, y3 + 11 + i * 3.4, t, 2.6, max_w=w - 4)

    # module used
    y4 = 243
    s.line(x, y4, xr, y4, "l")
    label(y4 + 2.2, "PV MODULE USED :")
    watt = f(num(pe["module"].get("wattage_wp"))) if num(pe["module"].get("wattage_wp")) else "?"
    s.text(x + w / 2, y4 + 11, f"{pe['module_label'] or 'PV'} / {n_modules}NOS /", 1.9, "middle", max_w=w - 4)
    s.text(x + w / 2, y4 + 13.6, f"{watt}Wp MODULE", 1.9, "middle")

    # data table
    y5 = 265
    s.line(x, y5, xr, y5, "l")
    rows = [("Drawn By", pr.get("drawn_by", "")), ("Approved By", pr.get("approved_by", "")),
            ("Date", pr.get("date", "")), ("Scale", pr.get("scale") or "NTS"),
            ("Revision", pr.get("revision", ""))]
    mid = x + 22
    for i, (k, v) in enumerate(rows):
        yy = y5 + 2.1 + i * 2.6
        s.text(tx, yy, f"{k} : {v}", 1.05, max_w=mid - tx - 0.5)
        s.line(x, y5 + (i + 1) * 2.6, mid, y5 + (i + 1) * 2.6, "t")
    s.line(mid, y5, mid, y5 + 13, "t")
    s.text(mid + 1, y5 + 7.3, f"Drawing No : {pr.get('drawing_no', '')}", 1.05, max_w=xr - mid - 2)
    s.line(x, y5 + 13, xr, y5 + 13, "t")
    s.line(mid, y5 + 2.6 * 2, xr, y5 + 2.6 * 2, "t")
    s.line(mid, y5 + 2.6 * 3, xr, y5 + 2.6 * 3, "t")
    rev = str(pr.get("revision", "")).strip()
    for i in range(8):
        bx = x + i * 3
        s.rect(bx, y5 + 13, 3, 3.6, "t")
        if i < len(rev):
            s.text(bx + 1.5, y5 + 15.7, rev[i], 1.6, "middle", True)


# --- sheet -----------------------------------------------------------------------------

def render_pe(pe):
    """Draw the sheet. Returns (svg, info). Never raises for bad input."""
    s = Svg()
    s.rect(18, 8, 386, 281, "k")
    tx = 354
    s.line(tx, 8, tx, 289, "k")
    rt = pe["roof_type"]

    box = (26, 26, 172, 202)
    s.rect(*box, "l")
    try:
        n = draw_layout(s, pe, box)
    except Exception as e:
        n = 0
        pe["problems"].append(f"Layout could not be drawn ({e}).")
    s.text(box[0] + box[2] / 2, 240, "PV MODULE LAYOUT", 3.0, "middle", True, under=True)
    for i, t in enumerate(CONFIRM):
        s.text(28, 255 + i * 2.6, t, 1.8, bold=True)

    exp = pe.get("expected_modules")
    if exp not in (None, "") and int(num(exp, -1)) != n:
        pe["problems"].append(f"Layout shows {n} modules but expected_modules is {exp}.")

    for name, fn in (("detail", lambda: (detail_tile_hook if rt == "tile" else detail_kliplok)(s, 258, 15)),
                     ("section A-A", lambda: section_aa(s, rt, 238, 92, 31)),
                     ("section B-B", lambda: section_bb(s, rt, 238, 309, 168, 29)),
                     ("rail strip", lambda: rail_strip(s, 234, 314, 222)),
                     ("legend", lambda: legend(s, rt, 296, 248))):
        try:
            fn()
        except Exception as e:
            pe["problems"].append(f"{name} could not be drawn ({e}).")
    s.text(275, 50, "DETAIL 'A'", 2.8, "middle", True, under=True)
    s.text(275, 131, "SECTION  'A - A'", 2.8, "middle", True, under=True)
    s.text(275, 233, "SECTION  'B - B'", 2.8, "middle", True, under=True)

    try:
        title_column(s, pe, n, tx, 404 - tx)
    except Exception as e:
        pe["problems"].append(f"Title block could not be completed ({e}).")

    if pe["problems"]:
        s.text(28, 246, "CHECK BEFORE ISSUE:", 1.6, bold=True, fill=RED)
        shown = pe["problems"][:3] if len(pe["problems"]) > 4 else pe["problems"]
        for i, t in enumerate(shown):
            s.text(28, 248.4 + i * 1.9, f"- {t}", 1.4, fill=RED, max_w=170)
        if len(pe["problems"]) > 4:
            s.text(28, 248.4 + 3 * 1.9, f"- and {len(pe['problems']) - 3} more (see the build output)",
                   1.4, fill=RED)

    kwp = n * num(pe["module"].get("wattage_wp")) / 1000
    return s.svg(), {"modules": n, "kwp": round(kwp, 3), "roof_type": rt, "problems": list(pe["problems"])}
